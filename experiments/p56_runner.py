"""P56 runner: submit a workflow to the ComfyUI HTTP API with a pinned seed,
wait for it to finish, and print every output file it wrote.

Carried over from P55 (experiments/p55_runner.py in the vigorous-bouman
worktree, not merged): expand_subgraphs / flat_nodes_to_prompt handle UI-format
subgraph wrappers that the HTTP API rejects; the seed is pinned on every
RandomNoise node and the frontend-only control_after_generate widget is
stripped so A/B submissions differ only in the nodes we meant to change.

Usage: python p56_runner.py <workflow.json> <label> [seed]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bench import workflow_to_prompt, api, wait_for_completion  # noqa: E402

DEFAULT_SEED = 261662374822964  # the r2v workflow's own RandomNoise value

# Virtual subgraph bridge node ids used by the ComfyUI frontend serializer.
INPUT_NODE = -10
OUTPUT_NODE = -20


def _prefixed(inner_id, wrapper_id):
    return f'{wrapper_id}:{inner_id}'


def expand_subgraphs(workflow):
    """Flatten UI-format subgraph wrappers into a single-level node list.

    Same algorithm P55 used (p55_runner.py), where the full docstring lives:
    inner nodes get string ids `wrapper:inner`, internal links are remapped,
    and each subgraph input is bound from the wrapper's matching input —
    either the top-level link on it, or the wrapper's widgets_values_named
    value. Bridge bindings are stored under the 'resolved' key, which
    flat_nodes_to_prompt consumes (bench.workflow_to_prompt cannot see them).
    """
    defs = {sg['id']: sg for sg in (workflow.get('definitions') or {})
            .get('subgraphs', [])}
    top_links = workflow.get('links', [])
    link_map = {l[0]: (l[1], l[2]) for l in top_links}
    flat = [n for n in workflow.get('nodes', []) if n.get('type') not in defs]
    notes = []

    for wrapper in workflow.get('nodes', []):
        sg = defs.get(wrapper.get('type'))
        if sg is None:
            continue
        wrapper_id = wrapper['id']
        named = wrapper.get('widgets_values_named') or {}
        sg_links = {l['id']: l for l in sg.get('links', [])}

        sg_inputs_by_name = {i['name']: i for i in sg.get('inputs', [])}
        input_sources = {}
        for wi in wrapper.get('inputs') or []:
            sgi = sg_inputs_by_name.get(wi.get('name'))
            if sgi is None:
                notes.append(f'wrapper input {wi.get("name")!r} matches no '
                             f'subgraph input')
                continue
            if wi.get('link') is not None:
                input_sources[sgi['name']] = ('link', wi['link'])
        for sgi in sg.get('inputs', []):
            if sgi['name'] not in input_sources:
                input_sources[sgi['name']] = ('value', named.get(sgi['name']))

        for n in sg.get('nodes', []):
            flat.append({**n, 'id': _prefixed(n['id'], wrapper_id)})

        for l in sg.get('links', []):
            src, tgt = l['origin_id'], l['target_id']
            if src in (INPUT_NODE, OUTPUT_NODE) or tgt in (INPUT_NODE,
                                                           OUTPUT_NODE):
                continue
            node = next(x for x in sg['nodes'] if x['id'] == tgt)
            inp = (node.get('inputs') or [])[l['target_slot']]
            notes.append(f'{tgt}.{inp["name"]} <- {src}:{l["origin_slot"]}')
            node['inputs'][l['target_slot']]['resolved'] = \
                [_prefixed(src, wrapper_id), l['origin_slot']]

        for sgi in sg.get('inputs', []):
            kind, val = input_sources[sgi['name']]
            for lid in sgi.get('linkIds') or []:
                l = sg_links.get(lid)
                if l is None:
                    continue
                node = next(x for x in sg['nodes'] if x['id'] == l['target_id'])
                inp = (node.get('inputs') or [])[l['target_slot']]
                if kind == 'link':
                    src = link_map.get(val)
                    if src is None:
                        notes.append(f'BROKEN bridge {sgi["name"]}: top link '
                                     f'{val} not found')
                        continue
                    inp['resolved'] = [str(src[0]), src[1]]
                    notes.append(f'bridge {sgi["name"]} (link) -> '
                                 f'{l["target_id"]}.{inp["name"]} = {src}')
                elif val is None:
                    notes.append(f'bridge {sgi["name"]} unconnected -> '
                                 f'{l["target_id"]}.{inp["name"]} left unset')
                else:
                    inp['resolved'] = val
                    notes.append(f'bridge {sgi["name"]} (value) -> '
                                 f'{l["target_id"]}.{inp["name"]} = '
                                 f'{str(val)[:60]}')

        out_bridges = {}
        for l in sg.get('links', []):
            if l['target_id'] == OUTPUT_NODE:
                out_bridges[l['id']] = (l['origin_id'], l['origin_slot'])
        sg_outputs = sg.get('outputs', [])
        for i, out in enumerate(sg_outputs):
            src = None
            for lid in out.get('linkIds') or []:
                if lid in out_bridges:
                    src = out_bridges[lid]
            if src is None:
                continue
            for tl in top_links:
                if tl[1] == wrapper_id and tl[2] == i:
                    dst_node = str(tl[3])
                    dst_slot = tl[4]
                    dst = next(x for x in workflow['nodes']
                               if str(x['id']) == dst_node)
                    inp = (dst.get('inputs') or [])[dst_slot]
                    inp['resolved'] = [_prefixed(src[0], wrapper_id), src[1]]
                    notes.append(f'bridge out {out["name"]} -> '
                                 f'{dst_node}.{inp["name"]}')

    return flat, notes


def flat_nodes_to_prompt(nodes, link_map):
    """Convert the flattened node list to the API prompt format.

    Inner (subgraph) nodes are recognized by the `wrapper:inner` id prefix:
    their own `link` ids live in the subgraph's link space and must NEVER be
    resolved against the top-level link_map — only a 'resolved' bridge binding
    or widget values may provide their inputs. Top-level nodes use link_map.
    """
    prompt = {}
    for n in nodes:
        if n.get('type') in ('MarkdownNote', 'Note', 'Reroute'):
            continue
        nid = str(n['id'])
        inner = ':' in nid
        inputs = {}

        named = n.get('widgets_values_named') or {}
        for k, v in named.items():
            inputs[k] = v

        names = n.get('widgets_names') or []
        values = n.get('widgets_values') or []
        for i, name in enumerate(names):
            if i < len(values) and name not in inputs:
                inputs[name] = values[i]

        for inp in (n.get('inputs') or []):
            name = inp.get('name')
            if name is None:
                continue
            if inp.get('resolved') is not None:
                inputs[name] = inp['resolved']
            elif not inner and inp.get('link') is not None:
                link_id = inp['link']
                if link_id in link_map:
                    src_id, src_slot = link_map[link_id]
                    inputs[name] = [str(src_id), src_slot]

        prompt[nid] = {'class_type': n['type'], 'inputs': inputs}
    return prompt


def to_prompt(workflow, seed=DEFAULT_SEED):
    """UI workflow JSON -> API prompt dict, subgraphs flattened. The seed is
    pinned here at the prompt level — a subgraph's RandomNoise is invisible at
    the workflow level, and frontend-only widgets are stripped.

    `_p56_expanded` marks an already-flattened workflow (bridges live under
    the 'resolved' key); bench.workflow_to_prompt cannot see those and its
    top-level link map would resurrect the deleted wrapper node, so such
    files must go through flat_nodes_to_prompt even without subgraphs."""
    if (workflow.get('definitions') or {}).get('subgraphs') \
            or workflow.get('_p56_expanded'):
        flat, notes = expand_subgraphs(workflow)
        for note in notes:
            print(f'[p56] expand: {note}')
        prompt = flat_nodes_to_prompt(
            flat, {l[0]: (l[1], l[2]) for l in workflow.get('links', [])})
    else:
        prompt, _ = workflow_to_prompt(workflow)

    for nid, node in prompt.items():
        if node['class_type'] == 'RandomNoise':
            node['inputs'].pop('control_after_generate', None)
            node['inputs']['noise_seed'] = seed
    return prompt


def pin_seed(workflow, seed):
    """Pin noise_seed on every top-level RandomNoise node, in widgets and
    named values both, so the value survives either serialization path. (The
    prompt-level pin in to_prompt is what actually reaches the API.)"""
    for n in workflow.get('nodes', []):
        if n['type'] == 'RandomNoise':
            n.setdefault('widgets_values_named', {})['noise_seed'] = seed
            wv = n.get('widgets_values') or []
            if wv:
                wv[0] = seed


def main():
    wf_path = Path(sys.argv[1])
    label = sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_SEED

    workflow = json.loads(wf_path.read_bytes().decode('utf-8'))
    pin_seed(workflow, seed)
    prompt = to_prompt(workflow, seed)
    seeds = [(k, v['inputs'].get('noise_seed')) for k, v in prompt.items()
             if v['class_type'] == 'RandomNoise']
    print(f'[p56] label={label} prompt_nodes={len(prompt)} '
          f'pinned_seeds={seeds}')

    t0 = time.time()
    result = api('/prompt', 'POST', {'prompt': prompt})
    prompt_id = result.get('prompt_id')
    print(f'[p56] prompt_id={prompt_id}')

    status, _, rec = wait_for_completion(prompt_id)
    elapsed = time.time() - t0
    outputs = rec.get('outputs', {})
    print(f'[p56] status={status.get("status_str", "unknown")} '
          f'elapsed={elapsed:.1f}s')
    if status.get('status_str') not in ('success', None, 'unknown'):
        print(f'[p56] STATUS DETAILS: {json.dumps(status)[:800]}')
        if rec.get('messages'):
            print(f'[p56] MESSAGES: {json.dumps(rec["messages"])[:1500]}')
    for node_id, node_output in outputs.items():
        for key, val in node_output.items():
            print(f'[p56] output node={node_id} {key}: {val}')
    print(f'[p56] DONE label={label} prompt_id={prompt_id}')


if __name__ == '__main__':
    main()

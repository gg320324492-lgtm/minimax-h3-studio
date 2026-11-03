"""P55 regression runner: submit a workflow to the ComfyUI HTTP API with a
pinned seed, wait for it to finish, and print every output file it wrote.

Why this exists
---------------
experiments/bench.py parses --seed but never uses it, so its seed is whatever
the workflow JSON happens to store. P55 needs the SAME prompt + seed submitted
before and after the ComfyUI upgrade, so the runner pins RandomNoise.noise_seed
explicitly, strips the frontend-only control_after_generate widget, and prints
the pinned value so the report can quote it.

Usage: python p55_runner.py <workflow.json> <label> [seed]
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

    The frontend serializes subgraph definitions under `definitions.subgraphs`
    and references them from wrapper nodes by UUID type. The HTTP API only
    accepts plain class types, so a wrapper must be lowered: inner nodes get
    string ids `wrapper:inner`, internal links are remapped, and each subgraph
    input (origin_id=-10) is bound from the wrapper's matching input — either
    the top-level link on it, or the wrapper's widgets_values_named value.

    Returns (flat_nodes, notes) where notes documents every bridge binding so
    the report can show what was actually submitted.
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

        # subgraph inputs, name-keyed. wrapper.inputs only serializes inputs
        # with an external link or widget; pure-widget bridges (prompt,
        # noise_seed, model names) exist only in widgets_values_named, so
        # matching MUST be by name — the two arrays are NOT index-aligned.
        sg_inputs_by_name = {i['name']: i for i in sg.get('inputs', [])}
        input_sources = {}  # sg.input name -> ('link', top_link_id) | ('value', v)
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

        # 1) inner nodes -> prompt with prefixed ids
        for n in sg.get('nodes', []):
            flat.append({**n, 'id': _prefixed(n['id'], wrapper_id)})

        # 2) internal links (both endpoints inner nodes)
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

        # 3) subgraph input bridges: sg input -> inner target slot
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
                    # optional bridge with nothing connected: leave unset
                    notes.append(f'bridge {sgi["name"]} unconnected -> '
                                 f'{l["target_id"]}.{inp["name"]} left unset')
                else:
                    inp['resolved'] = val
                    notes.append(f'bridge {sgi["name"]} (widget) -> '
                                 f'{l["target_id"]}.{inp["name"]} = '
                                 f'{str(val)[:60]}')

        # 4) subgraph output bridges: inner link -> wrapper output -> top link
        out_bridges = {}  # sglink id -> (inner_id, slot)
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
            # top_links are [id, origin_id, origin_slot, target_id, target_slot]:
            # the wrapper is the link's SOURCE here.
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
        if n.get('type') in {'MarkdownNote', 'Note', 'Reroute'}:
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
            if 'resolved' in inp:
                inputs[name] = inp['resolved']
            elif not inner and inp.get('link') is not None:
                src = link_map.get(inp['link'])
                if src is not None:
                    inputs[name] = [str(src[0]), src[1]]
            elif inp.get('link') is not None and inner:
                inputs.pop(name, None)  # unbound inner link: drop the widget
                print(f'[p55] WARNING unbound inner link on {nid}.{name}',
                      flush=True)
        prompt[nid] = {'class_type': n['type'], 'inputs': inputs}
    return prompt


def main():
    wf_path = Path(sys.argv[1])
    label = sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_SEED

    wf = json.loads(wf_path.read_text(encoding='utf-8'))
    notes = []
    if (wf.get('definitions') or {}).get('subgraphs'):
        flat, notes = expand_subgraphs(wf)
        prompt = flat_nodes_to_prompt(flat,
                                      {l[0]: (l[1], l[2])
                                       for l in wf.get('links', [])})
        skipped = []
        print(f'[p55] expanded {len(wf["definitions"]["subgraphs"])} '
              f'subgraph(s), {len(notes)} bridge bindings', flush=True)
    else:
        prompt, skipped = workflow_to_prompt(wf)

    pinned = []
    for nid, node in prompt.items():
        # control_after_generate is added by the frontend, not part of
        # RandomNoise.INPUT_TYPES; sending it risks confusing validation.
        node['inputs'].pop('control_after_generate', None)
        if node['class_type'] == 'RandomNoise':
            node['inputs']['noise_seed'] = seed
            pinned.append((nid, seed))

    print(f'[p55] label={label} prompt_nodes={len(prompt)} '
          f'skipped_doc={len(skipped)} pinned_seeds={pinned}', flush=True)

    resp = api('/prompt', method='POST', data={'prompt': prompt})
    pid = resp.get('prompt_id')
    if not pid:
        print(f'[p55] submit failed: {resp}', flush=True)
        return 1
    print(f'[p55] prompt_id={pid}', flush=True)

    status, elapsed, rec = wait_for_completion(pid, timeout=3600)
    print(f'[p55] status={status.get("status_str")} elapsed={elapsed:.1f}s',
          flush=True)

    for nid, out in (rec.get('outputs') or {}).items():
        for kind, entries in out.items():
            if isinstance(entries, list):
                for e in entries:
                    if isinstance(e, dict) and 'filename' in e:
                        print(f'[p55] output node={nid} {kind}: '
                              f'{e.get("subfolder", "")}/{e.get("filename")}',
                              flush=True)

    if status.get('status_str') != 'success':
        print('[p55] FAILED, last status messages:', flush=True)
        for m in (status.get('messages') or [])[-5:]:
            print('    ' + str(m), flush=True)
        return 1
    print(f'[p55] DONE label={label} prompt_id={pid}', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())

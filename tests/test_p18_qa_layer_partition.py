"""P18 — the four-layer QA partition, and the properties it has to keep.

WHAT THIS FILE GUARDS

`docs/UPGRADE_MASTER_PLAN.md` lists P18 as "Technical / Layout / Motion / Visual
four-layer gates". Before P18 those four words named nothing: no file said which
rule belonged to which layer. `studio/scripts/qa_layers.py` is the first such
statement, and THIS file is what keeps it a statement about the code rather
than an aspiration about it.

WHAT IT DELIBERATELY DOES NOT GUARD

It does not assert the partition is CORRECT. It asserts the partition is
EXHAUSTIVE over the rules that exist, MUTUALLY EXCLUSIVE, and that the
measurements offered as justification are still true. Correctness is a judgement
for a human; `docs/P18_QA_LAYERS.md` records it, including the entries it is
unsure about. A test that pinned correctness would make every future
re-classification a test rewrite, which is how a pin stops being a pin.

WHY THE ASSERTIONS ARE BEHAVIOURAL

This project has been fooled six times by guards that assert on source TEXT.
The three most recent:

  1. `assert 'mkdtemp' in source` matched the COMMENT explaining the bug.
  2. `assert 'depth' not in schema_text` was triggered by the SUBSTRING `depth`
     inside `depthCue`.
  3. After the unknown-flag fix was removed, `Unknown flag` survived in the
     fix's own explanatory comment, so the guard stayed green.

So nothing here reads `qa_layers.py` or `visual_qa.py` as text to decide what
belongs where. Every membership claim is checked by CALLING the code:

  * `LAYER_OF` must cover exactly the set of rule names the real functions EMIT.
    The emitted names are obtained by calling all eleven rules, not by parsing
    function names — because `rule_duplicate_check_props` emits `missing_asset`,
    which a function-name partition would have missed.
  * `behaves_like_static` / `reads_graph` / `requires_pair` come from running
    the rules on two different inputs, and `probe_is_sensitive()` is asserted
    first, because a differential probe that cannot detect a difference has
    measured nothing.
  * the "UNAVAILABLE rules have no layer" property is checked by running
    `unavailable_findings()`.

THE TWO MUTATIONS THIS FILE IS REQUIRED TO KILL are recorded in
`docs/P18_QA_LAYERS.md` §5 with raw `-rf` output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (str(ROOT), str(ROOT / 'studio' / 'scripts')):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import qa_layers as ql  # noqa: E402
import visual_qa as vqa  # noqa: E402


@pytest.fixture(scope='module')
def report() -> dict:
    return ql.build_report()


# ---------------------------------------------------------------------------
# 0b. THE CURRENT ASSIGNMENT IS PINNED — THIS IS THE GUARD THAT KILLS MUTATION 1
#
# WHY IT IS HERE, AND WHY IT HAD TO BE ADDED AFTER THE MUTATION SURVIVED.
#
# `qa_layers.build_report()` originally kept a module-level `LAYER_OF` dict and
# built the per-layer groupings by looking each rule up in it. Every structural
# assertion in this file — exhaustiveness, exclusivity, thinness, "every entry
# carries a note" — was then satisfied by whatever `LAYER_OF` said, because all
# of them read structures derived from it. Moving `blur` from Visual to
# Technical moved the grouping, the counts, and the thinness set with it, and
# all sixteen tests stayed green.
#
# That is not a near miss. It is the exact shape of the six text-assertion
# failures this project has already paid for, arriving through a different door:
# the guard was not wrong, it was DERIVED FROM THE THING IT WAS GUARDING. A
# partition that is derived from itself cannot be asserted against.
#
# So the assignment is authored in `build_report()`, and THIS is the independent
# copy. It duplicates the classification on purpose. If someone moves a rule,
# this test goes red and they have to update a table that was written by
# someone else, out of band — which is the reviewable event. Updating both in
# one commit is allowed; that is what "deliberately" means.
# ---------------------------------------------------------------------------

PINNED_LAYERS: dict[str, list[str]] = {
    'Technical': ['black_frame', 'aspect', 'missing_asset',
                  'graph_scene_renderable'],
    'Layout': ['safe_area', 'clipping', 'font_size'],
    'Motion': ['freeze', 'duplicate'],
    'Visual': ['blur', 'contrast'],
}

#: Files that must stay byte-identical to HEAD. This task is analysis only: it
#: writes a new module, a new test and a new document, and changes no behaviour.
#: `visual_qa.py` and `qa_report.py` are named here with the hashes measured at
#: the start of the task, so a later change to a rule's decision logic has to be
#: made deliberately rather than by editing the file this work touched.
UNTOUCHED: dict[str, str] = {
    # UPDATED BY P19, deliberately and out loud. The P18 value was
    # 9db0198e8db21bef696ead30114b1e242833cf2b39205880638fbded78565db3.
    # P19 changed `rule_duplicate`'s DECISION — its cut moves off the
    # cross-render 0.5 onto an exact identity cut, and its Finding stops
    # crediting take_ranker for the number. That is a rule's decision logic, so
    # it has to be a separate act and this is it. It changed nothing about the
    # layer partition, which is what the rest of this file pins: `duplicate`
    # stays in Motion, and `PINNED_LAYERS` is unchanged.
    #
    # UPDATED BY P21, also deliberately and also out loud. P21 added a rule —
    # `graph_scene_renderable` — which is new decision logic on this file by any
    # reading, so the "P18 changed no rule's decision logic" invariant does not
    # hold across it and the pin is updated in the same commit rather than
    # deleted. What P21 did NOT do is change any EXISTING rule's decision:
    # `missing_asset` keeps its four hardcoded paths (its docstring gained a
    # record of what was measured and rejected), and every other rule is
    # byte-identical. P21 also ADDED a rule to the partition, which is why
    # `PINNED_LAYERS` above grows by one entry and why `docs/P18_QA_LAYERS.md`'s
    # 3/3/2/2 headline becomes 4/3/2/2.
    'studio/scripts/visual_qa.py':
        '03a3f8c070f8e76250b24a4bf88a39869538865f8249ba73418f509f49eb6e42',
    'studio/scripts/qa_report.py':
        '9e7e4725fcfcbe201caa14cdfe8f5cb6ea4a51bf3ea3b6bfe831b99c79b41f38',
}


def test_the_two_qa_scripts_are_byte_identical_to_head():
    """P18 changed no rule's decision logic. Verified on the bytes, not the diff."""
    import hashlib
    for rel, expected in UNTOUCHED.items():
        actual = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
        assert actual == expected, (
            f'{rel} changed during a task whose deliverable was a layer '
            f'classification. {expected} -> {actual}. If a rule was meant to '
            'change, that is a separate decision and this test should be '
            'updated out loud, not silently.')


def test_new_files_use_the_repository_line_ending():
    """The repo is bare LF, measured on every existing file (visual_qa.py: 858
    bare LF, 0 CRLF; qa_report.py: 150 bare LF, 0 CRLF; core.autocrlf=false and
    there is no .gitattributes).

    This test exists because it happened: `qa_layers.py` was written with the
    Write tool as LF, then edited through several `python -c` rewrites, and
    `Path.write_text` under this Git-Bash-on-Windows environment round-tripped
    every line ending to CRLF. The file ended up 459 CRLF lines in a repo of
    bare-LF files — a whole-file diff for a change of one line. So it is
    measured, not asserted from anyone's memory.
    """
    for rel in ('studio/scripts/qa_layers.py',
                'tests/test_p18_qa_layer_partition.py'):
        b = (ROOT / rel).read_bytes()
        crlf, total_lf = b.count(b'\r\n'), b.count(b'\n')
        assert crlf == 0, (
            f'{rel} has {crlf} CRLF line endings in a repository whose files are '
            'all bare LF. This makes the whole file show as changed.')


def test_the_layer_assignment_is_exactly_what_was_delivered(report):
    """The pin. A rule moving between layers must be a deliberate edit here."""
    actual = {name: sorted(body['rules'])
              for name, body in report['layers'].items()}
    assert actual == {name: sorted(rules) for name, rules in PINNED_LAYERS.items()}, (
        'the layer partition changed. If this re-classification is intended, '
        'update PINNED_LAYERS in the same commit and say so in '
        'docs/P18_QA_LAYERS.md — a rule that changes layer silently is exactly '
        'what this project has been bitten by.')


def test_the_pinned_layers_are_those_of_the_code_not_an_arbitrary_subset(report):
    """The pin cannot drift away from reality by asserting about the wrong set."""
    emitted = {name for names in report['emitted_by'].values() for name in names}
    pinned = {r for rules in PINNED_LAYERS.values() for r in rules}
    assert pinned == emitted, (
        f'PINNED_LAYERS covers {sorted(pinned)} but the code emits {sorted(emitted)}')


# ---------------------------------------------------------------------------
# 0. THE PROBE MUST BE ABLE TO DETECT A DIFFERENCE
#
# This test is first because everything below reads its output. An earlier
# version of the probe used an 80x120 frame whose content block sat inside
# visual_qa's EDGE=40 backdrop-sample band; every rule answered UNVERIFIABLE on
# every frame, so `behaves_like_static` came out True everywhere and looked like
# a measurement. It was the absence of one.
# ---------------------------------------------------------------------------

def test_the_differential_probe_can_actually_detect_a_difference(report):
    assert report['probe_is_sensitive'] is True, (
        'the content/flat probe pair drives no rule to a different verdict, so '
        'every behaviour column below is void and would read as a measurement'
    )


def test_probe_geometry_clears_the_backdrop_sample_bands():
    """Stated as arithmetic so a resize fails loudly instead of silently.

    EDGE=40 is where backdrop_model samples; RING=24 is the ring it takes the
    worst residual over (top rows, bottom rows, left and right columns). The
    probe bars have to clear both or the model is untrusted and every
    backdrop-dependent rule returns UNVERIFIABLE for both inputs.
    """
    edge, ring = vqa.EDGE, vqa.RING
    left, right = min(b[0] for b in ql.PROBE_BARS), max(b[1] for b in ql.PROBE_BARS)
    top, bottom = ql.PROBE_ROWS
    assert left > edge, f'probe bars start at col {left}, inside the EDGE band 0..{edge}'
    assert right < ql.PROBE_W - edge, (
        f'probe bars end at col {right}, inside the EDGE band '
        f'{ql.PROBE_W - edge}..{ql.PROBE_W}')
    assert top > ring, f'probe bars start at row {top}, inside the RING band 0..{ring}'
    assert bottom < ql.PROBE_H - ring, (
        f'probe bars end at row {bottom}, inside the RING band '
        f'{ql.PROBE_H - ring}..{ql.PROBE_H}')


# ---------------------------------------------------------------------------
# 1. EXHAUSTIVE: every rule that exists is classified
# ---------------------------------------------------------------------------

def test_every_rule_the_code_actually_emits_has_a_layer(report):
    """Membership comes from CALLING the rules, so a comment cannot invent one."""
    emitted = {name for names in report['emitted_by'].values() for name in names}
    missing = emitted - set(report['layer_of'])
    assert not missing, (
        f'rules that emit a verdict but have no layer: {sorted(missing)}. '
        'The partition must be exhaustive — a rule with no layer is a rule no '
        'gate would ever run.'
    )


def test_no_rule_is_classified_but_absent_from_the_code(report):
    """The other direction: a layer entry for a rule that does not exist."""
    emitted = {name for names in report['emitted_by'].values() for name in names}
    ghost = set(report['layer_of']) - emitted
    assert not ghost, f'layer entries for rules the code never emits: {sorted(ghost)}'


def test_no_rule_emits_more_than_one_distinct_name(report):
    """A function that emitted two names would break the emitted-name partition."""
    for fn, names in report['emitted_by'].items():
        assert len(names) == 1, f'{fn} emits {names}; the partition assumes one name per rule'


# ---------------------------------------------------------------------------
# 2. MUTUALLY EXCLUSIVE: each rule belongs to exactly one layer
#
# LAYER_OF is a dict, so Python itself forbids a duplicate KEY. That is not the
# property being guarded — a dict cannot hold "this rule is in two layers" at
# all, and the mutation that has to die is a rule listed in TWO layer groupings.
# So the check is made against the GROUPINGS, which is where a second
# assignment can actually be written.
# ---------------------------------------------------------------------------

def test_a_rule_cannot_be_listed_in_two_layers(report):
    seen: dict[str, list[str]] = {}
    for layer, body in report['layers'].items():
        for rule in body['rules']:
            seen.setdefault(rule, []).append(layer)
    doubled = {r: ls for r, ls in seen.items() if len(ls) > 1}
    assert not doubled, f'rules assigned to more than one layer: {doubled}'


def test_each_layer_grouping_agrees_with_the_flat_assignment(report):
    """The grouping and the dict are written separately on purpose, so they can
    disagree — and if they do, one of them is lying about the partition."""
    flat = report['layer_of']
    for layer, body in report['layers'].items():
        for rule in body['rules']:
            assert flat.get(rule) == layer, (
                f'{rule} is listed under {layer} but LAYER_OF says '
                f'{flat.get(rule)!r}')
    for rule, layer in flat.items():
        assert rule in report['layers'].get(layer, {}).get('rules', []), (
            f'LAYER_OF puts {rule} in {layer} but that grouping does not list it')


def test_the_four_layer_names_are_the_ones_the_master_plan_spell():
    assert set(ql.LAYERS) == {'Technical', 'Layout', 'Motion', 'Visual'}


# ---------------------------------------------------------------------------
# 3. THE MEASUREMENTS OFFERED AS JUSTIFICATION ARE STILL TRUE
#
# MEASURED_NOTE asserts claims about rules. A note that is not re-derived is a
# comment, and this project has been fooled by comments.
# ---------------------------------------------------------------------------

def test_contrast_really_takes_no_input_and_really_fails(report):
    """It is the one rule whose verdict describes the palette, not the artefact.

    This is why a --frame run can never exit 0, and it is the single most
    important thing about the current gate. Asserted by CALLING it twice.
    """
    import inspect
    assert not inspect.signature(vqa.rule_contrast).parameters, (
        'rule_contrast now takes arguments; the whole claim that it is a '
        'constant lookup, and therefore that --frame can never pass, must be '
        're-measured')
    a = vqa.rule_contrast()
    b = vqa.rule_contrast()
    assert a[0].verdict == b[0].verdict == vqa.FAIL
    assert report['behaviour']['contrast']['behaves_like_static'] is True


def test_the_two_pair_taking_rules_really_need_two_paths(report):
    """Motion's cost axis: two rendered frames, the most expensive rules here."""
    import inspect
    for fn_name in ('rule_freeze', 'rule_duplicate'):
        params = list(inspect.signature(getattr(vqa, fn_name)).parameters)
        assert len(params) == 2, f'{fn_name} takes {params}'
        assert report['behaviour'][fn_name.split('_', 1)[1]]['requires_pair'] is True


def test_missing_asset_really_does_not_read_its_props_argument(report):
    """It is a repository check wearing a props argument.

    Checked two ways, because either alone is weak: behaviourally (three
    unrelated dicts, one Finding) and structurally (the body, docstring
    stripped, never names `props`). Neither is a text search for a rule name.
    """
    findings = [vqa.rule_missing_asset(p)[0]
                for p in ({}, {'scenes': [{'id': 'x'}]}, {'audio': ['nope.wav']})]
    assert len({(f.verdict, f.value, str(f.extra)) for f in findings}) == 1, (
        'rule_missing_asset now responds to its props argument; the claim that '
        'it does not — and the Technical classification that rests on it being '
        'a repository check — must be re-measured')
    assert report['behaviour']['missing_asset']['reads_graph'] is False

    import ast
    src = Path(vqa.__file__).read_text(encoding='utf-8')
    tree = ast.parse(src)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == 'rule_missing_asset')
    body = ast.unparse(ast.Module(body=node.body[1:], type_ignores=[]))
    assert 'props' not in body, (
        'the body of rule_missing_asset now references props ��� the AST check '
        'below is stale and the note in MEASURED_NOTE is stale with it')


def test_rule_duplicate_check_props_really_does_emit_missing_asset(report):
    """Two functions, one emitted name. Recorded because it nearly broke the
    partition: classifying by FUNCTION name gives `missing_asset` two owners."""
    assert report['emitted_by']['rule_duplicate_check_props'] == ['missing_asset']
    assert report['emitted_by']['rule_missing_asset'] == ['missing_asset']


def test_the_unimplemented_rules_report_no_number_and_have_no_layer(report):
    """UNAVAILABLE findings are declared absences, so they belong to no layer.

    A layer is a thing a gate can run. `overflow` and `collision` have no
    instrument and `collision` has no threshold, so putting them in a layer
    would put a rule in the partition that no gate could ever execute — which
    is the same shape as the missing `--props` defect P13 fixed.
    """
    unavailable = {f.rule for f in vqa.unavailable_findings()}
    assert unavailable == set(report['unimplemented']), (
        'UNIMPLEMENTED and unavailable_findings() disagree')
    assert all(f.value is None for f in vqa.unavailable_findings())
    assert not (unavailable & set(report['layer_of'])), (
        f'UNAVAILABLE rules were given a layer: '
        f'{sorted(unavailable & set(report["layer_of"]))}')


# ---------------------------------------------------------------------------
# 4. THE LAYERS THAT ARE THIN ARE RECORDED AS THIN
#
# The deliverable of P18 is allowed to conclude "there are not four layers".
# If it does, the thinness must be visible in data, not only in prose — prose is
# what gets edited away when the next person wants a fourth layer.
# ---------------------------------------------------------------------------

def test_layer_sizes_are_reported_not_merely_implied(report):
    assert report['counts'] == {name: len(report['layers'][name]['rules'])
                                for name in ql.LAYERS}
    assert sum(report['counts'].values()) == len(report['layer_of'])


def test_thin_layers_are_declared_thin_not_left_for_the_reader(report):
    """Layers holding <=2 rules are named in THIN_LAYERS.

    So a future "let's get to four layers" effort starts by reading the
    measurement rather than by assuming the four layers are comparable.
    """
    thin = {name: n for name, n in report['counts'].items() if n <= 2}
    assert set(ql.THIN_LAYERS) == set(thin), (
        f'THIN_LAYERS says {sorted(ql.THIN_LAYERS)} but the measured thin layers '
        f'are {sorted(thin)}. If a rule moved, this file must be updated '
        'deliberately — that is what it is for.')


def test_every_entry_carries_its_justification(report):
    for layer, body in report['layers'].items():
        for rule in body['rules']:
            assert body['notes'].get(rule), (
                f'{rule} is in {layer} with no MEASURED_NOTE; an entry without '
                'a reason is exactly the kind of claim this project has had to '
                'take back before')
    assert set(report['ambiguous']) <= set(report['layer_of']), (
        'an ambiguity note for a rule that is not classified is a note about '
        'nothing')

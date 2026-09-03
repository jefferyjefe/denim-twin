"""Characterisation of `gates.evaluate`, which is 1700 lines and had almost no direct coverage.

The scenarios in `selftest.py` drive whole sessions and assert what the gate concludes. That is the
right level for "would this garment be cut", and it is the wrong level for "does this engine have a
condition that can never fire, two conditions enforcing the same rule, or a blocker whose message
names a command that does not exist". Those questions are about the ENGINE, and nothing asked them.

So this pins the engine's shape before anything is refactored: the exact set of conditions it can
emit, which gate evaluates which, that a verdict cannot be ready and blocked at once, that a
condition which raises fails CLOSED, and that every blocker carries a stable dotted code, a sentence
saying what is wrong and a sentence saying what to do. A refactor that moves a rule is then visible
as a diff in this file rather than as a gate that quietly stopped checking something.
"""
import ast
import os
import re
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import gates as GATES, spec as SPEC          # noqa: E402
from denimtwin.pilot.selftest import Bench, _mini_spec            # noqa: E402
from denimtwin.pilot.store import Store                            # noqa: E402

GATES_PY = ROOT / "src" / "denimtwin" / "pilot" / "gates.py"

#: Every condition `evaluate` can name, frozen. Adding one is a deliberate edit here; losing one is
#: a test failure rather than a gate that silently stopped checking something.
EXPECTED_CONDITIONS = {
    "annotations.identify_instances",
    "captures.files_intact",
    "captures.instance_identity",
    "captures.no_undeclared_reuse",
    "captures.relays_independent",
    "captures.repositions_recorded",
    "captures.required_complete",
    "captures.reuse_legitimate",
    "captures.state_order",
    "captures.subjects_bound",
    "captures.verdicts_reproduce",
    "cut.confirmations",
    "cut.not_already_performed",
    "cut.performed_recorded",
    "cut.second_person_verified",
    "cut.specified",
    "features.answered",
    "log.intact",
    "log.readable",
    "measurements.complete",
    "measurements.post_wash",
    "measurements.revisions_explained",
    "offcuts.assigned",
    "plan.fully_expanded",
    "plan.generated",
    "rig.board_square_measured",
    "rig.calibrated",
    "rig.captures_attributable",
    "rig.frozen",
    "rig.one_configuration",
    "spec.bound",
    "spec.usable",
    "wash.actual",
    "wash.planned",
}


def _guard_names():
    """Every condition name passed to `_guard`, read out of the source."""
    tree = ast.parse(GATES_PY.read_text())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "_guard" and len(node.args) >= 3:
            a = node.args[2]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                out.append(a.value)
    return out


def _block_names():
    """Condition names constructed directly as a Block, outside any `_guard`."""
    tree = ast.parse(GATES_PY.read_text())
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "Block" and node.args:
            a = node.args[0]
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                out.append(a.value)
    return out


def test_the_condition_inventory_is_exactly_what_is_expected():
    found = set(_guard_names()) | set(_block_names())
    assert found == EXPECTED_CONDITIONS, (
        "conditions added: %s; conditions removed: %s"
        % (sorted(found - EXPECTED_CONDITIONS), sorted(EXPECTED_CONDITIONS - found)))


def test_the_modules_own_list_cannot_drift_from_the_code():
    """`gates.ALL_CONDITIONS` is what `make_runbook` enumerates from, because enumerating by
    RUNNING the gates cannot reach `log.readable` (the fold has to raise) or `spec.usable` (the
    plan has to be missing a state) -- and `log.readable`, the one block an operator sees when
    their log is damaged, therefore had no sentence on the green sheet."""
    found = set(_guard_names()) | set(_block_names())
    assert set(GATES.ALL_CONDITIONS) == found, (
        "gates.ALL_CONDITIONS disagrees with the code: extra %s, missing %s"
        % (sorted(set(GATES.ALL_CONDITIONS) - found), sorted(found - set(GATES.ALL_CONDITIONS))))


def test_every_condition_has_a_sentence_on_the_green_sheet():
    """The sheet is the one document that may not fall behind the gate."""
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("mkrb", ROOT / "tools" / "make_runbook.py")
    mod = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(mod)
    missing = sorted(set(GATES.ALL_CONDITIONS) - set(mod.CONDITION_LINES))
    assert not missing, "no sentence for: %s" % missing
    sheet = (ROOT / "protocol" / "pilot" / "DO_NOT_CUT_UNTIL_GREEN.md").read_text()
    for c in sorted(GATES.ALL_CONDITIONS):
        assert "`%s`" % c in sheet, "the printed sheet does not list %s" % c


def test_an_unreadable_log_is_UNAVAILABLE_not_merely_NO(tmp_path):
    """`pilot.py precut` exits 1 for "no" and 3 for "could not be determined". A gate whose log
    could not be read has not answered no; it has failed to answer, and the operator's next move is
    opposite in the two cases."""
    class _Exploding(object):
        dir = tmp_path

        def fold(self):
            raise ValueError("the log is shredded")

    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    v = GATES.evaluate("ready_to_cut", spec, _Exploding(), garment_dir=tmp_path)
    assert not v.ready
    assert v.unavailable, "an unreadable log reported as a plain refusal"
    assert all(b.unavailable for b in v.blocks)


def test_no_condition_is_registered_twice_for_one_gate():
    """`_guard` appends. Registering a condition twice on one path evaluates it twice, reports it
    twice, and lets one registration pass while the other blocks -- so the same name would appear in
    `satisfied` and in `blocks` at once."""
    names = _guard_names()
    dupes = sorted({n for n in names if names.count(n) > 1})
    # Asserted, not merely computed. This line used to read `assert isinstance(dupes, list)`, which
    # is true of every possible value and discarded the one thing the function had worked out.
    #
    # A name COULD in principle appear twice in the source in mutually exclusive gate-specific
    # branches; none does today, and if that changes the runtime check below is what has to carry
    # the weight, so the two are asserted together rather than one standing in for the other.
    assert not dupes, (
        "these conditions are registered more than once in gates.py: %s. `_guard` appends, so two "
        "registrations reached on one path evaluate the condition twice and can report it as both "
        "satisfied and blocking." % dupes)
    for gate_id in GATES.GATE_LAST_STATE:
        seen = _runtime_conditions(gate_id)
        assert not (seen["satisfied"] & seen["blocked"]), (
            "%s reports these as both satisfied and blocking: %s"
            % (gate_id, sorted(seen["satisfied"] & seen["blocked"])))


@pytest.fixture(scope="module")
def sessions():
    """One empty session and one complete session, per gate, on the small real specification."""
    tmp = Path(tempfile.mkdtemp(prefix="gatematrix_"))
    mini = _mini_spec(tmp)
    empty = Bench(tmp / "empty", mini, "DENIM_9701")
    full = Bench(tmp / "full", mini, "DENIM_9702")
    full.open_session(); full.freeze_rig(); full.answer_features(); full.measure()
    for s in full.activated()[0]:
        for rep in range(1, int(s.get("min_reps", 1)) + 1):
            full.add(s, rep, full.synth_for(s, rep, relay=rep, seed=90 + rep))
    full.resolve_humans(); full.cut_ready_extras(); full.after_cut_extras()
    return {"spec": mini, "empty": empty, "full": full, "tmp": tmp}


_MATRIX = {}


def _runtime_conditions(gate_id):
    """Which conditions this gate actually evaluates, observed rather than assumed."""
    if gate_id in _MATRIX:
        return _MATRIX[gate_id]
    tmp = Path(tempfile.mkdtemp(prefix="gatematrix_rt_"))
    mini = _mini_spec(tmp)
    b = Bench(tmp / "rt", mini, "DENIM_9703")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    for s in b.activated()[0]:
        for rep in range(1, int(s.get("min_reps", 1)) + 1):
            b.add(s, rep, b.synth_for(s, rep, relay=rep, seed=70 + rep))
    b.resolve_humans(); b.cut_ready_extras(); b.after_cut_extras()
    v = GATES.evaluate(gate_id, mini, b.store, garment_dir=b.dir, check_files=False)
    _MATRIX[gate_id] = {"satisfied": {x["condition"] for x in v.satisfied},
                        "blocked": {x.condition for x in v.blocks},
                        "verdict": v}
    return _MATRIX[gate_id]


@pytest.mark.parametrize("gate_id", sorted(GATES.GATE_LAST_STATE))
def test_each_gate_evaluates_the_conditions_it_is_responsible_for(gate_id):
    seen = _runtime_conditions(gate_id)
    evaluated = seen["satisfied"] | seen["blocked"]
    # Every gate is responsible for the evidence conditions; the cut-, wash- and post-wash-specific
    # ones are gated on which irreversible act the gate authorises.
    universal = {"spec.bound", "log.intact", "features.answered", "plan.fully_expanded",
                 "rig.frozen", "rig.calibrated", "rig.captures_attributable",
                 "rig.one_configuration", "measurements.complete",
                 "measurements.revisions_explained", "annotations.identify_instances",
                 "captures.instance_identity", "captures.subjects_bound",
                 "captures.state_order", "captures.required_complete",
                 "captures.verdicts_reproduce", "captures.relays_independent",
                 "captures.repositions_recorded", "captures.reuse_legitimate",
                 "captures.no_undeclared_reuse"}
    missing = universal - evaluated
    assert not missing, "%s does not evaluate %s" % (gate_id, sorted(missing))
    assert evaluated <= EXPECTED_CONDITIONS


def test_the_three_gates_do_not_evaluate_an_identical_condition_set():
    """If they did, the split would be decorative and one of them would be checking the wrong
    states."""
    sets = {g: frozenset(_runtime_conditions(g)["satisfied"] | _runtime_conditions(g)["blocked"])
            for g in GATES.GATE_LAST_STATE}
    assert len(set(sets.values())) == len(sets), sets


@pytest.mark.parametrize("gate_id", sorted(GATES.GATE_LAST_STATE))
def test_a_verdict_is_never_ready_and_blocked_at_once(gate_id, sessions):
    for b in (sessions["empty"], sessions["full"]):
        v = GATES.evaluate(gate_id, sessions["spec"], b.store, garment_dir=b.dir,
                           check_files=False)
        assert v.ready == (not v.blocks)
        if v.blocks:
            assert not v.ready
        # And an unavailable verdict is never a weaker verdict than not-ready.
        if v.unavailable:
            assert not v.ready


@pytest.mark.parametrize("gate_id", sorted(GATES.GATE_LAST_STATE))
def test_every_blocker_carries_a_stable_code_and_an_actionable_message(gate_id, sessions):
    v = GATES.evaluate(gate_id, sessions["spec"], sessions["empty"].store,
                       garment_dir=sessions["empty"].dir, check_files=False)
    assert v.blocks, "a garment with no evidence must block"
    for b in v.blocks:
        assert re.fullmatch(r"[a-z_]+\.[a-z_]+", b.condition), b.condition
        assert b.condition in EXPECTED_CONDITIONS, b.condition
        assert b.what and len(b.what) > 20, (b.condition, b.what)
        assert b.fix and len(b.fix) > 10, (b.condition, b.fix)
        assert b.as_dict()["condition"] == b.condition


def test_a_blockers_remedy_never_names_a_flag_the_cli_does_not_have():
    """A remedy the operator cannot run is not a remedy.

    `cut.confirmations` told them to run `pilot.py confirm <id> --claim X --value y`. `confirm`
    takes the claim positionally and has no `--value`, so the command the block named exited with a
    usage error.

    EVERY flag on the line is checked, not the first: an earlier version stopped at the first match,
    and `--field` and `--reason` -- named in most of the deviation remedies -- were never looked at.
    The subcommand is the first token that is not a global option or its value, because several
    remedies correctly put `--operator` before the subcommand, which is where argparse wants it.
    """
    import subprocess
    src = GATES_PY.read_text()
    g = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "--help"],
                       capture_output=True, text=True)
    global_help = g.stdout + g.stderr
    global_flags = set(re.findall(r"(--[a-z][a-z-]*)", global_help))

    lines = [m.group(0) for m in re.finditer(r"tools/pilot\.py [^\n\"]*", src)]
    assert lines, "no remedy commands found to check"
    helps, checked = {}, 0
    for line in lines:
        toks = line.split()[1:]                     # drop "tools/pilot.py"
        cmd, i = None, 0
        while i < len(toks):
            t = toks[i]
            if t.startswith("--"):
                # a global option, and its value if it takes one
                i += 2 if (i + 1 < len(toks) and not toks[i + 1].startswith("--")) else 1
                continue
            cmd = t
            break
        if cmd is None or not re.fullmatch(r"[a-z][a-z-]*", cmd):
            continue
        if cmd not in helps:
            r = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py"), cmd, "--help"],
                               capture_output=True, text=True)
            helps[cmd] = r.stdout + r.stderr
            assert "usage:" in helps[cmd], "gates.py names a command that does not exist: %s" % cmd
        for flag in re.findall(r"(--[a-z][a-z-]*)", line):
            # WHOLE flags. `--claim in help` was true because the help mentions `--claim-code`, so
            # the remedy naming a flag that does not exist passed this test.
            pat = re.compile(r"(?<![\w-])" + re.escape(flag) + r"(?![\w-])")
            assert pat.search(helps[cmd]) or flag in global_flags, (
                "gates.py tells the operator to run `pilot.py %s ... %s`, and that flag does not "
                "exist:\n    %s" % (cmd, flag, line))
            checked += 1
    assert checked >= 15, "only %d remedy flags were checked; the extraction has drifted" % checked


def test_a_condition_that_raises_fails_closed(monkeypatch, sessions):
    """AN ERROR IS A BLOCK. A condition whose truth is unknown is not permission.

    `plan_safe_measurements` and `gate_states` ran ABOVE every guard, so a data problem in either
    escaped `evaluate` entirely: the caller asking whether a garment may be cut received a
    traceback rather than a refusal, and `pilot.py` exited on the exception instead of with the
    code that means "could not be determined".
    """
    def boom(_state):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(GATES, "plan_safe_measurements", boom)
    v = GATES.evaluate("ready_to_cut", sessions["spec"], sessions["full"].store,
                       garment_dir=sessions["full"].dir, check_files=False)
    assert not v.ready
    assert {b.condition for b in v.blocks} == {"spec.usable"}
    assert v.unavailable, "a gate that could not be evaluated is UNAVAILABLE, not merely blocked"


def test_a_shot_plan_that_drops_a_guarded_state_blocks_rather_than_raising(tmp_path):
    """A loader-valid edit -- drop the offcut arm, its state and its shots together -- made
    `ready_to_finalize` raise ValueError out of `evaluate`."""
    import json as _json, shutil as _sh
    src = ROOT / "protocol" / "shotplan"
    d = tmp_path / "shotplan"
    d.mkdir(parents=True)
    for f in ("shotplan.schema.json", "regions.schema.json", "regions.json"):
        _sh.copy(str(src / f), str(d / f))
    doc = _json.loads((src / "shotplan.json").read_text())
    doc["states"] = [x for x in doc["states"] if x["state"] != "offcut_after"]
    doc["shots"] = [x for x in doc["shots"] if x["state"] != "offcut_after"]
    (d / "shotplan.json").write_text(_json.dumps(doc))
    sp = SPEC.load(d / "shotplan.json")
    g = tmp_path / "garments" / "DENIM_9001"
    g.mkdir(parents=True)
    st = Store(g)
    st.append("session_opened", {"spec_version": sp.version, "spec_hash": sp.content_hash})
    v = GATES.evaluate("ready_to_finalize", sp, st, garment_dir=g)
    assert not v.ready
    assert {b.condition for b in v.blocks} == {"spec.usable"}


def test_an_unreadable_log_is_a_verdict_not_a_traceback(tmp_path):
    """`evaluate`'s own first line used to break its own rule: the fold ran above every guard."""
    class _Exploding(object):
        dir = tmp_path

        def fold(self):
            raise ValueError("the log is shredded")

    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    v = GATES.evaluate("ready_to_cut", spec, _Exploding(), garment_dir=tmp_path)
    assert not v.ready
    assert {b.condition for b in v.blocks} == {"log.readable"}


def test_an_unknown_gate_is_refused_rather_than_defaulted():
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    with pytest.raises(ValueError):
        GATES.evaluate("ready_to_do_whatever", spec, None)


def test_gate_states_are_derived_from_the_specification_not_hand_listed():
    """Eight declared states and three hand-written tuples naming six left a fifth of the plan --
    the whole offcut experiment -- required by no gate at all."""
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    declared = {s["state"] for s in spec.states}
    covered = set()
    for g in GATES.GATE_LAST_STATE:
        covered |= set(GATES.gate_states(spec, g))
    assert declared == covered, "states no gate requires: %s" % sorted(declared - covered)


def test_a_plan_revision_that_adds_a_human_claim_is_not_satisfied_by_older_photographs(tmp_path):
    """THE FALSE READY. Two ordinary commands, following the gate's own printed remedy.

    `captures.required_complete` re-derived which MECHANICAL checks a record must contain, from the
    code, and then read the required HUMAN claims off the STORED RECORD -- which was written under
    whatever shot plan was on disk when the photograph was taken. So a revision that ADDS a
    `requires_human` claim to an already-photographed shot was satisfied by a frame accepted before
    the claim existed: `spec.bound` blocks on the revision, the operator records the deviation that
    block itself prints, and the gate returns READY with the new claim never asked of anybody.

    The evidence it silently dropped is precisely the class no pixel test can ever supply.
    """
    import json as _json
    from denimtwin.pilot import qa as QA

    mini = _mini_spec(tmp_path)
    b = Bench(tmp_path / "g", mini, "DENIM_9705")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    for s in b.activated()[0]:
        for rep in range(1, int(s.get("min_reps", 1)) + 1):
            b.add(s, rep, b.synth_for(s, rep, relay=rep, seed=1500 + rep))
    b.resolve_humans(); b.cut_ready_extras()
    assert b.gate("ready_to_cut").ready, "the fixture must start from READY"

    # The revision: one more thing a person must confirm about a frame already taken.
    doc = _json.loads((tmp_path / "shotplan" / "shotplan.json").read_text())
    target = doc["shots"][0]["shot_id"]
    doc["shots"][0].setdefault("requires_human", []).append(
        "the garment is the right way up and no tool is in the frame")
    (tmp_path / "shotplan" / "shotplan.json").write_text(_json.dumps(doc))
    revised = SPEC.load(tmp_path / "shotplan" / "shotplan.json")
    assert revised.content_hash != mini.content_hash

    v = GATES.evaluate("ready_to_cut", revised, b.store, garment_dir=b.dir)
    assert "spec.bound" in {x.condition for x in v.blocks}, "the revision must be noticed at all"

    # The remedy the block itself prints: acknowledge which plan the session is held to.
    b.store.append("deviation", {"kind": "protocol", "field": "spec_rebound",
                                 "actual": revised.content_hash,
                                 "reason": "added a confirmation to an existing shot"},
                   operator="alice")
    v2 = GATES.evaluate("ready_to_cut", revised, b.store, garment_dir=b.dir)
    conds = {x.condition for x in v2.blocks}
    assert "spec.bound" not in conds, "the acknowledgement should clear the binding itself"
    assert not v2.ready, "READY with a required confirmation nobody was ever asked for"
    assert "captures.required_complete" in conds, conds
    blk = [x for x in v2.blocks if x.condition == "captures.required_complete"][0]
    assert target in str(blk.evidence), blk.evidence

    # And it clears the ordinary way: by asking the person.
    st, _ = b.store.fold()
    # From the REVISED plan: the bench still holds the spec the session was opened under, and the
    # whole point is that the requirement now comes from the plan on disk.
    from denimtwin.pilot import plan as PLAN
    live = [x for x in PLAN.activate(revised, st["features"],
                                     GATES.plan_safe_measurements(st))[0]
            if x["shot_id"] == target][0]
    for rep in range(1, int(live.get("min_reps", 1)) + 1):
        cap = st["captures"].get((target, rep)) or {}
        for cid in QA.human_claim_ids(live, rep):
            b.store.append("human_verification",
                           {"shot_id": target, "rep": rep, "claim": cid, "value": True,
                            "operator": "alice", "verifier_name": "alice",
                            "capture_sha256": cap.get("sha256")}, operator="alice")
    v3 = GATES.evaluate("ready_to_cut", revised, b.store, garment_dir=b.dir)
    assert v3.ready, "confirming the new claim must open the gate again: %s" % [
        (x.condition, x.what[:120]) for x in v3.blocks]


def test_precut_reports_an_unreadable_log_as_UNDETERMINED(tmp_path):
    """`pilot.py precut` exits 0 / 1 / 3 for yes / no / could-not-be-determined.

    It decided between the last two by looking for the words "could not be evaluated" in the
    block's message, which `log.readable` and `spec.usable` do not use -- so a gate that had not
    been able to answer at all reported a plain refusal, and `precut` and `gate` disagreed about the
    same session. The verdict already carries the flag.
    """
    import subprocess
    g = tmp_path / "garments" / "DENIM_0044"
    (g / "pilot").mkdir(parents=True)
    (g / "pilot" / "manifest.jsonl").write_bytes(b"{}\n")
    (g / "pilot" / "manifest.jsonl").chmod(0o000)
    env = dict(os.environ, PILOT_GARMENTS=str(tmp_path / "garments"))
    try:
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "precut",
                            "DENIM_0044"], capture_output=True, text=True, env=env)
    finally:
        (g / "pilot" / "manifest.jsonl").chmod(0o600)
    assert r.returncode == 3, (
        "an unreadable log exited %d; 3 means 'could not be determined', 1 means 'no', and the "
        "operator's next move is opposite:\n%s%s" % (r.returncode, r.stdout[-800:], r.stderr[-800:]))


def test_no_condition_is_reported_satisfied_when_there_is_no_plan(tmp_path):
    """A fresh session printed `plan.fully_expanded` SATISFIED -- "every templated series expanded
    into frames" -- in the same verdict where `plan.generated` blocked with "no shot plan could be
    generated". A printed verdict that contradicts itself is one an operator learns to skim."""
    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    g = tmp_path / "garments" / "DENIM_0045"
    g.mkdir(parents=True)
    st = Store(g)
    st.append("session_opened", {"spec_version": spec.version, "spec_hash": spec.content_hash})
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=g, check_files=False)
    sat = {x["condition"] for x in v.satisfied}
    blocked = {x.condition for x in v.blocks}
    assert "plan.generated" in blocked, blocked
    assert "plan.fully_expanded" not in sat, (
        "the verdict says a plan expanded and that no plan was generated, in the same breath")
    assert not (sat & blocked)


def test_every_command_line_the_tool_prints_is_one_argparse_accepts():
    """A remedy the tool refuses to run is not a remedy.

    `pilot.py claims` printed `pilot.py confirm <G> --shot ... --operator <you>` -- and --operator
    is a TOP-LEVEL flag, so argparse answered "unrecognized arguments: --operator" to the exact
    line the operator had just been told to type. The neighbouring printers in gates.py put it
    before the subcommand and were fine, which is how it survived.

    Only lines carrying a FLAG are checked, which excludes the help table, and only the
    "unrecognized arguments" shape is treated as a failure -- that is the signature of an option in
    a position the parser does not accept. A command failing for want of a real garment is expected
    and ignored: what is under test is the shape of the line, not the state of the log.
    """
    import re
    import subprocess

    srcs = {
        "tools/pilot.py": (ROOT / "tools" / "pilot.py").read_text(),
        "gates.py": (ROOT / "src" / "denimtwin" / "pilot" / "gates.py").read_text(),
    }
    lines = []
    for name, src in srcs.items():
        # A printed command may be split across adjacent string literals; join them first.
        glued = re.sub(r'"\s*\n\s*(?:\+\s*)?"', "", src)
        for m in re.finditer(r'tools/pilot\.py ([^"\\\n]+)', glued):
            line = m.group(1).strip()
            # A printed command is often followed by prose in the same string -- "  (`pilot.py
            # claims` prints the codes)". Cut at the double space that separates them.
            line = re.split(r"\s{2,}", line)[0].strip()
            if "--" in line:
                lines.append((name, line))
    assert len(lines) >= 6, (
        "found only %d printed command lines carrying a flag; the extraction has broken and this "
        "test is no longer reading what the tool prints" % len(lines))

    FILL = {"<you>": "tester", "<SHOT>": "SOME.SHOT", "<N>": "1", "<n>": "1",
            "<CODE>": "H0000000000", "<claim>": "x", "<id>": "SOME.SHOT",
            "<field>": "water_temp_c", "<x>": "1", "<y>": "2", "<name>": "waist_cm",
            "%s": "DENIM_0001", "%d": "1"}
    bad = []
    for name, line in sorted(set(lines)):
        argv = []
        # Some options take a value from a closed set, so a generic filler is rejected for being
        # the wrong VALUE rather than for being in the wrong place. Fill those by the flag before.
        BY_FLAG = {"--state": "before", "--kind": "protocol", "--value": "y", "--rep": "1"}
        prev = None
        for tok in line.split():
            if prev in BY_FLAG and (tok.startswith("%") or tok.startswith("<")):
                argv.append(BY_FLAG[prev])
                prev = tok
                continue
            prev = tok
            tok = FILL.get(tok, tok)
            if tok.startswith("<") or tok.startswith("%"):
                tok = "placeholder"
            if tok.startswith("'") and tok.endswith("'"):
                tok = tok[1:-1]
            argv.append(tok)
        # A quoted phrase splits across tokens; drop anything after an opening quote that never
        # closed, so the shape of the OPTIONS is what gets tested.
        if any(t.startswith("'") for t in argv):
            argv = argv[:next(i for i, t in enumerate(argv) if t.startswith("'"))] + ["reason"]
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py")] + argv,
                           capture_output=True, text=True, cwd=str(ROOT),
                           env=dict(os.environ, PILOT_GARMENTS="/nonexistent-for-this-test"))
        out = r.stdout + r.stderr
        if "unrecognized arguments" in out or "invalid choice" in out:
            bad.append("%s prints `tools/pilot.py %s`\n      and the parser answers: %s"
                       % (name, line, out.strip().splitlines()[-1][:140]))
    assert not bad, "\n".join(bad)

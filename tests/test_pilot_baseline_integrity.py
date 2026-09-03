"""The pre-cut baseline, and everything derived from it.

Shrinkage is the difference between the garment before the cut and the garment after the wash. If
one of those two numbers can be replaced by the other, the quantity the whole experiment exists to
measure stops being computable at the moment it is recorded -- and the gate, re-reading the single
surviving value, reports the evidence complete.

The scenarios in `selftest.py` drive whole sessions through this. These are the same invariants at
module level, so a change to the fold or to a gate condition fails here in a second with a message
naming the invariant, rather than only in a fifteen-minute run.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import gates as GATES, plan as PLAN, spec as SPEC   # noqa: E402
from denimtwin.pilot.store import Store, PRE_MODIFICATION_STATE          # noqa: E402
from denimtwin.pilot.selftest import Bench                                # noqa: E402


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


def _store(tmp, gid="DENIM_9601"):
    d = Path(tmp) / "garments" / gid
    d.mkdir(parents=True, exist_ok=True)
    return Store(d)


def _measure(st, name, readings, **kw):
    st.append("measurement", dict({"name": name, "readings": list(readings),
                                   "mean": sum(readings) / len(readings),
                                   "spread": max(readings) - min(readings)}, **kw),
              operator="alice")


def _cut(st):
    st.append("cut_performed", {"achieved_inseam_cm": {"L": 15.0, "R": 15.0},
                                "achieved_outseam_cm": {"L": 16.0, "R": 16.0},
                                "tool": "shears", "legs_cut_separately": True}, operator="alice")


def _wash(st):
    st.append("wash_actual", {"machine": "m", "cycle": "c"}, operator="alice")


# -- the two buckets ------------------------------------------------------------------------------

def test_a_post_wash_reading_lands_in_its_own_bucket_and_leaves_the_baseline_alone(tmp_path):
    st = _store(tmp_path)
    _measure(st, "waist_cm", [97.0, 97.2])
    _cut(st)
    _wash(st)
    _measure(st, "waist_cm", [95.4, 95.6])
    state, problems = st.fold()
    assert not problems
    assert state["measurements"]["waist_cm"]["mean"] == pytest.approx(97.1)
    assert state["measurements_by_state"]["post_wash"]["waist_cm"]["mean"] == pytest.approx(95.5)
    assert state["lifecycle_state"] == "post_wash"


def test_the_measurements_view_is_only_ever_the_pre_modification_bucket(tmp_path):
    """`state["measurements"]` is what nine call sites mean by "the measurements", and every one of
    them wants the before-cut values. A gate asking whether this garment may be CUT must not be
    satisfiable by a number taken out of the tumble dryer."""
    st = _store(tmp_path, "DENIM_9602")
    _cut(st)
    _wash(st)
    _measure(st, "waist_cm", [95.0, 95.2])
    state, _ = st.fold()
    assert state["measurements"] == state["measurements_by_state"].get(PRE_MODIFICATION_STATE, {})
    assert "waist_cm" not in state["measurements"]


def test_the_lifecycle_advances_from_the_physical_facts_not_from_a_marker(tmp_path):
    st = _store(tmp_path, "DENIM_9603")
    assert st.fold()[0]["lifecycle_state"] == "before"
    _cut(st)
    assert st.fold()[0]["lifecycle_state"] == "immediate_after"
    _wash(st)
    assert st.fold()[0]["lifecycle_state"] == "post_wash"


def test_a_second_account_of_an_irreversible_act_does_not_overwrite_the_first(tmp_path):
    st = _store(tmp_path, "DENIM_9604")
    _cut(st)
    st.append("cut_performed", {"achieved_inseam_cm": {"L": 99.0, "R": 99.0}}, operator="mallory")
    state, _ = st.fold()
    assert state["cut_performed"]["achieved_inseam_cm"]["L"] == 15.0
    assert state["cut_performed_rewrites"], "the second account vanished instead of being recorded"


# -- writing back into the baseline ---------------------------------------------------------------

def test_a_reading_filed_into_a_state_the_garment_has_left_is_recorded_as_backdated(tmp_path):
    st = _store(tmp_path, "DENIM_9605")
    _cut(st)
    _measure(st, "waist_cm", [1.0, 1.1], state="before")
    state, _ = st.fold()
    assert state["measurement_backdated"], "a write into the pre-cut baseline after the cut"
    assert not state["measurement_ahead_of_record"]


def test_measuring_ahead_of_the_record_is_the_ordinary_order_of_work(tmp_path):
    """You measure the washed garment and type the wash record afterwards. Treating that as a
    conflict bricked the sequence the runbook itself prescribes."""
    st = _store(tmp_path, "DENIM_9606")
    _measure(st, "waist_cm", [95.0, 95.2], state="post_wash")
    state, _ = st.fold()
    assert state["measurement_ahead_of_record"]
    assert not state["measurement_backdated"]


def test_an_unknown_state_on_a_measurement_is_not_silently_treated_as_earliest(tmp_path):
    """`_ORDER.get(claimed, 9)` puts an unrecognised state LAST, so it can never look backdated.

    That is the safe direction -- it cannot be used to smuggle a write into the baseline -- and the
    reading still lands in a bucket of its own rather than in `before`.
    """
    st = _store(tmp_path, "DENIM_9607")
    _cut(st)
    _measure(st, "waist_cm", [1.0, 1.1], state="not_a_real_state")
    state, _ = st.fold()
    assert "waist_cm" not in state["measurements"], "it landed in the pre-cut baseline"
    assert state["measurements_by_state"]["not_a_real_state"]["waist_cm"]["mean"] \
        == pytest.approx(1.05)


def test_the_gate_refuses_a_backdated_baseline_with_no_acknowledgement_path(tmp_path, spec):
    st = _store(tmp_path, "DENIM_9608")
    _cut(st)
    _measure(st, "waist_cm", [1.0, 1.1], state="before")
    # Even a recorded deviation must not excuse it: a deviation can excuse a departure from
    # procedure; it cannot make a measurement of a cut garment into a measurement of the uncut one.
    st.append("deviation", {"kind": "protocol", "field": "measurement_revised:waist_cm",
                            "reason": "trying to explain it away"}, operator="alice")
    v = GATES.evaluate("ready_to_finalize", spec, st, garment_dir=st.dir, check_files=False)
    assert "measurements.revisions_explained" in {b.condition for b in v.blocks}


def test_a_silent_re_measurement_inside_one_state_blocks_until_it_is_explained(tmp_path, spec):
    st = _store(tmp_path, "DENIM_9609")
    _measure(st, "waist_cm", [97.0, 97.2])
    _measure(st, "waist_cm", [82.0, 82.2])
    state, _ = st.fold()
    assert state["measurement_revisions"]
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=st.dir, check_files=False)
    assert "measurements.revisions_explained" in {b.condition for b in v.blocks}
    st.append("deviation", {"kind": "protocol", "field": "measurement_revised:waist_cm",
                            "reason": "the tape had slipped off the waistband"}, operator="alice")
    v2 = GATES.evaluate("ready_to_cut", spec, st, garment_dir=st.dir, check_files=False)
    assert "measurements.revisions_explained" not in {b.condition for b in v2.blocks}


def test_an_explanation_only_clears_the_measurement_it_names(tmp_path, spec):
    """An untargeted acknowledgement cleared every revision in the session at once, including ones
    written after it."""
    st = _store(tmp_path, "DENIM_9610")
    _measure(st, "waist_cm", [97.0, 97.2])
    _measure(st, "waist_cm", [82.0, 82.2])
    _measure(st, "thigh_cm", [60.0, 60.1])
    _measure(st, "thigh_cm", [55.0, 55.1])
    st.append("deviation", {"kind": "protocol", "field": "measurement_revised:waist_cm",
                            "reason": "the tape had slipped"}, operator="alice")
    v = GATES.evaluate("ready_to_cut", spec, st, garment_dir=st.dir, check_files=False)
    b = [x for x in v.blocks if x.condition == "measurements.revisions_explained"]
    assert b, "the thigh revision was cleared by the waist's explanation"
    assert "thigh_cm" in b[0].what


# -- what the baseline SIZES ----------------------------------------------------------------------

def test_a_late_measurement_cannot_re_plan_photographs_already_taken(tmp_path, spec):
    """The hem series is SIZED from leg_opening_cm. Read from a flat name, the post-wash value
    re-sized a BEFORE-state series whose frames were already captured, so a session that had
    printed READY acquired missing frames nobody could ever take."""
    b = Bench(tmp_path, spec, "DENIM_9611")
    b.open_session(); b.answer_features(); b.measure()
    st0, _ = b.store.fold()
    n_before = len(PLAN.activate(spec, st0["features"], st0["measurements"])[0])
    _cut(b.store)
    _wash(b.store)
    _measure(b.store, "leg_opening_cm", [30.0, 30.1])
    st1, _ = b.store.fold()
    n_after = len(PLAN.activate(spec, st1["features"], st1["measurements"])[0])
    assert n_before == n_after, "%d planned before the post-wash reading, %d after" % (n_before,
                                                                                       n_after)


def test_a_measurement_outside_a_plausible_range_never_reaches_the_planner(tmp_path):
    """A leg opening of 10^7 is refused by measurements.complete -- but that condition runs AFTER
    the plan does, and expanding a hem series from that number builds millions of frames first."""
    st = _store(tmp_path, "DENIM_9612")
    _measure(st, "leg_opening_cm", [1e7, 1e7])
    state, _ = st.fold()
    safe = GATES.plan_safe_measurements(state)
    assert "leg_opening_cm" not in safe
    assert "leg_opening_cm" in state["measurements"], "the reading itself must stay on record"


def test_a_measurement_that_is_not_a_number_does_not_crash_the_planner(tmp_path):
    st = _store(tmp_path, "DENIM_9613")
    st.append("measurement", {"name": "leg_opening_cm", "readings": ["banana"], "mean": "banana"},
              operator="alice")
    state, _ = st.fold()
    assert "leg_opening_cm" not in GATES.plan_safe_measurements(state)


# -- what the baseline DERIVES --------------------------------------------------------------------

def test_correcting_a_measurement_invalidates_the_cut_line_derived_from_it(tmp_path, spec):
    b = Bench(tmp_path, spec, "DENIM_9614")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.cut_ready_extras()
    before = b.blocked_conditions("ready_to_cut", check_files=False)
    assert "cut.specified" not in before, before
    # Re-measure the dimension the cut line was computed from.
    _measure(b.store, "original_inseam_cm", [70.0, 70.1])
    conds = b.blocked_conditions("ready_to_cut", check_files=False)
    # NAMED, not `cut.specified or measurements.revisions_explained`. The `or` let this pass on the
    # revision block alone, so it held with the cut-line drift check entirely disabled -- it was a
    # test of the thing beside the thing it was written for.
    assert "cut.specified" in conds, (
        "the cut line survived a correction to the measurement it was computed from: %s" % conds)
    assert "measurements.revisions_explained" in conds, conds


def test_re_computing_the_cut_line_invalidates_the_approval_given_to_the_old_one(tmp_path, spec):
    from denimtwin.pilot import cutspec as CUT
    b = Bench(tmp_path, spec, "DENIM_9615")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    b.cut_ready_extras()
    assert "cut.second_person_verified" not in b.blocked_conditions("ready_to_cut",
                                                                    check_files=False)
    st, _ = b.store.fold()
    m = st["measurements"]
    s2 = CUT.compute(target_inseam_cm=20.0,
                     original_inseam_cm=m["original_inseam_cm"]["mean"],
                     thigh_cm=m["thigh_cm"]["mean"],
                     leg_opening_cm=m["leg_opening_cm"]["mean"])
    b.store.append("cut_spec", s2, operator="alice")
    conds = b.blocked_conditions("ready_to_cut", check_files=False)
    assert "cut.second_person_verified" in conds, conds
    assert "cut.confirmations" in conds, conds


def test_both_front_doors_restrict_which_state_a_measurement_may_be_filed_into(tmp_path, spec):
    """The CLI restricted `--state` by argparse choices and the phone took the field off the
    request, so the post-wash re-measurement could be filed into "post-wash" or "post_was" and land
    in a bucket no condition reads. It fails closed either way; it should fail at the keyboard."""
    import json as _json, os as _os, threading as _th, urllib.error, urllib.request
    from denimtwin.pilot import webapp
    from denimtwin.pilot.server import serve

    assert GATES.MEASUREMENT_STATES == ("before", "post_wash")
    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = Bench(str(root), spec, "DENIM_9616")
    b.open_session(); b.freeze_rig(); b.answer_features()
    sess = webapp.Session(str(root), str(root / "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = serve(webapp.build_api(sess), data_root=str(root / "garments"), port=0)
    _th.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = "http://127.0.0.1:%d/api/measure/DENIM_9616?t=%s" % (httpd.server_address[1],
                                                                   httpd.token)
        body = _json.dumps({"operator": "alice", "name": "waist_cm",
                            "readings": [95.0, 95.2], "state": "post-wash"}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            code = urllib.request.urlopen(req, timeout=30).status
        except urllib.error.HTTPError as e:
            code = e.code
    finally:
        httpd.shutdown(); httpd.server_close()
    assert code == 400, "the phone accepted a lifecycle state no gate reads"
    state, _ = b.store.fold()
    assert "post-wash" not in state["measurements_by_state"]


def test_the_lifecycle_only_ever_moves_forward(tmp_path):
    """A cut and a wash are irreversible, so the replay must not follow the order the entries were
    TYPED.

    Record the wash and then remember to type the cut record afterwards -- which the runbook's own
    sequence invites, since `measurement_ahead_of_record` exists for exactly that habit -- and the
    garment went from post_wash back to immediate_after. Every measurement written after that with
    no explicit state then landed in a bucket no gate reads: `measurements.post_wash` reported that
    the washed garment had never been measured, while the readings sat in the log under
    `immediate_after`, and shrinkage was uncomputable from a record that contained both numbers.
    """
    st = _store(tmp_path, "DENIM_9617")
    _measure(st, "waist_cm", [97.0, 97.2])
    _wash(st)
    assert st.fold()[0]["lifecycle_state"] == "post_wash"
    _cut(st)
    assert st.fold()[0]["lifecycle_state"] == "post_wash", "the lifecycle went backwards"
    _measure(st, "waist_cm", [95.4, 95.6])
    state, _ = st.fold()
    assert "waist_cm" in state["measurements_by_state"]["post_wash"]
    assert "immediate_after" not in state["measurements_by_state"]
    # and both facts are still on record, so nothing was lost by refusing to go back
    assert state["cut_performed"] is not None and state["wash_actual"] is not None
    # the baseline is untouched
    assert state["measurements"]["waist_cm"]["mean"] == pytest.approx(97.1)


def test_the_lifecycle_ordering_has_one_definition(tmp_path):
    """It was written out inside the measurement branch, where the advance itself could not reach
    it -- which is how the advance came to be a plain assignment that could move backwards."""
    from denimtwin.pilot.store import LIFECYCLE_ORDER
    spec_states = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json").states
    declared = {s["state"] for s in spec_states}
    assert declared <= set(LIFECYCLE_ORDER), (
        "the specification declares states the fold has no ordering for: %s"
        % sorted(declared - set(LIFECYCLE_ORDER)))
    # and the ordering agrees with the specification's own
    spec_order = {s["state"]: s["order"] for s in spec_states}
    pairs = sorted(spec_order, key=lambda k: spec_order[k])
    ranks = [LIFECYCLE_ORDER[k] for k in pairs]
    assert ranks == sorted(ranks), "the fold orders the lifecycle differently from the shot plan"


def test_a_cut_recorded_after_the_wash_must_say_when_it_was_measured(tmp_path, spec):
    """`c_cut_performed` checked the record's CONTENT and never its position.

    Its own docstring says the achieved lengths "can only be taken between the shears and the water,
    and after the wash it is gone: the garment has shrunk, and the length you measure is no longer
    the length you cut". A `cut_performed` entry appended AFTER `wash_actual` satisfied every
    content test and was accepted as the ground truth the whole prediction is scored against.
    """
    st = _store(tmp_path, "DENIM_9618")
    _wash(st)
    _cut(st)
    v = GATES.evaluate("ready_to_wash", spec, st, garment_dir=st.dir, check_files=False)
    b = [x for x in v.blocks if x.condition == "cut.performed_recorded"]
    assert b, "a cut recorded after the wash was accepted"
    assert "after the wash" in b[0].what

    # The legitimate version -- measured at the table, typed in afterwards -- is available, and it
    # has to say when the tape was laid. Refusing it outright would brick a real session on an
    # append-only log for a typing order.
    st.append("deviation", {"kind": "protocol", "field": "cut_recorded_after_wash",
                            "reason": "both lengths taken at the table before the machine; "
                                      "typed in after the cycle"}, operator="alice")
    v2 = GATES.evaluate("ready_to_wash", spec, st, garment_dir=st.dir, check_files=False)
    assert "cut.performed_recorded" not in {x.condition for x in v2.blocks}


def test_a_cut_recorded_before_the_wash_needs_no_excuse(tmp_path, spec):
    """The ordinary order of work must not need a deviation."""
    st = _store(tmp_path, "DENIM_9619")
    _cut(st)
    _wash(st)
    v = GATES.evaluate("ready_to_wash", spec, st, garment_dir=st.dir, check_files=False)
    assert "cut.performed_recorded" not in {x.condition for x in v.blocks}


def test_neither_door_files_a_reading_into_a_bucket_no_gate_reads(tmp_path, spec):
    """`MEASUREMENT_STATES` was enforced only when the client sent an explicit state.

    On the normal path the state is DERIVED from the lifecycle, and between a recorded cut and a
    recorded wash that is `immediate_after` -- a bucket no condition reads. Both doors answered
    "recorded" and orphaned the reading, which is the failure the list was added to end.
    """
    import json as _json, os as _os, subprocess as _sp, threading as _th
    import urllib.error, urllib.request
    from denimtwin.pilot import webapp
    from denimtwin.pilot.server import serve

    root = tmp_path / "root"
    (root / "garments").mkdir(parents=True)
    b = Bench(str(root), spec, "DENIM_9620")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    _cut(b.store)
    assert b.store.fold()[0]["lifecycle_state"] == "immediate_after"

    # the phone
    sess = webapp.Session(str(root), str(root / "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    httpd, _ = serve(webapp.build_api(sess), data_root=str(root / "garments"), port=0)
    _th.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        url = "http://127.0.0.1:%d/api/measure/DENIM_9620?t=%s" % (httpd.server_address[1],
                                                                   httpd.token)
        req = urllib.request.Request(
            url, data=_json.dumps({"operator": "bob", "name": "waist_cm",
                                   "readings": [95.0, 95.2]}).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        try:
            code = urllib.request.urlopen(req, timeout=30).status
        except urllib.error.HTTPError as e:
            code = e.code
    finally:
        httpd.shutdown(); httpd.server_close()
    assert code == 400, "the phone recorded a reading into a bucket no gate reads"

    # and the command line
    env = dict(_os.environ, PILOT_GARMENTS=str(root / "garments"))
    r = _sp.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "--operator", "bob",
                 "measure", "DENIM_9620"], capture_output=True, text=True, env=env, input="\n")
    assert r.returncode != 0, "the CLI recorded a reading into a bucket no gate reads:\n%s" % r.stdout
    assert "immediate_after" in (r.stdout + r.stderr)

    state, _ = b.store.fold()
    assert set(state["measurements_by_state"]) == {"before"}, state["measurements_by_state"].keys()


def test_an_implausible_cut_length_is_refused_before_it_is_written(tmp_path, spec):
    """`store.fold` is first-write-wins for `cut_performed`, and the gate's own remedy ("re-run
    with every field") appends a rewrite the fold never reads. So a first record the gate rejects
    can never be replaced: one mistyped digit closed ready_to_wash and ready_to_finalize
    permanently, on a garment already in two pieces. The number has to be refused at the keyboard."""
    import os as _os, subprocess as _sp
    root = tmp_path / "root"
    (root / "garments" / "DENIM_9621").mkdir(parents=True)
    st = Store(root / "garments" / "DENIM_9621")
    st.append("session_opened", {"spec_version": spec.version, "spec_hash": spec.content_hash})
    env = dict(_os.environ, PILOT_GARMENTS=str(root / "garments"))
    r = _sp.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "--operator", "alice",
                 "cut-performed", "DENIM_9621", "--inseam-l", "1.5", "--inseam-r", "15",
                 "--outseam-l", "16", "--outseam-r", "16", "--tool", "shears",
                 "--legs-separately", "y"], capture_output=True, text=True, env=env)
    assert r.returncode != 0, "an implausible cut length was written to an append-only log"
    assert "cannot be replaced" in (r.stdout + r.stderr)
    assert st.fold()[0]["cut_performed"] is None, "it was appended anyway"

    ok = _sp.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "--operator", "alice",
                  "cut-performed", "DENIM_9621", "--inseam-l", "15", "--inseam-r", "15",
                  "--outseam-l", "16", "--outseam-r", "16", "--tool", "shears",
                  "--legs-separately", "y"], capture_output=True, text=True, env=env)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    assert st.fold()[0]["cut_performed"] is not None

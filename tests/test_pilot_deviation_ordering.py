"""A deviation written before the departure is a permission slip, not an account of what happened.

`deviation_covers` grew an `after` parameter -- the log position at which the departure came into
existence -- and two of its twelve call sites passed one. The other ten matched on kind and field
alone, so a single line typed at intake, before a photograph existed, before the rig was frozen,
before the garment was measured, stood as a standing permission for whatever happened next.

docs/PILOT_OWNER_DECISIONS.md recorded the reason they were left: *"each needs its own answer to
'when did this departure come into existence' and inventing one per site is how a guard stops
meaning anything."* That reason does not survive reading the sites. At every one of them the
sequence position of the departure is a FACT ALREADY IN THE LOG, and at most of them the blocker
message already prints it:

    measurement_revised:<name>   the revising reading's own entry number, printed as "(entry N)"
    cut_recorded_after_wash      max(cut entry, wash entry), both printed in the message
    cut_performed_rewritten      the second cut record's entry number, printed in the evidence
    wash_actual_rewritten        the second wash record's entry number, printed in the evidence
    wash_plan_rewritten          the rewrite's entry number, printed in the evidence
    post_wash_out_of_range       the out-of-range reading's own entry number
    rig (one_configuration)      the second freeze's entry number, from setup_history
    offcut_alternation           the assignment that broke the alternation

None of those is invented. The one genuine exception is `spec_rebound`, whose departure is an edit
to a file OUTSIDE the log: nothing in the log can date it, so it passes `after=None` deliberately
and says so rather than inheriting a default.

Which is the structural half of this. `after` has no default any more, so a new consumer has to
answer the question in order to compile, and "nobody thought about it" and "there is no answer"
stop looking the same.
"""
import inspect
import re
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import gates as GATES, spec as SPEC        # noqa: E402
from denimtwin.pilot.selftest import Bench                      # noqa: E402


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


# ---------------------------------------------------------------- the structural half
def test_after_has_no_default():
    sig = inspect.signature(GATES.deviation_covers)
    p = sig.parameters["after"]
    assert p.default is inspect.Parameter.empty, (
        "`after` has a default again. A default is what let ten call sites answer 'when did this "
        "departure come into existence' by not answering it.")


def test_every_call_site_answers_the_ordering_question():
    """Parsed, not grepped. A regex over nested calls silently stops matching some of them."""
    import ast
    tree = ast.parse((ROOT / "src" / "denimtwin" / "pilot" / "gates.py").read_text())
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "deviation_covers"]
    assert len(calls) >= 12, (
        "only %d call sites found; either the module shrank or this scan has stopped seeing them"
        % len(calls))
    missing = [c.lineno for c in calls
               if not any(k.arg == "after" for k in c.keywords)]
    assert not missing, (
        "gates.py line(s) %s call deviation_covers without saying when the departure they excuse "
        "came into existence. A record written before the departure is a standing permission for "
        "whatever happens next." % ", ".join(str(n) for n in missing))


def test_a_deviation_at_or_before_the_departure_never_counts():
    d = [{"kind": "protocol", "field": "f", "actual": "x", "seq": 10}]
    assert GATES.deviation_covers(d, "protocol", "f", after=9) is not None
    assert GATES.deviation_covers(d, "protocol", "f", after=10) is None, (
        "a deviation recorded AT the departure's own entry counted; it was written in the same "
        "breath as the thing it excuses")
    assert GATES.deviation_covers(d, "protocol", "f", after=11) is None


def test_after_none_still_means_unbounded_for_the_one_site_that_needs_it():
    """`spec_rebound`'s departure is an edit to a file the log cannot see. None is an answer."""
    d = [{"kind": "protocol", "field": "f", "actual": "x", "seq": 1}]
    assert GATES.deviation_covers(d, "protocol", "f", after=None) is not None


# ---------------------------------------------------------------- the per-site half
def _base(spec):
    b = Bench(tempfile.mkdtemp(), spec)
    b.open_session()
    b.freeze_rig()
    b.answer_features()
    b.measure()
    return b


def _dev(b, field, kind="protocol", **kw):
    p = {"kind": kind, "field": field, "reason": "typed early"}
    p.update(kw)
    b.store.append("deviation", p, operator="alice")


def _blocks(b, spec, gate_id, cond):
    v = GATES.evaluate(gate_id, spec, b.store, garment_dir=b.dir, check_files=False)
    return [x for x in v.blocks if x.condition == cond]


def _cut(b, **kw):
    """The real payload shape, so a test that says 'the rewrite was excused' is not really
    saying 'the record was incomplete'."""
    p = {"achieved_inseam_cm": {"L": 15.1, "R": 15.0},
         "achieved_outseam_cm": {"L": 16.1, "R": 16.0},
         "tool": "Fiskars 9in dressmaking shears", "legs_cut_separately": True,
         "operator": "alice"}
    p.update(kw)
    b.store.append("cut_performed", p, operator="alice")


def _wash(b, **kw):
    p = {"machine": "m", "cycle": "c", "water_temp_c": 30.0, "spin_rpm": 800, "detergent": "d",
         "detergent_ml": 30.0, "filler_load": "none", "dryer_method": "line",
         "conditioning_start": "a", "conditioning_end": "b"}
    p.update(kw)
    b.store.append("wash_actual", p, operator="alice")


def test_a_premature_cut_rewrite_acknowledgement_does_not_stand(spec):
    """One line at intake, and every later contradictory account of the cut is pre-forgiven."""
    b = _base(spec)
    _dev(b, "cut_performed_rewritten")            # written before any cut exists at all
    _cut(b)
    _cut(b, achieved_inseam_cm={"L": 41.0, "R": 15.0})                  # a second, different account
    hits = _blocks(b, spec, "ready_to_wash", "cut.performed_recorded")
    assert hits, (
        "a `cut_performed_rewritten` deviation typed before the garment was even cut excused a "
        "contradictory second account of the cut. The two accounts differ about the number the "
        "whole prediction is scored against.")


def test_a_premature_cut_after_wash_acknowledgement_does_not_stand(spec):
    b = _base(spec)
    _dev(b, "cut_recorded_after_wash")
    _wash(b)
    _cut(b)                                       # the cut typed after the wash
    hits = _blocks(b, spec, "ready_to_finalize", "cut.performed_recorded")
    assert hits, (
        "a deviation typed before either act excused a cut recorded after the wash -- the case "
        "where the tape was laid on a garment that had already shrunk")


def test_a_premature_wash_rewrite_acknowledgement_does_not_stand(spec):
    b = _base(spec)
    _dev(b, "wash_actual_rewritten", kind="wash")
    _cut(b)
    _wash(b)
    _wash(b, water_temp_c=90.0)                   # a second, different account of the wash
    hits = _blocks(b, spec, "ready_to_finalize", "wash.actual")
    assert hits, (
        "a `wash_actual_rewritten` deviation typed at intake excused a rewritten wash record. The "
        "planned/actual split exists so a departure stays visible; a pre-registered waiver erases "
        "exactly what it was built to preserve.")


def test_a_premature_measurement_revision_acknowledgement_does_not_stand(spec):
    """One acknowledgement, typed once, standing for every later silent replacement."""
    b = _base(spec)
    _dev(b, "measurement_revised:waist_cm")
    b.store.append("measurement",
                   {"name": "waist_cm", "readings": [70.0, 70.1, 70.05], "state": "before"},
                   operator="alice")
    hits = _blocks(b, spec, "ready_to_cut", "measurements.revisions_explained")
    assert hits, (
        "a `measurement_revised:waist_cm` deviation typed before the revision existed excused it. "
        "A corrected measurement is fine and a silent one is not, and this made every later "
        "correction of that measurement silent, forever.")

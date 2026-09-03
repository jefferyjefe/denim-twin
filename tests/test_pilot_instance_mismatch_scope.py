"""A deviation must account for what happened, not license what happens next.

Two conditions read a recorded deviation as an excuse -- `captures.instance_identity` and
`captures.state_order` -- and both matched on the deviation's KIND and FIELD only. One record,
writable at intake before any photograph existed, therefore cleared the condition for every frame
in the session, in both directions in time. Both excuses are now per-frame and have to postdate
what they excuse.

The original note, on the first of the two:

`captures.instance_identity` is a ready_to_cut condition: it is what catches a photograph filed
against a slot the plan says is a different physical thing. `deviation_covers` matched on the
deviation's KIND and FIELD only, so a single record -- writable at intake, before any photograph
existed -- cleared the condition for every instanced frame in the session, in both directions in
time. The excuse is now per-frame and has to postdate what it excuses.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import plan as PLAN, spec as SPEC        # noqa: E402
from denimtwin.pilot.selftest import Bench                    # noqa: E402

COND = "captures.instance_identity"


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


def _three_tears(b):
    b.open_session(); b.answer_features(overrides={"n_tears": 3}); b.measure()
    for i, loc in enumerate(("left leg front", "right knee", "left hem"), 1):
        b.store.append("annotation",
                       {"annotation_id": "TEAR.%02d" % i, "feature": "n_tears", "type": "tear",
                        "location": loc, "note": "x"}, operator="alice")
    s = b.store.fold()[0]
    shots = PLAN.activate(b.spec, s["features"], s["measurements"], annotations=s["annotations"])[0]
    slots = {x["annotation_id"]: x["shot_id"] for x in shots
             if x.get("annotation_id") and x["shot_id"].startswith("BEFORE.ANOM.TEAR")}
    # Not a skip. The plan is committed; a tree where three tears do not produce three instanced
    # slots is a tree where this guard has quietly stopped guarding anything.
    assert len(slots) >= 3, (
        "the committed plan instanced %d tear slots for three tears, so this test would prove "
        "nothing" % len(slots))
    return slots


def _capture(b, shot_id, of, where, sha="d"):
    b.store.append("capture",
                   {"shot_id": shot_id, "rep": 1, "sha256": sha * 64,
                    "path": "images/before/x.png", "state": "before",
                    "annotation_id": of, "annotation_location": where}, operator="alice")


def _deviation(b, reason, actual=None):
    b.store.append("deviation", {"kind": "protocol", "field": "instance_mismatch",
                                 "planned": None, "actual": actual, "reason": reason},
                   operator="alice")


def _blocked(b):
    return COND in b.blocked_conditions("ready_to_cut", check_files=False)


def test_an_instance_mismatch_deviation_excuses_only_the_frame_it_names(spec, tmp_path):
    """One recorded annoyance may not clear every other frame in the session.

    `deviation_covers(..., "instance_mismatch")` matched on the field alone, so a single record
    suppressed this condition for EVERY instanced frame -- including a frame borrowed from another
    tear and a frame filed against a slot the plan never instanced. An operator clearing one
    genuine re-description silently authorised the scissors over both.
    """
    b = Bench(tmp_path, spec, "DENIM_9811")
    slots = _three_tears(b)

    # an honest frame of TEAR.02, then an honest later correction to TEAR.02's description
    _capture(b, slots["TEAR.02"], "TEAR.02", "right knee", sha="e")
    b.store.append("annotation",
                   {"annotation_id": "TEAR.02", "feature": "n_tears", "type": "tear",
                    "location": "right knee, 8 cm above the hem", "note": "measured properly"},
                   operator="alice")
    assert _blocked(b), "a re-described instance must close the gate until it is accounted for"

    # a deviation that names no frame accounts for no frame
    _deviation(b, "TEAR.02 was re-described after its frame was taken")
    assert _blocked(b), "a deviation naming no frame must not excuse any frame"

    # naming the frame, after the fact, is the path forward -- and it opens
    _deviation(b, "TEAR.02 re-described after its frame was taken; the frame still shows it",
               actual="%s r1" % slots["TEAR.02"])
    assert not _blocked(b), "a deviation naming that frame, recorded after it, must clear it"

    # and it clears NOTHING else: a frame of TEAR.01 filed into TEAR.03's slot still blocks
    _capture(b, slots["TEAR.03"], "TEAR.01", "left leg front")
    assert _blocked(b), "the acknowledged frame must not excuse a frame of a different instance"


def test_an_instance_mismatch_deviation_cannot_be_written_before_the_disagreement(spec, tmp_path):
    """A deviation recorded before the departure is a standing permission, not an account.

    It could be written at intake -- before the frame existed, before the annotation was touched --
    and every later contradiction landed pre-excused.
    """
    b = Bench(tmp_path, spec, "DENIM_9812")
    slots = _three_tears(b)

    # written first, naming the slot, before anything disagrees with anything
    _deviation(b, "pre-authorising whatever this slot turns out to be",
               actual="%s r1" % slots["TEAR.03"])
    _capture(b, slots["TEAR.03"], "TEAR.01", "left leg front")
    assert _blocked(b), "a deviation predating the frame it names must not excuse it"

    # recording it after the fact is always available, so the operator is never stranded
    _deviation(b, "filed TEAR.01's frame into TEAR.03's slot; recording it now, after the fact",
               actual="%s r1" % slots["TEAR.03"])
    assert not _blocked(b), "a deviation recorded after the disagreement must still be a way out"


# -- the same amnesty on the neighbouring condition ----------------------------------------------

ORDER = "captures.state_order"


def _out_of_order(b):
    """A 'before' photograph filed AFTER the cut: a picture of the intact garment that cannot
    exist. Nothing can re-take it, which is exactly why the excuse matters."""
    b.store.append("cut_performed",
                   {"achieved_inseam_left_cm": 60.0, "achieved_inseam_right_cm": 60.1,
                    "legs_cut_separately": True, "offcuts_retained": True},
                   operator="alice")
    b.store.append("capture",
                   {"shot_id": "BEFORE.WHOLE.FRONT.FLAT", "rep": 1, "sha256": "a" * 64,
                    "path": "images/before/x.png", "state": "before"},
                   operator="alice")
    return ("BEFORE.WHOLE.FRONT.FLAT", 1)


def _order_deviation(b, reason, actual=None):
    b.store.append("deviation", {"kind": "protocol", "field": "capture_order",
                                 "planned": None, "actual": actual, "reason": reason},
                   operator="alice")


def test_a_capture_order_deviation_excuses_only_the_frame_it_names(spec, tmp_path):
    """One record written at intake pre-excused every out-of-order photograph for the rest of the
    session, and both later gates went green with no blocks at all -- on a required `before`
    photograph that was never taken and now cannot be, satisfied by a photograph of the cut,
    washed garment. Same defect as `instance_mismatch` above, on the neighbouring condition.
    """
    b = Bench(tmp_path, spec, "DENIM_9821")
    b.open_session(); b.answer_features(); b.measure()
    key = _out_of_order(b)
    assert ORDER in b.blocked_conditions("ready_to_cut", check_files=False), \
        "a before-frame filed after the cut must close the gate"

    _order_deviation(b, "the frame was filed late")
    assert ORDER in b.blocked_conditions("ready_to_cut", check_files=False), \
        "a deviation naming no frame must not excuse any frame"

    _order_deviation(b, "that frame was filed after the cut; recording it now",
                     actual="%s r%s" % key)
    assert ORDER not in b.blocked_conditions("ready_to_cut", check_files=False), \
        "a deviation naming that frame, recorded after it, must clear it"

    # and it clears nothing else
    b.store.append("capture",
                   {"shot_id": "BEFORE.WHOLE.BACK.FLAT", "rep": 1, "sha256": "b" * 64,
                    "path": "images/before/y.png", "state": "before"},
                   operator="alice")
    assert ORDER in b.blocked_conditions("ready_to_cut", check_files=False), \
        "the acknowledged frame excused a different out-of-order frame too"


def test_a_capture_order_deviation_cannot_be_written_before_the_frame_it_excuses(spec, tmp_path):
    """It was writable at intake, before a single photograph existed."""
    b = Bench(tmp_path, spec, "DENIM_9822")
    b.open_session(); b.answer_features(); b.measure()
    _order_deviation(b, "pre-authorising whatever gets filed late",
                     actual="BEFORE.WHOLE.FRONT.FLAT r1")
    key = _out_of_order(b)
    assert ORDER in b.blocked_conditions("ready_to_cut", check_files=False), \
        "a deviation predating the frame it names must not excuse it"

    _order_deviation(b, "filed that frame after the cut; recording it now, after the fact",
                     actual="%s r%s" % key)
    assert ORDER not in b.blocked_conditions("ready_to_cut", check_files=False), \
        "recording it after the fact must still be a way out"

"""A photograph of an earlier physical state cannot arrive after the act that ended it.

`captures.state_order` was written against the cut and named its two ends by hand:

    PRE  = ("intake", "before", "marked")
    POST = ("post_wash", "offcut_after")

The specification declares EIGHT states. Those two tuples name five, and the three they leave out
are the ones the whole wash arm is made of. `immediate_after` and `offcut_before` are the states
that exist only in the window between the shears and the water -- the tape laid against the freshly
cut inseam, the cut-edge macros, the offcut's own faces and labels before it goes into its wash --
and neither tuple contained them, so neither boundary applied to them.

The false READY that follows is the one round 7 already closed once for `before` frames and did not
close for these:

  1. the operator cuts the garment and, in the rush of cut day, never takes the twenty
     IMMEDIATE_AFTER frames or the ten OFFCUT_BEFORE frames;
  2. the garment and the offcuts go into the wash and `wash_actual` is recorded;
  3. afterwards the operator notices the empty slots and photographs the WASHED garment and the
     WASHED offcuts into them.

Every one of those thirty frames is a photograph of cloth that has been through the water, filed as
evidence of cloth that had not. `IMMEDIATE_AFTER.CUT.LEFT.ACTUAL_INSEAM_TAPE` is the ground truth
the whole prediction is scored against, and it is the one measurement that stops being takeable the
moment the garment shrinks. `ready_to_wash` and `ready_to_finalize` both returned ready with no
`captures.state_order` blocker at all.

The condition now derives its boundaries from the specification's own ordering rather than from two
hand-kept tuples, and it applies them at BOTH physical acts. `rig` is deliberately outside both:
those seventeen shots are of the backdrop, the board and the camera, not of the garment, so a rig
frame taken later is still a true photograph of the rig.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import gates as GATES, spec as SPEC          # noqa: E402
from denimtwin.pilot.selftest import Bench                        # noqa: E402

COND = "captures.state_order"

#: The two physical acts and the state each one ends. These are protocol facts, and the test states
#: them independently of the module under test so that a change to either is a failure here rather
#: than a silent agreement.
PRE_CUT = ("intake", "before", "marked")
PRE_WASH = PRE_CUT + ("immediate_after", "offcut_before")
POST_WASH = ("post_wash", "offcut_after")


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


def _cut_and_washed(spec):
    """A garment the log says has been cut and then washed."""
    b = Bench(tempfile.mkdtemp(), spec)
    b.open_session()
    b.freeze_rig()
    b.answer_features()
    b.measure()
    b.store.append("cut_performed",
                   {"inseam_left_cm": 60.0, "inseam_right_cm": 60.0, "cut_tool": "shears"},
                   operator="alice")
    b.store.append("wash_actual",
                   {"machine": "m", "cycle": "c", "water_temp_c": 30.0, "spin_rpm": 800,
                    "detergent": "d", "detergent_ml": 30.0, "filler_load": "none",
                    "dryer_method": "line", "conditioning_start": "a", "conditioning_end": "b"},
                   operator="alice")
    return b


def _file_frame(b, state, shot_id=None, rep=1):
    sid = shot_id or ("PROBE.%s" % state.upper())
    b.store.append("capture",
                   {"shot_id": sid, "rep": rep, "sha256": "a" * 64,
                    "path": "images/%s/x.png" % state, "state": state},
                   operator="alice")
    return (sid, rep)


def _state_order_blocks(b, spec, gate_id):
    v = GATES.evaluate(gate_id, spec, b.store, garment_dir=b.dir, check_files=False)
    return [bl for bl in v.blocks if bl.condition == COND]


@pytest.mark.parametrize("state", PRE_WASH)
@pytest.mark.parametrize("gate_id", ("ready_to_wash", "ready_to_finalize"))
def test_a_pre_wash_frame_cannot_be_filed_after_the_wash(spec, state, gate_id):
    """Every state that exists only before the water, blocked once the water is recorded."""
    b = _cut_and_washed(spec)
    key = _file_frame(b, state)
    hits = _state_order_blocks(b, spec, gate_id)
    assert hits, (
        "%s r%s is a %s frame filed after the wash was recorded, and %s raised no %s blocker at "
        "%s. A photograph of cloth that has been through the water is not evidence of cloth that "
        "had not." % (key[0], key[1], state, gate_id, COND, gate_id))
    assert key[0] in hits[0].what, (
        "the blocker fired but does not name the offending frame: %r" % hits[0].what)


def test_the_thirty_frames_that_only_exist_between_the_shears_and_the_water(spec):
    """The concrete session: the cut-day frames are skipped, then filled from the washed garment."""
    b = _cut_and_washed(spec)
    filled = [_file_frame(b, "immediate_after", "IMMEDIATE_AFTER.CUT.LEFT.ACTUAL_INSEAM_TAPE"),
              _file_frame(b, "immediate_after", "IMMEDIATE_AFTER.HEM.LEFT.MACRO.PNN"),
              _file_frame(b, "offcut_before", "OFFCUT_BEFORE.CUT_EDGE.LEFT.MACRO.PNN"),
              _file_frame(b, "offcut_before", "OFFCUT_BEFORE.LEFT.LABEL")]
    for gate_id in ("ready_to_wash", "ready_to_finalize"):
        hits = _state_order_blocks(b, spec, gate_id)
        assert hits, (
            "%s accepted %d frames of the pre-wash garment filed after the wash with no %s "
            "blocker" % (gate_id, len(filled), COND))
        named = hits[0].what + repr(hits[0].evidence)
        for sid, _rep in filled:
            assert sid in named, "the blocker does not name %s" % sid


def test_a_rig_frame_is_not_bound_to_the_garments_lifecycle(spec):
    """The seventeen rig shots are of the backdrop and the board, not of the garment."""
    b = _cut_and_washed(spec)
    _file_frame(b, "rig", "RIG.BACKDROP.EMPTY")
    for gate_id in ("ready_to_wash", "ready_to_finalize"):
        assert not _state_order_blocks(b, spec, gate_id), (
            "a photograph of the empty backdrop taken after the wash was refused as if it were a "
            "photograph of the garment")


@pytest.mark.parametrize("state", ("immediate_after", "offcut_before"))
def test_the_new_boundary_is_still_excusable_one_frame_at_a_time(spec, state):
    """The remedy the blocker prints has to work, and has to work for one frame only."""
    b = _cut_and_washed(spec)
    victim = _file_frame(b, state, "PROBE.%s.A" % state.upper())
    other = _file_frame(b, state, "PROBE.%s.B" % state.upper())
    b.store.append("deviation",
                   {"kind": "protocol", "field": "capture_order",
                    "actual": "%s r%s" % victim, "reason": "the frame was never taken"},
                   operator="alice")
    hits = _state_order_blocks(b, spec, "ready_to_finalize")
    assert hits, "the deviation naming one frame excused the other frame as well"
    assert other[0] in hits[0].what, "the surviving blocker names the wrong frame: %r" % hits[0].what
    assert victim[0] not in hits[0].what, (
        "the frame the deviation names is still blocking: %r" % hits[0].what)


@pytest.mark.parametrize("state", ("immediate_after", "offcut_before"))
def test_a_deviation_written_before_the_frame_does_not_excuse_it(spec, state):
    """A record written before the departure is a permission slip, not an account."""
    b = _cut_and_washed(spec)
    sid = "PROBE.%s.EARLY" % state.upper()
    b.store.append("deviation",
                   {"kind": "protocol", "field": "capture_order", "actual": "%s r1" % sid,
                    "reason": "written before the frame existed"},
                   operator="alice")
    _file_frame(b, state, sid)
    hits = _state_order_blocks(b, spec, "ready_to_finalize")
    assert hits, (
        "a deviation recorded BEFORE the frame it names excused that frame, which is a standing "
        "permission for a departure that had not happened yet")


def test_the_boundary_states_the_condition_relies_on_are_declared(spec):
    """If the specification renames a boundary state the condition must fail loudly, not quietly."""
    declared = {st["state"] for st in spec.states}
    for st in PRE_WASH + POST_WASH:
        assert st in declared, (
            "the specification no longer declares %r, and %s is written in terms of it" % (st, COND))

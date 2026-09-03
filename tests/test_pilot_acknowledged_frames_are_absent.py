"""A deviation that acknowledges an impossible photograph does not turn it into evidence.

`captures.state_order` and `captures.instance_identity` each end their blocker with the same
instruction: record one deviation naming the frame, *and treat those frames as absent*. Both
conditions then honoured the deviation -- and nothing treated the frame as absent.
`captures.required_complete` never read the deviations at all. So the exact false READY the
per-frame scoping was built to close survived it, one command per frame:

  1. a required before-state frame is never taken;
  2. the garment is cut (and washed);
  3. a photograph of the cut garment is filed into the empty before slot -- it decodes, the board is
     in it, every pixel check passes, and the operator confirms the region against it truthfully,
     because it IS that region, of the wrong garment;
  4. `captures.state_order` blocks, and prints the deviation command;
  5. the operator types it;
  6. `captures.state_order` reports the frame acknowledged, `captures.required_complete` reports it
     captured and passing, and the gate is one frame closer to READY on a photograph of cloth that
     no longer exists in that state.

The frame is now what the message always said it was. A standing per-frame `capture_order` or
`instance_mismatch` deviation makes the frame ABSENT for `required_complete`: the deviation
explains why the log contradicts itself, it does not supply the photograph. A garment whose
before-state evidence was never taken cannot be made ready by typing, and the gate says so.
"""
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import gates as GATES, spec as SPEC          # noqa: E402
from denimtwin.pilot.selftest import Bench                        # noqa: E402

VICTIM = "BEFORE.HEM.LEFT.CONSTRUCTION.MACRO"


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


def _session_with_late_before_frame(spec):
    """Cut first; then a genuinely passing photograph filed into a before slot."""
    b = Bench(tempfile.mkdtemp(), spec)
    b.open_session()
    b.freeze_rig()
    b.answer_features()
    b.measure()
    b.store.append("cut_performed",
                   {"achieved_inseam_cm": {"L": 15.1, "R": 15.0},
                    "achieved_outseam_cm": {"L": 16.1, "R": 16.0},
                    "tool": "shears", "legs_cut_separately": True, "operator": "alice"},
                   operator="alice")
    shots, _ = b.activated()
    shot = [s for s in shots if s["shot_id"] == VICTIM][0]
    b.add(shot, 1, b.synth_for(shot, 1, seed=0))
    b.resolve_humans()
    return b


def _required_complete(b, spec):
    v = GATES.evaluate("ready_to_cut", spec, b.store, garment_dir=b.dir, check_files=False)
    rc = [x for x in v.blocks if x.condition == "captures.required_complete"]
    so = [x for x in v.blocks if x.condition == "captures.state_order"]
    return rc, so


def _counts(block):
    import re
    m = re.search(r"(\d+) missing, (\d+) failing, (\d+) unresolved", block.what)
    return tuple(int(x) for x in m.groups())


def test_the_frame_counts_as_present_before_it_is_acknowledged(spec):
    """Establishes what the deviation is being compared against: the frame passes, and counts."""
    b = _session_with_late_before_frame(spec)
    rc, so = _required_complete(b, spec)
    assert so, "the out-of-order frame was not caught by state_order; the fixture is wrong"
    assert rc, "a one-frame session is not otherwise complete; the fixture is wrong"
    missing, failing, unresolved = _counts(rc[0])
    assert VICTIM not in " ".join(rc[0].evidence.get("missing", [])), (
        "the frame is already reported missing before any deviation, so the test below would "
        "prove nothing about the deviation")
    assert failing == 0 and unresolved == 0, rc[0].what


def test_an_acknowledged_out_of_order_frame_is_absent(spec):
    b = _session_with_late_before_frame(spec)
    rc_before, _ = _required_complete(b, spec)
    missing_before = _counts(rc_before[0])[0]
    b.store.append("deviation",
                   {"kind": "protocol", "field": "capture_order", "actual": "%s r1" % VICTIM,
                    "reason": "never taken before the cut; this is the cut garment"},
                   operator="alice")
    rc, so = _required_complete(b, spec)
    assert not so, "the deviation did not clear state_order; the ceremony itself is broken"
    assert rc, "the gate has no required_complete blocker at all after the deviation"
    missing_after = _counts(rc[0])[0]
    assert missing_after == missing_before + 1, (
        "captures.state_order told the operator to 'treat those frames as absent' and "
        "captures.required_complete still counts the acknowledged frame as captured and passing: "
        "missing went %d -> %d. The photograph is of the cut garment; the deviation explains the "
        "contradiction, it does not supply the before-state evidence."
        % (missing_before, missing_after))
    assert VICTIM in " ".join(rc[0].evidence.get("missing", [])), (
        "the acknowledged frame is not named among the missing: %r" % rc[0].evidence)


def test_an_acknowledged_instance_mismatch_frame_is_absent_too(spec):
    """The other per-frame deviation ends with the same sentence and has the same hole."""
    b = Bench(tempfile.mkdtemp(), spec)
    b.open_session()
    b.freeze_rig()
    b.answer_features(overrides={"n_tears": 1})
    b.measure()
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "left knee", "note": "x"}, operator="alice")
    shots, _ = b.activated()
    slot = [s for s in shots if s.get("annotation_id") == "TEAR.01"
            and s["shot_id"].startswith("BEFORE.ANOM.TEAR")]
    assert slot, "the committed plan instanced no tear slot; the fixture is wrong"
    shot = slot[0]
    b.add(shot, 1, b.synth_for(shot, 1, seed=0))
    b.resolve_humans()
    # Re-describe the instance AFTER the photograph: the frame now disagrees with the plan.
    b.store.append("annotation",
                   {"annotation_id": "TEAR.01", "feature": "n_tears", "type": "tear",
                    "location": "right hem", "note": "moved"}, operator="alice")
    v = GATES.evaluate("ready_to_cut", spec, b.store, garment_dir=b.dir, check_files=False)
    ii = [x for x in v.blocks if x.condition == "captures.instance_identity"]
    assert ii, "the re-description was not caught by instance_identity; the fixture is wrong"
    rc0 = [x for x in v.blocks if x.condition == "captures.required_complete"]
    m0 = _counts(rc0[0])[0]
    b.store.append("deviation",
                   {"kind": "protocol", "field": "instance_mismatch",
                    "actual": "%s r1" % shot["shot_id"], "reason": "the tear was re-described"},
                   operator="alice")
    v = GATES.evaluate("ready_to_cut", spec, b.store, garment_dir=b.dir, check_files=False)
    assert not [x for x in v.blocks if x.condition == "captures.instance_identity"], (
        "the deviation did not clear instance_identity; the ceremony itself is broken")
    rc = [x for x in v.blocks if x.condition == "captures.required_complete"]
    assert _counts(rc[0])[0] == m0 + 1, (
        "an instance_mismatch deviation acknowledged the frame and required_complete still counts "
        "it as evidence of a feature the plan now says is somewhere else")

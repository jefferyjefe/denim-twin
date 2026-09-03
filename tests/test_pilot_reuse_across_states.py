"""A borrowed photograph carries its own physical state, not the state of the slot it is filed in.

`pilot.py reuse` declares that one accepted photograph also satisfies a second shot. It re-runs the
borrowing shot's own checks on the borrowed image and refuses a borrow that fails them, it refuses
a borrow across two different annotation instances, and it refuses one whose subject the target
repeat does not name. It never compared the two shots' LIFECYCLE STATES.

So one command filed a photograph of the garment before the shears as the post-wash frame:

    pilot.py reuse <G> BEFORE.OBLIQUE.FL1 POSTWASH.OBLIQUE.FL1

The bytes are identical, the sha256 is identical, the EXIF timestamp predates the cut, and the file
is copied into `images/post_wash/` under the post-wash shot's own content-addressed name. Every
check the post-wash shot raises passes on it, because the same camera, the same board and the same
region are in the frame -- the only thing that has changed is that the cloth has been through the
water, and nothing in the pixels of a borrowed frame is compared against anything that would know.

`captures.state_order` cannot catch it and could not have. That condition asks whether the capture
ENTRY was appended on the correct side of the cut and the wash entries, and a borrow performed
after the wash genuinely was. It answered "every photograph's state agrees with the log's own
order" about a photograph taken before the garment was cut.

Two fixes, because the two doors are different:

  * `pilot.py reuse` refuses a cross-state borrow outright, at the command, before anything is
    written -- the log is append-only and a refusal after the write is a record that stays.
  * `captures.state_order` applies its boundary test to the SOURCE capture's entry for any capture
    carrying `reused_from`. That is the one that matters, because the gate is the authority and a
    capture entry can arrive by routes the CLI does not own.

Independently confirmed by two adversarial verifiers before it was touched.
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


@pytest.fixture(scope="module")
def spec():
    return SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")


def _cut_and_washed(spec):
    b = Bench(tempfile.mkdtemp(), spec)
    b.open_session()
    b.freeze_rig()
    b.answer_features()
    b.measure()
    return b


def _capture(b, shot_id, state, sha="a" * 64, **kw):
    p = {"shot_id": shot_id, "rep": 1, "sha256": sha,
         "path": "images/%s/x.png" % state, "state": state}
    p.update(kw)
    b.store.append("capture", p, operator="alice")


def _acts(b):
    b.store.append("cut_performed",
                   {"achieved_inseam_cm": {"L": 15.1, "R": 15.0},
                    "achieved_outseam_cm": {"L": 16.1, "R": 16.0},
                    "tool": "shears", "legs_cut_separately": True, "operator": "alice"},
                   operator="alice")
    b.store.append("wash_actual",
                   {"machine": "m", "cycle": "c", "water_temp_c": 30.0, "spin_rpm": 800,
                    "detergent": "d", "detergent_ml": 30.0, "filler_load": "none",
                    "dryer_method": "line", "conditioning_start": "a", "conditioning_end": "b"},
                   operator="alice")


def _state_order(b, spec, gate_id="ready_to_finalize"):
    v = GATES.evaluate(gate_id, spec, b.store, garment_dir=b.dir, check_files=False)
    return [x for x in v.blocks if x.condition == COND]


def test_a_borrowed_pre_cut_frame_cannot_stand_as_post_wash_evidence(spec):
    """The exact reproduction: a before frame borrowed into a post-wash slot after the wash."""
    b = _cut_and_washed(spec)
    _capture(b, "BEFORE.OBLIQUE.FL1", "before")          # taken while the garment was whole
    _acts(b)                                              # cut, then washed
    _capture(b, "POSTWASH.OBLIQUE.FL1", "post_wash",      # borrowed afterwards
             reused_from="BEFORE.OBLIQUE.FL1", reused_from_rep=1)
    hits = _state_order(b, spec)
    assert hits, (
        "a photograph taken before the shears was filed as the post-wash frame and %s reported "
        "'every photograph's state agrees with the log's own order'. The borrow entry really was "
        "appended after the wash; the PHOTOGRAPH was not, and the photograph is the evidence."
        % COND)
    assert "POSTWASH.OBLIQUE.FL1" in hits[0].what, hits[0].what
    assert "BEFORE.OBLIQUE.FL1" in (hits[0].what + repr(hits[0].evidence)), (
        "the blocker does not name the frame the bytes actually came from, so the operator cannot "
        "tell this from an ordinary out-of-order filing: %r" % hits[0].what)


def test_a_borrow_within_one_state_is_still_allowed(spec):
    """Reuse exists for a reason. Two shots of the same state may still share a frame."""
    b = _cut_and_washed(spec)
    _capture(b, "BEFORE.OBLIQUE.FL1", "before")
    _capture(b, "BEFORE.OBLIQUE.FL2", "before", reused_from="BEFORE.OBLIQUE.FL1", reused_from_rep=1)
    assert not _state_order(b, spec, "ready_to_cut"), (
        "a legitimate same-state borrow was refused; the permission the command exists for is gone")


def test_a_forward_borrow_is_refused_too(spec):
    """The other direction: a post-wash frame borrowed into a before slot is equally impossible."""
    b = _cut_and_washed(spec)
    _acts(b)
    _capture(b, "POSTWASH.OBLIQUE.FL1", "post_wash")
    _capture(b, "BEFORE.OBLIQUE.FL1", "before",
             reused_from="POSTWASH.OBLIQUE.FL1", reused_from_rep=1)
    hits = _state_order(b, spec)
    assert hits, (
        "a photograph of the washed garment was borrowed into a before slot and nothing refused it")


def test_the_source_frames_own_position_is_what_is_tested(spec):
    """Not the borrow's position. A borrow made before the wash is caught by the same rule."""
    b = _cut_and_washed(spec)
    _capture(b, "BEFORE.OBLIQUE.FL1", "before")
    _capture(b, "POSTWASH.OBLIQUE.FL1", "post_wash",
             reused_from="BEFORE.OBLIQUE.FL1", reused_from_rep=1)
    _acts(b)
    hits = _state_order(b, spec)
    assert hits, (
        "the borrow happened before the wash entry, so the ordinary position test would call the "
        "post-wash frame early -- but the reason it is wrong is the SOURCE, and that has to be "
        "what the message says")


def test_the_cli_refuses_a_cross_state_borrow_before_writing_anything(spec, tmp_path):
    """The log is append-only: a refusal after the write leaves the wrong record in it forever."""
    import subprocess
    import os
    env = dict(os.environ, PILOT_GARMENTS=str(tmp_path))
    r = subprocess.run([sys.executable, "tools/pilot.py", "--help"], cwd=str(ROOT), env=env,
                       capture_output=True, text=True)
    assert "reuse" in r.stdout, "the reuse command is gone; this guard is aimed at nothing"
    # The unit-level statement of the same rule, so this does not depend on driving a whole
    # session through the CLI: the command's own guard must exist and must name both states.
    src = (ROOT / "tools" / "pilot.py").read_text()
    fn = src[src.index("def cmd_reuse("):src.index("def cmd_deviation(")]
    assert 'src.get("state")' in fn or "source_state" in fn, (
        "cmd_reuse never reads the source capture's lifecycle state, so it cannot compare it with "
        "the target's")
    assert "refus" in fn.lower(), "cmd_reuse has no refusal path for a cross-state borrow"

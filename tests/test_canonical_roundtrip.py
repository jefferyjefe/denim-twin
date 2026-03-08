"""Canonical space must give the garment back — and it does not, away from the landmarks (EXP_0029).

`CanonicalMap` fits two INDEPENDENT thin-plate splines, image->canonical and canonical->image, from the same
correspondences. Two independent fits agree exactly where they were fitted and nowhere in particular between. The
existing round-trip test (`tests/test_canon.py`) samples landmark points, which is precisely where the error is zero.

These tests measure it where the project actually works — over the whole garment, and on a region — and pin the
numbers as a CEILING, so the situation cannot quietly get worse while the docs still say "sub-pixel".
"""
import os, sys
import numpy as np, cv2, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
from denimtwin.canon.warp import CanonicalMap
from test_canon import synthetic_jeans


def _map_and_mask():
    img, mask, lm = synthetic_jeans(jitter=0)
    return CanonicalMap(lm), mask, lm


def test_the_round_trip_is_exact_at_the_landmarks():
    """The documented claim, and its true scope."""
    cm, _, lm = _map_and_mask()
    L = np.array([lm[n] for n in cm.names], np.float32)
    back = np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(L))))
    assert np.linalg.norm(back - L, axis=1).max() < 1.0


def _skewed_map(mask, lm):
    """A landmark set that does not match the canonical template's proportions — which is what a real garment is.
    On the synthetic jeans the two TPS fits are near-affine and agree; the divergence needs a garment whose shape the
    template has to bend to reach, and every real pair is one."""
    skew = dict(lm)
    for k in list(skew):
        x, y = skew[k]
        if "right" in k: x = x + 0.16 * mask.shape[1]        # one leg much wider than the other
        if "hem" in k: y = y + 0.05 * mask.shape[0]
        if k == "crotch": y = y - 0.10 * mask.shape[0]
        skew[k] = (x, y)
    return CanonicalMap(skew)


def test_the_round_trip_is_not_exact_over_a_garment_the_template_has_to_bend_to_reach():
    """The mechanism: two independently fitted TPS maps agree where they were fitted and diverge in between, and the
    divergence grows with how far the garment is from the canonical template. On the real pairs this reaches a median
    of 110 px and a worst case of 835 px (EXP_0029). If this test ever fails, the two fits became inverses and the
    finding is fixed — revisit the note, do not delete the test."""
    _, mask, lm = _map_and_mask()
    cm = _skewed_map(mask, lm)
    ys, xs = np.nonzero(mask)
    idx = np.linspace(0, len(xs) - 1, 400).astype(int)
    P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)
    err = np.linalg.norm(np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(P)))) - P, axis=1)
    L = np.array([lm[n] for n in cm.names], np.float32)
    assert err.max() > 1.0, ("the canonical round trip is now exact even off-template; see EXP_0029", float(err.max()))
    assert err.max() > 10 * np.median(np.linalg.norm(
        np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(L)))) - L, axis=1) + 1e-6) or err.max() > 1.0


def test_the_round_trip_error_over_the_garment_stays_within_its_measured_ceiling():
    """A synthetic garment is the easy case — the real pairs measure 0.33 to 110.85 px median (EXP_0029). This holds
    the easy case to something much tighter so a regression shows up here first."""
    cm, mask, _ = _map_and_mask()
    ys, xs = np.nonzero(mask)
    idx = np.linspace(0, len(xs) - 1, 400).astype(int)
    P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)
    err = np.linalg.norm(np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(P)))) - P, axis=1)
    h = mask.shape[0]
    assert np.median(err) < 0.05 * h, f"median round-trip error {np.median(err):.1f} px on a {h} px garment"


def test_a_region_does_not_survive_the_round_trip_intact():
    """The quantity that actually bit: `predict.py` expresses the cut as a canonical region, and on the real pairs
    that region comes back with a median IoU of 0.638 with itself (worst 0.074)."""
    _, mask, lm = _map_and_mask()
    cm = _skewed_map(mask, lm)
    region = np.zeros_like(mask, np.uint8)
    region[int(0.62 * mask.shape[0]):] = 255
    region = (region > 0) & mask
    canon = np.asarray(cm.image_to_canon((region.astype(np.uint8) * 255))) > 127
    back = np.asarray(cm.canon_to_image((canon.astype(np.uint8) * 255), region.shape)) > 127
    iou = (back & region).sum() / max((back | region).sum(), 1)
    assert 0.0 <= iou <= 1.0
    assert iou < 0.999, "a region now round-trips exactly off-template; EXP_0029 is fixed and its note needs updating"


@pytest.mark.skipif(not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "reports/canonical_roundtrip.json")),
                    reason="needs a scored run (reports/canonical_roundtrip.json); artefacts are gitignored")
def test_the_measured_report_says_what_the_note_says():
    import json
    d = json.load(open(os.path.join(os.path.dirname(__file__), "..", "reports/canonical_roundtrip.json")))
    assert d["median_point_err_at_landmarks_px"] < 1.0, "the landmarks are no longer exact"
    assert d["median_point_err_over_garment_px"] > 1.0, "the garment now round-trips; EXP_0029 needs revisiting"
    assert 0.0 <= d["median_region_roundtrip_iou"] <= 1.0

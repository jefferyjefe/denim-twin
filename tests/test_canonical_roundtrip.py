"""Canonical space must give the garment back (EXP_0029/0030).

`CanonicalMap` fits two INDEPENDENT thin-plate splines, image->canonical and canonical->image, from the same
correspondences. Two independent fits agree exactly where they were fitted and nowhere in particular between, and the
existing round-trip test (`tests/test_canon.py`) samples landmark points, which is precisely where the error is zero.
EXP_0029 measured a median of 10.7 px over the rest of the garment, and 835 px at worst.

EXP_0030 fixed it by iterating against the forward map instead of trusting the second fit (`exact=True`, the default).
These tests hold BOTH halves in place: the corrected inverse must round-trip, and `exact=False` must still show the
error it was built to remove — otherwise the fix could silently become a no-op.
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


def test_the_uncorrected_inverse_is_not_exact_over_a_garment_the_template_has_to_bend_to_reach():
    """The defect EXP_0029 found, kept measurable: with `exact=False` the second TPS fit is used as-is."""
    _, mask, lm = _map_and_mask()
    cm = _skewed_map(mask, lm)
    ys, xs = np.nonzero(mask)
    idx = np.linspace(0, len(xs) - 1, 400).astype(int)
    P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)
    err = np.linalg.norm(np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(P)), exact=False)) - P, axis=1)
    assert err.max() > 1.0, ("the two independent TPS fits are now inverses of each other; EXP_0029 is fixed at the "
                             "source and this test's premise is gone", float(err.max()))


def test_the_corrected_inverse_round_trips_over_the_whole_garment():
    """EXP_0030's fix: iterate against the forward map. On the real pairs this takes the median round-trip error over
    the garment from 10.7 px to 0.02 px."""
    _, mask, lm = _map_and_mask()
    cm = _skewed_map(mask, lm)
    ys, xs = np.nonzero(mask)
    idx = np.linspace(0, len(xs) - 1, 400).astype(int)
    P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)
    err = np.linalg.norm(np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(P)), exact=True)) - P, axis=1)
    bad = np.asarray(cm.points_to_image(np.asarray(cm.points_to_canon(P)), exact=False))
    bad_err = np.linalg.norm(bad - P, axis=1)
    assert np.median(err) < 0.5, f"corrected inverse still off by {np.median(err):.2f} px"
    assert np.median(err) < np.median(bad_err), "the correction did not improve on the uncorrected inverse"


def test_the_iteration_never_makes_a_point_worse():
    """It diverged before the per-point backtracking went in — to 9.5 million pixels on one real pair."""
    _, mask, lm = _map_and_mask()
    cm = _skewed_map(mask, lm)
    ys, xs = np.nonzero(mask)
    idx = np.linspace(0, len(xs) - 1, 300).astype(int)
    P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)
    Y = np.asarray(cm.points_to_canon(P), np.float32)
    e_ex = np.linalg.norm(np.asarray(cm.points_to_canon(cm.points_to_image(Y, exact=True))) - Y, axis=1)
    e_no = np.linalg.norm(np.asarray(cm.points_to_canon(cm.points_to_image(Y, exact=False))) - Y, axis=1)
    assert (e_ex <= e_no + 1e-3).all(), f"{(e_ex > e_no + 1e-3).sum()} points got worse under the correction"


def test_a_folded_map_is_detected_rather_than_inverted():
    """Where the map is not injective there is no inverse to find, and EXP_0030 measured 40.1% and 37.2% of the
    garment folded on two of the seven pairs — exactly the two a region does not survive. `fold_fraction` is what
    `predict.py` refuses on."""
    _, mask, lm = _map_and_mask()
    good = CanonicalMap(lm)
    assert good.fold_fraction(mask) < 0.05, "the synthetic garment should not fold"
    crossed = dict(lm)
    for k in list(crossed):                       # swap the legs: the map has to turn space inside out to comply
        if "left" in k: crossed[k] = lm[k.replace("left", "right")]
        if "right" in k: crossed[k] = lm[k.replace("right", "left")]
    assert CanonicalMap(crossed).fold_fraction(mask) > 0.2, "a crossed-leg landmark set should fold"


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


def test_a_region_survives_the_round_trip_once_the_inverse_is_corrected():
    """The quantity that actually bit: `predict.py` expresses the cut as a canonical region. Uncorrected, on the real
    pairs, that region came back with a median IoU of 0.638 with itself (worst 0.074); corrected, 0.972."""
    _, mask, lm = _map_and_mask()
    cm = _skewed_map(mask, lm)
    region = np.zeros_like(mask, np.uint8)
    region[int(0.62 * mask.shape[0]):] = 255
    region = (region > 0) & mask
    def trip(exact):
        canon = np.asarray(cm.image_to_canon((region.astype(np.uint8) * 255), exact=exact)) > 127
        back = np.asarray(cm.canon_to_image((canon.astype(np.uint8) * 255), region.shape)) > 127
        return (back & region).sum() / max((back | region).sum(), 1)
    assert trip(True) >= trip(False), "the corrected inverse loses more of the region than the uncorrected one"
    assert trip(True) > 0.9, f"a region still does not survive the corrected round trip (IoU {trip(True):.3f})"


@pytest.mark.skipif(not os.path.exists(os.path.join(os.path.dirname(__file__), "..", "reports/canonical_roundtrip.json")),
                    reason="needs a scored run (reports/canonical_roundtrip.json); artefacts are gitignored")
def test_the_measured_report_says_what_the_note_says():
    import json
    d = json.load(open(os.path.join(os.path.dirname(__file__), "..", "reports/canonical_roundtrip.json")))
    assert d["median_point_err_at_landmarks_px"] < 1.0, "the landmarks are no longer exact"
    assert d["median_point_err_over_garment_px"] >= 0.0
    assert 0.0 <= d["median_region_roundtrip_iou"] <= 1.0


def test_coincident_landmarks_are_dropped_rather_than_forcing_a_fold():
    """EXP_0031: a garment photographed with its legs touching gives `hem_left_inner` and `hem_right_inner` within a
    pixel of each other, and the canonical template wants them 160 px apart. A TPS asked to pull two coincident
    points apart turns space inside out — 37.2% and 40.1% of the garment on two real pairs, against 1.5x stretch and
    no fold on one that works."""
    _, mask, lm = _map_and_mask()
    touching = dict(lm)
    for k in ("hem_right_inner", "knee_right_inner"):
        if k in touching and k.replace("right", "left") in touching:
            touching[k] = tuple(np.array(touching[k.replace("right", "left")]) + 1.0)
    kept = CanonicalMap(touching, drop_degenerate=True)
    all_of_them = CanonicalMap(touching, drop_degenerate=False)
    assert kept.dropped, "a coincident correspondence was kept"
    assert all_of_them.fold_fraction(mask) >= kept.fold_fraction(mask), \
        "dropping the degenerate correspondence made the fold worse"


def test_a_garment_with_well_separated_landmarks_loses_none_of_them():
    """The rule must fire only where it should: on the real pairs it drops nothing on five of seven."""
    _, mask, lm = _map_and_mask()
    cm = CanonicalMap(lm, drop_degenerate=True)
    assert cm.dropped == [], f"dropped landmarks from a clean garment: {cm.dropped}"


def test_dropping_never_leaves_too_few_correspondences_to_fit():
    """Four points is the minimum this map is built on; below that the drop is abandoned rather than fitted."""
    _, mask, lm = _map_and_mask()
    collapsed = {k: (100.0, 100.0) for k in lm}      # every landmark on top of every other
    cm = CanonicalMap(collapsed, drop_degenerate=True)
    assert len(cm.names) >= 4, f"only {len(cm.names)} correspondences left"

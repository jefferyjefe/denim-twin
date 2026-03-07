"""Uprighting is the guarantee EXP_0021's tilt finding needs: after it, a measurement of one garment must not depend
on how the phone was held. These tests pin that property, and the regime where the estimate is known to be unsafe.
"""
import os, sys
import numpy as np, cv2, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from denimtwin.canon.upright import upright, tilt_angle, unreliable, max_correctable_tilt
from denimtwin.canon.autolm import landmarks_from_mask


def silhouette(H=1200, W=900, kind="jeans"):
    m = np.zeros((H, W), np.uint8)
    cx, top = W // 2, int(0.10 * H)
    ww = int(0.44 * W); hh = int(0.42 * H if kind == "shorts" else 0.82 * H)
    body = int(0.40 * (0.50 * H))
    cv2.rectangle(m, (cx - ww // 2, top), (cx + ww // 2, top + body), 255, -1)
    leg_w = int(ww * 0.44); gap = int(ww * 0.06)
    for s in (-1, 1):
        x0 = cx + s * gap // 2 - (leg_w if s < 0 else 0)
        cv2.rectangle(m, (x0, top + body), (x0 + leg_w, top + hh), 255, -1)
    return m > 0


def photo(mask):
    img = np.full((*mask.shape, 3), 215, np.uint8)
    img[mask] = (115, 72, 44)
    return img


def rotate(mask, deg):
    h, w = mask.shape
    return cv2.warpAffine(mask.astype(np.uint8), cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0), (w, h),
                          flags=cv2.INTER_NEAREST) > 0


def ratios(mask):
    lm, _ = landmarks_from_mask(mask)
    ww = float(lm["waist_right"][0] - lm["waist_left"][0])
    ys = np.nonzero(mask.any(axis=1))[0]
    top = float(lm["waist_left"][1])
    out = {"height_over_waist": (float(ys.max()) - top) / ww}
    if "hip_left" in lm: out["hip_over_waist"] = float(lm["hip_right"][0] - lm["hip_left"][0]) / ww
    if "crotch" in lm: out["rise_over_waist"] = (float(lm["crotch"][1]) - top) / ww
    return out


@pytest.mark.parametrize("tilt", [-20, -12, -8, -5, -3, -1, 1, 3, 5, 8, 12, 20])
def test_shape_ratios_survive_camera_tilt_once_upright_runs(tilt):
    """The property EXP_0021 found missing: without uprighting these ratios move 18-33% at 8 degrees."""
    base = silhouette(kind="jeans")
    ref = ratios(base)
    tilted = rotate(base, tilt)
    _, corrected, applied = upright(photo(tilted), tilted)
    got = ratios(corrected)
    for k, v in ref.items():
        assert abs(got[k] - v) / abs(v) < 0.05, f"{k} moved {abs(got[k]-v)/abs(v):.1%} at {tilt}° (applied {applied:.1f}°)"


def test_uncorrected_tilt_really_does_break_the_ratios():
    """If this ever passes, the landmark heuristic became rotation-invariant and uprighting is no longer load-bearing."""
    base = silhouette(kind="jeans"); ref = ratios(base)
    got = ratios(rotate(base, 8))
    assert any(abs(got[k] - v) / abs(v) > 0.05 for k, v in ref.items()), \
        "landmarks are now tilt-invariant; EXP_0021's finding and this module need revisiting"


def test_the_deadband_reproduces_the_old_behaviour():
    base = silhouette(kind="jeans"); tilted = rotate(base, 4)
    _, _, applied_old = upright(photo(tilted), tilted, deadband=8.0)
    _, _, applied_new = upright(photo(tilted), tilted, deadband=0.0)
    assert applied_old == 0.0 and abs(applied_new) > 1.0


def test_a_near_isotropic_silhouette_is_flagged_rather_than_trusted():
    shorts = silhouette(kind="shorts")
    ang, elong = tilt_angle(rotate(shorts, 8))
    assert elong < 1.5, "the synthetic shorts stopped being squat; the guard needs a new subject"
    assert unreliable(8.0, 1.1) and not unreliable(8.0, 1.6) and not unreliable(2.0, 1.1)


def test_a_wildly_tilted_squat_mask_is_left_alone():
    """60 degrees on a squat silhouette is more likely a mask error than a photograph of a tilted garment."""
    assert max_correctable_tilt(1.05) == 30.0 and max_correctable_tilt(2.4) == 80.0
    shorts = silhouette(kind="shorts")
    img, m, applied = upright(photo(shorts), shorts, deadband=0.0)
    assert abs(applied) <= max_correctable_tilt(tilt_angle(shorts)[1])


def test_upright_returns_the_mask_it_rotated_not_a_stale_one():
    base = silhouette(kind="jeans"); tilted = rotate(base, 10)
    img, m, applied = upright(photo(tilted), tilted)
    assert m.shape == img.shape[:2] and m.any()
    assert abs(tilt_angle(m)[0]) < 1.0, "the returned mask is still tilted"


def wide_shorts(H=700, W=1100):
    """A pair of shorts laid flat with the legs spread: WIDER THAN TALL, like 9 of the 16 photographs in EXP_0021.
    The long axis runs left-to-right, which is what broke the original tilt estimate."""
    m = np.zeros((H, W), np.uint8)
    cx, top = W // 2, int(0.12 * H)
    ww = int(0.66 * W); body = int(0.34 * H)
    cv2.rectangle(m, (cx - ww // 2, top), (cx + ww // 2, top + body), 255, -1)
    leg_w = int(ww * 0.46)
    for s in (-1, 1):
        x0 = cx + (0 if s < 0 else 0) - (leg_w if s < 0 else -int(ww * 0.04))
        cv2.rectangle(m, (max(x0, 0), top + body), (min(x0 + leg_w, W - 1), top + body + int(0.42 * H)), 255, -1)
    return m > 0


def test_a_garment_wider_than_tall_reports_its_real_tilt_not_ninety_degrees():
    """The estimate used to read the LONG axis unconditionally. On a flat-laid pair of shorts that axis is
    horizontal, so it returned ~±88° — outside the correctable range, so uprighting did nothing on exactly the
    garment this project is about (EXP_0023)."""
    m = wide_shorts()
    ys, xs = np.nonzero(m)
    assert (ys.max() - ys.min()) < (xs.max() - xs.min()), "the fixture stopped being wider than tall"
    ang, _ = tilt_angle(m)
    assert abs(ang) < 10, f"a barely-tilted wide garment reads as {ang:.1f}° from vertical"
    ang6, _ = tilt_angle(rotate(m, 6))
    assert abs(ang6 - (ang + 6)) < 2.0, f"a 6° tilt of a wide garment reads as {ang6:.1f}°, not {ang + 6:.1f}°"


@pytest.mark.parametrize("tilt", [-12, -8, -5, -3, 3, 5, 8, 12])
def test_wide_shorts_shape_ratios_survive_tilt_once_upright_runs(tilt):
    base = wide_shorts()
    _, base_up, _ = upright(photo(base), base)      # the reference goes through the pipeline too: this fixture has
    ref = ratios(base_up)                           # a -2.8 degree intrinsic tilt of its own
    tilted = rotate(base, tilt)
    _, corrected, _ = upright(photo(tilted), tilted)
    got = ratios(corrected)
    for k, v in ref.items():
        assert abs(got[k] - v) / abs(v) < 0.05, f"{k} moved {abs(got[k]-v)/abs(v):.1%} at {tilt}°"


def test_the_tilt_estimate_cannot_exceed_forty_five_degrees_by_construction():
    """Documented consequence of reading the near-vertical axis: at 45° the two axes swap roles, so a garment truly
    lying at 50° reads as -40°. Nothing in the silhouette can distinguish them."""
    m = wide_shorts()
    for d in (0, 10, 30, 44, 50, 70):
        ang, _ = tilt_angle(rotate(m, d))
        assert abs(ang) <= 45.001, f"{ang} at {d}°"


def test_the_waistband_estimator_is_deterministic():
    """RANSAC with an unseeded generator would give a different answer to the same photograph on every run, which is
    the opposite of what a repeatability fix is for."""
    from denimtwin.canon.upright import waistband_angle
    m = wide_shorts()
    a = [waistband_angle(m) for _ in range(4)]
    assert len({(None if x[0] is None else round(x[0], 9), round(x[1], 9)) for x in a}) == 1, a


def test_the_waistband_estimator_declines_rather_than_guessing():
    """It answers about 60% of the time on real masks and must return None — not a number — for the rest, so the
    caller can fall back rather than act on a line that explains nothing."""
    from denimtwin.canon.upright import waistband_angle
    noise = np.zeros((400, 400), bool)
    rng = np.random.default_rng(0)
    for x in range(60, 340):                       # a top edge that is not a line at all
        noise[rng.integers(50, 300):380, x] = True
    ang, frac = waistband_angle(noise)
    assert ang is None, f"fitted a waistband to noise: {ang:.1f}° at inlier fraction {frac:.2f}"


def test_the_hybrid_says_which_estimator_answered():
    from denimtwin.canon.upright import tilt_estimate
    for m in (silhouette(kind="jeans"), wide_shorts()):
        ang, elong, src = tilt_estimate(m)
        assert src in ("waistband", "principal_axis")
        assert abs(ang) <= 45.001 and elong >= 1.0


def test_uprighting_a_mask_twice_changes_nothing():
    """The invariant: a photograph that has already been corrected must be left alone. It holds for the mask path."""
    for kind in ("jeans", "shorts"):
        base = silhouette(kind=kind)
        for tilt in (-20, -7, 0, 4, 15):
            m = rotate(base, tilt)
            i1, m1, a1 = upright(photo(m), m)
            _, _, a2 = upright(i1, m1)
            assert abs(a2) < 0.5, f"{kind} at {tilt}°: second pass rotated another {a2:.2f}°"


def test_uprighting_is_idempotent_through_a_resegmentation():
    """The invariant that actually matters, and the one that broke: the pipeline does not carry a mask between runs,
    it segments the image again. EXP_0028 found run_pair rotating 2b0123d732 by -23.5° and predict, handed that same
    output, rotating it back by +24.3°. Here segmentation is a colour threshold, so the only thing that can change
    between passes is the geometry — which is exactly what this pins."""
    seg = lambda im: (np.abs(im.astype(int) - np.array([115, 72, 44])).sum(axis=2) < 60)
    base = silhouette(kind="jeans")
    for tilt in (-15, -6, 3, 11):
        img = photo(rotate(base, tilt))
        i1, _, a1 = upright(img, seg(img))
        _, _, a2 = upright(i1, seg(i1))
        assert abs(a2) < 1.0, f"tilt {tilt}°: first pass {a1:.2f}°, second pass {a2:.2f}° after re-segmenting"

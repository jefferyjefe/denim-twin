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

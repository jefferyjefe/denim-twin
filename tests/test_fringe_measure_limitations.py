"""KNOWN, ACCEPTED LIMITATIONS of `measure_fringe_depth` — recorded as strict xfails (adopted from review 5).

These tests state what the direct fringe-depth measurement does wrong. They are expected to FAIL: the behaviour is not
a bug we intend to fix, it is the reason fringe *depth* was withdrawn as evidence entirely (EXP_0015). Anything below
the garment mask that is lighter than, or differently coloured from, the deep part of the search band is scored as
thread — the fabric itself when the mask stops short, the lit gap before a displaced drop shadow, a patterned floor.
No thresholding fixes that: the measurement cannot distinguish "the mask sits k px inside the fabric" from "there are
k px of threads", because both are literally the same pixels.

They are `strict` so that if someone ever makes the measurement robust, this file fails and the project is forced to
revisit EXP_0015's conclusion and re-enable depth as evidence. Use `eval/hem_texture.hem_roughness` instead: it
measures the SHAPE of the boundary rather than its position, and it survives its negative control (EXP_0016).
"""
import pytest

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.eval.fringe_measure import measure_fringe_depth

W, H, EDGE, BACKDROP, FABRIC = 400, 300, 180, 170, (95, 55, 35)


def _bare(seed=0, backdrop=BACKDROP, fabric=FABRIC):
    """A denim block on a plain backdrop with NO fringe at all. Ground truth depth = 0 px."""
    rng = np.random.default_rng(seed)
    img = np.clip(np.full((H, W, 3), backdrop, np.int16) + rng.integers(-6, 6, (H, W, 3)), 0, 255).astype(np.uint8)
    mask = np.zeros((H, W), bool); mask[60:EDGE, 40:W - 40] = True
    img[mask] = fabric
    return img, mask


@pytest.mark.xfail(strict=True, reason='accepted limitation: see module docstring and EXP_0015')
def test_a_drop_shadow_that_does_not_touch_the_hem_is_counted_as_fringe():
    """fringe_measure.py:13-14 claims "The lightness condition is what separates threads from the garment's own
    drop shadow". It only does so when the shadow starts flush with the fabric edge (the one case
    tests/test_fringe_measure.py:30 covers). With an off-axis light the shadow is displaced, and the lit
    backdrop between the hem and the shadow is lighter than the background model (which is sampled from
    INSIDE the shadow, fringe_measure.py:43-44), so it is scored as thread.

    observed: shadow starting 4/8/12/16 px below the fabric edge -> median_px = 4/8/12/16, coverage 1.00,
              ok=True, on a garment with no fringe.
    expected: median_px ~ 0 in every case."""
    got = {}
    for offset in (4, 8, 12, 16):
        img, mask = _bare()
        band = img[EDGE + offset:EDGE + offset + 40, 40:W - 40]
        img[EDGE + offset:EDGE + offset + 40, 40:W - 40] = (band * 0.62).astype(np.uint8)
        r = measure_fringe_depth(img, mask, waist_px=320)
        got[offset] = (r["median_px"], round(r["coverage"], 2), r["ok"])
    assert all(v[0] <= 2 for v in got.values()), (
        f"a displaced drop shadow is measured as fringe on a garment that has none: {got}")


@pytest.mark.xfail(strict=True, reason='accepted limitation: see module docstring and EXP_0015')
def test_garment_mask_boundary_error_is_returned_as_fringe_depth():
    """EXP_0015/NOTE.md:37-38 diagnoses the floor as garment-mask boundary error but the function neither
    bounds it nor reports it. Eroding the mask by k rows (SAM stopping k px inside the true fabric edge)
    returns exactly k px of "fringe" with coverage 1.00 and ok=True — the caller cannot tell it apart from
    a real k-px fringe.

    observed: erosion 1/2/3/5/8 px -> median_px 1/2/3/5/8, coverage 1.00, ok True (no fringe present).
    expected: the result carries no signal from mask error, or flags it."""
    got = {}
    for k in (1, 2, 3, 5, 8):
        img, mask = _bare()
        m = mask.copy(); m[EDGE - k:EDGE, :] = False
        r = measure_fringe_depth(img, m, waist_px=320)
        got[k] = (r["median_px"], round(r["coverage"], 2), r["ok"])
    assert all(v[0] <= 2 for v in got.values()), (
        f"mask boundary error is read back as fringe depth, 1 px of error = 1 px of 'fringe': {got}")


@pytest.mark.xfail(strict=True, reason='accepted limitation: see module docstring and EXP_0015')
def test_a_light_garment_on_a_dark_backdrop_reads_its_own_fabric_as_fringe():
    """The lightness test `z_L > 0.8` means "lighter than the backdrop". A bleached/light garment on a dark
    surface satisfies it with its own fabric, so every pixel of mask error is a confident thread detection.

    observed: light fabric (200,205,210) on backdrop 60, mask eroded 3 px, no fringe ->
              median 3.0 px, mean 4.04, coverage 1.00, ok True.
    expected: ~0."""
    img, mask = _bare(backdrop=60, fabric=(200, 205, 210))
    m = mask.copy(); m[EDGE - 3:EDGE, :] = False
    r = measure_fringe_depth(img, m, waist_px=320)
    assert r["median_px"] <= 2, r


# FIXED, not a limitation: the one-pixel mask-sensitivity check catches this one, so it is a live regression test.
def test_a_busy_backdrop_produces_a_deep_fringe_where_there_is_none():
    """data/priors/exclude.txt already records a real photo of this kind ("jeans at ~45 deg on a patterned
    rug"). With a perfect garment mask and no fringe whatsoever, a mottled backdrop is scored as a fringe
    several times deeper than every real value in data/priors/fringe.json (2-8 px).

    observed: blurred-noise backdrop (sigma 3/6/10) -> median 18.5 / 12.0 / 20.0 px, ok=True.
    expected: median ~ 0 px, or ok=False."""
    got = {}
    for sigma, seed in ((3, 3), (6, 4), (10, 5)):
        rng = np.random.default_rng(seed)
        img, mask = _bare()
        n = cv2.GaussianBlur(rng.integers(0, 255, (H, W)).astype(np.float32), (0, 0), sigma)
        n = (n - n.min()) / max(np.ptp(n), 1e-6) * 170 + 45
        img = np.where((~mask)[..., None], np.repeat(n[..., None], 3, 2).astype(np.uint8), img)
        r = measure_fringe_depth(img, mask, waist_px=320)
        got[sigma] = (r["median_px"], r["ok"])
    assert all((not v[1]) or v[0] <= 3 for v in got.values()), (
        f"a patterned backdrop alone yields a deep 'fringe' on a garment that has none: {got}")


@pytest.mark.xfail(strict=True, reason='accepted limitation: gap-walk truncation at high resolution; see EXP_0015')
def test_depth_rel_is_not_scale_free_once_the_threads_are_resolved():
    """`max_gap` is a constant 3 PIXELS (fringe_measure.py:23). Photographing the same fringe at higher
    resolution scales the gaps between the threads past it, so the walk in fringe_measure.py:51-55 stops at
    the first gap and the measured depth COLLAPSES as resolution rises.

    This is the opposite of what EXP_0015/NOTE.md:57-59, the issue form and CONTRIBUTING_PAIRS.md now tell
    contributors ("send a close-up ... the only one where the thing we are trying to predict is actually
    resolvable"), and the opposite of the premise of tools/experiment_resolution.py.

    observed: a 20 px gapped fringe -> depth_rel 0.0625 at 1x, 0.0094 at 3x (6.7x smaller, 20 px -> 9 px
              where 60 px was the truth).
    expected: depth_rel equal to within a few thousandths, as tests/test_fringe_measure.py:47 asserts for a
              solid-block fringe."""
    a = measure_fringe_depth(*_gapped(20, scale=1), waist_px=320)
    b = measure_fringe_depth(*_gapped(20, scale=3), waist_px=960)
    assert abs(a["depth_rel"] - b["depth_rel"]) < 0.006, (
        f"depth_rel 1x={a['depth_rel']:.4f} ({a['median_px']:.0f}px) vs 3x={b['depth_rel']:.4f} "
        f"({b['median_px']:.0f}px, truth 60px): the fixed 3-px max_gap makes the measurement resolution-dependent")


def test_the_measurement_does_not_read_outside_the_image_when_the_mask_disagrees_in_shape():
    """fringe_measure.py:32 takes H, W from the MASK and fringe_measure.py:44/47 indexes the IMAGE with them.
    Two of the repo's own committed pairs already store an amask.png whose shape differs from after_used.png
    (experiments/pairs/660bef67bf: image (629,348) vs mask (193,600); experiments/pairs/85d48013a2:
    (370,267) vs (370,555)), so this is reachable from stored artefacts.

    observed: mask 20 px wider than the image -> IndexError deep inside the column loop.
    expected: an explicit shape check with a clear message (or a documented contract enforced by an assert)."""
    rng = np.random.default_rng(0)
    img = np.clip(np.full((300, 400, 3), 170, np.int16) + rng.integers(-6, 6, (300, 400, 3)), 0, 255).astype(np.uint8)
    mask = np.zeros((300, 420), bool); mask[60:180, 40:410] = True     # garment spans past the image width
    img[60:180, 40:400] = (95, 55, 35)
    try:
        r = measure_fringe_depth(img, mask, waist_px=320)
    except IndexError as e:
        raise AssertionError(f"a mask/image shape mismatch raises IndexError instead of being reported: {e}")
    assert "shape_mismatch" in r or r.get("ok") is False, r

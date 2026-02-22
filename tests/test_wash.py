"""Procedural wash v0 (plan §4.7/§4.8): shrink, hem roll, colour — and nothing else."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon.wash import apply_wash, PRESETS, WashParams

def _cut():
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    return img, mask, cut, removed, keep

def test_none_is_byte_identical():
    img, mask, cut, removed, keep = _cut()
    out, g, r, ch = apply_wash(cut, mask, removed, 1.0, PRESETS["none"])
    assert np.array_equal(out, cut) and np.array_equal(g, mask) and np.array_equal(r, removed) and not ch.any()

def test_shrinkage_is_anisotropic_and_matches_parameters():
    img, mask, cut, removed, keep = _cut()
    p = WashParams(shrink_along_frac=0.04, shrink_across_frac=0.01, hem_roll_mm=0, roll_strength=0, lightness_shift=0, chroma_scale=1)
    out, g, r, ch = apply_wash(cut, mask, removed, 1.0, p)
    k0, k1 = mask & ~removed, g & ~r
    ys0, xs0 = np.nonzero(k0); ys1, xs1 = np.nonzero(k1)
    h0, h1 = ys0.max() - ys0.min(), ys1.max() - ys1.min(); w0, w1 = xs0.max() - xs0.min(), xs1.max() - xs1.min()
    assert abs(h1 / h0 - 0.96) < 0.01, (h1, h0)
    assert abs(w1 / w0 - 0.99) < 0.01, (w1, w0)
    assert abs(k1.sum() / k0.sum() - 0.96 * 0.99) < 0.01

def test_changes_confined_to_old_and_new_garment_footprint():
    img, mask, cut, removed, keep = _cut()
    out, g, r, ch = apply_wash(cut, mask, removed, 1.0, PRESETS["aggressive"])
    outside = ch & ~mask & ~g
    assert outside.sum() == 0, outside.sum()

def test_colour_shift_is_lighter_and_less_saturated():
    img, mask, cut, removed, keep = _cut()
    p = WashParams(0, 0, 0, 0, lightness_shift=3.0, chroma_scale=0.9)
    out, g, r, ch = apply_wash(cut, mask, removed, 1.0, p)
    lab0 = cv2.cvtColor(cut.astype(np.float32) / 255, cv2.COLOR_BGR2LAB); lab1 = cv2.cvtColor(out.astype(np.float32) / 255, cv2.COLOR_BGR2LAB)
    k = mask & ~removed
    assert lab1[..., 0][k].mean() - lab0[..., 0][k].mean() > 2.0
    c0 = np.hypot(lab0[..., 1], lab0[..., 2])[k].mean(); c1 = np.hypot(lab1[..., 1], lab1[..., 2])[k].mean()
    assert c1 < c0
    assert not ch[~k].any()                    # colour touches only kept fabric

def test_hem_roll_is_a_thin_strip_at_the_cut_only():
    img, mask, cut, removed, keep = _cut()
    p = WashParams(0, 0, hem_roll_mm=6.0, roll_strength=0.4, lightness_shift=0, chroma_scale=1)
    out, g, r, ch = apply_wash(cut, mask, removed, 1.0, p)
    d = cv2.distanceTransform((~removed).astype(np.uint8), cv2.DIST_L2, 5)
    assert ch.any() and ch[d > 7].sum() == 0 and not ch[removed].any()
    # the strip's darkest row (nearest the cut) is darker than the untouched fabric
    ys = np.nonzero(ch)[0]; row_near = ys.max(); row_far = ys.min() - 20
    assert out[row_near][ch[row_near]].mean() < cut[row_far][keep[row_far]].mean()

def test_presets_are_ordered_intervals():
    c, m, a = PRESETS["conservative"], PRESETS["median"], PRESETS["aggressive"]
    for f in ("shrink_along_frac", "shrink_across_frac", "hem_roll_mm", "roll_strength", "lightness_shift"):
        assert getattr(c, f) <= getattr(m, f) <= getattr(a, f), f
    assert c.chroma_scale >= m.chroma_scale >= a.chroma_scale

def test_texture_backdrop_touches_only_the_removed_region_and_matches_background_statistics():
    from denimtwin.canon.cut2d import texture_backdrop_fill, backdrop_fill
    img, mask, cut, removed, keep = _cut()
    rng = np.random.default_rng(1)                                  # patterned backdrop, like a carpet
    bg = np.clip(180 + cv2.GaussianBlur(rng.normal(0, 60, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = np.where(mask[..., None], img, bg)
    flat = backdrop_fill(scene, mask, removed); tex = texture_backdrop_fill(scene, mask, removed, seed=0)
    assert np.array_equal(tex[~removed], scene[~removed])           # nothing outside the cut is touched
    bstd = float(bg[~mask].std())
    assert abs(tex[removed].std() - bstd) < abs(flat[removed].std() - bstd)   # texture, not a flat blob

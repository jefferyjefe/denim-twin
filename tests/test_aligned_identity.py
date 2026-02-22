"""§6.2: identity must be judged after alignment, so a legitimate shrink is not scored as identity loss (EXP_0013)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon.wash import apply_wash, WashParams, PRESETS
from denimtwin.eval import identity as I

def _textured():
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0); tex = rng.integers(-25, 25, img.shape, np.int16)
    tex = cv2.GaussianBlur(tex.astype(np.float32), (0, 0), 1.5) * 2.5          # denim-like texture, not per-pixel noise
    img = np.clip(img.astype(np.float32) + tex * mask[..., None], 0, 255).astype(np.uint8)
    cm = CanonicalMap(lm); cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    return img, mask, cut, removed, keep

def test_shrunk_garment_recovers_identity_after_alignment():
    img, mask, cut, removed, keep = _textured()
    p = WashParams(shrink_along_frac=0.02, shrink_across_frac=0.01, hem_roll_mm=0, roll_strength=0, lightness_shift=0, chroma_scale=1.0)
    out, g, r, ch = apply_wash(cut, mask, removed, 1.0, p)
    k2 = g & ~r
    naive = I.unchanged_ssim(out, cut, k2)
    al = I.aligned_identity(out, k2, cut, keep, ref_mask=mask)
    assert naive < 0.9, naive                                   # a 2%/1% shrink already costs the naive metric a lot
    assert al["ssim"] > 0.95 and al["dE"] < 2.0, al
    sy, sx = al["align"]["axis_scales"]                          # recovered scales invert the applied shrink
    assert abs(max(sy, sx) - 1 / 0.98) < 0.01 and abs(min(sy, sx) - 1 / 0.99) < 0.01, al["align"]

def test_alignment_cannot_rescue_destroyed_content():
    img, mask, cut, removed, keep = _textured()
    al = I.aligned_identity(cv2.GaussianBlur(cut, (0, 0), 6), keep, cut, keep, ref_mask=mask)
    assert al["ssim"] < 0.85 and al["feat_ret"] < 0.2, al

def test_pure_translation_is_fully_recovered():
    img, mask, cut, removed, keep = _textured()
    M = np.float32([[1, 0, 17], [0, 1, -11]]); H, W = cut.shape[:2]
    tr = cv2.warpAffine(cut, M, (W, H), borderMode=cv2.BORDER_REPLICATE); tk = cv2.warpAffine(keep.astype(np.uint8), M, (W, H), flags=cv2.INTER_NEAREST) > 0
    al = I.aligned_identity(tr, tk, cut, keep, ref_mask=mask)
    assert al["ssim"] > 0.99 and al["feat_ret"] > 0.95, al

def test_alignment_scale_is_bounded():
    img, mask, cut, removed, keep = _textured()
    small = cv2.resize(cut, None, fx=0.5, fy=0.5); sm = cv2.resize(keep.astype(np.uint8), None, fx=0.5, fy=0.5) > 0
    pad = np.full_like(cut, 180); pad[:small.shape[0], :small.shape[1]] = small
    pm = np.zeros_like(keep); pm[:sm.shape[0], :sm.shape[1]] = sm
    _, _, info = I.align_to_reference(pad, pm, cut, mask, ref_moment_mask=keep)
    assert all(abs(v - 1.0) <= 0.15 for v in info["axis_scales"]), info      # a 2x rescale is refused, not "aligned"

def test_wash_presets_are_ordered_under_aligned_identity():
    img, mask, cut, removed, keep = _textured()
    dEs = []
    for k in ("none", "conservative", "median", "aggressive"):
        out, g, r, _ = apply_wash(cut, mask, removed, 1.0, PRESETS[k]); al = I.aligned_identity(out, g & ~r, cut, keep, ref_mask=mask)
        dEs.append(al["dE"])
    assert dEs == sorted(dEs), dEs        # heavier wash = further from the before photo, even after alignment

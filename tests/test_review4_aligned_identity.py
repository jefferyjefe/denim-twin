"""Review 4 — what `eval/identity.aligned_identity` actually measures (EXP_0013 Part C).

Three separate holes, all in src/denimtwin/eval/identity.py:94-130:
  1. the "bound" is applied to the SINGULAR VALUES of the ECC affine (line 114-115). A rotation has
     singular values (1, 1), so rotation is not bounded at all — contradicting the docstring
     ("shear/rotation from ECC is rejected if it exceeds the bound", line 100-101) and EXP_0013
     ("alignment must not be able to drag arbitrary content into place").
  2. `info["axis_scales"]` means [x, y] on the moments path (line 108) but SVD singular values sorted
     descending on the ECC path (line 116), so the reported "recovered axis scales" carry no axis identity.
  3. the evaluation zone is `warped pred mask ∩ ref_keep` (line 128), so any kept fabric the prediction
     omits from its own mask is EXCLUDED from scoring instead of being penalised.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon.wash import apply_wash, WashParams
from denimtwin.eval import identity as I


def _textured():
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0); tex = rng.integers(-25, 25, img.shape, np.int16)
    tex = cv2.GaussianBlur(tex.astype(np.float32), (0, 0), 1.5) * 2.5
    img = np.clip(img.astype(np.float32) + tex * mask[..., None], 0, 255).astype(np.uint8)
    cm = CanonicalMap(lm); cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    return img, mask, cut, removed, keep


def test_alignment_does_not_rescue_a_rotated_garment():
    """identity.py:113-116 — the acceptance test is `all(abs(sv - 1) <= 0.15)` on the SVD of the ECC
    affine; a pure rotation has sv == (1, 1) and is always accepted.
    observed: a 15 deg rotation of the whole garment scores aligned SSIM 0.980 / feat_ret 0.688 and the
    returned info says scale=0.9998, axis_scales=[0.9999, 0.9997] — i.e. 'no scale change, aligned'.
    expected: a garment rotated 15 deg is not the same rendering; identity must not be handed back."""
    img, mask, cut, removed, keep = _textured()
    h, w = cut.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), 15.0, 1.0)
    rot = cv2.warpAffine(cut, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    rk = cv2.warpAffine(keep.astype(np.uint8), M, (w, h), flags=cv2.INTER_NEAREST) > 0
    al = I.aligned_identity(rot, rk, cut, keep, ref_mask=mask)
    assert al["ssim"] < 0.90, f"a 15 deg rotation was aligned away: {al}"


def test_axis_scales_identify_which_axis_shrank():
    """identity.py:116 — `axis_scales` on the ECC path are `np.linalg.svd(...)` singular values, which come
    back sorted descending, so they cannot say WHICH axis moved. EXP_0013 Part C quotes them as
    'recovered axis scales 1.0204 / 1.0102 (exactly 1/0.98 and 1/0.99)'.
    observed: a 5% shrink ALONG the leg (y only) reports axis_scales [1.0526, 0.9992] — identical to what a
    5% shrink ACROSS the leg (x only) reports. expected [x, y] = [1.0, 1.0526]."""
    img, mask, cut, removed, keep = _textured()
    p = WashParams(shrink_along_frac=0.05, shrink_across_frac=0.0, hem_roll_mm=0, roll_strength=0, lightness_shift=0, chroma_scale=1.0)
    out, g, r, _ = apply_wash(cut, mask, removed, 1.0, p)
    _, _, info = I.align_to_reference(out, g & ~r, cut, mask, ref_moment_mask=keep)
    sx, sy = info["axis_scales"]
    assert abs(sy - 1 / 0.95) < 0.01 and abs(sx - 1.0) < 0.01, \
        f"axis_scales do not identify the shrunk axis: got [x={sx:.4f}, y={sy:.4f}], expected [1.0000, {1/0.95:.4f}] ({info})"


def test_content_the_prediction_omits_is_penalised_not_excluded():
    """identity.py:127-130 — `zone = kw & ref_keep` where `kw` is the PREDICTION's own warped mask, so a
    system that destroys kept fabric and simply leaves it out of its mask is never scored on it.
    observed: destroying 20% of the kept region (painted solid red) scores aligned SSIM 0.968 — better than
    the strict pixel metric's 0.926 for the same prediction, and better than the honest wash model's 0.935
    mean on the 11 real pairs (EXP_0013 Part C). expected: <= the strict score."""
    img, mask, cut, removed, keep = _textured()
    ys = np.nonzero(keep)[0]; y0, hgt = ys.min(), ys.max() - ys.min()
    hole = np.zeros_like(keep); hole[int(y0 + 0.45 * hgt):int(y0 + 0.65 * hgt)] = True; hole &= keep
    pred = cut.copy(); pred[hole] = (0, 0, 255)
    naive = I.unchanged_ssim(pred, cut, keep)
    al = I.aligned_identity(pred, keep & ~hole, cut, keep, ref_mask=mask)
    assert al["ssim"] <= naive, \
        f"destroying {hole.sum()} kept px scored HIGHER after alignment: aligned {al['ssim']:.3f} > strict {naive:.3f}"

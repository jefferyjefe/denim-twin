import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon.register import warp_after_to_before, SURVIVING
from denimtwin.eval import geometry as G, identity as I

def test_registration_recovers_relaid_after_photo():
    # BEFORE: synthetic jeans. AFTER: the cut garment, then re-laid (rotated+shifted+slightly scaled) as a new photo.
    img, mask, lm = synthetic_jeans(jitter=3, seed=1); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    M = cv2.getRotationMatrix2D((300, 450), 7, 1.04); M[:, 2] += (25, -15)
    after = cv2.warpAffine(cut, M, (img.shape[1], img.shape[0]), borderValue=(180, 180, 180))
    amask = cv2.warpAffine(keep.astype(np.uint8), M, (img.shape[1], img.shape[0])) > 0
    lma = {n: tuple((M @ np.array([lm[n][0], lm[n][1], 1.0]))) for n in SURVIVING}
    real, rmask, resid = warp_after_to_before(after, amask, lma, lm, img.shape)
    assert resid < 1.0
    assert G.silhouette_iou(rmask, keep) > 0.97
    # the registered real photo should match the prediction (=cut) almost perfectly in the kept region
    assert I.unchanged_ssim(real, cut, keep & rmask) > 0.9

def test_heldout_residual_is_nonzero_but_small_for_affine_relay():
    from denimtwin.canon.register import heldout_residual
    img, mask, lm = synthetic_jeans(jitter=3, seed=2)
    M = cv2.getRotationMatrix2D((300, 450), 5, 1.02); M[:, 2] += (10, -8)
    names = SURVIVING; b = np.array([lm[n] for n in names], np.float32); a = np.array([(M @ np.array([*lm[n], 1.0])) for n in names], np.float32)
    r = heldout_residual(a, b)
    assert 0 < r < 3.0, r          # affine is recoverable by TPS from the other 9 points, but not exactly

def test_match_lighting_removes_global_shift():
    from denimtwin.eval import identity as I
    rng = np.random.default_rng(0); img = rng.integers(40, 200, (64, 64, 3), np.uint8); m = np.ones((64, 64), bool)
    darker = np.clip(img.astype(int) * 0.7 - 10, 0, 255).astype(np.uint8)
    assert I.unchanged_color_delta_e(darker, img, m) > 8
    assert I.unchanged_color_delta_e(I.match_lighting(darker, img, m), img, m) < 3

def test_feature_registration_adds_correspondences_on_textured_garment():
    from denimtwin.canon.register_feat import warp_after_to_before_feat
    rng = np.random.default_rng(3)
    img, mask, lm = synthetic_jeans(jitter=2, seed=3)
    tex = rng.integers(0, 60, img.shape, np.uint8); img = np.where(mask[..., None], np.clip(img.astype(int) + tex - 30, 0, 255).astype(np.uint8), img)  # denim-like texture
    cm = CanonicalMap(lm); cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    M = cv2.getRotationMatrix2D((300, 450), 4, 1.03); M[:, 2] += (15, -10)
    after = cv2.warpAffine(cut, M, (img.shape[1], img.shape[0]), borderValue=(180, 180, 180))
    amask = cv2.warpAffine(keep.astype(np.uint8), M, (img.shape[1], img.shape[0])) > 0
    lma = {n: tuple(M @ np.array([*lm[n], 1.0])) for n in SURVIVING[:6]}          # only 6 landmarks, like real shorts
    lmb6 = {n: lm[n] for n in SURVIVING[:6]}
    _, _, r0 = warp_after_to_before(after, amask, lma, lmb6, img.shape)
    real, rmask, r1, nfeat = warp_after_to_before_feat(after, amask, lma, lmb6, img, mask)
    assert nfeat >= 10 and r1 < 3.0, (nfeat, r0, r1)     # affine re-lay: both should be small; features must not break it
    assert G.silhouette_iou(rmask, keep) > 0.95

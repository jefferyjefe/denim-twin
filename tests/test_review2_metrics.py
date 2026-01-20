"""Review 2: metrics in compare.py / null_baselines.py that a trivial system aces or that ignore their region."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon import rawedge_v1
from denimtwin.eval import geometry as G, identity as I

def _setup():
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    return img, mask, cut, removed, keep

def test_fringe_iou_is_aced_by_an_opaque_block():
    # compare.py:57 -- fringe_iou = IoU of (pred silhouette below the cut) vs (real silhouette below the cut). The
    # predicted silhouette is keep | changed (run_pair.py:75), i.e. every fringe-zone pixel with coverage > 0.02.
    # A solid rectangle down to the fitted depth scores 1.0; the actual fringe render scores less. Depth is fitted
    # from the real image (run_pair.py:70), so the metric measures nothing about fringe appearance.
    img, mask, cut, removed, keep = _setup()
    d_out = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 5)
    real = keep | (removed & (d_out <= 20))                          # real garment with a 20 px dense fringe
    fiou = lambda sil: G.silhouette_iou(sil & ~keep & mask, real & ~keep & mask)
    im, ch = rawedge_v1.render_fringe(cut, removed, mask, 1.0, rawedge_v1.FringeParams(fringe_depth_mm=20, depth_jitter_mm=0))
    bg = np.median(cut[~mask], axis=0)
    block_img = cut.copy(); block_img[removed & (d_out <= 20)] = (60, 40, 30)
    real_img = cut.copy(); rf = removed & (d_out <= 20); rng = np.random.default_rng(0)
    real_img[rf] = np.where(rng.random((rf.sum(), 1)) < 0.6, (215, 222, 228), bg).astype(np.uint8)   # 60% thread coverage
    # appearance-based profile distance: the render (coverage-matched) must beat the opaque block
    d_render = G.fringe_profile_distance(im, real_img, keep, mask, removed, bg)
    d_block = G.fringe_profile_distance(block_img, real_img, keep, mask, removed, bg)
    assert d_render < d_block, (d_render, d_block)

def test_hem_chamfer_is_dominated_by_the_rest_of_the_silhouette():
    # compare.py:45 -- 'hem_chamfer' is the chamfer of the WHOLE silhouette boundary; a 40 px hem error is averaged
    # away over waist/outseams (EXP_0005: pred 10 px == crop-only 10 px). Restricted to the hem it is ~40 px.
    img, mask, cut, removed, keep = _setup()
    wrong = keep.copy(); wrong[np.nonzero(keep)[0].max() - 40:] = False   # hem 40 px too high, everything else exact
    assert G.hem_chamfer(wrong, keep, keep, mask) > 20.0                        # hem-restricted chamfer sees the 40 px error

def test_null_baseline_ssim_vs_real_cut_measures_background_not_cut():
    # null_baselines.py:26 -- ssim_vs_real_cut is evaluated over ~keep, which is mostly background (identical in
    # pred and real by construction). Replacing the ENTIRE cut region by white barely moves it.
    img, mask, cut, removed, keep = _setup()
    bad = cut.copy(); bad[removed] = 255
    assert I.cut_region_similarity(bad, cut, keep, removed, removed) < 0.5           # cut-region SSIM sees the change

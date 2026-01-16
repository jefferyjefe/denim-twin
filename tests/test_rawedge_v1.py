import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon.rawedge_v1 import render_three, render_fringe, FringeParams
from denimtwin.eval import identity as I

def _setup():
    img, mask, lm = synthetic_jeans(jitter=4); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35)); return mask, cut, removed, keep

def test_fringe_confined_to_zone_and_ordered():
    mask, cut, removed, keep = _setup(); mmpp = 0.35
    res = render_three(cut, removed, mask, mmpp)
    d_in = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3); far = keep & (d_in > 4 / mmpp)
    d_out = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 3)
    for k, (im, ch) in res.items():
        assert I.changed_pixel_fraction_outside(im, cut, far) == 0.0, k
        assert not (ch & removed & (d_out > 50 / mmpp)).any(), k        # nothing deeper than max depth + jitter
    ext = {k: int(v[1].sum()) for k, v in res.items()}
    assert ext["conservative"] < ext["median"] < ext["aggressive"], ext

def test_depth_parameter_controls_extent():
    mask, cut, removed, keep = _setup()
    a = (render_fringe(cut, removed, mask, 0.35, FringeParams(fringe_depth_mm=5, depth_jitter_mm=0))[1] & removed).sum()
    b = (render_fringe(cut, removed, mask, 0.35, FringeParams(fringe_depth_mm=25, depth_jitter_mm=0))[1] & removed).sum()
    assert b > 2.5 * a, (a, b)   # fringe-zone pixels only (excludes the constant abraded band)

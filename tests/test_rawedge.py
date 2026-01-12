import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon.rawedge import render_three, PRESETS
from denimtwin.eval import identity as I

def _setup():
    img, mask, lm = synthetic_jeans(jitter=4); cm = CanonicalMap(lm)
    out, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    return img, mask, out, removed, keep

def test_raw_edge_only_touches_edge_band_and_removed_region():
    img, mask, cut, removed, keep = _setup()
    res = render_three(cut, removed, mask, mm_per_px=0.35)
    for name, (im, changed) in res.items():
        far = keep.copy(); far[:] = False
        # pixels more than 8 mm inside the kept garment must be byte-identical
        import cv2
        d = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3)
        far = keep & (d > 8 / 0.35)   # beyond band + jag of the most aggressive preset
        assert I.changed_pixel_fraction_outside(im, cut, far) == 0.0, name
        assert (changed & far).sum() == 0, name
        assert changed.sum() > 0, name

def test_presets_are_ordered_by_extent():
    img, mask, cut, removed, keep = _setup()
    res = render_three(cut, removed, mask, mm_per_px=0.35)
    ext = {k: int(v[1].sum()) for k, v in res.items()}
    assert ext["conservative"] < ext["median"] < ext["aggressive"], ext

def test_deterministic_given_seed():
    img, mask, cut, removed, keep = _setup()
    a = render_three(cut, removed, mask, 0.35, seed=3)["median"][0]; b = render_three(cut, removed, mask, 0.35, seed=3)["median"][0]
    assert np.array_equal(a, b)

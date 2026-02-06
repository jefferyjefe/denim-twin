import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut, backdrop_fill

def test_backdrop_fill_uses_background_not_fabric():
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    bg = img[~mask].mean(axis=0); fabric = img[mask].mean(axis=0)
    filled = cut[removed].mean(axis=0)
    assert np.linalg.norm(filled - bg) < np.linalg.norm(filled - fabric)      # closer to backdrop than to denim
    assert np.array_equal(cut[~removed], img[~removed])                         # nothing else touched

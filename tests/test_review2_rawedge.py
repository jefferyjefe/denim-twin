"""Review 2: raw-edge renderers write outside the cut zone. Expected to FAIL."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.canon import rawedge_v1, rawedge

def _setup():
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    cut_y = np.nonzero(removed)[0].min()
    far = keep.copy(); far[cut_y - 60:] = False        # kept fabric >60px above the cut: waistband, hips, outseams
    return cut, removed, mask, far

def test_v1_abraded_band_only_near_the_cut_edge():
    # rawedge_v1.py:57-58 -- d_in = distance to ANY non-kept pixel, so the 'abraded strip' is painted along the
    # entire garment outline (waistband, outseams), not just the cut edge. Docstring: modifies only removed-zone + edge band.
    cut, removed, mask, far = _setup()
    out, ch = rawedge_v1.render_fringe(cut, removed, mask, 1.0)
    assert not (ch & far).any(), int((ch & far).sum())            # observed: hundreds of px at the waist row alone
    assert np.array_equal(out[far], cut[far])

def test_v0_abraded_band_only_near_the_cut_edge():
    # rawedge.py:57-59 -- same defect in v0.
    cut, removed, mask, far = _setup()
    out, ch = rawedge.render_raw_edge(cut, removed, mask, 1.0)
    assert not (ch & far).any(), int((ch & far).sum())

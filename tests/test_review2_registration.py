"""Review 2 (2026-08-29): registration + auto-landmark interaction. Each test demonstrates a bug (expected to FAIL)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from test_canon import synthetic_jeans
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon.register import warp_after_to_before, SURVIVING
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.eval import geometry as G

def _pair():
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    cut, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    return img, mask, cut, keep

def test_auto_knees_on_cut_garment_are_not_knees_and_wreck_registration():
    # autolm.py:56-59 emits knee_* at 47% of crotch->hem of WHATEVER leg remains; on the after (shorts) photo that
    # is mid-thigh. run_pair.py:61 feeds all shared SURVIVING landmarks (incl. these) to the TPS, so the shorts
    # are stretched down to the jeans' knees. After photo == before photo here (no re-lay), so ideal IoU is 1.
    img, mask, cut, keep = _pair()
    lmb, _ = landmarks_from_mask(mask); lma, _ = landmarks_from_mask(keep)
    use = [n for n in SURVIVING if n in lma and n in lmb]
    assert not any("knee" in n for n in use)                    # fixed: autolm emits no knees on a cut garment
    _, rmask, resid = warp_after_to_before(cut, keep, lma, lmb, img.shape, use=use)
    true_hem = np.nonzero(keep)[0].max(); got_hem = np.nonzero(rmask)[0].max()
    assert abs(got_hem - true_hem) < 15, (got_hem, true_hem)     # observed: 842 vs 480
    assert G.silhouette_iou(rmask, keep) > 0.9                   # observed: 0.52

def test_uint8_255_after_mask_is_not_silently_emptied():
    # register.py:33 -- after_mask.astype(np.uint8) * 255 wraps 255*255 -> 1 for a 0/255 uint8 mask; result is empty.
    img, mask, cut, keep = _pair(); lmb, _ = landmarks_from_mask(mask)
    _, m_bool, _ = warp_after_to_before(cut, keep, lmb, lmb, img.shape)
    _, m_u8, _ = warp_after_to_before(cut, keep.astype(np.uint8) * 255, lmb, lmb, img.shape)
    assert m_u8.sum() == m_bool.sum() and m_u8.sum() > 0          # observed: 0

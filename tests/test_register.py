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

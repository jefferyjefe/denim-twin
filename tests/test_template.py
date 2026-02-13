import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from test_canon import synthetic_jeans
from denimtwin.canon import template as T
def test_template_fits_synthetic_silhouette():
    img, mask, lm = synthetic_jeans(jitter=0)
    params, iou, p = T.fit(mask, iters=300)
    assert iou > 0.85, iou
    auto = T.landmarks_from_params(p)
    for k in ("crotch", "waist_left", "hem_right_outer"):
        err = np.hypot(auto[k][0] - lm[k][0], auto[k][1] - lm[k][1]); assert err < 0.06 * mask.shape[1], (k, err)

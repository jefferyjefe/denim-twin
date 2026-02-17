import sys, os; sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from test_canon import synthetic_jeans
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon import template_v1 as T
def test_v1_refines_heuristic_landmarks_on_synthetic():
    img, mask, lm = synthetic_jeans(jitter=0)
    auto, _ = landmarks_from_mask(mask); fitted, resid, v = T.fit(mask, auto)
    err = lambda d: np.mean([np.hypot(d[k][0] - lm[k][0], d[k][1] - lm[k][1]) for k in T.OUTLINE])
    assert resid < 3.0 and err(fitted) <= err(auto) + 1.0, (resid, err(auto), err(fitted))

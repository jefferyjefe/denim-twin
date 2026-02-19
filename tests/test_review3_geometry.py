"""Review 3: eval/geometry.py hem metrics."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np
from denimtwin.eval import geometry as G

def test_hem_chamfer_is_diluted_by_non_hem_columns():
    # geometry.py:74-82 -- hem_chamfer averages |lowest pred px - lowest real px| over EVERY column where both masks
    # exist, ignoring keep/garment_before/band_px. Columns under the waist/hip (no hem there) contribute 0, so the
    # docstring's "a 40 px hem error reads as ~40" is false: on a T-shaped garment it reads 10.7.
    H, W = 400, 400; real = np.zeros((H, W), bool)
    real[50:150, 50:350] = True; real[150:300, 100:140] = True; real[150:300, 260:300] = True
    pred = real.copy(); pred[260:300, 100:140] = False; pred[260:300, 260:300] = False        # both hems 40 px too high
    e = G.hem_chamfer(pred, real, keep=pred, garment_before=real)
    assert e > 30, e

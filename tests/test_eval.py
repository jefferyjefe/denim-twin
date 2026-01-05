import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.eval import geometry as G, identity as I, fray as F, uncertainty as U

def test_geometry_basic():
    line = np.array([[0, 100], [200, 100]]); real = np.array([[50, 103], [150, 97]])
    assert abs(G.cut_line_error(line, real) - 3.0) < 1e-6
    assert abs(G.cut_line_error(line, real, mm_per_px=0.5) - 1.5) < 1e-6
    m = np.zeros((10, 10), bool); m[:5] = True
    n = np.zeros((10, 10), bool); n[:4] = True
    assert abs(G.silhouette_iou(m, n) - 0.8) < 1e-9
    assert G.boundary_chamfer(line, line) == 0.0
    assert G.landmark_displacement({"a": (0, 0)}, {"a": (3, 4)})["a"] == 5.0
    assert G.mask_boundary(m).shape[1] == 2

def test_identity_untouched_is_perfect():
    rng = np.random.default_rng(0)
    img = rng.integers(0, 255, (64, 64, 3), np.uint8)
    keep = np.ones((64, 64), bool); keep[40:] = False
    pred = img.copy(); pred[40:] = 0                      # only touched the cut region
    assert I.unchanged_ssim(pred, img, keep) > 0.999
    assert I.unchanged_color_delta_e(pred, img, keep) == 0.0
    assert I.changed_pixel_fraction_outside(pred, img, keep) == 0.0
    assert I.diff_map(pred, img)[40:].all() and not I.diff_map(pred, img)[:40].any()
    bad = pred.copy(); bad[:40] = cv2.GaussianBlur(bad[:40], (0, 0), 3)
    assert I.unchanged_ssim(bad, img, keep) < I.unchanged_ssim(pred, img, keep)

def test_fray_and_uncertainty():
    s = F.fray_depth_stats([1, 2, 3, 4]); assert s["mean"] == 2.5 and s["max"] == 4
    assert F.fray_depth_profile_error([1, 2], [2, 2]) == 0.5
    assert F.visible_fray_fraction([0.2, 1.5, 3.0]) == 2 / 3
    assert F.thread_length_distribution_distance([1, 2, 3], [1, 2, 3]) == 0.0
    assert U.interval_coverage([0, 0, 0], [1, 1, 1], [0.5, 2, 0.1]) == 2 / 3
    assert U.calibration_error([0], [1], [0.5], 0.8) - 0.2 < 1e-9
    assert U.confidence_error_correlation([0.9, 0.5, 0.1], [0.1, 0.5, 0.9]) == -1.0

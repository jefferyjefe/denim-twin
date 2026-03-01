"""Direct fringe measurement (eval/fringe_measure.py): synthetic garments with a KNOWN fringe depth."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.eval.fringe_measure import measure_fringe_depth

def _scene(depth=14, W=400, H=300, edge=180, backdrop=170, shadow=True, thread=(215, 222, 228), seed=0):
    """Denim block ending at row `edge`, ecru threads hanging `depth` px below it, on a mid-grey backdrop,
    with (optionally) a drop shadow under the garment — the false positive this detector must survive."""
    rng = np.random.default_rng(seed)
    img = np.full((H, W, 3), backdrop, np.uint8)
    img += rng.integers(-6, 6, img.shape, dtype=np.int16).astype(np.uint8) // 1
    img = np.clip(img, 0, 255).astype(np.uint8)
    if shadow:
        img[edge:edge + int(depth * 1.8), 40:W - 40] = (img[edge:edge + int(depth * 1.8), 40:W - 40] * 0.72).astype(np.uint8)
    mask = np.zeros((H, W), bool); mask[60:edge, 40:W - 40] = True
    img[mask] = (95, 55, 35)
    for x in range(40, W - 40):
        if rng.random() < 0.12: continue                     # gaps between thread bundles
        d = max(int(depth + rng.normal(0, 1.5)), 1)
        img[edge:edge + d, x] = np.clip(np.array(thread) + rng.normal(0, 5, 3), 0, 255).astype(np.uint8)
    return img, mask

def test_recovers_a_known_fringe_depth():
    for depth in (6, 14, 25):
        img, mask = _scene(depth=depth)
        r = measure_fringe_depth(img, mask, waist_px=320)
        assert r["ok"] and abs(r["median_px"] - depth) <= 2, (depth, r)

def test_a_drop_shadow_is_not_counted_as_fringe():
    img, mask = _scene(depth=0, shadow=True)
    img[180:212, 40:360] = (img[180:212, 40:360] * 0.72).astype(np.uint8)     # shadow only, no threads
    r = measure_fringe_depth(img, mask, waist_px=320)
    assert r["median_px"] <= 2, r

def test_a_clean_hem_measures_about_zero():
    img, mask = _scene(depth=1, shadow=False, thread=(95, 55, 35))            # fabric-coloured, i.e. no visible fringe
    r = measure_fringe_depth(img, mask, waist_px=320)
    assert r["median_px"] <= 3, r

def test_relative_depth_is_scale_free():
    img, mask = _scene(depth=14)
    big = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    bm = cv2.resize(mask.astype(np.uint8), None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST) > 0
    a = measure_fringe_depth(img, mask, waist_px=320)["depth_rel"]
    b = measure_fringe_depth(big, bm, waist_px=640)["depth_rel"]
    assert abs(a - b) < 0.006, (a, b)

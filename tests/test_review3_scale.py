"""Review 3: scale detectors on adversarial inputs with NO reference object present."""
import os, sys, json, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def test_scale_from_coin_reports_a_jeans_button_as_a_quarter(tmp_path):
    # scale_from_coin.py:17-33 -- with no --mask (how run_pairs_batch.py calls it) a bright round button ON the garment
    # is accepted as the coin with confidence 0.375 > the 0.3 the batch runner requires, giving mm_per_px 1.73 for an
    # image with no coin at all. There is no absolute-size / no-coin rejection.
    img, mask, lm = synthetic_jeans(jitter=0); rng = np.random.default_rng(0)
    img = np.clip(img.astype(int) + rng.integers(-10, 10, img.shape), 0, 255).astype(np.uint8)
    cx, cy = int(lm["waist_center"][0]), int(lm["waist_center"][1]) + 30
    cv2.circle(img, (cx, cy), 9, (200, 200, 210), -1); cv2.circle(img, (cx - 100, cy + 40), 7, (190, 190, 200), -1)
    f = str(tmp_path / "nocoin.png"); cv2.imwrite(f, img)
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools/scale_from_coin.py"), f, "--coin", "us_quarter"], capture_output=True, text=True)
    d = json.loads(p.stdout)
    assert p.returncode != 0 or d.get("confidence", 0) <= 0.3, d

def test_scale_from_grid_is_confident_on_pure_noise(tmp_path):
    # scale_from_grid.py:26-34 -- 'confidence' is an unbounded autocorrelation SNR; pure noise (no grid) yields
    # confidence ~2 and a definite mm_per_px, with no rejection path. A real 40 px grid scores ~14; nothing documents
    # or enforces a threshold, so the JSON is indistinguishable from a detection to a caller.
    rng = np.random.default_rng(0); f = str(tmp_path / "noise.png"); cv2.imwrite(f, rng.integers(150, 200, (600, 800, 3)).astype(np.uint8))
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools/scale_from_grid.py"), f], capture_output=True, text=True); d = json.loads(p.stdout)
    assert d["mm_per_px"] is None or d["confidence"] < 1.0, d

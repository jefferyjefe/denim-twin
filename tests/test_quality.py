import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.capture.quality import check_image

def _write(tmp_path, name, img):
    p = str(tmp_path / name); cv2.imwrite(p, img); return p

def test_white_cutout_passes_and_is_flagged(tmp_path):
    img = np.full((800, 600, 3), 255, np.uint8)
    cv2.rectangle(img, (150, 100), (450, 700), (110, 70, 40), -1)   # denim-ish garment
    rng = np.random.default_rng(0); img[100:700, 150:450] += rng.integers(0, 20, (600, 300, 3), np.uint8)
    r = check_image(_write(tmp_path, "cutout.png", img))
    assert r.cutout_background and r.ok, r.reasons

def test_garment_touching_edge_fails(tmp_path):
    img = np.full((800, 600, 3), 200, np.uint8)
    cv2.rectangle(img, (150, 0), (450, 800), (110, 70, 40), -1)     # runs off top and bottom
    rng = np.random.default_rng(1); img += rng.integers(0, 10, img.shape, np.uint8)
    r = check_image(_write(tmp_path, "edge.png", img))
    assert not r.ok and any("frame edge" in x for x in r.reasons)

def test_overexposed_garment_fails(tmp_path):
    img = np.full((800, 600, 3), 120, np.uint8)
    cv2.rectangle(img, (150, 100), (450, 700), (254, 254, 254), -1)  # blown-out garment
    rng = np.random.default_rng(2); img[:, :, :] = np.clip(img.astype(int) + rng.integers(-3, 3, img.shape), 0, 255)
    r = check_image(_write(tmp_path, "blown.png", img))
    assert not r.ok and any("clipping" in x or "exposure" in x for x in r.reasons)

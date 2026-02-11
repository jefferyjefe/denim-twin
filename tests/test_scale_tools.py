import subprocess, sys, os, json, numpy as np, cv2
ROOT = os.path.join(os.path.dirname(__file__), "..")
def test_coin_scale_on_synthetic(tmp_path):
    rng = np.random.default_rng(0); img = np.full((900, 700, 3), 190, np.uint8); img = np.clip(img + rng.normal(0, 4, img.shape), 0, 255).astype(np.uint8)
    cv2.rectangle(img, (200, 100), (500, 800), (110, 70, 40), -1)                    # garment
    cv2.circle(img, (110, 760), 21, (150, 140, 120), -1); cv2.circle(img, (110, 760), 21, (90, 80, 60), 2)   # a 42 px coin on the backdrop
    p = tmp_path / "c.png"; cv2.imwrite(str(p), img)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/scale_from_coin.py"), str(p), "--coin", "us_quarter"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads(r.stdout); assert abs(d["diameter_px"] - 42) <= 4 and abs(d["mm_per_px"] - 24.26 / 42) < 0.06
def test_grid_scale_on_synthetic(tmp_path):
    img = np.full((800, 800, 3), 235, np.uint8)
    for v in range(0, 800, 30): cv2.line(img, (v, 0), (v, 800), (200, 200, 200), 1); cv2.line(img, (0, v), (800, v), (200, 200, 200), 1)
    cv2.rectangle(img, (250, 100), (550, 700), (110, 70, 40), -1); m = np.zeros((800, 800), np.uint8); m[100:700, 250:550] = 255
    cv2.imwrite(str(tmp_path / "g.png"), img); cv2.imwrite(str(tmp_path / "m.png"), m)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/scale_from_grid.py"), str(tmp_path / "g.png"), "--mask", str(tmp_path / "m.png")], capture_output=True, text=True)
    d = json.loads(r.stdout); assert abs(d["px_per_cell"] - 30) <= 1.5, d
def test_coin_key_mapping():
    sys.path.insert(0, os.path.join(ROOT, "src")); from denimtwin.util.coins import coin_key
    assert [coin_key(x) for x in ("US quarter", "a penny", "2 euro coin", "£1", "canadian quarter", "no idea")] == ["us_quarter", "us_penny", "eur_2", "gbp_1", "cad_quarter", None]

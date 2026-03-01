"""Review 4 — tools/predict.py states a millimetre quantity in a run that has no metric scale.

tools/predict.py:88 sets `mmpp_eff = mmpp or 1.0`, so with no coin / no --mm-per-px the wash model's
`hem_roll_mm` is divided by 1.0 and rendered as a strip of `hem_roll_mm` PIXELS
(canon/wash.py:67 `D = max(p.hem_roll_mm / mm_per_px, 1.0)`).
tools/predict.py:121 nevertheless writes the flag "... hem roll 5 mm ...", and NOTE.md line 170 in the
same run says "scale: **unknown** — every length below is in pixels".
On a phone photo at ~0.13 mm/px a 5 mm roll is ~38 px, so the rendered strip is off by ~8x while the
report calls it 5 mm.
"""
import sys, os, json, subprocess, tempfile
import pytest
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(ROOT, "models", "sam_vit_b_01ec64.pth")) or __import__("importlib").util.find_spec("torch") is None,
    reason="needs the SAM checkpoint and torch")


def test_no_millimetre_claim_without_metric_scale():
    """observed flag with no scale: "wash 'median': shrink 2.0% along / 1.0% across, hem roll 5 mm —
    PRIOR values, not measured (EXP_0013)", in a run whose prediction.json says
    scale.mm_per_px is null / "UNKNOWN — all lengths are pixels"."""
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0)
    bg = np.clip(200 + cv2.GaussianBlur(rng.normal(0, 40, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = cv2.copyMakeBorder(np.where(mask[..., None], img, bg), 60, 60, 60, 60, cv2.BORDER_REPLICATE)
    with tempfile.TemporaryDirectory() as tmp:
        cv2.imwrite(f"{tmp}/jeans.png", scene)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "predict.py"), "--image", f"{tmp}/jeans.png",
                            "--out", f"{tmp}/out", "--inseam-fraction", "0.35", "--wash", "median"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        pred = json.load(open(f"{tmp}/out/prediction.json"))
        assert pred["scale"]["mm_per_px"] is None and "UNKNOWN" in pred["scale"]["source"]
        wash_flags = [f for f in pred["flags"] if f.startswith("wash ")]
        assert wash_flags, pred["flags"]
        assert "mm" not in wash_flags[0], \
            f"millimetre claim in a run with no metric scale (the strip was rendered {5} px wide): {wash_flags[0]!r}"

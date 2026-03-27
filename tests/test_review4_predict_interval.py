"""Review 4 — tools/predict.py reports a fringe interval that is not the one it rendered.

tools/predict.py:136-140:
    half = 1.28 * sd_rel * ww
    lo_px, hi_px = max(0.0, depth_px - half), depth_px + half
    res = render_three(..., depth_override={"conservative": max(lo_px, depth_px * 0.5) * mmpp_eff,
                                            "median": depth_mm,
                                            "aggressive": max(hi_px, depth_px * 1.5) * mmpp_eff})
The two `max(...)` floors mean the images can be rendered at a depth the report never mentions, yet
prediction.json (line 159) publishes `lo`/`hi`, panel.jpg labels the tiles "conservative (lo)" /
"aggressive (hi)" (line 152), and NOTE.md prints "80% interval lo-hi" (line 171).
"""
import sys, os, json, subprocess, tempfile
import pytest
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans

pytestmark = pytest.mark.needs("sam_checkpoint", "torch")


def test_rendered_aggressive_fringe_matches_the_published_upper_bound():
    """observed on the synthetic photo: prediction.json says median 12.79 px, hi 15.51 px (ratio 1.213),
    but the aggressive tile was rendered at max(15.51, 1.5*12.79) = 19.18 px. The predicted-fringe area
    (which is proportional to the rendered depth: 1.49 measured for a 1.50 override, 1.15 for a 1.21
    override) comes out at ratio 1.49 instead of 1.21."""
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0)
    bg = np.clip(200 + cv2.GaussianBlur(rng.normal(0, 40, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = cv2.copyMakeBorder(np.where(mask[..., None], img, bg), 60, 60, 60, 60, cv2.BORDER_REPLICATE)
    with tempfile.TemporaryDirectory() as tmp:
        cv2.imwrite(f"{tmp}/jeans.png", scene)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "predict.py"), "--image", f"{tmp}/jeans.png",
                            "--out", f"{tmp}/out", "--inseam-fraction", "0.35"], capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        pred = json.load(open(f"{tmp}/out/prediction.json")); f = pred["fringe_depth"]
        rm = cv2.imread(f"{tmp}/out/removed_mask.png", 0) > 127
        area = {}
        for k in ("median", "aggressive"):
            m = cv2.imread(f"{tmp}/out/pred_{k}_mask.png", 0) > 127
            area[k] = float((m & rm).sum())
        rendered_ratio = area["aggressive"] / area["median"]
        published_ratio = f["hi"] / f["median"]
        if f.get("below_render_resolution"):
            # sub-pixel fringe: the renders cannot represent the interval, so predict.py must say so rather than
            # publishing three pictures that differ by less than a pixel of fringe (EXP_0015)
            assert any("below the renderer's resolution" in x for x in pred["flags"]), pred["flags"]
            return
        assert abs(rendered_ratio - published_ratio) < 0.15, (
            f"the aggressive render does not correspond to the published hi: rendered fringe-area ratio "
            f"{rendered_ratio:.3f} vs published hi/median {published_ratio:.3f} "
            f"(median {f['median']:.2f} {f['unit']}, hi {f['hi']:.2f} {f['unit']})")

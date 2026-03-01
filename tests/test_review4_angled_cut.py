"""Review 4 — `--angle-deg` in tools/predict.py is silently discarded.

`cut2d.apply_cut` (src/denimtwin/canon/cut2d.py:18-28) reduces ANY canonical removal mask to a single
scalar `canon_y = rows.min()` and then removes every garment pixel whose canonical y is >= that scalar.
An angled removal mask therefore collapses to a FLAT canonical cut at the topmost point of the angle.
tools/predict.py:107 is the only caller that ever passes an angled mask, so `--angle-deg` moves the cut
UP but never tilts it, while prediction.json / NOTE.md / README report an angled ("a-line") cut.
"""
import sys, os, json, subprocess, tempfile
import pytest
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import apply_cut, cut_mask_canon_angled


def test_apply_cut_preserves_the_cut_angle():
    """cut2d.py:20-28 — an angled canonical mask and the flat mask starting at its topmost row differ by
    12.5% of the canonical raster, yet apply_cut turns both into the SAME image-space removal mask.
    observed: 0 differing pixels; expected: a genuinely angled cut."""
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    ang = cut_mask_canon_angled((cm.W, cm.H), inner_frac=0.45, outer_frac=0.20)
    ytop = int(np.nonzero(ang.any(axis=1))[0].min())
    flat = np.zeros_like(ang); flat[ytop:] = True
    assert (ang != flat).mean() > 0.05, "the two canonical masks must differ for this test to mean anything"
    _, removed_angled, _ = apply_cut(img, mask, cm, ang)
    _, removed_flat, _ = apply_cut(img, mask, cm, flat)
    assert not np.array_equal(removed_angled, removed_flat), \
        f"apply_cut discarded the cut angle: identical removal masks ({int((removed_angled != removed_flat).sum())} differing px)"


@pytest.mark.skipif(
    not os.path.exists(os.path.join(ROOT, "models", "sam_vit_b_01ec64.pth")) or __import__("importlib").util.find_spec("torch") is None,
    reason="needs the SAM checkpoint and torch")
def test_predict_positive_and_negative_angles_are_not_nested():
    """tools/predict.py:101-108 — `--angle-deg +30` (outseam higher) and `--angle-deg -30` (inseam higher)
    must each remove fabric the other keeps. observed: the -30 removal is a STRICT SUBSET of the +30 one
    (24064 px only in +30, 0 px only in -30) i.e. both are flat cuts at different heights, and
    prediction.json still reports angle_deg 30 / -30."""
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0)
    bg = np.clip(200 + cv2.GaussianBlur(rng.normal(0, 40, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = cv2.copyMakeBorder(np.where(mask[..., None], img, bg), 60, 60, 60, 60, cv2.BORDER_REPLICATE)
    with tempfile.TemporaryDirectory() as tmp:
        cv2.imwrite(f"{tmp}/jeans.png", scene)
        out = {}
        for deg in ("30", "-30"):
            d = f"{tmp}/a{deg}"
            r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "predict.py"), "--image", f"{tmp}/jeans.png",
                                "--out", d, "--inseam-fraction", "0.45", "--angle-deg", deg,
                                "--wash", "none", "--state", "after_cut"], capture_output=True, text=True)
            assert r.returncode == 0, r.stdout + r.stderr
            out[deg] = cv2.imread(f"{d}/removed_mask.png", 0) > 127
            assert json.load(open(f"{d}/prediction.json"))["cut"]["angle_deg"] == float(deg)
        pos, neg = out["30"], out["-30"]
        assert (pos & ~neg).any() and (neg & ~pos).any(), \
            f"the two angles are nested, not mirrored: +30-only={int((pos & ~neg).sum())} px, -30-only={int((neg & ~pos).sum())} px"

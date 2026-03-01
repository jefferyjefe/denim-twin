"""Review 4, finding 7 (adopted, restated).

The reviewer's original tests demanded that `texture_backdrop_fill`'s invented pixels never fall inside a scored
band. That cannot hold for the helper itself — the band is defined by the caller and reaches into `removed` by
construction. The real invariant is architectural: **images that scoring reads are never produced by the
presentation fill**, so no scored number can depend on the presentation RNG seed.
"""
import sys, os, json, subprocess, tempfile, importlib.util
import pytest
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import apply_cut, cut_mask_canon, backdrop_fill, texture_backdrop_fill

def test_the_presentation_fill_really_does_invent_texture():
    """If this ever stops being true the invariant below becomes vacuous."""
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    rng = np.random.default_rng(1)
    bg = np.clip(180 + cv2.GaussianBlur(rng.normal(0, 60, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = np.where(mask[..., None], img, bg)
    _, removed, keep = apply_cut(scene, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    flat = backdrop_fill(scene, mask, removed)
    a = texture_backdrop_fill(scene, mask, removed, seed=0); b = texture_backdrop_fill(scene, mask, removed, seed=7)
    assert (removed & np.any(a != flat, axis=2)).any() and np.any(a != b)

def test_no_scoring_code_path_imports_the_presentation_fill():
    for f in ("tools/compare.py", "tools/run_pair.py", "tools/run_pairs_batch.py", "tools/score_predict.py",
              "src/denimtwin/eval/identity.py", "src/denimtwin/eval/geometry.py"):
        src = open(os.path.join(ROOT, f)).read()
        assert "texture_backdrop_fill" not in src, f"{f} reaches the scoring path and must not use the presentation fill"

@pytest.mark.skipif(
    not os.path.exists(os.path.join(ROOT, "models", "sam_vit_b_01ec64.pth")) or importlib.util.find_spec("torch") is None,
    reason="needs the SAM checkpoint and torch")
def test_predict_writes_scored_images_with_the_deterministic_fill():
    """pred_*.png are consumed by compare.py (via score_predict.py); inside the removed region they must equal the
    deterministic inpaint wherever the fringe renderer did not paint, not invented texture."""
    img, mask, lm = synthetic_jeans(jitter=0)
    rng = np.random.default_rng(0)
    bg = np.clip(200 + cv2.GaussianBlur(rng.normal(0, 40, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = cv2.copyMakeBorder(np.where(mask[..., None], img, bg), 60, 60, 60, 60, cv2.BORDER_REPLICATE)
    with tempfile.TemporaryDirectory() as tmp:
        cv2.imwrite(f"{tmp}/jeans.png", scene)
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "predict.py"), "--image", f"{tmp}/jeans.png",
                            "--out", f"{tmp}/out", "--inseam-fraction", "0.35", "--wash", "none", "--state", "after_cut"],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        orig = cv2.imread(f"{tmp}/out/orig.png"); pred = cv2.imread(f"{tmp}/out/pred_median.png")
        gm = cv2.imread(f"{tmp}/out/mask.png", 0) > 127; removed = cv2.imread(f"{tmp}/out/removed_mask.png", 0) > 127
        flat = backdrop_fill(orig, gm, removed)
        untouched = removed & ~np.any(np.abs(pred.astype(int) - flat.astype(int)) > 0, axis=2)
        painted = removed & ~untouched
        # whatever the fringe renderer did not paint must be the deterministic fill, pixel for pixel
        assert untouched.sum() > 0.3 * removed.sum(), (untouched.sum(), removed.sum())
        assert np.array_equal(pred[untouched], flat[untouched])
        assert painted.sum() > 0     # and the fringe did paint something

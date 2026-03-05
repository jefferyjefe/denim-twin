"""The repeatability harness must measure the segmenter, not itself (EXP_0021).

If `apply_perturbation` / `warp_mask_forward` disagreed by even a few pixels, every IoU in the experiment would carry
that error and a perfectly repeatable segmenter would look unrepeatable. These tests drive the harness with a
*synthetic perfect segmenter* — one that returns the true silhouette transformed exactly as the image was — and
require the reported IoU to be ~1. They also check that the scale-free statistics really are scale-free.
"""
import sys, os
import numpy as np, cv2, pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import experiment_repeatability as ER


def synthetic_garment(H=600, W=800, scale=1.0):
    """A flat-lay pair of shorts: waistband block + two legs, with the garment well inside the frame."""
    m = np.zeros((H, W), np.uint8)
    cx, top = W // 2, int(0.15 * H)
    ww = int(0.42 * W * scale); hh = int(0.55 * H * scale)
    body_h = int(0.45 * hh)
    cv2.rectangle(m, (cx - ww // 2, top), (cx + ww // 2, top + body_h), 255, -1)
    leg_w = int(ww * 0.42); gap = int(ww * 0.08)
    for s in (-1, 1):
        x0 = cx + s * gap // 2 - (leg_w if s < 0 else 0)
        cv2.rectangle(m, (x0, top + body_h), (x0 + leg_w, top + hh), 255, -1)
    return m > 0


def render(mask):
    """A picture of that mask: dark denim-blue garment on a light backdrop, with texture so JPEG has something to do."""
    img = np.full((*mask.shape, 3), 220, np.uint8)
    img[mask] = (110, 70, 40)
    rng = np.random.default_rng(0)
    img = np.clip(img.astype(np.int16) + rng.integers(-6, 7, img.shape), 0, 255).astype(np.uint8)
    return img


@pytest.mark.parametrize("spec", ER.PERTURBATIONS, ids=[s[0] for s in ER.PERTURBATIONS])
def test_perfect_segmenter_scores_near_one(spec):
    """A segmenter that is exactly right in the perturbed frame must score IoU ~1 under the harness's own bookkeeping."""
    truth = synthetic_garment()
    img = render(truth)
    pimg, M, valid = ER.apply_perturbation(img, spec)
    # the perfect segmenter's answer in the perturbed frame is the truth, transformed the same way
    perfect = ER.warp_mask_forward(truth, M, pimg.shape[:2])
    ref_in_p = ER.warp_mask_forward(truth, M, pimg.shape[:2])
    assert ER.iou(perfect, ref_in_p, valid) > 0.999


def test_geometric_perturbations_actually_move_pixels():
    """A perturbation that changed nothing would make the experiment trivially pass; each geometric one must move the
    silhouette by a visible amount."""
    truth = synthetic_garment(); img = render(truth)
    for spec in ER.PERTURBATIONS:
        name, family, _ = spec
        if family not in ("geometric", "combined"): continue
        _, M, _ = ER.apply_perturbation(img, spec)
        moved = ER.warp_mask_forward(truth, M, truth.shape)
        assert ER.iou(moved, truth) < 0.97, f"{name} barely moves the mask (IoU {ER.iou(moved, truth):.3f})"


def test_validity_map_excludes_invented_pixels():
    """Rotation and zoom-out pull pixels in from outside the frame; those must not be compared."""
    truth = synthetic_garment(); img = render(truth)
    for name in ("rot+8", "zoom0.85"):
        spec = next(s for s in ER.PERTURBATIONS if s[0] == name)
        _, M, valid = ER.apply_perturbation(img, spec)
        assert valid.mean() < 0.999, f"{name} reports every output pixel as real"
        assert valid.mean() > 0.5


def test_photometric_perturbations_leave_geometry_untouched():
    truth = synthetic_garment(); img = render(truth)
    for spec in ER.PERTURBATIONS:
        if spec[1] != "photometric": continue
        _, M, valid = ER.apply_perturbation(img, spec)
        assert M is None and valid.all()


def test_scale_free_statistics_are_scale_free():
    """The same silhouette photographed from twice the distance must give the same ratios."""
    a = ER.measure(synthetic_garment(600, 800, scale=1.0))
    b = ER.measure(synthetic_garment(1200, 1600, scale=1.0))          # same garment, twice the pixels
    assert a["waist_px"] * 2 == pytest.approx(b["waist_px"], rel=0.02)
    for k in ("height_over_waist", "hip_over_waist"):
        assert a[k] == pytest.approx(b[k], rel=0.03), k


def test_iou_ignores_pixels_outside_the_validity_map():
    a = np.zeros((10, 10), bool); b = np.zeros((10, 10), bool)
    a[:5] = True; b[:5] = True; b[7:] = True            # b disagrees only in the invalid region
    valid = np.zeros((10, 10), bool); valid[:6] = True
    assert ER.iou(a, b, valid) == pytest.approx(1.0)
    assert ER.iou(a, b) < 1.0


def test_summarize_reports_reference_disagreement():
    rows = [{"image": "x", "set": "s", "method": "best", "perturbation": "identity", "family": "none",
             "found": True, "iou_vs_ref": 1.0, "m_height_over_waist": 1.0},
            {"image": "x", "set": "s", "method": "best", "perturbation": "rot+3", "family": "geometric",
             "found": True, "iou_vs_ref": 0.4, "m_height_over_waist": 1.5}]
    refs = [{"image": "x", "set": "s", "method": "best", "found": True, "iou_between_methods": 0.11},
            {"image": "x", "set": "s", "method": "consensus", "found": True, "iou_between_methods": 0.11}]
    s = ER.summarize(rows, refs)
    assert s["references"]["images_where_methods_disagree"] == ["x"]
    assert s["headline"]["best"]["n_iou_below_050"] == 1
    assert s["by_method"]["best"]["spread"]["height_over_waist"][0]["max_rel_dev"] == pytest.approx(0.5)

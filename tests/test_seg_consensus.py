"""Consensus segmentation: agreement across prompts instead of SAM's own confidence (EXP_0018/0019)."""
import sys, os, pytest, importlib.util
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, cv2
from denimtwin.seg.validate import check_garment_mask, _runs

pytestmark = pytest.mark.skipif(
    not os.path.exists(os.path.join(ROOT, "models", "sam_vit_b_01ec64.pth")) or importlib.util.find_spec("torch") is None,
    reason="needs the SAM checkpoint and torch")

def _scene(distractor=True, W=700, H=520):
    """A denim-ish garment on a floor, plus a bright rectangle above it — the shape SAM preferred over the garment
    on two real photos (a wall panel, a pale board)."""
    rng = np.random.default_rng(0)
    img = np.full((H, W, 3), 150, np.uint8)
    img = np.clip(img + rng.integers(-8, 8, img.shape, dtype=np.int16).astype(np.int16), 0, 255).astype(np.uint8)
    if distractor: cv2.rectangle(img, (40, 8), (W - 40, 60), (225, 225, 220), -1)   # bright strip along the top edge
    g = np.zeros((H, W), bool)
    cv2.rectangle(g, (140, 95), (W - 140, 300), True, -1)           # body: a flat-lay fills most of the frame
    cv2.rectangle(g, (140, 300), (330, 480), True, -1)              # left leg
    cv2.rectangle(g, (W - 330, 300), (W - 140, 480), True, -1)      # right leg
    tex = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 1.2) * 12
    denim = np.clip(np.dstack([120 + tex, 70 + tex, 45 + tex]), 0, 255).astype(np.uint8)
    img[g] = denim[g]
    return img, g

def test_consensus_prefers_the_agreed_object_and_reports_agreement():
    from denimtwin.seg.sam import SamSegmenter
    from denimtwin.seg.validate import segment_garment_consensus
    img, truth = _scene()
    m, agreement, info = segment_garment_consensus(SamSegmenter(), img, boundary="member")
    assert m is not None, info
    iou = (m & truth).sum() / max((m | truth).sum(), 1)
    assert iou > 0.75, (iou, info)                    # the garment, not the bright panel
    assert 0.0 <= agreement <= 1.0 and info["n_prompt_sets"] >= 6

def test_agreement_is_reported_even_when_the_mask_is_returned():
    from denimtwin.seg.sam import SamSegmenter
    from denimtwin.seg.validate import segment_garment_consensus
    img, _ = _scene(distractor=False)
    m, agreement, info = segment_garment_consensus(SamSegmenter(), img)
    assert m is not None and agreement >= 0.5 and "agreement" in info

def test_a_high_min_agreement_refuses_rather_than_guesses():
    from denimtwin.seg.sam import SamSegmenter
    from denimtwin.seg.validate import segment_garment_consensus
    img, _ = _scene()
    m, agreement, info = segment_garment_consensus(SamSegmenter(), img, min_agreement=1.01)
    assert m is None and "disagree" in info.get("reason", ""), info

def test_check_garment_mask_rejects_a_detail_sized_mask():
    img, truth = _scene()
    pocket = np.zeros_like(truth); pocket[240:300, 300:360] = True
    ok, reasons, stats = check_garment_mask(img, pocket)
    assert not ok and any("detail" in r or "frame width" in r for r in reasons), reasons

def test_runs_counts_separated_segments():
    row = np.zeros(100, bool); row[10:20] = True; row[60:70] = True
    assert _runs(row) == 2 and _runs(np.zeros(10, bool)) == 0

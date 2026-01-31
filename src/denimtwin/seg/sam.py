"""Garment segmentation with Segment Anything (ViT-B), prompted from landmarks.

Prompts derived from the 14 jeans landmarks:
  box      = padded bbox of all landmarks
  positive = points safely inside the garment (hip midline, mid-thigh of each leg, mid-shin of each leg)
  negative = the gap between the legs at knee height and below the crotch (keeps the between-leg
             background out, which convex-hull GrabCut got wrong)
"""
from pathlib import Path
import numpy as np, cv2, torch

DEFAULT_CKPT = Path(__file__).resolve().parents[3] / "models" / "sam_vit_b_01ec64.pth"

def _mid(a, b, t=0.5): return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

def prompts_from_landmarks(lm, pad_frac=0.04, image_shape=None):
    pts = np.array(list(lm.values()), float)
    x0, y0 = pts.min(0); x1, y1 = pts.max(0)
    pad = pad_frac * max(x1 - x0, y1 - y0)
    box = np.array([x0 - pad, y0 - pad, x1 + pad, y1 + pad])
    if image_shape is not None:
        h, w = image_shape[:2]; box = np.clip(box, [0, 0, 0, 0], [w - 1, h - 1, w - 1, h - 1])
    pos = [_mid(lm["waist_center"], lm["crotch"], 0.5),
           _mid(_mid(lm["knee_left_outer"], lm["knee_left_inner"]), _mid(lm["hip_left"], lm["crotch"]), 0.5),
           _mid(_mid(lm["knee_right_outer"], lm["knee_right_inner"]), _mid(lm["hip_right"], lm["crotch"]), 0.5),
           _mid(_mid(lm["knee_left_outer"], lm["knee_left_inner"]), _mid(lm["hem_left_outer"], lm["hem_left_inner"]), 0.5),
           _mid(_mid(lm["knee_right_outer"], lm["knee_right_inner"]), _mid(lm["hem_right_outer"], lm["hem_right_inner"]), 0.5)]
    gap_knee = _mid(lm["knee_left_inner"], lm["knee_right_inner"])
    gap_hem = _mid(lm["hem_left_inner"], lm["hem_right_inner"])
    neg = [gap_knee, _mid(gap_knee, gap_hem, 0.6), _mid(lm["crotch"], gap_knee, 0.4)]
    return box, np.array(pos, float), np.array(neg, float)

class SamSegmenter:
    def __init__(self, checkpoint=DEFAULT_CKPT, model_type="vit_b", device=None):
        from segment_anything import sam_model_registry, SamPredictor
        if device is None:
            device = "mps" if torch.backends.mps.is_available() else ("cuda" if torch.cuda.is_available() else "cpu")
        sam = sam_model_registry[model_type](checkpoint=str(checkpoint)).to(device)
        self.predictor = SamPredictor(sam); self.device = device

    def segment(self, image_bgr, landmarks=None, box=None, pos=None, neg=None, max_side=1024):
        """Return boolean garment mask at full image resolution. Image is downscaled for SAM if large."""
        h, w = image_bgr.shape[:2]; s = min(1.0, max_side / max(h, w))
        small = cv2.resize(image_bgr, None, fx=s, fy=s) if s < 1 else image_bgr
        if landmarks is not None:
            box, pos, neg = prompts_from_landmarks(landmarks, image_shape=image_bgr.shape)
        self.predictor.set_image(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        pc = np.concatenate([p for p in (pos, neg) if p is not None and len(p)]) * s if (pos is not None or neg is not None) else None
        pl = np.concatenate([np.ones(len(pos)) if pos is not None else [], np.zeros(len(neg)) if neg is not None else []]) if pc is not None else None
        masks, scores, _ = self.predictor.predict(point_coords=pc, point_labels=pl,
                                                  box=(np.asarray(box) * s) if box is not None else None, multimask_output=True)
        m = masks[int(np.argmax(scores))]
        m = m.astype(np.uint8) * 255
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
        # keep the largest connected component (garment), drop specks
        n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
        if n > 1: m = (lab == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8) * 255
        if s < 1: m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
        return m > 127, float(scores.max())


def _border_frac(m, b=4):
    return float(np.concatenate([m[:b].ravel(), m[-b:].ravel(), m[:, :b].ravel(), m[:, -b:].ravel()]).mean())

def segment_garment_coarse(seg, image_bgr, max_side=1024):
    """Find the garment with no landmarks: try several point-prompt sets, collect all SAM candidates, and choose
    the one that looks like a flat-laid garment: area 5-70% of frame, minimal frame-border contact, highest score.
    Returns (mask, score, info)."""
    h, w = image_bgr.shape[:2]; s = min(1.0, max_side / max(h, w))
    small = cv2.resize(image_bgr, None, fx=s, fy=s) if s < 1 else image_bgr
    seg.predictor.set_image(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
    cands = []
    hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
    denimish = ((hsv[..., 0] >= 95) & (hsv[..., 0] <= 135) & (hsv[..., 1] >= 40)) | (hsv[..., 2] < 60)   # blue denim or black/dark denim
    prompt_sets = [np.array([[0.5, 0.4]]), np.array([[0.5, 0.35], [0.4, 0.6], [0.6, 0.6]]), np.array([[0.5, 0.5]]), np.array([[0.5, 0.3], [0.5, 0.7]]),
                   np.array([[0.35, 0.5], [0.65, 0.5]]), np.array([[0.5, 0.25]])]
    for pts in prompt_sets:
        pc = pts * np.array([small.shape[1], small.shape[0]])
        masks, scores, _ = seg.predictor.predict(point_coords=pc, point_labels=np.ones(len(pc)), multimask_output=True)
        for m, sc in zip(masks, scores):
            area = m.mean(); bf = _border_frac(m)
            if not (0.03 <= area <= 0.70): continue
            dn = float(denimish[m].mean())                     # soft prior: a garment mask should be mostly denim-coloured
            cands.append((float(sc) - 2.0 * bf - 0.3 * max(0, area - 0.5) + 0.8 * dn, m, float(sc), area, bf))
    if not cands: return None, 0.0, {}
    best = max(cands, key=lambda c: c[0]); m = best[1].astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m)
    if n > 1: m = (lab == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8) * 255
    if s < 1: m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
    return m > 127, best[2], {"area": best[3], "border_frac": best[4]}

def segment_fringe(seg, image_bgr, garment_mask, band_frac=0.15, max_side=1024):
    """Fringe/loose-thread mask via SAM prompted on the hem band of a cut garment: positive points along the
    bottom band of the garment, negatives on the body. Returns the SAM candidate whose area is < 50% of the garment
    with the highest score, restricted to the garment mask and to the bottom 35% of the garment rows."""
    h, w = image_bgr.shape[:2]; s = min(1.0, max_side / max(h, w))
    small = cv2.resize(image_bgr, None, fx=s, fy=s) if s < 1 else image_bgr
    seg.predictor.set_image(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
    am = garment_mask.astype(bool); rows = np.nonzero(am.any(axis=1))[0]
    if len(rows) < 10: return None
    yt, yb = rows.min(), rows.max(); band = max(int(band_frac * (yb - yt)), 4)
    xs = np.nonzero(am[max(yb - band // 2, yt)])[0]
    if len(xs) < 20: return None
    cols = np.linspace(xs.min() + 5, xs.max() - 5, 7).astype(int)
    pos = np.array([[x, yb - band // 3] for x in cols], float); neg = np.array([[x, yt + (yb - yt) // 2] for x in cols[::2]] + [[cols[3], yt + (yb - yt) // 6]], float)
    pc = np.concatenate([pos, neg]) * s; pl = np.array([1] * len(pos) + [0] * len(neg))
    masks, scores, _ = seg.predictor.predict(point_coords=pc, point_labels=pl, multimask_output=True)
    cands = [(float(sc), m) for m, sc in zip(masks, scores) if 0.01 < m.mean() and m.sum() < 0.5 * (am.sum() * s * s)]
    if not cands: return None
    m = max(cands, key=lambda c: c[0])[1].astype(np.uint8) * 255
    if s < 1: m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
    fr = (m > 127) & am
    fr[: yt + int(0.65 * (yb - yt))] = False        # fringe lives at the bottom; thigh distressing is not fringe
    return fr

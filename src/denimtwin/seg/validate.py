"""Is this mask actually the garment? (plan §4.2)

`segment_garment_coarse` returns SAM's best-scoring plausible candidate, and SAM is confidently wrong often enough to
matter: on four real flat-lay photos inspected in EXP_0018 it segmented **a back pocket** (mask 4.4% of frame, score
0.906) and **the wall above the garment** (37.7%, score 0.992). Both then produced fringe and roughness numbers that
entered the prior. SAM's own score does not detect this, and neither does contour compactness — the wrong object can
have a perfectly clean outline.

These checks are cheap, object-level, and deliberately conservative: they reject, they never repair. Anything they
reject needs a human to look at the photo, which is the correct outcome for a research dataset.
"""
import numpy as np
import cv2

DEFAULTS = dict(min_area=0.06, max_area=0.75, min_fill_of_bbox=0.35, max_aspect=2.6, min_denim_frac=0.35,
                min_width_frac=0.25, max_border_frac=0.02)

def _denim_frac(image_bgr, m):
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    denimish = ((hsv[..., 0] >= 95) & (hsv[..., 0] <= 135) & (hsv[..., 1] >= 40)) | (hsv[..., 2] < 60)
    return float(denimish[m].mean()) if m.any() else 0.0

def check_garment_mask(image_bgr, mask, expect="shorts", **kw):
    """Return (ok, reasons, stats). `expect` is 'shorts', 'jeans' or None (either)."""
    p = {**DEFAULTS, **kw}
    m = np.asarray(mask, bool)
    H, W = m.shape
    reasons = []
    area = float(m.mean())
    ys, xs = np.nonzero(m)
    if not len(ys): return False, ["empty mask"], {"area": 0.0}
    h = ys.max() - ys.min() + 1; w = xs.max() - xs.min() + 1
    stats = {"area": area, "bbox_fill": float(m.sum() / (h * w)), "aspect": float(h / max(w, 1)),
             "width_frac": float(w / W), "denim_frac": _denim_frac(image_bgr, m),
             "border_frac": float((m[0].mean() + m[-1].mean() + m[:, 0].mean() + m[:, -1].mean()) / 4)}
    if area < p["min_area"]: reasons.append(f"mask covers only {area:.1%} of the frame — a detail, not a garment")
    if area > p["max_area"]: reasons.append(f"mask covers {area:.1%} of the frame — probably the backdrop")
    if stats["width_frac"] < p["min_width_frac"]: reasons.append(f"mask spans only {stats['width_frac']:.0%} of the frame width")
    if stats["bbox_fill"] < p["min_fill_of_bbox"]: reasons.append(f"mask fills only {stats['bbox_fill']:.0%} of its own bounding box")
    if stats["denim_frac"] < p["min_denim_frac"]: reasons.append(f"only {stats['denim_frac']:.0%} of the mask is denim-coloured")
    if stats["border_frac"] > p["max_border_frac"]: reasons.append(f"mask touches the frame border ({stats['border_frac']:.1%})")
    if expect == "shorts" and stats["aspect"] > p["max_aspect"]:
        reasons.append(f"mask is {stats['aspect']:.1f}x taller than wide — not a pair of shorts")
    # a flat-laid pair of shorts/jeans has ONE waistband run at the top and TWO legs lower down
    top = ys.min(); band = m[top:top + max(int(0.12 * h), 3)]
    runs_top = _runs(band.any(axis=0))
    low = m[ys.min() + int(0.75 * h):]
    runs_low = _runs(low.any(axis=0)) if low.any() else 0
    stats["runs_top"], stats["runs_low"] = runs_top, runs_low
    if runs_top != 1: reasons.append(f"{runs_top} separate runs across the top of the mask — not a single waistband")
    return (not reasons), reasons, stats

def _runs(row_bool, gap=3):
    x = np.nonzero(row_bool)[0]
    if not len(x): return 0
    return 1 + int((np.diff(x) > gap).sum())


def segment_garment_consensus(seg, image_bgr, max_side=1024, min_agreement=0.5, iou_same=0.7, boundary='median'):
    """Segment the garment by AGREEMENT across prompt sets instead of by best score (EXP_0018).

    `segment_garment_coarse` takes the highest-scoring plausible candidate, and SAM is confidently wrong: it returned
    a back pocket at score 0.906 and a wall at 0.992 on real flat-lay photos, and those masks produced measurements.
    Here every prompt set votes: candidates are clustered by IoU, and the cluster with the most *distinct prompt sets*
    wins. `agreement` is the fraction of prompt sets that found essentially this mask — a number the caller can refuse
    on, which is what the best-score interface could never provide.

    Returns (mask, agreement, info) — mask is None when no cluster reaches `min_agreement`."""
    h, w = image_bgr.shape[:2]
    s = min(1.0, max_side / max(h, w))
    small = cv2.resize(image_bgr, None, fx=s, fy=s) if s < 1 else image_bgr
    seg.predictor.set_image(cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
    prompt_sets = [np.array([[0.5, 0.4]]), np.array([[0.5, 0.35], [0.4, 0.6], [0.6, 0.6]]), np.array([[0.5, 0.5]]),
                   np.array([[0.5, 0.3], [0.5, 0.7]]), np.array([[0.35, 0.5], [0.65, 0.5]]), np.array([[0.5, 0.25]]),
                   np.array([[0.3, 0.35], [0.7, 0.35]]), np.array([[0.5, 0.6]])]
    cands = []
    for i, pts in enumerate(prompt_sets):
        pc = pts * np.array([small.shape[1], small.shape[0]])
        masks, scores, _ = seg.predictor.predict(point_coords=pc, point_labels=np.ones(len(pc)), multimask_output=True)
        for m, sc in zip(masks, scores):
            a = float(m.mean())
            if not (0.05 <= a <= 0.75): continue
            cands.append({"prompt": i, "mask": m, "score": float(sc), "area": a})
    if not cands: return None, 0.0, {"reason": "no plausible candidate from any prompt"}
    clusters = []
    for c in sorted(cands, key=lambda c: -c["score"]):
        for cl in clusters:
            inter = (cl["rep"] & c["mask"]).sum(); union = (cl["rep"] | c["mask"]).sum()
            if union and inter / union >= iou_same:
                cl["members"].append(c); cl["prompts"].add(c["prompt"]); break
        else:
            clusters.append({"rep": c["mask"], "members": [c], "prompts": {c["prompt"]}})
    n_prompts = len(prompt_sets)
    best = max(clusters, key=lambda cl: (len(cl["prompts"]), max(m["score"] for m in cl["members"])))
    agreement = len(best["prompts"]) / n_prompts
    info = {"agreement": agreement, "boundary": boundary, "n_clusters": len(clusters), "n_prompt_sets": n_prompts,
            "best_score": max(m["score"] for m in best["members"]), "area": float(best["rep"].mean()),
            "rival_areas": sorted({round(float(np.mean([m["area"] for m in cl["members"]])), 3) for cl in clusters})[:5]}
    if agreement < min_agreement:
        info["reason"] = (f"prompt sets disagree: the most-agreed mask was found by {len(best['prompts'])} of "
                          f"{n_prompts} prompts ({len(clusters)} distinct candidates)")
        return None, agreement, info
    # Which boundary to return from the winning cluster:
    #   'median' — per-pixel majority of its members: robust, but it smooths the hem, and hem *texture* is the fray
    #              signal (EXP_0019: fray detection fell from 6/8 to 3/7 with the median boundary),
    #   'member' — the highest-scoring single member: identity comes from the agreement, detail from one mask.
    if boundary == "member":
        stack = max(best["members"], key=lambda m: m["score"])["mask"]
    else:
        stack = np.stack([m["mask"] for m in best["members"]]).mean(axis=0) > 0.5
    u = (stack.astype(np.uint8) * 255)
    u = cv2.morphologyEx(u, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(u)
    if n > 1: u = (lab == (1 + np.argmax(stats[1:, cv2.CC_STAT_AREA]))).astype(np.uint8) * 255
    if s < 1: u = cv2.resize(u, (w, h), interpolation=cv2.INTER_NEAREST)
    return u > 127, agreement, info

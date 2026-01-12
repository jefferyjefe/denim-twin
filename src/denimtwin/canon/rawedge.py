"""Procedural raw edge v0 (Phase 2 baseline, plan §4.7 'procedural base model', 2D only).

Given the cut image, the removed-region mask and garment mask, draw a raw hem:
  1. a jagged edge (weave-scale irregularity along the cut boundary),
  2. a faded/lighter band just above the edge (exposed weft, abrasion),
  3. loose threads hanging into the removed region (length ~ fray_depth), coloured like the weft
     (denim weft is undyed: pale ecru/white) with a few indigo warp threads.
Parameters are physical (mm) and converted with mm_per_px. Deterministic given seed.
The output changes ONLY pixels inside `removed` (the band drawn above the edge is applied to
garment pixels within `edge_band_mm` of the cut and is reported in the returned changed-mask).
"""
from dataclasses import dataclass
import numpy as np, cv2

@dataclass
class RawEdgeParams:
    fray_depth_mm: float = 6.0        # mean hanging-thread length
    fray_depth_sd_mm: float = 2.5
    threads_per_cm: float = 6.0       # hanging thread density along the edge
    edge_band_mm: float = 2.0         # lighter abraded band above the edge
    jag_mm: float = 1.0               # edge irregularity amplitude
    weft_color: tuple = (215, 220, 225)   # BGR pale ecru
    warp_fraction: float = 0.15       # fraction of threads that are indigo (warp)
    seed: int = 0

PRESETS = {
    "conservative": RawEdgeParams(fray_depth_mm=3.0, fray_depth_sd_mm=1.2, threads_per_cm=4, edge_band_mm=1.0),
    "median":       RawEdgeParams(),
    "aggressive":   RawEdgeParams(fray_depth_mm=11.0, fray_depth_sd_mm=4.0, threads_per_cm=9, edge_band_mm=3.0, jag_mm=1.8),
}

def _edge_pixels(removed, garment):
    """Boundary pixels of the kept garment adjacent to the removed region, and the local 'down' direction."""
    kept = garment & ~removed
    k8 = kept.astype(np.uint8)
    dil = cv2.dilate(removed.astype(np.uint8), np.ones((3, 3), np.uint8))
    edge = (k8 > 0) & (dil > 0)
    ys, xs = np.nonzero(edge)
    # local outward normal: gradient of distance-to-kept (points from kept into removed)
    dist = cv2.distanceTransform((~kept).astype(np.uint8), cv2.DIST_L2, 3)
    gy = cv2.Sobel(dist, cv2.CV_32F, 0, 1, ksize=3); gx = cv2.Sobel(dist, cv2.CV_32F, 1, 0, ksize=3)
    n = np.stack([gx[ys, xs], gy[ys, xs]], 1); nn = np.linalg.norm(n, axis=1, keepdims=True); n = n / np.maximum(nn, 1e-6)
    return xs, ys, n

def render_raw_edge(cut_img, removed, garment, mm_per_px, params=PRESETS["median"], background=None):
    """Return (image, changed_mask). `cut_img` is the output of apply_cut (removed region = background)."""
    rng = np.random.default_rng(params.seed)
    out = cut_img.copy(); H, W = removed.shape
    px = lambda mm: mm / mm_per_px
    xs, ys, normals = _edge_pixels(removed, garment)
    if len(xs) == 0: return out, np.zeros_like(removed)
    changed = np.zeros_like(removed)

    # 1. jagged edge: nibble small bites out of the kept side along the boundary
    jag = np.zeros((H, W), np.uint8)
    for x, y, n in zip(xs[::2], ys[::2], normals[::2]):
        a = rng.uniform(0, px(params.jag_mm))
        if a < 0.5: continue
        cv2.circle(jag, (int(x - n[0] * a * 0.5), int(y - n[1] * a * 0.5)), max(1, int(a)), 255, -1)
    bite = (jag > 0) & garment & ~removed
    bg = background if background is not None else np.median(cut_img[removed], axis=0) if removed.any() else np.array([0, 0, 0])
    out[bite] = bg; changed |= bite
    removed_now = removed | bite

    # 2. abraded band above the edge: lighten + desaturate garment pixels within edge_band_mm
    kept = garment & ~removed_now
    d_in = cv2.distanceTransform(kept.astype(np.uint8), cv2.DIST_L2, 3)
    band = kept & (d_in <= px(params.edge_band_mm))
    w = (1.0 - d_in[band] / max(px(params.edge_band_mm), 1e-6))[:, None] * 0.45
    out[band] = np.clip(out[band] * (1 - w) + np.array(params.weft_color) * w, 0, 255).astype(np.uint8)
    changed |= band

    # 3. hanging threads: polylines from edge points into the removed region, along the normal, with wobble
    xs, ys, normals = _edge_pixels(removed_now, garment)
    edge_len_cm = len(xs) * mm_per_px / 10.0
    n_threads = int(edge_len_cm * params.threads_per_cm)
    idx = rng.choice(len(xs), size=min(n_threads, len(xs)), replace=False)
    thread_layer = out.copy()
    for i in idx:
        L = max(px(0.5), rng.normal(px(params.fray_depth_mm), px(params.fray_depth_sd_mm)))
        x, y = float(xs[i]), float(ys[i]); n = normals[i].copy()
        col = (60, 40, 25) if rng.random() < params.warp_fraction else tuple(int(c + rng.normal(0, 8)) for c in params.weft_color)
        col = tuple(int(np.clip(c, 0, 255)) for c in col)
        pts = [(x, y)]; ang = np.arctan2(n[1], n[0]); step = max(1.0, px(0.4)); s = 0.0
        while s < L:
            ang += rng.normal(0, 0.25); x += np.cos(ang) * step; y += np.sin(ang) * step; s += step
            if not (0 <= int(x) < W and 0 <= int(y) < H) or not removed_now[int(y), int(x)]: break
            pts.append((x, y))
        if len(pts) > 1:
            cv2.polylines(thread_layer, [np.array(pts, np.int32)], False, col, 1, cv2.LINE_AA)
    tmask = np.any(thread_layer != out, axis=2) & removed_now
    out[tmask] = thread_layer[tmask]; changed |= tmask
    return out, changed

def render_three(cut_img, removed, garment, mm_per_px, seed=0):
    res = {}
    for k, p in PRESETS.items():
        q = RawEdgeParams(**{**p.__dict__, "seed": seed}); res[k] = render_raw_edge(cut_img, removed, garment, mm_per_px, q)
    return res

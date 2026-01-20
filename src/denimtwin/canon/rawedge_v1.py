"""Raw edge v1 — fringe as a density band (from EXP_0003).

At found-image resolution (~1 mm/px) individual threads are sub-pixel; what the camera sees is a band whose
coverage (fraction of pixels that are thread rather than background) decays from ~1 at the fabric edge to 0 at the
fringe tip, with colour a mix of undyed weft (ecru) and indigo, plus a lighter abraded strip on the fabric side.
Parameters are in mm; `fringe_depth_mm` is the tip-to-edge distance (5–40 mm observed in tutorials).
Output modifies only: the removed region within `fringe_depth` of the edge, and the fabric within `edge_band_mm`.
"""
from dataclasses import dataclass
import numpy as np, cv2

@dataclass
class FringeParams:
    fringe_depth_mm: float = 20.0
    depth_jitter_mm: float = 4.0      # low-frequency variation of depth along the hem
    coverage_at_edge: float = 0.95
    falloff: float = 1.6              # coverage ~ (1 - d/D)^falloff
    clump_mm: float = 2.5             # horizontal clump size of thread bundles
    weft_color: tuple = (215, 222, 228)
    indigo_fraction: float = 0.25     # share of indigo (warp) threads in the fringe
    edge_band_mm: float = 2.5
    seed: int = 0

PRESETS = {"conservative": FringeParams(fringe_depth_mm=8, coverage_at_edge=0.85),
           "median": FringeParams(),
           "aggressive": FringeParams(fringe_depth_mm=35, depth_jitter_mm=7, indigo_fraction=0.3)}

def render_fringe(cut_img, removed, garment, mm_per_px, p=PRESETS["median"], background=None):
    rng = np.random.default_rng(p.seed); H, W = removed.shape; px = lambda mm: max(mm / mm_per_px, 0.5)
    out = cut_img.copy().astype(np.float32); changed = np.zeros_like(removed)
    kept = garment & ~removed
    if not kept.any() or not removed.any(): return cut_img.copy(), changed
    # distance from every pixel to the kept fabric; direction handled implicitly (band grows into `removed`)
    d_out = cv2.distanceTransform((~kept).astype(np.uint8), cv2.DIST_L2, 5)       # in removed region: distance to fabric
    d_in = cv2.distanceTransform((~removed).astype(np.uint8), cv2.DIST_L2, 5)     # inside fabric: distance to the CUT (not the outline)
    # local depth varies slowly along the hem: low-frequency noise field
    noise = cv2.resize(rng.normal(0, 1, (max(H // 40, 2), max(W // 40, 2))).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    depth = px(p.fringe_depth_mm) + noise * px(p.depth_jitter_mm)
    depth = np.clip(depth, px(2), None)
    # coverage in the fringe zone
    zone = removed & (d_out <= depth)
    cov = np.zeros((H, W), np.float32)
    cov[zone] = p.coverage_at_edge * np.clip(1 - d_out[zone] / depth[zone], 0, 1) ** p.falloff
    # clumping: multiply by a horizontally-structured texture so coverage forms bundles/gaps
    tex = cv2.resize(rng.random((max(H // int(px(p.clump_mm) * 2), 2), max(W // int(px(p.clump_mm)), 2))).astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
    tex = cv2.GaussianBlur(tex, (0, 0), max(px(0.6), 0.6)); tex = (tex - tex.min()) / (tex.max() - tex.min() + 1e-6)
    cov *= np.clip(0.55 + 0.9 * tex, 0, 1.2)
    # vertical streakiness: thin strokes along the hanging direction (approx image-down)
    streak = cv2.resize(rng.random((max(H // 2, 2), max(W // max(int(px(0.7)), 1), 2))).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST)
    cov *= np.clip(0.6 + 0.8 * streak, 0, 1.2)
    cov = np.clip(cov, 0, 1)
    # per-pixel thread colour: weft or indigo, blended with background by coverage
    bg = (background if background is not None else np.median(cut_img[removed], axis=0)).astype(np.float32)
    indigo = np.array((70, 45, 30), np.float32); weft = np.array(p.weft_color, np.float32)
    isind = cv2.resize(rng.random((max(H // 3, 2), max(W // max(int(px(0.8)), 1), 2))).astype(np.float32), (W, H), interpolation=cv2.INTER_NEAREST) < p.indigo_fraction
    col = np.where(isind[..., None], indigo, weft)
    col += rng.normal(0, 6, col.shape).astype(np.float32)
    a = cov[..., None]
    out[zone] = (out[zone] * (1 - a[zone]) + col[zone] * a[zone])
    changed |= zone & (cov > 0.5)      # 'predicted fringe pixel' = mostly thread, not faint haze
    # abraded strip on the fabric side
    band = kept & (d_in <= px(p.edge_band_mm))
    w = (1 - d_in[band] / px(p.edge_band_mm))[:, None] * 0.5
    out[band] = out[band] * (1 - w) + weft * w; changed |= band
    return np.clip(out, 0, 255).astype(np.uint8), changed

def render_three(cut_img, removed, garment, mm_per_px, seed=0, depth_override=None):
    res = {}
    for k, p in PRESETS.items():
        q = FringeParams(**{**p.__dict__, "seed": seed}); 
        if depth_override is not None: q.fringe_depth_mm = depth_override[k]
        res[k] = render_fringe(cut_img, removed, garment, mm_per_px, q)
    return res

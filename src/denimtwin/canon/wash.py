"""Procedural wash appearance v0 (plan §4.7/§4.8: "cut AND washed once").

What one laundering cycle does to a raw-cut cotton denim garment, beyond the fringe (which `rawedge_v1` handles):
  1. Shrinkage — anisotropic, larger along the warp (leg direction) than across. Typical first-wash relaxation
     shrinkage of sanforized cotton denim is ~1–3% warp, ~0.5–2% weft; unsanforized ("shrink-to-fit") can be 7–10%.
     These are textile-industry ranges, NOT measured on our data: EXP_0013 shows found-photo landmarks are far too
     noisy to measure a 2% length change, so the numbers are priors until metric-scale contributed pairs arrive.
  2. Hem roll — the raw edge curls after agitation; in a flat photo it reads as a shading strip (shadow under the
     curl, lit crest) on the fabric side of the cut, a few mm wide.
  3. Colour — a small loss of surface indigo: slightly lighter, slightly less saturated. Unvalidated prior; lighting
     differences between found before/after photos are larger than this effect, so it cannot be fitted from them.

Only the garment (and the backdrop it uncovers by shrinking) is modified. Every parameter has conservative /
median / aggressive presets so the render is an interval, never a point (plan §4.9). `none` is byte-identical.
"""
from dataclasses import dataclass
import numpy as np, cv2
from .cut2d import backdrop_fill

@dataclass
class WashParams:
    shrink_along_frac: float = 0.02      # along the leg (warp)
    shrink_across_frac: float = 0.01     # across the leg (weft)
    hem_roll_mm: float = 5.0             # width of the roll shading strip on the fabric side of the cut
    roll_strength: float = 0.35          # peak darkening of L* inside the strip (0 = none)
    lightness_shift: float = 1.5         # Lab L* added inside the garment (dye loss)
    chroma_scale: float = 0.97           # multiplier on Lab a*, b*
    seed: int = 0

PRESETS = {
    "none": WashParams(0.0, 0.0, 0.0, 0.0, 0.0, 1.0),
    "conservative": WashParams(0.01, 0.005, 3.0, 0.2, 0.7, 0.985),
    "median": WashParams(),
    "aggressive": WashParams(0.04, 0.02, 8.0, 0.5, 3.0, 0.94),
}

def _shrink(img, garment, removed, p):
    """Scale the garment about the centroid of the KEPT fabric; uncovered pixels get backdrop texture."""
    keep = garment & ~removed
    if not keep.any() or (p.shrink_along_frac == 0 and p.shrink_across_frac == 0):
        return img.copy(), garment.copy(), removed.copy()
    ys, xs = np.nonzero(keep); cx, cy = float(xs.mean()), float(ys.mean())
    sx, sy = 1.0 - p.shrink_across_frac, 1.0 - p.shrink_along_frac
    M = np.array([[sx, 0, cx * (1 - sx)], [0, sy, cy * (1 - sy)]], np.float32)
    H, W = garment.shape
    warp = lambda a, interp: cv2.warpAffine(a, M, (W, H), flags=interp, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    g2 = warp(garment.astype(np.uint8), cv2.INTER_NEAREST) > 0
    r2 = warp(removed.astype(np.uint8), cv2.INTER_NEAREST) > 0
    im2 = warp(img, cv2.INTER_LINEAR)
    bg = backdrop_fill(img, garment, garment)          # whole old garment footprint replaced by backdrop texture
    out = bg.copy(); out[g2] = im2[g2]                 # shrunk garment composited on top
    return out, g2, r2

def _colour(img, garment, p):
    if p.lightness_shift == 0 and p.chroma_scale == 1: return img.copy()
    lab = cv2.cvtColor(img.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    lab[..., 0][garment] = np.clip(lab[..., 0][garment] + p.lightness_shift, 0, 100)
    lab[..., 1][garment] *= p.chroma_scale; lab[..., 2][garment] *= p.chroma_scale
    out = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR) * 255.0, 0, 255).astype(np.uint8)
    res = img.copy(); res[garment] = out[garment]; return res

def _hem_roll(img, garment, removed, mm_per_px, p):
    """Shading strip on the kept fabric within hem_roll_mm of the cut: shadow (dark) at the edge rising to a lit crest."""
    if p.hem_roll_mm <= 0 or p.roll_strength <= 0 or not removed.any(): return img.copy(), np.zeros_like(garment)
    kept = garment & ~removed
    d_in = cv2.distanceTransform((~removed).astype(np.uint8), cv2.DIST_L2, 5)     # distance to the cut, inside fabric
    D = max(p.hem_roll_mm / mm_per_px, 1.0)
    band = kept & (d_in <= D)
    if not band.any(): return img.copy(), band
    t = d_in[band] / D                                 # 0 at the cut, 1 at the strip's inner edge
    # curl profile: darkest just inside the edge, a lit crest around t~0.55, back to neutral at t=1
    shade = -p.roll_strength * np.exp(-((t - 0.15) / 0.18) ** 2) + 0.45 * p.roll_strength * np.exp(-((t - 0.55) / 0.15) ** 2)
    lab = cv2.cvtColor(img.astype(np.float32) / 255.0, cv2.COLOR_BGR2LAB)
    L = lab[..., 0]; L[band] = np.clip(L[band] * (1 + shade), 0, 100); lab[..., 0] = L
    out = np.clip(cv2.cvtColor(lab, cv2.COLOR_LAB2BGR) * 255.0, 0, 255).astype(np.uint8)
    res = img.copy(); res[band] = out[band]; return res, band

def apply_wash(img, garment, removed, mm_per_px, p=PRESETS["median"]):
    """Return (image, garment_mask, removed_mask, changed_mask) after one wash. `removed` is the cut-away region
    (already backdrop-filled in `img`); it is shrunk with the garment so the fringe renderer sees the new edge."""
    garment = np.asarray(garment, bool); removed = np.asarray(removed, bool)
    out, g2, r2 = _shrink(img, garment, removed, p)
    out = _colour(out, g2 & ~r2, p)
    out, band = _hem_roll(out, g2, r2, mm_per_px, p)
    changed = np.any(out != img, axis=2)
    return out, g2, r2, changed

def wash_three(img, garment, removed, mm_per_px, seed=0):
    return {k: apply_wash(img, garment, removed, mm_per_px, WashParams(**{**p.__dict__, "seed": seed})) for k, p in PRESETS.items() if k != "none"}

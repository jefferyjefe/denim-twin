"""2D baseline (plan Phase 2): cut in canonical space, warp back, touch nothing else."""
import numpy as np, cv2
from .landmarks import inseam_fraction_to_canonical_y

def cut_mask_canon(canon_size, inseam_fraction=None, canon_y=None):
    """Boolean mask (H, W) of canonical pixels to REMOVE: everything below the cut line."""
    W, H = canon_size
    if canon_y is None:
        canon_y = inseam_fraction_to_canonical_y(inseam_fraction) * H
    m = np.zeros((H, W), bool); m[int(round(canon_y)):] = True
    return m

def apply_cut(image, garment_mask, cmap, remove_canon_mask, background_fill=None):
    """Return (out_image, removed_mask_image, keep_mask_image).
    Pixels in removed region are replaced by background (median of non-garment pixels
    unless background_fill given). All other pixels are byte-identical to the input."""
    gm = garment_mask.astype(bool)
    rows = np.nonzero(remove_canon_mask.any(axis=1))[0]
    if len(rows) == 0:
        removed = np.zeros_like(gm)
    else:
        canon_y = float(rows.min())
        ys, xs = np.nonzero(gm)
        pts = np.stack([xs, ys], 1).astype(np.float32)
        cy = np.empty(len(pts), np.float32)
        for i in range(0, len(pts), 200_000):
            cy[i:i + 200_000] = cmap.points_to_canon(pts[i:i + 200_000])[:, 1]
        removed = np.zeros_like(gm); removed[ys, xs] = cy >= canon_y   # works for pixels outside the raster too
    out = image.copy()
    if background_fill is None:
        # inpaint the removed region from the surrounding background (Telea) instead of a flat median colour, so the
        # cut-away area looks like the floor/backdrop. Metrics never read these pixels (they use masks).
        out = backdrop_fill(image, gm, removed)
    else:
        out[removed] = background_fill
    keep = garment_mask.astype(bool) & ~removed
    return out, removed, keep

def cut_mask_canon_angled(canon_size, inner_frac, outer_frac):
    """Angled cut: per leg, a straight line from the inseam side at `inner_frac` (crotch->hem, 0..1)
    to the outseam side at `outer_frac`; mirrored for the two legs. Returns removal mask (H, W)."""
    from .landmarks import CANONICAL, inseam_fraction_to_canonical_y
    W, H = canon_size
    yi = inseam_fraction_to_canonical_y(inner_frac) * H; yo = inseam_fraction_to_canonical_y(outer_frac) * H
    xi, xo = CANONICAL["knee_left_inner"][0] * W, CANONICAL["knee_left_outer"][0] * W
    xs = np.arange(W, dtype=float)
    xl = np.minimum(xs, W - 1 - xs)                       # distance-from-edge coordinate, mirrored
    t = np.clip((xl - xo) / (xi - xo), -0.5, 1.5)          # 0 at outer edge, 1 at inner edge (extrapolate a bit)
    ycut = yo + t * (yi - yo)
    m = np.arange(H)[:, None] >= ycut[None, :]
    return m

def backdrop_fill(image, garment_mask, removed):
    """Fill `removed` with background texture only: inpaint the WHOLE garment from the surrounding backdrop
    (so no fabric colour can bleed in), then composite the kept garment back. Metrics never read these pixels."""
    gm = garment_mask.astype(np.uint8)
    big = cv2.dilate(gm, np.ones((7, 7), np.uint8))
    small = cv2.resize(image, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA); msmall = cv2.resize(big, (small.shape[1], small.shape[0]), interpolation=cv2.INTER_NEAREST)
    bg_small = cv2.inpaint(small, msmall, 9, cv2.INPAINT_TELEA)                     # half-res for speed on large garments
    bg = cv2.resize(bg_small, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_LINEAR)
    out = image.copy(); out[removed] = bg[removed]; return out

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


def texture_backdrop_fill(image, garment_mask, removed, patch=48, seed=0):
    """Backdrop fill for PRESENTATION renders: tile random background patches over `removed`, then blend.
    `backdrop_fill` (diffusion inpaint) is what metrics see — it is deterministic and never invents texture;
    on a patterned backdrop (carpet, wood) it produces a flat grey blob that reads as a rendering error to a viewer.
    Never used in scoring: the evaluation masks exclude these pixels."""
    gm = np.asarray(garment_mask, bool); rm = np.asarray(removed, bool)
    base = backdrop_fill(image, gm, rm)
    bgm = ~cv2.dilate(gm.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool)
    if not rm.any() or bgm.sum() < 4 * patch * patch: return base
    ys, xs = np.nonzero(bgm); H, W = rm.shape; rng = np.random.default_rng(seed)
    # candidate patch origins fully inside the background
    ok = [(y, x) for y, x in zip(ys[::37], xs[::37]) if y + patch < H and x + patch < W and bgm[y:y + patch, x:x + patch].all()]
    if len(ok) < 4: return base
    y0, y1 = np.nonzero(rm.any(axis=1))[0][[0, -1]]; x0, x1 = np.nonzero(rm.any(axis=0))[0][[0, -1]]
    out = base.copy()
    step = patch // 2
    for yy in range(y0 - step, y1 + 1, step):
        for xx in range(x0 - step, x1 + 1, step):
            sy, sx = ok[int(rng.integers(len(ok)))]
            th, tw = min(patch, H - max(yy, 0)), min(patch, W - max(xx, 0))
            if th < 4 or tw < 4: continue
            dy, dx = max(yy, 0), max(xx, 0)
            src = image[sy:sy + th, sx:sx + tw].astype(np.float32)
            # cosine window so tiles cross-fade instead of showing seams
            wy = np.hanning(max(th, 3))[:th][:, None]; wx = np.hanning(max(tw, 3))[:tw][None, :]
            wgt = np.clip(wy * wx, 0.02, 1)[..., None]
            dst = out[dy:dy + th, dx:dx + tw].astype(np.float32)
            out[dy:dy + th, dx:dx + tw] = np.clip(dst * (1 - wgt) + src * wgt, 0, 255).astype(np.uint8)
    res = image.copy(); res[rm] = out[rm]                      # only the removed region is touched
    return res

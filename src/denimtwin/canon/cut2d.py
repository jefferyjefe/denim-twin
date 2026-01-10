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
        bg = image[~garment_mask.astype(bool)]
        background_fill = np.median(bg, axis=0) if len(bg) else np.array([0, 0, 0])
    out[removed] = background_fill
    keep = garment_mask.astype(bool) & ~removed
    return out, removed, keep

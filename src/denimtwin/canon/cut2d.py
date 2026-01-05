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
    canon = (remove_canon_mask * 255).astype(np.uint8)
    removed = cmap.canon_to_image(canon, image.shape) > 127
    removed &= garment_mask.astype(bool)
    out = image.copy()
    if background_fill is None:
        bg = image[~garment_mask.astype(bool)]
        background_fill = np.median(bg, axis=0) if len(bg) else np.array([0, 0, 0])
    out[removed] = background_fill
    keep = garment_mask.astype(bool) & ~removed
    return out, removed, keep

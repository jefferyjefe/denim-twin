"""Review 4 — `texture_backdrop_fill`'s invented pixels ARE read by the scoring code.

src/denimtwin/canon/cut2d.py:64-68 docstring: "Never used in scoring: the evaluation masks exclude these
pixels." tools/predict.py:114 comments the same ("presentation fill; scoring never reads these pixels").
Both are false: tools/compare.py:56-60 builds the edge band as
    band = ((keep & d_in<=band_px) | (~keep & d_out<=band_px)) & garment_before & (rmask | sil)
whose `~keep` half lies inside `removed`, i.e. exactly the invented patches, and scores
ssim_edge_band_vs_real / dE_edge_band_vs_real there. eval/identity.cut_region_similarity:78 scores the
whole `removed` region outright. EXP_0014 scored predict.py's renders with compare.py; on those artefacts
(experiments/pairs_predict/*/cmp) up to 9.9% of the band (13 217 px on f542c57cec) is invented texture.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut, backdrop_fill, texture_backdrop_fill
from denimtwin.eval import identity as I


def _scene():
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    rng = np.random.default_rng(1)
    bg = np.clip(180 + cv2.GaussianBlur(rng.normal(0, 60, img.shape).astype(np.float32), (0, 0), 2.0), 0, 255).astype(np.uint8)
    scene = np.where(mask[..., None], img, bg)
    _, removed, keep = apply_cut(scene, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    return scene, bg, mask, removed, keep


def test_invented_backdrop_is_outside_every_scored_mask():
    """observed: 4080 of the 68018 band pixels are invented texture, and the scored metric moves with the
    RNG seed alone: dE_edge_band 0.5161 (seed 0) vs 0.5027 (seed 7), cut_region_similarity 0.6943 vs 0.6905.
    expected: 0 invented pixels inside any scored mask."""
    scene, bg, mask, removed, keep = _scene()
    flat = backdrop_fill(scene, mask, removed)
    tex = texture_backdrop_fill(scene, mask, removed, seed=0)
    invented = removed & np.any(tex != flat, axis=2)
    assert invented.any(), "the presentation fill must actually invent something for this test to mean anything"
    # the real after-garment reaches a little below our predicted cut, as it does on every found pair
    d_out = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 3)
    d_in = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3)
    rmask = keep | (removed & (d_out <= 15)); sil = keep; garment_before = keep | removed
    band = ((keep & (d_in <= 40)) | (~keep & (d_out <= 40))) & garment_before & (rmask | sil)   # tools/compare.py:58
    assert not (band & invented).any(), \
        f"{int((band & invented).sum())} of {int(band.sum())} scored edge-band pixels are invented backdrop texture"


def test_scored_edge_band_is_independent_of_the_presentation_seed():
    """A scored number must not depend on the RNG seed of a presentation-only fill.
    observed: dE_edge_band_vs_real 0.5161 (seed 0) vs 0.5027 (seed 7)."""
    scene, bg, mask, removed, keep = _scene()
    real = np.where(removed[..., None], bg, scene)
    d_out = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 3)
    d_in = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3)
    rmask = keep | (removed & (d_out <= 15)); sil = keep; garment_before = keep | removed
    band = ((keep & (d_in <= 40)) | (~keep & (d_out <= 40))) & garment_before & (rmask | sil)
    a = I.unchanged_color_delta_e(texture_backdrop_fill(scene, mask, removed, seed=0), real, band)
    b = I.unchanged_color_delta_e(texture_backdrop_fill(scene, mask, removed, seed=7), real, band)
    assert a == b, f"dE_edge_band_vs_real depends on the presentation seed: {a:.4f} (seed 0) vs {b:.4f} (seed 7)"

#!/usr/bin/env python3
"""Score a prediction against the real after-capture, in the before-image frame.

Usage: compare.py --before B.jpg --before-lm B.json --pred PRED.png --keep KEEP.png --removed REMOVED.png \
                  --after A.jpg --after-lm A.json [--after-mask M.png] [--mm-per-px 0.34] --out DIR
Writes DIR/{real_registered.png, real_mask.png, metrics.json, metrics.md} including null baselines
(no-op, crop-only) so a gamed metric is visible. Also writes DIR/{orig,pred,keep_mask,real}.png for
tools/null_baselines.py and tools/judge_pairs.py."""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.canon.register import warp_after_to_before
from denimtwin.eval import identity as I, geometry as G

p = argparse.ArgumentParser()
for k in ("before", "before-lm", "pred", "keep", "removed", "after", "after-lm"): p.add_argument("--" + k, required=True)
p.add_argument("--after-mask"); p.add_argument("--after-mask-native", help="the after mask AS SEGMENTED, before uprighting or registration: hem texture is measured on this one (EXP_0024)"); p.add_argument("--pred-mask", help="predicted garment mask incl. fringe (default: keep)"); p.add_argument("--mm-per-px", type=float); p.add_argument("--out", required=True)
a = p.parse_args(); os.makedirs(a.out, exist_ok=True)
before = cv2.imread(a.before); pred = cv2.imread(a.pred); after = cv2.imread(a.after)
keep = cv2.imread(a.keep, 0) > 127; removed = cv2.imread(a.removed, 0) > 127
lmb = json.load(open(a.before_lm))["landmarks"]; lma = json.load(open(a.after_lm))["landmarks"]
if a.after_mask: amask = cv2.imread(a.after_mask, 0) > 127
else:
    from denimtwin.seg.sam import SamSegmenter
    amask, _ = SamSegmenter().segment(after, landmarks={**lma, **{k: lma.get(k, v) for k, v in lma.items()}}) if all(k in lma for k in ("hem_left_outer",)) else (None, None)
    if amask is None:
        g = cv2.cvtColor(after, cv2.COLOR_BGR2GRAY); amask = np.abs(g.astype(int) - np.median(g[:8])) > 40
# the after mask as segmented (no upright, no registration): the only mask hem TEXTURE may be measured on (EXP_0024)
NATIVE = (cv2.imread(a.after_mask_native, 0) > 127) if (a.after_mask_native and os.path.exists(a.after_mask_native)) else None
def _native_waist(m):
    from denimtwin.canon.autolm import landmarks_from_mask
    _lm, _ = landmarks_from_mask(m)
    return float(_lm["waist_right"][0] - _lm["waist_left"][0]) if "waist_left" in _lm else None
real, rmask, resid = warp_after_to_before(after, amask, lma, lmb, before.shape)
p.add_argument  # (no-op; keeps linters quiet)
real_raw = real.copy()
real = I.match_lighting(real, before, keep & rmask)      # normalise lighting on the unchanged region before scoring
garment_before = keep | removed
pm = (cv2.imread(a.pred_mask, 0) > 127) if a.pred_mask else keep   # predicted post-cut silhouette incl. fringe
bg = np.median(before[~garment_before], axis=0).astype(np.uint8) if (~garment_before).any() else np.zeros(3, np.uint8)
systems = {"prediction": (pred, pm), "null:no-op": (before, garment_before),
           "null:crop-only": (np.where(keep[..., None], before, bg), keep)}
band_px0 = int(15 / a.mm_per_px) if a.mm_per_px else 40
_dk = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3)
rows = []
for name, (im, sil) in systems.items():
    r = dict(system=name,
             sil_iou_vs_real=G.silhouette_iou(sil, rmask),
             sil_chamfer=G.boundary_chamfer(G.mask_boundary(sil), G.mask_boundary(rmask), a.mm_per_px),
             hem_chamfer=G.hem_chamfer(sil, rmask, keep, garment_before, a.mm_per_px),
             ssim_keep_vs_real=I.unchanged_ssim(im, real, keep & rmask),
             dE_keep_vs_real=I.unchanged_color_delta_e(im, real, keep & rmask),
             feat_ret_keep_vs_real=I.feature_retention(im, real, keep & rmask),
             ssim_keep_vs_before=I.unchanged_ssim(im, before, keep))
    # §6.2 / EXP_0013: identity judged AFTER a bounded affine alignment, so a legitimate global shrink (wash) is not
    # scored as identity loss. `ssim_keep_vs_before` above stays as the strict pixel-copy check for --wash none.
    ali = I.aligned_identity(im, sil & keep, before, keep, ref_mask=garment_before)
    r["ssim_keep_vs_before_aligned"] = ali["ssim"]; r["feat_ret_keep_vs_before_aligned"] = ali["feat_ret"]
    r["align_scale"] = ali["align"]["scale"]
    # edge-region appearance: band within ±15 mm (or 40 px) of the cut edge, BOTH sides, where either the
    # real or the predicted garment exists (so fringe pixels count). Also report plain SSIM there.
    band_px = int(15 / a.mm_per_px) if a.mm_per_px else 40
    d_in = cv2.distanceTransform(keep.astype(np.uint8), cv2.DIST_L2, 3); d_out = cv2.distanceTransform((~keep).astype(np.uint8), cv2.DIST_L2, 3)
    band = ((keep & (d_in <= band_px)) | (~keep & (d_out <= band_px))) & garment_before & (rmask | sil)
    r["ssim_edge_band_vs_real"] = I.unchanged_ssim(im, real, band) if band.sum() > 500 else float("nan")
    r["dE_edge_band_vs_real"] = I.unchanged_color_delta_e(im, real, band) if band.sum() > 500 else float("nan")
    # §6.3: hem roughness — the only fray observable that passes a negative control (EXP_0016). A crop-only null
    # has a perfectly smooth hem, so this is where a fringe renderer must show up if it is doing anything real.
    from denimtwin.eval.hem_texture import hem_roughness
    _ww = abs(lmb["waist_right"][0] - lmb["waist_left"][0]) if all(k in lmb for k in ("waist_left", "waist_right")) else None
    # `rmask` is the real after-mask WARPED into the before frame (compare.py:28), so its hem boundary has been
    # resampled and its roughness includes the resampler's staircase — EXP_0024: a rotation alone makes 12 of 12
    # finished-hem controls read as frayed. `sil` is synthesised in this frame and carries no such artefact, so the
    # comparison is biased toward whichever system renders SOME roughness. Marked, not silently dropped.
    _hp = hem_roughness(sil, waist_px=_ww); _hr = hem_roughness(rmask, waist_px=_ww, resampled=True)
    # a refused measurement (broken mask) is UNKNOWN, not zero: reporting 0.0 would read as "this hem is smooth"
    # Compare roughness RELATIVE to waist width: the same fray photographed twice as large doubles the pixel value,
    # so a pixel-space error ranks photo size (review 6, finding on scale). `rough_fraction` accompanies it because a
    # p90 of 0 only means "fewer than 10% of hem columns deviate", not "smooth".
    r["hem_rough_p90_pred"] = _hp["p90_px"] if _hp["ok"] else float("nan")
    r["hem_rough_p90_real"] = _hr["p90_px"] if _hr["ok"] else float("nan")
    r["hem_rough_rel_pred"] = _hp.get("p90_rel", float("nan")) if _hp["ok"] else float("nan")
    r["hem_rough_rel_real"] = _hr.get("p90_rel", float("nan")) if _hr["ok"] else float("nan")
    r["hem_rough_frac_pred"] = _hp["rough_fraction"] if _hp["ok"] else float("nan")
    r["hem_rough_frac_real"] = _hr["rough_fraction"] if _hr["ok"] else float("nan")
    r["hem_rough_real_is_resampled"] = True          # see above; the real mask is registered into the before frame
    r["hem_rough_valid_for_fray"] = False
    # The comparison that IS valid: both sides measured on a boundary nothing has resampled, and compared as a
    # fraction of waist width, which is what p90_rel is for. The prediction's hem is drawn synthetically in its own
    # frame; the real hem comes straight out of segmentation. Neither carries a resampling staircase.
    if NATIVE is not None:
        _wn = _native_waist(NATIVE) or _ww
        _hn = hem_roughness(NATIVE, waist_px=_wn)
        r["hem_rough_rel_real_native"] = _hn.get("p90_rel", float("nan")) if _hn["ok"] else float("nan")
        r["hem_rough_frac_real_native"] = _hn["rough_fraction"] if _hn["ok"] else float("nan")
        r["hem_rough_rel_err_native"] = (abs(r["hem_rough_rel_pred"] - r["hem_rough_rel_real_native"])
                                         if r["hem_rough_rel_pred"] == r["hem_rough_rel_pred"]
                                         and r["hem_rough_rel_real_native"] == r["hem_rough_rel_real_native"] else float("nan"))
        r["hem_rough_native_valid_for_fray"] = bool(_hn["ok"] and _hn.get("valid_for_fray"))
    r["hem_rough_err_rel"] = abs(r["hem_rough_rel_pred"] - r["hem_rough_rel_real"]) if (_hp["ok"] and _hr["ok"]) else float("nan")
    r["hem_rough_err_px"] = abs(r["hem_rough_p90_pred"] - r["hem_rough_p90_real"]) if (_hp["ok"] and _hr["ok"]) else float("nan")
    r["hem_rough_refused"] = (not _hp["ok"]) or (not _hr["ok"])
    r["fringe_iou_vs_real"] = G.fringe_iou(sil, rmask, keep, garment_before)
    r["fringe_profile_dist"] = G.fringe_profile_distance_masks(sil, rmask, keep, garment_before)
    rows.append(r)
cols = list(rows[0]); md = f"registration residual (leave-one-landmark-out): {resid:.2f} px; lighting matched on kept region\n\n| " + " | ".join(cols) + " |\n|" + "---|" * len(cols) + "\n"
for r in rows: md += "| " + " | ".join(r[c] if isinstance(r[c], str) else f"{r[c]:.4f}" for c in cols) + " |\n"
unit = "mm" if a.mm_per_px else "px"; md += f"\n(hem_chamfer in {unit})\n"
json.dump(dict(registration_residual_px=resid, rows=rows), open(f"{a.out}/metrics.json", "w"), indent=1)
open(f"{a.out}/metrics.md", "w").write(md); print(md)
cv2.imwrite(f"{a.out}/real_registered.png", real); cv2.imwrite(f"{a.out}/real_registered_raw.png", real_raw); cv2.imwrite(f"{a.out}/real_mask.png", rmask.astype(np.uint8) * 255)
cv2.imwrite(f"{a.out}/orig.png", before); cv2.imwrite(f"{a.out}/pred.png", pred); cv2.imwrite(f"{a.out}/keep_mask.png", keep.astype(np.uint8) * 255); cv2.imwrite(f"{a.out}/real.png", real); cv2.imwrite(f"{a.out}/removed_mask.png", removed.astype(np.uint8) * 255)

#!/usr/bin/env python3
"""One command per found/contributed pair: before + after images -> prediction, registration, scoring.

Usage: run_pair.py --before B.jpg --after A.jpg --out experiments/PAIR_x [--before-lm B.json] [--after-lm A.json]
                   [--mm-per-px 1.0] [--seed 1]
Landmarks default to the mask-based heuristic (canon/autolm.py); pass JSON files to override.
Writes: masks, landmarks (auto/used), cut, fringe predictions (3 presets), registered real, metrics for each preset
with null baselines, a panel.jpg, and NOTE.md."""
import argparse, json, os, sys, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse, segment_fringe
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon import upright as U
from denimtwin.canon.register import warp_after_to_before, SURVIVING
from denimtwin.canon.hemfit import estimate_hems, cut_mask_from_lines
from denimtwin.canon.cut2d import backdrop_fill
from denimtwin.canon.rawedge_v1 import render_three

p = argparse.ArgumentParser()
p.add_argument("--before", required=True); p.add_argument("--after", required=True); p.add_argument("--out", required=True)
p.add_argument("--before-lm"); p.add_argument("--after-lm"); p.add_argument("--mm-per-px", type=float, default=None); p.add_argument("--seed", type=int, default=1)
p.add_argument("--prior", help="data/priors/fringe.json: predict fringe depth from the prior (depth_rel_mean * waist width) instead of reading it off the after-photo")
p.add_argument("--exclude", help="pair id to EXCLUDE from the prior (leave-one-out: never let a pair predict itself)")
p.add_argument("--state", choices=["after_cut", "after_wash"], default="after_wash", help="what the after-photo shows; the fringe prior is conditional on it")
p.add_argument("--refine-landmarks", action="store_true", help="refine heuristic landmarks with template_v1 (boundary-Chamfer fit); experimental (EXP_0011)")
p.add_argument("--coin", help="coin type in the BEFORE photo (see util/coins.py); metric scale is recovered with the garment masked out")
p.add_argument("--seg", choices=["coarse", "consensus"], default="coarse",
               help="garment segmentation: 'coarse' takes SAM's best-scoring candidate; 'consensus' takes the object "
                    "the most prompt sets agree on and reports that agreement (EXP_0019)")
p.add_argument("--edge-treatment", choices=["raw", "cuffed", "hemmed", "serged", "hand_frayed"], default="raw",
               help="how the cut edge was finished; a finished hem does not fray, so no fringe is rendered (modification.expects_fringe)")
p.add_argument("--wash", choices=["none", "conservative", "median", "aggressive"], default="none", help="procedural wash appearance v0 (shrink + hem roll + colour; canon/wash.py). Default none keeps the bench unchanged")
p.add_argument("--cropped", default="", help="comma list of 'before'/'after' that were manually cropped: frame-edge contact becomes a flag, not a rejection")
p.add_argument("--upright-deadband", type=float, default=0.0,
               help="skip the upright rotation below this tilt (degrees). Was 8.0 until EXP_0022. The landmark "
                    "heuristic loses more than 5%% of every shape ratio at 1-8 degrees of tilt (EXP_0021), and the "
                    "principal-axis estimate tracks a known rotation to <=0.41 degrees in that band (EXP_0022), so "
                    "the old deadband skipped correction exactly where it was both needed and reliable. Pass 8.0 to "
                    "reproduce the pre-EXP_0022 baseline.")
a = p.parse_args(); os.makedirs(a.out, exist_ok=True); O = a.out
bf = cv2.imread(a.before); af = cv2.imread(a.after); assert bf is not None and af is not None
FLAGS = []
FAIL = lambda why: (print(f"REJECT: {why}"), open(f"{O}/NOTE.md", "w").write(f"# PAIR — rejected\n\n{why}\n"), sys.exit(3))

def split_collage(img):
    """Collage detection: a near-uniform bright gutter in the middle 35-65% of width (side-by-side -> keep LEFT panel)
    or of height (stacked -> keep TOP panel). Tutorials put the front view first."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32); h, w = g.shape
    def gutter(std, mean, n):
        lo, hi = int(0.35 * n), int(0.65 * n); cand = [i for i in range(lo, hi) if std[i] < 12 and mean[i] > 150]
        return int(np.median(cand)) if len(cand) >= 3 else None
    dark = (g < 120)
    x = gutter(g.std(axis=0), g.mean(axis=0), w)
    if x is not None and dark[:, :x].mean() > 0.03 and dark[:, x:].mean() > 0.03:      # a garment on BOTH sides
        return img[:, :max(x - int(0.01 * w), 10)], f"collage split (side-by-side) at x={x}, kept left"
    y = gutter(g.std(axis=1), g.mean(axis=1), h)
    if y is not None and dark[:y].mean() > 0.03 and dark[y:].mean() > 0.03:
        return img[:max(y - int(0.01 * h), 10)], f"collage split (stacked) at y={y}, kept top"
    return img, None
bf, note_b = split_collage(bf); af, note_a = split_collage(af)
cv2.imwrite(f"{O}/before_used.png", bf); cv2.imwrite(f"{O}/after_used.png", af)
BEFORE_PATH, AFTER_PATH = f"{O}/before_used.png", f"{O}/after_used.png"
seg = SamSegmenter()
# masks: first pass with a coarse box (whole image minus margins), then refine with auto landmarks
def coarse(img):
    if a.seg == "consensus":
        from denimtwin.seg.validate import segment_garment_consensus
        m, agr, info = segment_garment_consensus(seg, img, boundary="member")
        if m is None: print(f"consensus segmentation refused: {info.get('reason')}"); sys.exit(2)
        FLAGS.append(f"segmentation by consensus: {agr:.0%} of prompt sets agree, area {info['area']:.2f}")
        print(f"consensus mask agreement {agr:.2f} area {info['area']:.2f}"); return m
    m, sc, info = segment_garment_coarse(seg, img)
    if m is None: print("coarse segmentation failed"); sys.exit(2)
    print(f"coarse mask score {sc:.3f} area {info['area']:.2f} border {info['border_frac']:.2f}"); return m
def upright(img, mask, name):
    """Rotate image+mask so the garment is upright (canon/upright.py — one implementation, shared with predict.py)."""
    img2, mask2, ang = U.upright(img, mask, deadband=a.upright_deadband)
    if ang:
        FLAGS.append(f"{name}: rotated {ang:.1f}° to upright")
        if U.unreliable(ang, U.tilt_angle(mask)[1]):
            FLAGS.append(f"{name}: tilt {ang:.1f}° estimated from a near-isotropic silhouette — the principal-axis "
                         "estimate is off by up to 4.7° there (EXP_0022) and the correction may be several degrees out")
    return img2, mask2, ang
bf_pre_rot, af_pre_rot = bf, af
# the photographs as they came in, before uprighting. `before_used.png` is overwritten with the uprighted version
# later, and anything that re-runs a segmenter on THAT is correcting an already-corrected image (EXP_0028).
cv2.imwrite(f"{O}/before_native.png", bf); cv2.imwrite(f"{O}/after_native.png", af)
bmask = coarse(bf); amask = coarse(af)
# The after mask AS SEGMENTED, before any rotation. Hem texture must be measured on it and not on the registered
# copy: a warp alone makes 12 of 12 finished-hem controls read as frayed (EXP_0024).
amask_native = amask.copy()
bf, bmask, rot_b = upright(bf, bmask, "before"); af, amask, rot_a = upright(af, amask, "after")
def _xform(lm, note, rot, shape_before, shape_after):
    """Manual landmarks were clicked on the ORIGINAL photo: apply the collage crop (left/top panel: offset 0) and the upright rotation."""
    if not lm: return lm
    if rot:
        h0, w0 = shape_before[:2]; M = cv2.getRotationMatrix2D((w0 / 2, h0 / 2), -rot, 1.0)
        cos, sin = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(h0 * sin + w0 * cos), int(h0 * cos + w0 * sin); M[0, 2] += nw / 2 - w0 / 2; M[1, 2] += nh / 2 - h0 / 2
        lm = {k: tuple(float(v) for v in (M @ np.array([x, y, 1.0]))) for k, (x, y) in lm.items()}
    return lm
def _snap(lm, mask, r=8):
    if not lm: return lm
    ys, xs = np.nonzero(mask); pts = np.stack([xs, ys], 1); out = {}
    for k, (x, y) in lm.items():
        if 0 <= int(y) < mask.shape[0] and 0 <= int(x) < mask.shape[1] and mask[int(y), int(x)]: out[k] = (x, y); continue
        d = np.hypot(pts[:, 0] - x, pts[:, 1] - y); i = int(np.argmin(d)); out[k] = (float(pts[i, 0]), float(pts[i, 1])) if d[i] <= r else (x, y)
    return out
SHAPE_B0, SHAPE_A0 = bf_pre_rot.shape, af_pre_rot.shape
cv2.imwrite(f"{O}/before_used.png", bf); cv2.imwrite(f"{O}/after_used.png", af)
CROPPED = set(x.strip() for x in a.cropped.split(",") if x.strip())
def sane(mask, name):
    h, w = mask.shape; ys, xs = np.nonzero(mask)
    if mask.mean() < 0.02: FAIL(f"{name}: garment too small ({mask.mean():.2f} of frame)")   # 2%: small garment on a big rug is still fine
    manual = name.split()[0] in CROPPED
    edge = (xs.min() <= 2) or (xs.max() >= w - 3) or (ys.min() <= 2); bottom = ys.max() >= h - 3
    if manual and (edge or bottom): FLAGS.append(f"{name}: touches the edge of a MANUAL crop (second object removed from frame)"); return
    if edge: FAIL(f"{name}: garment touches the frame edge (cropped photo)")
    if bottom:
        if name.startswith("before"): FLAGS.append(f"{name}: legs reach the frame bottom — original hem unknown; cut expressed vs frame, not inseam")
        else: FAIL(f"{name}: garment touches the frame bottom (cropped photo)")
    if (ys.max() - ys.min()) < 0.25 * h: FAIL(f"{name}: garment too short in frame")
    # a whole garment has ONE waistband run near the top; two runs = a cropped pair of legs
    k = max(int(0.03 * w), 3); mo = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8)).astype(bool)   # drop hanger hooks/clips
    if mo.sum() < 0.5 * mask.sum(): mo = mask
    ys2 = np.nonzero(mo)[0]; top, hh = ys2.min(), ys2.max() - ys2.min(); band = range(top, top + int(0.15 * hh))
    widths = [(mo[y].sum(), y) for y in band]; yt = max(widths)[1]; row = np.nonzero(mo[yt])[0]
    if len(row) and (np.diff(row) > 5).sum() >= 1: FAIL(f"{name}: widest top row is not a single waistband run (legs-only crop?)")
sane(bmask, "before"); sane(amask, "after")
try:
    from denimtwin.seg.clipgate import whole_garment_probability
    pw = whole_garment_probability(bf)
    print(f"clip whole-garment p={pw}")   # informational only: CLIP scores a hanging whole pair 0.27 and a legs-only crop 0.36 (EXP_0005) — not a usable gate
except SystemExit: raise
except Exception as e: print("clip gate skipped:", e)
lmb_auto, cb = landmarks_from_mask(bmask); lma_auto, ca = landmarks_from_mask(amask)
if a.refine_landmarks and len(lmb_auto) >= 14:
    from denimtwin.canon.template_v1 import fit as _v1fit
    try: lmb_auto, _r, _ = _v1fit(bmask, lmb_auto); print(f"template_v1 refine (before): boundary resid {_r:.2f}px")
    except Exception as e: print("template_v1 refine skipped:", e)
lmb = _snap(_xform(json.load(open(a.before_lm))["landmarks"], note_b, rot_b, SHAPE_B0, bf.shape), bmask) if a.before_lm else lmb_auto
lma = _snap(_xform(json.load(open(a.after_lm))["landmarks"], note_a, rot_a, SHAPE_A0, af.shape), amask) if a.after_lm else lma_auto
if (a.before_lm and note_b) or (a.after_lm and note_a): FLAGS.append("manual landmarks + collage split: landmarks assumed to be in the kept (left/top) panel's frame")
if not a.before_lm and len(lmb) >= 14:
    bmask, _ = seg.segment(bf, landmarks=lmb)          # refine with landmark prompts (landmarks stay from the coarse mask:
    sane(bmask, "before (refined)")                    #  recomputing them on the refined mask regressed pair1 — see EXP_0004)
if a.coin and a.mm_per_px is None:
    cv2.imwrite(f"{O}/bmask.png", bmask.astype(np.uint8) * 255)
    r_ = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "scale_from_coin.py"), BEFORE_PATH, "--coin", a.coin, "--mask", f"{O}/bmask.png"], capture_output=True, text=True)
    try: d_ = json.loads(r_.stdout)
    except Exception: d_ = {}
    if r_.returncode == 0 and d_.get("accepted"): a.mm_per_px = d_["mm_per_px"]; FLAGS.append(f"scale from coin ({a.coin}): {a.mm_per_px:.4f} mm/px, edge support {d_['edge_support']:.2f}")
    else: FLAGS.append(f"coin scale rejected: {d_.get('reject_reason') or d_.get('error') or 'no result'}")
json.dump({"before_auto": lmb_auto, "after_auto": lma_auto, "before_used": lmb, "after_used": lma, "conf": {"before": cb, "after": ca}}, open(f"{O}/landmarks.json", "w"), indent=1, default=int)
mmpp = a.mm_per_px or 1.0; scale_note = "given" if a.mm_per_px else "UNKNOWN (1.0 placeholder; mm values are px)"
use = [n for n in SURVIVING if n in lma and n in lmb]
if not a.after_lm: use = [n for n in use if not n.startswith("knee")]     # auto knees on a cut garment are meaningless
real, rmask, resid = warp_after_to_before(af, amask, lma, lmb, bf.shape, use=use)
from denimtwin.modification import CutModification as _CM, WashProtocol as _WP
# A finished hem cannot fray, so a fringe mask on one is a segmentation error, not a measurement.
# This used to be computed AFTER estimate_hems and used only to suppress RENDERING, so a spurious
# SAM fringe on a cuffed garment still drove the hem fit -- which is what regressed 443d1d4658
# (EXP_0037): uprighting changed whether SAM produced a fringe mask at all, switching estimate_hems
# onto its fringe-mask branch and moving the fitted hem by 14 degrees on one leg.
_expects = _CM(inseam_fraction=0.5, edge_treatment=a.edge_treatment,
               wash=_WP(cycles=1 if a.state == "after_wash" else 0)).expects_fringe()
fr_after = segment_fringe(seg, af, amask); fr_before = None
if fr_after is not None and fr_after.sum() > 50:
    # plausibility: a fringe is a thin band. Median column depth (tip - first fringe row) must be < 15% of garment height,
    # otherwise SAM grabbed fabric (happens on clean hems and at high resolution) -> fall back to the mask/colour edge.
    rows_a = np.nonzero(amask.any(axis=1))[0]; gh_ = rows_a.max() - rows_a.min()
    dcols = [np.nonzero(amask[:, x])[0].max() - np.nonzero(fr_after[:, x])[0].min() for x in range(amask.shape[1]) if amask[:, x].any() and fr_after[:, x].any()]
    if dcols and np.median(dcols) > 0.15 * gh_: FLAGS.append(f"SAM fringe mask rejected: median depth {np.median(dcols):.0f}px > 15% of garment height {gh_}px"); fr_after = None
if fr_after is not None and fr_after.sum() > 50:
    _, fr_before, _ = warp_after_to_before(af, fr_after, lma, lmb, bf.shape, use=use); cv2.imwrite(f"{O}/fringe_mask.png", fr_before.astype(np.uint8) * 255)
legs = estimate_hems(rmask, bmask, lmb, real_img=real,
                     fringe_mask=fr_before if _expects else None)
if fr_before is not None and not _expects:
    FLAGS.append(f"fringe mask ignored for the hem fit: edge_treatment '{a.edge_treatment}' cannot fray")
fringe_src = "SAM" if fr_before is not None else "colour split"
if not all(legs.get(s) and legs[s]["line"] for s in ("left", "right")): FAIL("hem fit failed on at least one leg (refusing to cut one leg only)")
removed = cut_mask_from_lines(bmask, lmb, legs); keep = bmask & ~removed
rf = removed.sum() / max(bmask.sum(), 1)
if not (0.01 <= rf <= 0.75): FAIL(f"degenerate cut: removed fraction {rf:.2f}")   # 1%: a small hem trim is a valid cut
ov = (rmask & bmask).sum() / max(rmask.sum(), 1)
if ov < 0.6: FAIL(f"registration failed: only {ov:.2f} of the registered real garment lies inside the before garment")
if cb.get("garment_type") != "jeans": FLAGS.append("before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts")
bg = np.median(bf[~bmask], axis=0)
cut = backdrop_fill(bf, bmask, removed)   # backdrop-only inpainting, no fabric bleed
if a.wash != "none":                       # plan §4.7/4.8: the wash itself (shrinkage, hem roll, dye loss), before the fringe grows from the new edge
    from denimtwin.canon.wash import apply_wash, PRESETS as WASH_PRESETS
    cut, bmask_w, removed_w, wash_changed = apply_wash(cut, bmask, removed, mmpp, WASH_PRESETS[a.wash])
    FLAGS.append(f"wash preset {a.wash}: shrink {WASH_PRESETS[a.wash].shrink_along_frac:.1%} along / {WASH_PRESETS[a.wash].shrink_across_frac:.1%} across (PRIOR, not measured); {wash_changed.sum()} px changed")
    # the PREDICTION's silhouette shrinks with the wash; the SCORING masks must not. keep_mask/removed_mask define
    # `garment_before` in compare.py, which is what the null baselines are built from — if they moved with --wash,
    # the A/B would not be against a fixed reference (review 4, finding 5).
    bmask_pred, removed_pred = bmask_w, removed_w
    keep_pred = bmask_pred & ~removed_pred
depth_measured_px = np.mean([L["fringe_depth_px"] for L in legs.values() if L])
depth_after_frame = None
if fr_after is not None and fr_after.sum() > 50:                       # depth measured on the UN-WARPED after-photo, scaled by waist-width ratio
    ds = [np.nonzero(amask[:, x])[0].max() - np.nonzero(fr_after[:, x])[0].min() for x in range(amask.shape[1]) if amask[:, x].any() and fr_after[:, x].any()]
    if len(ds) >= 20:
        wwb = abs(lmb["waist_right"][0] - lmb["waist_left"][0]); wwa = abs(lma["waist_right"][0] - lma["waist_left"][0])
        depth_after_frame = float(np.median(ds)) * (wwb / max(wwa, 1))
        depth_measured_px = depth_after_frame                             # prefer the un-warped measurement
# Direct thread measurement on the un-warped after-photo. SAM's prompted "fringe" mask returns fabric, not threads,
# on real after-wash photos (EXP_0015: rel 0.10-0.61 vs 0.004-0.03 measured directly, confirmed by eye), so it is the
# fringe number of record now; the SAM/hem-fit value is kept alongside for comparison.
from denimtwin.eval.fringe_measure import measure_fringe_depth as _mfd
_wwa = abs(lma["waist_right"][0] - lma["waist_left"][0]); _wwb = abs(lmb["waist_right"][0] - lmb["waist_left"][0])
_direct = _mfd(af, amask, waist_px=_wwa)
depth_sam_px = depth_measured_px
depth_direct_px = float(_direct["median_px"]) * (_wwb / max(_wwa, 1)) if _direct["ok"] else None
if depth_direct_px is not None:
    depth_measured_px = depth_direct_px
    FLAGS.append(f"fringe measured directly: {_direct['median_px']:.1f}px in the after frame (rel {_direct.get('depth_rel', 0):.4f}, coverage {_direct['coverage']:.2f}); SAM/hem-fit said {depth_sam_px:.1f}px")
else:
    FLAGS.append(f"direct fringe measurement failed ({_direct['n_columns_with_fringe']} columns); falling back to the SAM/hem-fit value {depth_sam_px:.1f}px")
if a.prior:
    from denimtwin.prior import predict_depth_rel
    pr = json.load(open(a.prior)); ww = abs(lmb["waist_right"][0] - lmb["waist_left"][0])
    rel, n_eff, sd_rel_prior = predict_depth_rel(pr, a.state, a.exclude, os.path.join(os.path.dirname(__file__), '..', 'data/external/pairs.jsonl'))
    depth_px = rel * ww; depth_source = f"prior[{a.state}] (n={n_eff}{' after excluding self' if a.exclude else ''}{', INSUFFICIENT' if n_eff < 5 else ''})"
else:
    depth_px = depth_measured_px; depth_source = "measured from after-photo (NOT a prediction)"
if not _expects:
    FLAGS.append(f"no fringe rendered: edge_treatment '{a.edge_treatment}' with {'a wash' if a.state == 'after_wash' else 'no wash'} does not fray (EXP_0017)")
    depth_px = 0.0; depth_source += " [suppressed: finished hem]"
depth_mm = depth_px * mmpp
bmask_pred = locals().get("bmask_pred", bmask); removed_pred = locals().get("removed_pred", removed); keep_pred = locals().get("keep_pred", keep)
res = render_three(cut, removed_pred, bmask_pred, mmpp, seed=a.seed, depth_override={"conservative": depth_mm * 0.5, "median": depth_mm, "aggressive": depth_mm * 1.5})
for k, (im, ch) in res.items():
    cv2.imwrite(f"{O}/pred_{k}.png", im); cv2.imwrite(f"{O}/pred_{k}_mask.png", ((keep_pred | (ch & removed_pred)).astype(np.uint8) * 255))
for n, im in (("orig", bf), ("cut", cut), ("keep_mask", keep.astype(np.uint8) * 255), ("removed_mask", removed.astype(np.uint8) * 255), ("bmask", bmask.astype(np.uint8) * 255), ("amask", amask.astype(np.uint8) * 255), ("amask_native", amask_native.astype(np.uint8) * 255), ("real", real), ("real_mask", rmask.astype(np.uint8) * 255)):
    cv2.imwrite(f"{O}/{n}.png", im)
cv2.imwrite(f"{O}/pred.png", res["median"][0]); cv2.imwrite(f"{O}/diff.png", (np.any(res["median"][0] != bf, axis=2) & True).astype(np.uint8) * 255)   # plan §4.8: exactly which pixels changed
json.dump({"landmarks": lmb}, open(f"{O}/before_lm.json", "w")); json.dump({"landmarks": lma}, open(f"{O}/after_lm.json", "w"))
rows = {}
for k in res:
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "compare.py"), "--before", BEFORE_PATH, "--before-lm", f"{O}/before_lm.json", "--pred", f"{O}/pred_{k}.png", "--pred-mask", f"{O}/pred_{k}_mask.png",
                        "--keep", f"{O}/keep_mask.png", "--removed", f"{O}/removed_mask.png", "--after", AFTER_PATH, "--after-lm", f"{O}/after_lm.json", "--after-mask", f"{O}/amask.png", "--after-mask-native", f"{O}/amask_native.png", "--out", f"{O}/cmp_{k}"] + (["--mm-per-px", str(mmpp)] if a.mm_per_px else []), capture_output=True, text=True)
    rows[k] = json.load(open(f"{O}/cmp_{k}/metrics.json"))["rows"]
# panel
y0 = int(np.nonzero(removed)[0].min()) if removed.any() else bf.shape[0] // 2; H = bf.shape[0]
crop = lambda im: im[max(y0 - int(0.15 * H), 0): min(y0 + int(0.2 * H), H)]
tiles = [crop(bf), crop(res["median"][0]), crop(real)]
for t, n in zip(tiles, ("before", f"pred median (depth {depth_mm:.0f} {'mm' if a.mm_per_px else 'px'})", "real registered")): cv2.putText(t, n, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
cv2.imwrite(f"{O}/panel.jpg", np.concatenate(tiles, 1))
def row(name, r): return f"| {name} | {r['sil_iou_vs_real']:.3f} | {r['hem_chamfer']:.1f} | {r['dE_edge_band_vs_real']:.1f} | {r['fringe_iou_vs_real']:.3f} |"
md = f"# PAIR — auto pipeline\n\nflags: {'; '.join(FLAGS) or 'none'}\nbefore: {a.before} {note_b or ''}\nafter: {a.after} {note_a or ''}\nscale: {scale_note}\nlandmarks: {'manual' if a.before_lm else 'auto'} / {'manual' if a.after_lm else 'auto'} (crotch: {cb.get('crotch')} / {ca.get('crotch')})\n"
md += f"fringe depth used: {depth_px:.1f} px from {depth_source}; measured on after-photo: {depth_measured_px:.1f} px (fabric/fringe split: {fringe_src}; {'after-frame' if depth_after_frame is not None else 'registered-frame'})\n"
md += f"hem fit: " + ", ".join(f"{k}: angle {L['angle_deg']:.1f}°, depth {L['fringe_depth_px']:.0f} px" for k, L in legs.items() if L) + (f" (mm_per_px {mmpp:.4f})" if a.mm_per_px else "") + f"\nregistration residual (leave-one-landmark-out): {resid:.2f}px\n\n"
md += "| system | sil IoU | chamfer | edge ΔE | fringe IoU |\n|---|---|---|---|---|\n"
for k in res:
    for r in rows[k]:
        if r["system"] == "prediction": md += row(f"pred {k}", r) + "\n"
for r in rows["median"]:
    if r["system"] != "prediction": md += row(r["system"], r) + "\n"
from denimtwin.modification import CutModification, WashProtocol
mod = CutModification(cut_path_canonical=[[0.0, 0.0]], edge_treatment=a.edge_treatment, wash=WashProtocol(cycles=1 if a.state == "after_wash" else 0), seed=a.seed)
# `inseam_fraction` is defined in CANONICAL coordinates (see modification.py); measuring it in image y between the
# crotch and hem landmarks gave a different number — off by up to 0.21 of the leg on the found pairs, and negative
# (clipped to 0) on four of them (EXP_0014, finding 1). Map the fitted cut into canonical space instead.
from denimtwin.canon.warp import CanonicalMap as _CM
from denimtwin.canon.landmarks import inseam_fraction_to_canonical_y as _f2y
_cm = _CM(lmb)
_pts = np.array([(x, np.nonzero(removed[:, x])[0].min()) for x in range(removed.shape[1]) if removed[:, x].any()], np.float32)
_cy = _cm.points_to_canon(_pts)[:, 1] / _cm.H
_y0, _y1 = _f2y(0.0), _f2y(1.0)
mod.cut_path_canonical = None; mod.inseam_fraction = float(np.clip((float(np.median(_cy)) - _y0) / max(_y1 - _y0, 1e-6), 0.0, 1.0))
FLAGS.append(f"cut height (canonical inseam fraction): {mod.inseam_fraction:.3f}")
open(f"{O}/modification.json", "w").write(mod.to_json())
# plan §4.9: never imply certainty — emit a prediction interval for fringe depth (from the prior's spread when available)
interval = {"garment_id": os.path.basename(O), "stratum": a.state, "metric": "fringe_depth_px", "median": float(depth_px), "nominal": 0.8}
if a.prior:
    ww_ = abs(lmb["waist_right"][0] - lmb["waist_left"][0]); half = 1.28 * sd_rel_prior * ww_    # ~80% interval under a normal assumption; sd is LOO, per state
    interval.update(lo=max(0.0, float(depth_px - half)), hi=float(depth_px + half), real=float(depth_measured_px), source=f"prior sd (LOO, n={n_eff})")
else:
    interval.update(lo=float(depth_px * 0.5), hi=float(depth_px * 1.5), real=None, source="preset spread (not calibrated; real omitted because median IS the measurement)")
open(f"{O}/intervals.jsonl", "w").write(json.dumps(interval) + "\n")
json.dump({"state": a.state, "waist_px_before": float(_wwb), "waist_px_after": float(_wwa),
           "depth_direct_px_before_frame": depth_direct_px, "depth_direct_rel": (depth_direct_px / _wwb) if depth_direct_px else None,
           "direct_coverage": _direct["coverage"], "direct_ok": _direct["ok"],
           "depth_sam_hemfit_px": float(depth_sam_px), "depth_used_px": float(depth_px), "depth_source": depth_source},
          open(f"{O}/measure.json", "w"), indent=1)
open(f"{O}/NOTE.md", "w").write(md); print(md)

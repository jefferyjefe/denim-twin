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
p.add_argument("--cropped", default="", help="comma list of 'before'/'after' that were manually cropped: frame-edge contact becomes a flag, not a rejection")
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
    m, sc, info = segment_garment_coarse(seg, img)
    if m is None: print("coarse segmentation failed"); sys.exit(2)
    print(f"coarse mask score {sc:.3f} area {info['area']:.2f} border {info['border_frac']:.2f}"); return m
def upright(img, mask, name):
    """Rotate image+mask so the garment's principal axis is vertical (flat-lays are often photographed at an angle)."""
    ys, xs = np.nonzero(mask); pts = np.stack([xs, ys], 1).astype(np.float32); pts -= pts.mean(0)
    cov = pts.T @ pts / len(pts); w_, v_ = np.linalg.eigh(cov); major = v_[:, np.argmax(w_)]
    ang = np.degrees(np.arctan2(major[0], major[1]))          # angle of the long axis from vertical
    ang = (ang + 90) % 180 - 90
    elong = float(np.sqrt(w_.max() / max(w_.min(), 1e-6)))     # major/minor extent ratio: jeans ≈ 2–3, shorts ≈ 1
    cap = 80 if elong > 1.8 else 30                                # elongated garment: any tilt is a tilt; squat garment: only modest tilts
    if abs(ang) < 8 or abs(ang) > cap: return img, mask, 0.0
    h, w = img.shape[:2]; M = cv2.getRotationMatrix2D((w / 2, h / 2), -ang, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(h * sin + w * cos), int(h * cos + w * sin); M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
    bgc = tuple(int(c) for c in np.median(img[~mask], axis=0)) if (~mask).any() else (128, 128, 128)
    FLAGS.append(f"{name}: rotated {ang:.1f}° to upright"); return cv2.warpAffine(img, M, (nw, nh), borderValue=bgc), cv2.warpAffine(mask.astype(np.uint8), M, (nw, nh)) > 0, ang
bmask = coarse(bf); amask = coarse(af)
bf, bmask, _ = upright(bf, bmask, "before"); af, amask, _ = upright(af, amask, "after")
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
lmb = json.load(open(a.before_lm))["landmarks"] if a.before_lm else lmb_auto
lma = json.load(open(a.after_lm))["landmarks"] if a.after_lm else lma_auto
if not a.before_lm and len(lmb) >= 14:
    bmask, _ = seg.segment(bf, landmarks=lmb)          # refine with landmark prompts (landmarks stay from the coarse mask:
    sane(bmask, "before (refined)")                    #  recomputing them on the refined mask regressed pair1 — see EXP_0004)
json.dump({"before_auto": lmb_auto, "after_auto": lma_auto, "before_used": lmb, "after_used": lma, "conf": {"before": cb, "after": ca}}, open(f"{O}/landmarks.json", "w"), indent=1, default=int)
mmpp = a.mm_per_px or 1.0; scale_note = "given" if a.mm_per_px else "UNKNOWN (1.0 placeholder; mm values are px)"
use = [n for n in SURVIVING if n in lma and n in lmb]
if not a.after_lm: use = [n for n in use if not n.startswith("knee")]     # auto knees on a cut garment are meaningless
real, rmask, resid = warp_after_to_before(af, amask, lma, lmb, bf.shape, use=use)
fr_after = segment_fringe(seg, af, amask); fr_before = None
if fr_after is not None and fr_after.sum() > 50:
    _, fr_before, _ = warp_after_to_before(af, fr_after, lma, lmb, bf.shape, use=use); cv2.imwrite(f"{O}/fringe_mask.png", fr_before.astype(np.uint8) * 255)
legs = estimate_hems(rmask, bmask, lmb, real_img=real, fringe_mask=fr_before)
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
depth_measured_px = np.mean([L["fringe_depth_px"] for L in legs.values() if L])
depth_after_frame = None
if fr_after is not None and fr_after.sum() > 50:                       # depth measured on the UN-WARPED after-photo, scaled by waist-width ratio
    ds = [np.nonzero(amask[:, x])[0].max() - np.nonzero(fr_after[:, x])[0].min() for x in range(amask.shape[1]) if amask[:, x].any() and fr_after[:, x].any()]
    if len(ds) >= 20:
        wwb = abs(lmb["waist_right"][0] - lmb["waist_left"][0]); wwa = abs(lma["waist_right"][0] - lma["waist_left"][0])
        depth_after_frame = float(np.median(ds)) * (wwb / max(wwa, 1))
        depth_measured_px = depth_after_frame                             # prefer the un-warped measurement
if a.prior:
    pr = json.load(open(a.prior)); ww = abs(lmb["waist_right"][0] - lmb["waist_left"][0])
    rows_ = [x for x in pr.get("pairs", []) if x["pair"] != a.exclude and x["kind"] == a.state]      # same STATE, leave-one-out
    rel = np.mean([x["depth_rel"] for x in rows_]) if rows_ else 0.0
    if a.state == "after_wash" and pr.get("unpaired", {}).get("n"):   # unpaired samples are after-wash only
        nu = pr["unpaired"]["n"]; rel = (rel * len(rows_) + pr["unpaired"]["depth_rel_mean"] * nu) / (len(rows_) + nu)
    n_eff = len(rows_) + (pr.get("unpaired", {}).get("n", 0) if a.state == "after_wash" else 0)
    depth_px = rel * ww; depth_source = f"prior[{a.state}] (n={n_eff}{' after excluding self' if a.exclude else ''}{', INSUFFICIENT' if n_eff < 5 else ''})"
else:
    depth_px = depth_measured_px; depth_source = "measured from after-photo (NOT a prediction)"
depth_mm = depth_px * mmpp
res = render_three(cut, removed, bmask, mmpp, seed=a.seed, depth_override={"conservative": depth_mm * 0.5, "median": depth_mm, "aggressive": depth_mm * 1.5})
for k, (im, ch) in res.items():
    cv2.imwrite(f"{O}/pred_{k}.png", im); cv2.imwrite(f"{O}/pred_{k}_mask.png", ((keep | (ch & removed)).astype(np.uint8) * 255))
for n, im in (("orig", bf), ("cut", cut), ("keep_mask", keep.astype(np.uint8) * 255), ("removed_mask", removed.astype(np.uint8) * 255), ("bmask", bmask.astype(np.uint8) * 255), ("amask", amask.astype(np.uint8) * 255), ("real", real), ("real_mask", rmask.astype(np.uint8) * 255)):
    cv2.imwrite(f"{O}/{n}.png", im)
cv2.imwrite(f"{O}/pred.png", res["median"][0]); json.dump({"landmarks": lmb}, open(f"{O}/before_lm.json", "w")); json.dump({"landmarks": lma}, open(f"{O}/after_lm.json", "w"))
rows = {}
for k in res:
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "compare.py"), "--before", BEFORE_PATH, "--before-lm", f"{O}/before_lm.json", "--pred", f"{O}/pred_{k}.png", "--pred-mask", f"{O}/pred_{k}_mask.png",
                        "--keep", f"{O}/keep_mask.png", "--removed", f"{O}/removed_mask.png", "--after", AFTER_PATH, "--after-lm", f"{O}/after_lm.json", "--after-mask", f"{O}/amask.png", "--out", f"{O}/cmp_{k}"] + (["--mm-per-px", str(mmpp)] if a.mm_per_px else []), capture_output=True, text=True)
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
md += f"hem fit: " + ", ".join(f"{k}: angle {L['angle_deg']:.1f}°, depth {L['fringe_depth_px']*mmpp:.0f}" for k, L in legs.items() if L) + f"\nregistration residual (leave-one-landmark-out): {resid:.2f}px\n\n"
md += "| system | sil IoU | chamfer | edge ΔE | fringe IoU |\n|---|---|---|---|---|\n"
for k in res:
    for r in rows[k]:
        if r["system"] == "prediction": md += row(f"pred {k}", r) + "\n"
for r in rows["median"]:
    if r["system"] != "prediction": md += row(r["system"], r) + "\n"
open(f"{O}/NOTE.md", "w").write(md); print(md)

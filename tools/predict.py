#!/usr/bin/env python3
"""THE product of the thesis: one photo of one pair of jeans + a cut specification -> what it will look like after
being cut into jorts and washed once. No after-photo, no ground truth: this is a prediction, with an interval.

    predict.py --image jeans.jpg --out out/ --inseam-fraction 0.35 [--target-inseam-cm 12] [--angle-deg 0]
               [--coin us_quarter | --mm-per-px 0.5] [--wash median] [--prior data/priors/fringe.json]

Writes: pred_conservative/median/aggressive.png (+ masks), cut.png, diff.png (exactly which pixels changed, §4.8),
modification.json (§4.5), prediction.json (§4.9 interval + provenance), panel.jpg, NOTE.md.

Honesty rules baked in: the fringe depth is a PRIOR (n is printed, and 'INSUFFICIENT' below n=5); wash shrinkage is a
textile-industry prior never measured on our data (EXP_0013); without metric scale everything is reported in pixels.
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2
from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import apply_cut, cut_mask_canon, cut_mask_canon_angled, backdrop_fill, texture_backdrop_fill
from denimtwin.canon.rawedge_v1 import render_three
from denimtwin.canon.wash import apply_wash, PRESETS as WASH_PRESETS
from denimtwin.modification import CutModification, WashProtocol
from denimtwin.canon.landmarks import inseam_fraction_to_canonical_y

p = argparse.ArgumentParser()
p.add_argument("--image", required=True, help="one flat-lay photo of the jeans, front view, whole garment in frame")
p.add_argument("--out", required=True)
g = p.add_mutually_exclusive_group(required=True)
g.add_argument("--inseam-fraction", type=float, help="0 = at the crotch, 1 = the original hem")
g.add_argument("--target-inseam-cm", type=float, help="finished inseam in cm (needs metric scale: --coin or --mm-per-px)")
p.add_argument("--angle-deg", type=float, default=0.0, help="cut angle: positive = outseam side cut higher (a-line jorts)")
p.add_argument("--mm-per-px", type=float, default=None)
p.add_argument("--coin", help="coin lying in frame (see util/coins.py) to recover metric scale")
p.add_argument("--wash", choices=["none", "conservative", "median", "aggressive"], default="median",
               help="wash appearance model (shrink/hem-roll/dye loss). PRIOR parameters, never fitted (EXP_0013)")
p.add_argument("--prior", default=os.path.join(os.path.dirname(__file__), "..", "data/priors/fringe.json"))
p.add_argument("--state", choices=["after_cut", "after_wash"], default="after_wash", help="predict the just-cut garment or the washed one")
p.add_argument("--edge-treatment", choices=["raw", "cuffed", "hemmed", "serged", "hand_frayed"], default="raw")
p.add_argument("--seed", type=int, default=1)
p.add_argument("--seg", choices=["coarse", "consensus"], default="coarse",
               help="garment segmentation: 'coarse' takes SAM's best-scoring candidate; 'consensus' takes the "
                    "object the most prompt sets agree on and reports that agreement. Consensus fixes the "
                    "catastrophic object-identity failures (a back pocket at score 0.906) that best-score cannot "
                    "detect, and is the only setting that survives re-capture perturbation (EXP_0019/0021); it is "
                    "opt-in because it changes every rendered output and has its own failure on plain studio "
                    "backdrops, where the vote can elect the backdrop instead of the garment.")
p.add_argument("--min-agreement", type=float, default=0.5, help="--seg consensus: refuse below this prompt agreement")
a = p.parse_args(); os.makedirs(a.out, exist_ok=True); O = a.out
FLAGS = []
def FAIL(why):
    print(f"REJECT: {why}"); open(f"{O}/NOTE.md", "w").write(f"# PREDICTION — rejected\n\n{why}\n"); sys.exit(3)

img = cv2.imread(a.image)
if img is None: FAIL(f"cannot read {a.image}")
seg = SamSegmenter()
SEG_PROVENANCE = {"method": a.seg}
if a.seg == "consensus":
    from denimtwin.seg.validate import segment_garment_consensus
    mask, agr, info = segment_garment_consensus(seg, img, boundary="member", min_agreement=a.min_agreement)
    if mask is None:
        FAIL(f"consensus segmentation refused: {info.get('reason', 'no cluster reached the agreement threshold')}. "
             "Re-shoot the garment against a background it does not blend into, or pass --seg coarse and check the mask by eye.")
    SEG_PROVENANCE.update(agreement=float(agr), area=float(info.get("area", 0.0)), denim_frac=info.get("denim_frac"),
                          n_clusters=info.get("n_clusters"))
    FLAGS.append(f"segmentation by consensus: {agr:.0%} of prompt sets agree, area {info['area']:.2f} of frame")
    if info.get("denim_frac") is not None and info["denim_frac"] < 0.35:
        FLAGS.append(f"only {info['denim_frac']:.0%} of the chosen mask is denim-coloured — on a plain studio backdrop "
                     "the prompts can agree on the BACKDROP instead of the garment (EXP_0019); check diff.png before trusting this")
else:
    mask, sc, info = segment_garment_coarse(seg, img)
    if mask is None: FAIL("segmentation failed (garment not found against the background)")
    SEG_PROVENANCE.update(score=float(sc), area=float(info["area"]))
    FLAGS.append(f"mask score {sc:.3f}, area {info['area']:.2f} of frame")
    FLAGS.append("mask chosen by SAM's own score, which does not detect a confidently wrong object (EXP_0018 found a "
                 "back pocket returned at 0.906): look at diff.png, or use --seg consensus")

# upright: flat-lays are often shot at an angle
ys, xs = np.nonzero(mask); pts = np.stack([xs, ys], 1).astype(np.float32); pts -= pts.mean(0)
cov = pts.T @ pts / len(pts); w_, v_ = np.linalg.eigh(cov); major = v_[:, np.argmax(w_)]
ang = (np.degrees(np.arctan2(major[0], major[1])) + 90) % 180 - 90
elong = float(np.sqrt(w_.max() / max(w_.min(), 1e-6)))
if 8 <= abs(ang) <= (80 if elong > 1.8 else 30):
    h, w = img.shape[:2]; M = cv2.getRotationMatrix2D((w / 2, h / 2), -ang, 1.0)
    cos, sin = abs(M[0, 0]), abs(M[0, 1]); nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    M[0, 2] += nw / 2 - w / 2; M[1, 2] += nh / 2 - h / 2
    bgc = tuple(int(c) for c in np.median(img[~mask], axis=0)) if (~mask).any() else (128, 128, 128)
    img = cv2.warpAffine(img, M, (nw, nh), borderValue=bgc); mask = cv2.warpAffine(mask.astype(np.uint8), M, (nw, nh)) > 0
    FLAGS.append(f"rotated {ang:.1f}° to upright")

h, w = mask.shape; ys, xs = np.nonzero(mask)
if mask.mean() < 0.02: FAIL(f"garment covers only {mask.mean():.1%} of the frame")
if (xs.min() <= 2) or (xs.max() >= w - 3) or (ys.min() <= 2): FAIL("garment touches the frame edge (re-shoot with the whole garment in frame)")
if ys.max() >= h - 3: FLAGS.append("legs reach the frame bottom: the original hem is out of frame, so an inseam fraction is measured against the frame, not the hem")

lm, conf = landmarks_from_mask(mask)
if len(lm) >= 14: mask, _ = seg.segment(img, landmarks=lm)
if conf.get("garment_type") != "jeans": FLAGS.append(f"landmark heuristic calls this '{conf.get('garment_type')}', not full-length jeans: a shorter->shorter cut")
json.dump({"landmarks": lm, "conf": conf}, open(f"{O}/landmarks.json", "w"), indent=1, default=float)

# metric scale
mmpp = a.mm_per_px
if a.coin and mmpp is None:
    import subprocess
    cv2.imwrite(f"{O}/mask.png", mask.astype(np.uint8) * 255)
    r_ = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "scale_from_coin.py"), a.image, "--coin", a.coin, "--mask", f"{O}/mask.png"], capture_output=True, text=True)
    try: d_ = json.loads(r_.stdout)
    except Exception: d_ = {}
    if r_.returncode == 0 and d_.get("accepted"): mmpp = d_["mm_per_px"]; FLAGS.append(f"scale from coin ({a.coin}): {mmpp:.4f} mm/px")
    else: FLAGS.append(f"coin scale rejected: {d_.get('reject_reason') or d_.get('error') or 'no result'}")
metric = mmpp is not None
if a.target_inseam_cm is not None and not metric: FAIL("--target-inseam-cm needs metric scale: pass --coin or --mm-per-px")
mmpp_eff = mmpp or 1.0
unit = "mm" if metric else "px"

# the cut, in canonical space (so 'inseam fraction' means the same thing on every garment)
cmap = CanonicalMap(lm)
if a.target_inseam_cm is not None:
    crotch_y, hem_y = lm["crotch"][1], np.mean([lm["hem_left_inner"][1], lm["hem_right_inner"][1]])
    inseam_px = (hem_y - crotch_y); inseam_cm = inseam_px * mmpp_eff / 10.0
    frac = float(np.clip(a.target_inseam_cm / max(inseam_cm, 1e-6), 0.0, 1.0))
    FLAGS.append(f"target inseam {a.target_inseam_cm} cm of {inseam_cm:.1f} cm original -> inseam fraction {frac:.3f}")
else:
    frac = float(a.inseam_fraction)
if not 0.0 <= frac <= 1.0: FAIL(f"cut fraction {frac:.3f} outside the garment")
if a.angle_deg:
    # convert an angle to the canonical inner/outer fractions: outer side moves by tan(angle) * (half leg width) in canonical y
    # the cut line pivots about the requested height at mid-leg: +angle raises the outseam side and lowers the
    # inseam side by the same amount, so +a and -a are mirror images (nesting them would make the sign meaningless).
    span = abs(cmap.W * 0.24) / max(cmap.H, 1)            # canonical half-leg width as a fraction of canonical height
    d = float(np.tan(np.radians(a.angle_deg))) * span
    y_c = inseam_fraction_to_canonical_y(frac)
    y_in = float(np.clip(y_c + d / 2, 0.02, 0.99)); y_out = float(np.clip(y_c - d / 2, 0.02, 0.99))
    y0_, y1_ = inseam_fraction_to_canonical_y(0.0), inseam_fraction_to_canonical_y(1.0)
    to_frac = lambda y: float(np.clip((y - y0_) / max(y1_ - y0_, 1e-6), 0.0, 1.0))
    inner_f, outer_f = to_frac(y_in), to_frac(y_out)
    remove_canon = cut_mask_canon_angled((cmap.W, cmap.H), inner_f, outer_f)
    FLAGS.append(f"angled cut {a.angle_deg:+.1f}°: inner fraction {inner_f:.3f}, outer {outer_f:.3f}")
else:
    remove_canon = cut_mask_canon((cmap.W, cmap.H), inseam_fraction=frac)
_, removed, keep = apply_cut(img, mask, cmap, remove_canon)
rf = removed.sum() / max(mask.sum(), 1)
if not (0.01 <= rf <= 0.85): FAIL(f"degenerate cut: it removes {rf:.0%} of the garment")
cut = backdrop_fill(img, mask, removed)      # deterministic fill: parts of it ARE read by the edge-band and
                                             # cut-region metrics, so invented texture must not enter here

# the wash itself (shrinkage, hem roll, dye loss) — before the fringe grows from the new edge
gm, rm = mask, removed
if a.state == "after_wash" and a.wash != "none":
    wp = WASH_PRESETS[a.wash]
    cut, gm, rm, _ = apply_wash(cut, mask, removed, mmpp_eff, wp)
    roll = (f"{wp.hem_roll_mm:.0f} mm" if metric else
            f"{wp.hem_roll_mm:.0f} px — with no metric scale the roll width parameter is applied as pixels, so it is NOT a physical width")
    FLAGS.append(f"wash '{a.wash}': shrink {wp.shrink_along_frac:.1%} along / {wp.shrink_across_frac:.1%} across, hem roll {roll} — PRIOR values, not measured (EXP_0013)")
keep = gm & ~rm

# fringe depth: from the prior, conditional on the state and the edge treatment
mod = CutModification(inseam_fraction=frac, outer_fraction=(outer_f if a.angle_deg else None), edge_treatment=a.edge_treatment,
                      wash=WashProtocol(cycles=1 if a.state == "after_wash" else 0), seed=a.seed).validate()
ww = abs(lm["waist_right"][0] - lm["waist_left"][0])
if not mod.expects_fringe():
    depth_px, sd_rel, n_eff, src = 0.0, 0.0, 0, f"edge treatment '{a.edge_treatment}' does not fray"
else:
    from denimtwin.prior import predict_depth_rel
    pr = json.load(open(a.prior)); rel, n_eff, sd_rel = predict_depth_rel(pr, a.state, None)
    depth_px = rel * ww
    prior_validated = bool(pr.get("validated", False)); prior_note = pr.get("validation_note", "")
    src = f"prior[{a.state}] n={n_eff}" + ("" if prior_validated else " — UNVALIDATED")
    if n_eff == 0:
        FLAGS.append(f"the prior has NO observations for state '{a.state}' (every row for it was a rule output, not a "
                     f"measurement), so the predicted fringe depth is 0 by absence of evidence, not by measurement")
    elif n_eff < 5:
        FLAGS.append(f"the prior for '{a.state}' rests on {n_eff} sample(s)")
    if not prior_validated:
        # unconditional: not gated on n, not gated on resolution (review 5, finding 6)
        FLAGS.append("fringe depth is a PLACEHOLDER, not an estimate: " + (prior_note or "the prior declares itself unvalidated"))
        src += " — " + (prior_note or "the prior declares itself unvalidated")
    _ad = pr.get("assumed_depth")
    if _ad:
        FLAGS.append(f"the only sourced fray depth we have is {_ad['value_mm']} mm — {_ad['basis']} Caveat: {_ad['caveat']}")
    if n_eff < 5: FLAGS.append(f"fringe prior has only n={n_eff} samples: the depth below is not yet evidence-backed")
depth_mm = depth_px * mmpp_eff
half = 1.28 * sd_rel * ww                                    # ~80% interval under a normal assumption (uncalibrated: EXP_0009)
lo_px, hi_px = max(0.0, depth_px - half), depth_px + half

# the three renders ARE the published interval: conservative = lo, median = centre, aggressive = hi. No flooring —
# a picture labelled "aggressive (15 px)" must contain a 15 px fringe (review 4, finding 4).
if depth_px < 5.0:
    FLAGS.append(f"fringe depth {depth_px:.1f} px is below the renderer's resolution: the three renders differ by less than a "
                 f"pixel of fringe and must not be read as an interval (EXP_0015 — the depth itself is a placeholder)")
res = render_three(cut, rm, gm, mmpp_eff, seed=a.seed,
                   depth_override={"conservative": lo_px * mmpp_eff, "median": depth_mm, "aggressive": hi_px * mmpp_eff})
for k, (im, ch) in res.items():
    cv2.imwrite(f"{O}/pred_{k}.png", im); cv2.imwrite(f"{O}/pred_{k}_mask.png", ((keep | (ch & rm)).astype(np.uint8) * 255))
cv2.imwrite(f"{O}/orig.png", img); cv2.imwrite(f"{O}/cut.png", cut); cv2.imwrite(f"{O}/mask.png", mask.astype(np.uint8) * 255)
cv2.imwrite(f"{O}/keep_mask.png", keep.astype(np.uint8) * 255); cv2.imwrite(f"{O}/removed_mask.png", rm.astype(np.uint8) * 255)
cv2.imwrite(f"{O}/pred.png", res["median"][0])
cv2.imwrite(f"{O}/diff.png", (np.any(res["median"][0] != img, axis=2)).astype(np.uint8) * 255)
open(f"{O}/modification.json", "w").write(mod.to_json())

y0 = int(np.nonzero(rm)[0].min()) if rm.any() else img.shape[0] // 2; H = img.shape[0]
crop = lambda im: im[max(y0 - int(0.18 * H), 0): min(y0 + int(0.22 * H), H)].copy()
def presentation(im):
    """Same prediction, prettier hole: invented backdrop texture where the fabric was, for the panel only."""
    return np.where(rm[..., None] & (np.abs(im.astype(int) - cut.astype(int)).max(axis=2) <= 8)[..., None],
                    texture_backdrop_fill(img, mask, rm, seed=a.seed), im)
tiles = [crop(img)] + [crop(presentation(res[k][0])) for k in ("conservative", "median", "aggressive")]
for t, n in zip(tiles, ("before", f"conservative ({lo_px * mmpp_eff:.0f} {unit})", f"median ({depth_mm:.0f} {unit})", f"aggressive ({hi_px * mmpp_eff:.0f} {unit})")):
    cv2.putText(t, n, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
cv2.imwrite(f"{O}/panel.jpg", np.concatenate(tiles, 1))

from denimtwin.eval.identity import changed_pixel_fraction_outside
changed_outside = float(changed_pixel_fraction_outside(res["median"][0], img, keep & mask))
pred = {"image": os.path.abspath(a.image), "state": a.state, "wash_preset": a.wash if a.state == "after_wash" else "none",
        "scale": {"mm_per_px": mmpp, "source": "coin" if (a.coin and metric) else ("given" if metric else "UNKNOWN — all lengths are pixels")},
        "cut": {"inseam_fraction": frac, "angle_deg": a.angle_deg, "removed_fraction_of_garment": float(rf)},
        "fringe_depth": {"unit": unit, "median": float(depth_mm), "lo": float(lo_px * mmpp_eff), "hi": float(hi_px * mmpp_eff),
                         "below_render_resolution": bool(depth_px < 5.0),
                         "nominal_coverage": 0.8, "calibrated": False, "n": int(n_eff), "source": src,
                         "prior_validated": bool(locals().get("prior_validated", False)),
                         "prior_validation_note": locals().get("prior_note", ""),
                         "assumed_depth_mm_sourced": (json.load(open(a.prior)).get("assumed_depth") or {}).get("value_mm")},
        "changed_fraction_of_kept_region": changed_outside,
        "segmentation": SEG_PROVENANCE,
        "flags": FLAGS}
json.dump(pred, open(f"{O}/prediction.json", "w"), indent=1)

md = f"""# PREDICTION — {os.path.basename(a.image)}

**This is a prediction, not a measurement.** No after-photo exists for this garment.

- cut: inseam fraction **{frac:.3f}**{f", angle {a.angle_deg:+.1f}°" if a.angle_deg else ""} — removes {rf:.0%} of the garment
- state: **{a.state}**{f", wash preset '{a.wash}'" if a.state == "after_wash" else ""}
- scale: {"%.4f mm/px (%s)" % (mmpp, "coin" if a.coin else "given") if metric else "**unknown** — every length below is in pixels"}
- fringe depth: **{depth_mm:.1f} {unit}** (80% interval {lo_px * mmpp_eff:.1f}–{hi_px * mmpp_eff:.1f} {unit}) from {src}
- interval calibration: **not established** (EXP_0009 coverage 0/10) — read the range as a spread, not a guarantee
- fringe depth provenance: **no validated measurement exists** (EXP_0015) — the number above is a placeholder and the
  three renders differ only in a quantity nobody has yet measured on real garments

flags: {'; '.join(FLAGS) or 'none'}

| file | what |
|---|---|
| `panel.jpg` | before + the three predictions side by side |
| `pred_median.png` | the central prediction |
| `pred_conservative.png` / `pred_aggressive.png` | the ends of the fringe interval |
| `diff.png` | exactly which pixels the system changed (§4.8) |
| `modification.json` | the modification as structured parameters (§4.5) |
| `prediction.json` | machine-readable prediction + provenance |

Outside the cut region, {changed_outside:.1%} of kept pixels differ from the input photo{" (the wash model's shrink, hem roll and dye loss — set `--wash none` for a strict pixel copy)" if (a.state == "after_wash" and a.wash != "none") else " (a strict pixel copy: only the abraded band at the cut edge)"}.
"""
open(f"{O}/NOTE.md", "w").write(md); print(md)

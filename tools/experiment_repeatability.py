#!/usr/bin/env python3
"""EXP_0021 — How reproducible is a measurement of one garment? (Gate 1)

Gate 1 asks for "repeated captures of the same garment [that] align consistently; physical measurements reproducible
within tolerance (set after pilot)". EXP_0018 recorded it as FAILED for a stated reason: the only two photographs of
one garment in the dataset (a front and a back view) returned waist widths of 874 px and 191 px, because SAM
segmented a back pocket at score 0.906. EXP_0019 then showed consensus segmentation fixes that mask. This experiment
asks the two questions that follow, on the data that exists:

  Part A  Does the same-garment pair agree once the mask is right? (2 photos, 1 garment — the real, tiny test)
  Part B  What is the repeatability FLOOR under re-capture-like variation? (16 photos x 13 perturbations x 2 methods)

Part B is a **simulated** re-capture: the same photograph re-framed, re-exposed, re-compressed. It cannot move the
fabric, change the drape, or move the light, so it bounds repeatability from ABOVE — a real second capture will be
worse than the numbers here. It is still the only tolerance measurement available without a second photograph of
anything, and a method that cannot survive a 3-degree rotation cannot survive a real re-capture either.

Two perturbation families are reported separately, because they mean different things:
  photometric (jpeg, exposure, white balance, blur)   — the garment's geometry is untouched: ANY change in a
                                                        scale-free shape statistic is instrument noise.
  geometric   (rotation, zoom, shift)                 — the pixels move, so a change may be the segmenter failing OR
                                                        the landmark definitions being frame-dependent. Mask IoU
                                                        (computed after undoing the known transform) separates them.

    experiment_repeatability.py [--out reports/repeatability] [--limit N] [--methods best,consensus]

Writes rows.json (one row per image x method x perturbation) and summary.json. No image is redistributed.
"""
import argparse, json, os, sys, math, glob
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2

from denimtwin.seg.sam import SamSegmenter, segment_garment_coarse
from denimtwin.seg.validate import segment_garment_consensus
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.eval.hem_texture import hem_roughness, mask_compactness
from denimtwin.canon import upright as U

ROOT = Path(__file__).resolve().parents[1]
UNPAIRED = ROOT / "data/external/unpaired_images"
CONTROLS = ROOT / "data/external/control_images"
VERDICTS = ROOT / "data/external/mask_verdicts.json"

# ---------------------------------------------------------------- perturbations
# Each returns (image, affine 2x3 or None). The affine maps ORIGINAL -> PERTURBED pixel coordinates, so the reference
# mask can be warped forward into the perturbed frame and compared there (no invented pixels enter the comparison:
# a validity map marks which output pixels came from real input).

def _rot(img, deg, scale=1.0):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, scale)
    return M

def _shift(img, fx, fy):
    h, w = img.shape[:2]
    return np.array([[1.0, 0.0, fx * w], [0.0, 1.0, fy * h]])

def _jpeg(img, q):
    ok, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)

def _gain(img, g):
    return np.clip(img.astype(np.float32) * g, 0, 255).astype(np.uint8)

def _wb(img, rg, bg):
    f = img.astype(np.float32)
    f[..., 2] *= rg; f[..., 0] *= bg                     # BGR
    return np.clip(f, 0, 255).astype(np.uint8)

PERTURBATIONS = [
    # (name, family, fn(img) -> (image, affine|None))
    ("identity",   "none",        lambda im: (im, None)),
    ("jpeg40",     "photometric", lambda im: (_jpeg(im, 40), None)),
    ("jpeg15",     "photometric", lambda im: (_jpeg(im, 15), None)),
    ("bright+20",  "photometric", lambda im: (_gain(im, 1.20), None)),
    ("dark-20",    "photometric", lambda im: (_gain(im, 0.80), None)),
    ("warm_wb",    "photometric", lambda im: (_wb(im, 1.08, 0.92), None)),
    ("blur3",      "photometric", lambda im: (cv2.GaussianBlur(im, (0, 0), 1.5), None)),
    ("rot+3",      "geometric",   lambda im: (None, _rot(im, 3))),
    ("rot-3",      "geometric",   lambda im: (None, _rot(im, -3))),
    ("rot+8",      "geometric",   lambda im: (None, _rot(im, 8))),
    ("zoom0.85",   "geometric",   lambda im: (None, _rot(im, 0, 0.85))),
    ("zoom1.15",   "geometric",   lambda im: (None, _rot(im, 0, 1.15))),
    ("shift4pct",  "geometric",   lambda im: (None, _shift(im, 0.04, -0.03))),
    ("recapture_a", "combined",   lambda im: (_jpeg(_gain(im, 1.10), 60), _rot(im, 5, 0.92))),
    ("recapture_b", "combined",   lambda im: (_jpeg(_wb(im, 1.06, 0.94), 60), _rot(im, -4, 1.08))),
]

def apply_perturbation(img, spec):
    """Return (perturbed image, affine or None, validity map of the perturbed frame)."""
    name, family, fn = spec
    im2, M = fn(img)
    base = img if im2 is None else im2
    if M is None:
        return base, None, np.ones(base.shape[:2], bool)
    h, w = base.shape[:2]
    out = cv2.warpAffine(base, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    valid = cv2.warpAffine(np.ones((h, w), np.uint8), M, (w, h), flags=cv2.INTER_NEAREST,
                           borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0
    return out, M, valid

def warp_mask_forward(mask, M, shape):
    if M is None: return np.asarray(mask, bool)
    h, w = shape
    return cv2.warpAffine(np.asarray(mask, np.uint8), M, (w, h), flags=cv2.INTER_NEAREST,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=0) > 0

# ---------------------------------------------------------------- measurement
def measure(mask, image_bgr=None, upright=False):
    """Scale-free shape statistics from a garment mask. Ratios only: a re-capture from a different distance must not
    change them, and a px measurement would.

    `upright=True` applies `canon/upright.py` first, which is what `run_pair`/`predict` now do on every photograph
    (EXP_0022). The first run of this experiment measured the raw mask and found the ratios swinging 30% at 8 degrees
    of tilt; this is how that number is re-measured after the fix."""
    m = np.asarray(mask, bool)
    if upright:
        _img = image_bgr if image_bgr is not None else np.zeros((*m.shape, 3), np.uint8)
        _, m, _ang = U.upright(_img, m, deadband=0.0)
    out = {"area_frac": float(m.mean())}
    if not m.any(): return out
    lm, conf = landmarks_from_mask(m)
    out["garment_type"] = conf.get("garment_type")
    if "waist_left" in lm and "waist_right" in lm:
        ww = float(lm["waist_right"][0] - lm["waist_left"][0])
        out["waist_px"] = ww
        if ww > 4:
            ys = np.nonzero(m.any(axis=1))[0]
            top = float(lm["waist_left"][1]); bot = float(ys.max())
            out["height_over_waist"] = (bot - top) / ww
            if "hip_left" in lm and "hip_right" in lm:
                out["hip_over_waist"] = float(lm["hip_right"][0] - lm["hip_left"][0]) / ww
            if "crotch" in lm:
                out["rise_over_waist"] = (float(lm["crotch"][1]) - top) / ww
    r = hem_roughness(m, waist_px=out.get("waist_px"))
    out["rough_ok"] = bool(r.get("ok"))
    out["rough_p90_rel"] = float(r.get("p90_rel", 0.0) or 0.0)
    out["rough_fraction"] = float(r.get("rough_fraction", 0.0) or 0.0)
    out["compactness"] = float(mask_compactness(m))
    return out

def iou(a, b, valid=None):
    a = np.asarray(a, bool); b = np.asarray(b, bool)
    if valid is not None: a = a & valid; b = b & valid
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0

# ---------------------------------------------------------------- segmentation methods
def seg_best(seg, img):
    m, sc, info = segment_garment_coarse(seg, img)
    return m, {"score": float(sc), **{k: v for k, v in (info or {}).items() if isinstance(v, (int, float))}}

def seg_consensus(seg, img):
    m, agr, info = segment_garment_consensus(seg, img, boundary="member")
    keep = {k: v for k, v in (info or {}).items() if isinstance(v, (int, float, str))}
    return m, {"agreement": float(agr), **keep}

METHODS = {"best": seg_best, "consensus": seg_consensus}

# ---------------------------------------------------------------- run
def subjects(limit=0, extra_glob=None):
    out = []
    for d, kind in ((UNPAIRED, "unpaired"), (CONTROLS, "control")):
        for p in sorted(glob.glob(str(d / "*.jpg"))) + sorted(glob.glob(str(d / "*.jpeg"))):
            out.append({"id": Path(p).stem, "path": p, "set": kind})
    if extra_glob:
        for p in sorted(glob.glob(extra_glob)):
            out.append({"id": Path(p).stem, "path": p, "set": "extra"})
    return out[:limit] if limit else out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/repeatability")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--methods", default="best,consensus")
    ap.add_argument("--glob", default=None, help="extra images to include")
    ap.add_argument("--upright", action="store_true",
                    help="apply canon/upright.py before measuring, as run_pair and predict now do (EXP_0022). "
                         "Without it this measures the raw mask, which is what the first run of EXP_0021 did.")
    a = ap.parse_args()
    outdir = ROOT / a.out; outdir.mkdir(parents=True, exist_ok=True)
    methods = [m for m in a.methods.split(",") if m in METHODS]
    subs = subjects(a.limit, a.glob)
    if not subs:
        print("no images on disk (they are gitignored — see tools/ingest_unpaired.py --fetch)"); return 1
    verdicts = json.load(open(VERDICTS))["verdicts"] if VERDICTS.exists() else {}
    seg = SamSegmenter()
    rows, refs = [], []
    for si, s in enumerate(subs):
        img = cv2.imread(s["path"])
        if img is None: continue
        print(f"[{si+1}/{len(subs)}] {s['id']} {img.shape[1]}x{img.shape[0]}", flush=True)
        # Reference masks for BOTH methods first: self-consistency is worthless if the reference is the wrong object,
        # so every reference carries the human verdict and the two methods' disagreement with each other.
        ref_masks = {}
        for meth in methods:
            rm, ri = METHODS[meth](seg, img)
            ref_masks[meth] = rm
            refs.append({"image": s["id"], "set": s["set"], "method": meth, "found": rm is not None,
                         "verdict": (verdicts.get(s["id"], {}) or {}).get("verdict"),
                         "px": [int(img.shape[1]), int(img.shape[0])],
                         **{f"info_{k}": v for k, v in ri.items()},
                         **({f"m_{k}": v for k, v in measure(rm, img, a.upright).items()} if rm is not None else {})})
        if len(methods) == 2 and all(ref_masks.get(m) is not None for m in methods):
            x = iou(ref_masks[methods[0]], ref_masks[methods[1]])
            for r in refs[-2:]: r["iou_between_methods"] = x
        for meth in methods:
            ref_mask = ref_masks[meth]
            for spec in PERTURBATIONS:
                name, family, _ = spec
                pimg, M, valid = apply_perturbation(img, spec)
                mask, info = METHODS[meth](seg, pimg)
                row = {"image": s["id"], "set": s["set"], "method": meth, "perturbation": name, "family": family,
                       "verdict": (verdicts.get(s["id"], {}) or {}).get("verdict"),
                       "found": mask is not None, **{f"info_{k}": v for k, v in info.items()}}
                if mask is not None and ref_mask is not None:
                    ref_in_p = warp_mask_forward(ref_mask, M, pimg.shape[:2])
                    row["iou_vs_ref"] = iou(mask, ref_in_p, valid)
                    row.update({f"m_{k}": v for k, v in measure(mask, pimg, a.upright).items()})
                rows.append(row)
                print(f"    {meth:9s} {name:12s} iou={row.get('iou_vs_ref', float('nan')):.3f}", flush=True)
    (outdir / "rows.json").write_text(json.dumps(rows, indent=1))
    (outdir / "references.json").write_text(json.dumps(refs, indent=1))
    summ = summarize(rows, refs)
    (outdir / "summary.json").write_text(json.dumps(summ, indent=1))
    print(json.dumps(summ["headline"], indent=1))
    return 0

STATS = ["height_over_waist", "hip_over_waist", "rise_over_waist", "rough_p90_rel", "rough_fraction"]

def summarize(rows, refs=()):
    out = {"n_rows": len(rows), "by_method": {}, "headline": {}}
    if refs:
        out["references"] = {"n": len(refs),
                             "iou_between_methods_median": float(np.median([r["iou_between_methods"] for r in refs
                                                                           if "iou_between_methods" in r])) if any("iou_between_methods" in r for r in refs) else None,
                             "images_where_methods_disagree": sorted({r["image"] for r in refs
                                                                      if r.get("iou_between_methods", 1.0) < 0.8}),
                             "not_found": sorted({r["image"] + ":" + r["method"] for r in refs if not r["found"]})}
    for meth in sorted({r["method"] for r in rows}):
        R = [r for r in rows if r["method"] == meth]
        per_family = {}
        for fam in ("photometric", "geometric", "combined"):
            F = [r for r in R if r["family"] == fam]
            ious = [r["iou_vs_ref"] for r in F if "iou_vs_ref" in r]
            per_family[fam] = {
                "n": len(F),
                "refused_or_lost": sum(1 for r in F if not r.get("found")),
                "iou_median": float(np.median(ious)) if ious else None,
                "iou_p10": float(np.percentile(ious, 10)) if ious else None,
                "iou_below_080": sum(1 for v in ious if v < 0.8),
                "iou_below_050": sum(1 for v in ious if v < 0.5),
            }
        # measurement spread per image: max relative deviation from the identity run, per statistic
        spread = {k: [] for k in STATS}
        for img in sorted({r["image"] for r in R}):
            I = [r for r in R if r["image"] == img]
            base = next((r for r in I if r["perturbation"] == "identity"), None)
            if not base: continue
            for k in STATS:
                b = base.get(f"m_{k}")
                if b is None: continue
                vals = [r.get(f"m_{k}") for r in I if r["perturbation"] != "identity" and r.get(f"m_{k}") is not None]
                if not vals: continue
                denom = abs(b) if abs(b) > 1e-9 else None
                dev = max(abs(v - b) for v in vals)
                spread[k].append({"image": img, "base": b, "max_abs_dev": dev,
                                  "max_rel_dev": (dev / denom) if denom else None})
        out["by_method"][meth] = {"per_family": per_family, "spread": spread,
                                  "spread_median_rel": {k: (float(np.median([s["max_rel_dev"] for s in v if s["max_rel_dev"] is not None]))
                                                            if any(s["max_rel_dev"] is not None for s in v) else None)
                                                        for k, v in spread.items()}}
    for meth, d in out["by_method"].items():
        out["headline"][meth] = {
            "photometric_iou_median": d["per_family"]["photometric"]["iou_median"],
            "geometric_iou_median": d["per_family"]["geometric"]["iou_median"],
            "n_iou_below_050": sum(d["per_family"][f]["iou_below_050"] for f in d["per_family"]),
            "n_iou_below_080": sum(d["per_family"][f]["iou_below_080"] for f in d["per_family"]),
            "n_refused_or_lost": sum(d["per_family"][f]["refused_or_lost"] for f in d["per_family"]),
        }
        out["headline"][meth].update(fray_verdict_stability(rows, meth))
    return out


def fray_verdict_stability(rows, method):
    """Does the FRAY VERDICT (hem roughness p90 > 0) survive a perturbation that never touched the garment?

    EXP_0016 reports 0 false positives on 9 high-resolution finished-hem controls. That is a statement about one
    photograph each. This asks the harder question the gate actually needs: re-encode or re-frame the same photo and
    does the verdict hold? (Counts are per photo, over the perturbations where a mask was returned.)"""
    flips_to_frayed, flips_to_finished, stable, controls_that_flip = 0, 0, 0, []
    for img in sorted({r["image"] for r in rows}):
        I = [r for r in rows if r["image"] == img and r["method"] == method and r.get("m_rough_p90_rel") is not None]
        base = next((r for r in I if r["perturbation"] == "identity"), None)
        if not base: continue
        vals = [r["m_rough_p90_rel"] for r in I if r["perturbation"] != "identity"]
        if not vals: continue
        b = base["m_rough_p90_rel"]
        if b == 0 and any(v > 0 for v in vals):
            flips_to_frayed += 1
            if base["set"] == "control": controls_that_flip.append(img)
        elif b > 0 and any(v == 0 for v in vals): flips_to_finished += 1
        else: stable += 1
    return {"fray_verdict_stable_photos": stable, "fray_verdict_unstable_photos": flips_to_frayed + flips_to_finished,
            "fray_verdict_flips_to_frayed": flips_to_frayed,
            "fray_verdict_flips_to_finished": flips_to_finished,
            "finished_hem_controls_that_read_frayed_under_perturbation": len(controls_that_flip),
            "which_controls_flip": controls_that_flip}

if __name__ == "__main__":
    raise SystemExit(main())

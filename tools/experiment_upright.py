#!/usr/bin/env python3
"""EXP_0022 — can we estimate camera tilt well enough to correct it? (the fix EXP_0021 asks for)

EXP_0021 Part C: `canon/autolm.landmarks_from_mask` measures axis-aligned extents, so a 5-8 degree tilt moves every
shape ratio by more than 5% even on a geometrically exact silhouette. `run_pair.py`/`predict.py` correct tilt only
above **8 degrees** — above the angle where the damage is already done. Before lowering that deadband, the question
is whether the angle estimate is good enough to act on at small angles: correcting by a wrong 3 degrees is worse than
not correcting.

Two estimators, measured against a KNOWN rotation of an already-correct mask (no SAM, no photograph, no confound):

  pca      the current one — angle of the silhouette's principal axis. For full-length jeans the long axis is a real
           feature; for shorts the silhouette is nearly isotropic (elongation ~1) and the axis is whatever the legs
           happen to do, which is why the deadband exists.
  waistband a flat-laid garment has one nearly straight, nearly horizontal edge: the top of the waistband. Fit a line
           to it (robustly, over the middle of its span) and its slope is the tilt. This is a physical feature of the
           garment rather than a statistic of its outline.

    experiment_upright.py [--out reports/repeatability/upright.json]

Prints, per estimator, the median absolute error over real masks and the fraction of cases where correcting by the
estimate would leave a residual tilt LARGER than doing nothing.
"""
import argparse, json, os, sys, glob
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import numpy as np, cv2

ROOT = Path(__file__).resolve().parents[1]
TRUE_ANGLES = [-15, -8, -5, -3, -1, 0, 1, 3, 5, 8, 15]

def pca_angle(mask):
    """The estimator `run_pair.upright` uses. Returns (angle_deg, elongation)."""
    ys, xs = np.nonzero(mask)
    pts = np.stack([xs, ys], 1).astype(np.float32); pts -= pts.mean(0)
    cov = pts.T @ pts / len(pts); w_, v_ = np.linalg.eigh(cov); major = v_[:, np.argmax(w_)]
    ang = np.degrees(np.arctan2(major[0], major[1])); ang = (ang + 90) % 180 - 90
    return float(ang), float(np.sqrt(w_.max() / max(w_.min(), 1e-6)))

def _wrap(d):
    """Angles are defined modulo 180 degrees (a garment rotated by 180 is still a garment, and the PCA axis has no
    sign). Errors must be wrapped the same way or a 1 degree miss reads as 179."""
    return (float(d) + 90.0) % 180.0 - 90.0

def waistband_angle(mask, span=(0.15, 0.85)):
    """Tilt from the top edge of the waistband, fitted robustly (cv2.fitLine, L1) over the middle of the span.

    The waistband is the one part of a flat-laid garment that is straight by construction — a stiff band with a sewn
    edge. Hems are cut, legs splay, the crotch is a curve. Returns (angle_deg, inlier_fraction)."""
    m = np.asarray(mask, bool)
    cols = np.nonzero(m.any(axis=0))[0]
    if len(cols) < 20: return None, 0.0
    x0, x1 = cols.min(), cols.max()
    lo, hi = int(x0 + span[0] * (x1 - x0)), int(x0 + span[1] * (x1 - x0))
    xs = np.array([x for x in range(lo, hi + 1) if m[:, x].any()])
    if len(xs) < 20: return None, 0.0
    ys = np.array([np.nonzero(m[:, x])[0].min() for x in xs], float)
    pts = np.stack([xs.astype(np.float32), ys.astype(np.float32)], 1)
    vx, vy, _, _ = cv2.fitLine(pts, cv2.DIST_L1, 0, 0.01, 0.01).ravel()
    if abs(vx) < 1e-6: return None, 0.0
    ang = _wrap(np.degrees(np.arctan2(vy, vx)))
    # how much of the edge actually lies on that line: a waistband gives a high fraction, a jumbled top edge does not
    d = np.abs(-vy * (xs - xs.mean()) + vx * (ys - ys.mean()))
    H = np.ptp(np.nonzero(m.any(axis=1))[0]) + 1
    return ang, float((d <= max(0.02 * H, 2.0)).mean())

def flatten_top_angle(mask, lim=25, step=0.5, band_px=None):
    """Tilt as the rotation that makes the top edge FLATTEST — no feature definition at all, just the angle at which
    the most columns share the garment's topmost row.

    This asks the question the pipeline actually needs answered ("which way is up for this flat-lay?") instead of a
    proxy for it, and it does not care whether the garment is elongated, which is where the principal axis fails."""
    m = np.asarray(mask, bool)
    h, w = m.shape
    H = np.ptp(np.nonzero(m.any(axis=1))[0]) + 1
    k = band_px if band_px is not None else max(int(0.01 * H), 2)
    best, best_score = 0.0, -1.0
    for a in np.arange(-lim, lim + 1e-9, step):
        r = cv2.warpAffine(m.astype(np.uint8), cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0), (w, h),
                           flags=cv2.INTER_NEAREST) > 0 if a else m
        cols = np.nonzero(r.any(axis=0))[0]
        if not len(cols): continue
        tops = np.array([np.nonzero(r[:, x])[0].min() for x in cols])
        score = float((tops <= tops.min() + k).mean())
        if score > best_score: best_score, best = score, float(a)
    return -best, best_score          # negative: the angle the garment is tilted BY

def rotate(mask, deg):
    h, w = mask.shape
    M = cv2.getRotationMatrix2D((w / 2, h / 2), deg, 1.0)
    return cv2.warpAffine(mask.astype(np.uint8), M, (w, h), flags=cv2.INTER_NEAREST) > 0

def synthetic(H=1000, W=800, kind="shorts"):
    m = np.zeros((H, W), np.uint8)
    cx, top = W // 2, int(0.12 * H)
    ww = int(0.46 * W); hh = int(0.55 * H if kind == "shorts" else 0.80 * H)
    body = int(0.42 * (0.55 * H))
    cv2.rectangle(m, (cx - ww // 2, top), (cx + ww // 2, top + body), 255, -1)
    leg_w = int(ww * 0.44); gap = int(ww * 0.06)
    for s in (-1, 1):
        x0 = cx + s * gap // 2 - (leg_w if s < 0 else 0)
        cv2.rectangle(m, (x0, top + body), (x0 + leg_w, top + hh), 255, -1)
    return m > 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="reports/repeatability/upright.json")
    a = ap.parse_args()
    subjects = {"synthetic_shorts": synthetic(kind="shorts"), "synthetic_jeans": synthetic(kind="jeans")}
    for p in sorted(glob.glob(str(ROOT / "reports/repeatability/masks/*.png"))):
        subjects[Path(p).stem] = cv2.imread(p, 0) > 127
    rows = []
    for name, m0 in subjects.items():
        base_pca, _ = pca_angle(m0)
        base_wb, _ = waistband_angle(m0)
        base_flat, _ = flatten_top_angle(m0)
        for t in TRUE_ANGLES:
            m = rotate(m0, t) if t else m0
            pa, el = pca_angle(m)
            wa, fr = waistband_angle(m)
            fa, fs = flatten_top_angle(m)
            rows.append({"subject": name, "true_delta_deg": t, "elongation": el,
                         "pca_deg": pa, "pca_err": _wrap(pa - (base_pca + t)),
                         "wb_deg": wa, "wb_err": _wrap(wa - (base_wb + t)) if (wa is not None and base_wb is not None) else None,
                         "wb_inlier_frac": fr,
                         "flat_deg": fa, "flat_err": _wrap(fa - (base_flat + t)), "flat_score": fs,
                         "synthetic": name.startswith("synthetic")})
    real = [r for r in rows if not r["synthetic"]]
    def stats(key):
        e = [abs(r[key]) for r in real if r[key] is not None]
        return {"n": len(e), "median_abs_err_deg": float(np.median(e)) if e else None,
                "p90_abs_err_deg": float(np.percentile(e, 90)) if e else None,
                "over_3deg": sum(1 for v in e if v > 3.0), "over_1deg": sum(1 for v in e if v > 1.0)}
    # would correcting make it worse? residual |true+base - estimate| vs |true| (doing nothing leaves the true tilt)
    def harm(key):
        bad = 0; n = 0
        for r in real:
            if r[key] is None: continue
            n += 1
            if abs(r[key]) > abs(r["true_delta_deg"]) and r["true_delta_deg"] != 0: bad += 1
        return {"n": n, "correction_worse_than_nothing": bad}
    out = {"true_angles_deg": TRUE_ANGLES, "rows": rows,
           "pca": {**stats("pca_err"), **harm("pca_err")},
           "waistband": {**stats("wb_err"), **harm("wb_err")},
           "flatten_top": {**stats("flat_err"), **harm("flat_err")},
           "waistband_unavailable": sum(1 for r in real if r["wb_deg"] is None)}
    (ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out).write_text(json.dumps(out, indent=1))
    for k in ("pca", "waistband", "flatten_top"):
        d = out[k]
        print(f"{k:10s} n={d['n']:3d} median |err| {d['median_abs_err_deg']:.2f}°  p90 {d['p90_abs_err_deg']:.2f}°  "
              f">1° in {d['over_1deg']}  >3° in {d['over_3deg']}  correction worse than nothing in {d['correction_worse_than_nothing']}")
    print(f"waistband estimate unavailable on {out['waistband_unavailable']} of {len(real)} real cases")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

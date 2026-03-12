"""EXP_0033: does the AFTER->BEFORE registration TPS fold?

EXP_0030/0031 measured folding in the canonical map (image -> canonical template). That map is
built from a single garment's landmarks and is used by predict.py. It is NOT the map that makes
the ground truth. `register.warp_after_to_before` fits a SEPARATE thin-plate spline directly from
before-coords to after-coords (register.py:26) and remaps the after photo through it. Its output --
real.png and real_mask.png -- is what every silhouette IoU and hem chamfer in the bench is scored
AGAINST. A TPS has no injectivity guarantee here either, and if this one folds, the ground truth
itself is mangled: two before-pixels pull from the same after-pixel, duplicating garment content.

Nobody has measured it. This does, over the before-frame garment, for every pair the bench scores.

Usage: python tools/experiment_registration_fold.py [--usable-only]
"""
import argparse, glob, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import cv2, numpy as np
from denimtwin.canon.register import _tps, SURVIVING, heldout_residual


def fold_fraction(t_b2a, mask, h=2.0, samples=1500):
    """Fraction of before-frame garment pixels where the before->after TPS turns space inside out."""
    ys, xs = np.nonzero(mask)
    if not len(xs):
        return float("nan")
    idx = np.linspace(0, len(xs) - 1, min(samples, len(xs))).astype(int)
    P = np.stack([xs[idx], ys[idx]], 1).astype(np.float32)

    def f(p):
        _, m = t_b2a.applyTransformation(np.ascontiguousarray(p, np.float32)[None])
        return m[0]

    f0 = f(P); fx = f(P + np.array([h, 0], np.float32)); fy = f(P + np.array([0, h], np.float32))
    jx = (fx - f0) / h; jy = (fy - f0) / h
    det = jx[:, 0] * jy[:, 1] - jx[:, 1] * jy[:, 0]
    return float((det <= 0).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="experiments/pairs")
    ap.add_argument("--usable-only", action="store_true")
    a = ap.parse_args()
    ex = Path("data/priors/exclude.txt")
    EXCLUDE = {l.split()[0] for l in ex.read_text().splitlines()
               if l.strip() and not l.startswith("#")} if ex.exists() else set()
    rows = []
    for d in sorted(glob.glob(f"{a.pairs}/*")):
        d = Path(d); pid = d.name
        note = d / "NOTE.md"
        rejected = note.exists() and "rejected" in note.open().readline()
        if a.usable_only and (rejected or pid in EXCLUDE or not (d / "modification.json").exists()):
            continue
        try:
            lmb = json.load(open(d / "before_lm.json"))["landmarks"]
            lma = json.load(open(d / "after_lm.json"))["landmarks"]
            bmask = cv2.imread(str(d / "bmask.png"), cv2.IMREAD_GRAYSCALE) > 127
        except Exception:
            continue
        names = [n for n in SURVIVING if n in lma and n in lmb]
        if len(names) < 4:
            continue
        A = np.array([lma[n] for n in names], np.float32)
        B = np.array([lmb[n] for n in names], np.float32)
        t = _tps(B, A)
        rows.append({"pair": pid, "n_landmarks": len(names), "names": names,
                     "fold_fraction": round(fold_fraction(t, bmask), 4),
                     "heldout_resid_px": round(float(heldout_residual(A, B)), 2)})
    ff = np.array([r["fold_fraction"] for r in rows], float)
    print(json.dumps({"summary": {
        "n_pairs": len(rows),
        "median_fold": round(float(np.nanmedian(ff)), 4) if len(ff) else None,
        "max_fold": round(float(np.nanmax(ff)), 4) if len(ff) else None,
        "n_over_20pct": int((ff > 0.20).sum()),
        "n_zero": int((ff == 0).sum()),
    }, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()

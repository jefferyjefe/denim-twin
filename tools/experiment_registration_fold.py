"""EXP_0033: does the AFTER->BEFORE registration TPS fold?

EXP_0030/0031 measured folding in the canonical map (image -> canonical template). That map is
built from a single garment's landmarks and is used by predict.py. It is NOT the map that makes
the ground truth. `register.warp_after_to_before` fits a SEPARATE thin-plate spline directly from
before-coords to after-coords (register.py:26) and remaps the after photo through it. Its output --
real.png and real_mask.png -- is what every silhouette IoU and hem chamfer in the bench is scored
AGAINST. A TPS has no injectivity guarantee here either, and if this one folds, the ground truth
itself is mangled: two before-pixels pull from the same after-pixel, duplicating garment content.

Nobody has measured it. This does, over the before-frame garment, for every pair the bench scores.

Usage: python tools/experiment_registration_fold.py [--all-pairs]
The seven scored pairs are the default; --all-pairs is a diagnostic view, not a publishable one.
"""
import argparse, glob, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
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


def build(pairs=None, all_pairs=False):
    """The report as a value, so tools/make_reports.py --check can detect it going stale."""
    return _run(argparse.Namespace(pairs=pairs or str(ROOT / "experiments/pairs"), all_pairs=all_pairs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(ROOT / "experiments/pairs"))
    # The scored-pair filter is the DEFAULT, not an opt-in. It used to be `--usable-only`, so the
    # obvious invocation silently produced a report over every directory on disk -- excluded pairs
    # (a legs-only crop, a back view, a TEST submission) and rejected ones included -- while the
    # committed report and the NOTE quoting it described the seven scored pairs. Regenerating the
    # obvious way would have replaced one with the other and nothing would have said so.
    ap.add_argument("--all-pairs", action="store_true",
                    help="include excluded and rejected directories (diagnostic only; not publishable)")
    ap.add_argument("--usable-only", action="store_true",
                    help=argparse.SUPPRESS)   # deprecated: this is now the default, kept so old invocations still work
    a = ap.parse_args()
    print(json.dumps(_run(a), indent=2))


def _run(a):
    # Resolved against the repository, never the working directory: a cwd-relative read of
    # exclude.txt silently yields an EMPTY exclude set when the tool is run from anywhere else,
    # and the excluded pairs (a legs-only crop, a back view, a TEST submission) then enter a
    # published result with no error raised. Missing is a hard failure for the same reason.
    ex = ROOT / "data/priors/exclude.txt"
    if not ex.exists():
        sys.exit(f"missing {ex}: refusing to run with an empty exclude set")
    EXCLUDE = {l.split()[0] for l in ex.read_text().splitlines()
               if l.strip() and not l.startswith("#")} if ex.exists() else set()
    rows = []
    for d in sorted(glob.glob(f"{a.pairs}/*")):
        d = Path(d); pid = d.name
        note = d / "NOTE.md"
        rejected = note.exists() and "rejected" in note.open().readline()
        if not a.all_pairs and (rejected or pid in EXCLUDE or not (d / "modification.json").exists()):
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
    return {"summary": {
        "n_pairs": len(rows),
        "median_fold": round(float(np.nanmedian(ff)), 4) if len(ff) else None,
        "max_fold": round(float(np.nanmax(ff)), 4) if len(ff) else None,
        "n_over_20pct": int((ff > 0.20).sum()),
        "n_zero": int((ff == 0).sum()),
    }, "rows": rows}


if __name__ == "__main__":
    main()

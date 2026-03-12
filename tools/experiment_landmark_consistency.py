"""EXP_0032: how many found-pair landmark sets are geometrically inconsistent, and does it
predict which garments the canonical map folds?

Usage: python tools/experiment_landmark_consistency.py [--pairs experiments/pairs]
"""
import argparse, glob, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import cv2, numpy as np
from denimtwin.canon.lmcheck import check_landmarks, worst_severity
from denimtwin.canon.warp import CanonicalMap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="experiments/pairs")
    ap.add_argument("--tol-frac", type=float, default=0.01)
    ap.add_argument("--usable-only", action="store_true",
                    help="only pairs the bench actually scores: accepted, not in exclude.txt, has modification.json")
    a = ap.parse_args()
    ex = Path("data/priors/exclude.txt")
    EXCLUDE = {l.split()[0] for l in ex.read_text().splitlines()
               if l.strip() and not l.startswith("#")} if ex.exists() else set()
    rows = []
    for f in sorted(glob.glob(f"{a.pairs}/*/*_lm.json")):
        p = Path(f); pid = p.parent.name; which = p.name.split("_")[0]
        note = p.parent / "NOTE.md"
        rejected = note.exists() and "rejected" in note.open().readline()
        if a.usable_only and (rejected or pid in EXCLUDE or not (p.parent / "modification.json").exists()):
            continue
        lm = json.load(open(f))["landmarks"]
        fnd = check_landmarks(lm, tol_frac=a.tol_frac)
        mp = p.parent / ("bmask.png" if which == "before" else "amask.png")
        try:
            mask = cv2.imread(str(mp), cv2.IMREAD_GRAYSCALE) > 127
            fold = CanonicalMap(lm, drop_degenerate=False).fold_fraction(mask)
        except Exception:
            fold = float("nan")
        try:
            cm = CanonicalMap(lm, drop_degenerate=True)
            fold_d = cm.fold_fraction(mask); dropped = list(cm.dropped)
        except Exception:
            fold_d, dropped = float("nan"), []
        rows.append({"pair": pid, "which": which, "severity": worst_severity(fnd),
                     "rejected": bool(rejected), "excluded": pid in EXCLUDE,
                     "findings": fnd, "fold_fraction_undropped": round(float(fold), 4),
                     "fold_fraction_dropped": round(float(fold_d), 4), "warp_dropped": dropped})
    n_inv = sum(r["severity"] == "inverted" for r in rows)
    n_deg = sum(r["severity"] == "degenerate" for r in rows)
    folds = np.array([r["fold_fraction_undropped"] for r in rows], float)
    foldd = np.array([r["fold_fraction_dropped"] for r in rows], float)
    flag = np.array([r["severity"] is not None for r in rows])
    ok = ~np.isnan(folds)
    summary = {
        "n_sets": len(rows), "n_inverted": n_inv, "n_degenerate": n_deg,
        "n_clean": len(rows) - n_inv - n_deg,
        "median_fold_flagged": round(float(np.median(folds[flag & ok])), 4) if (flag & ok).any() else None,
        "median_fold_clean": round(float(np.median(folds[~flag & ok])), 4) if (~flag & ok).any() else None,
        "max_fold_clean": round(float(np.max(folds[~flag & ok])), 4) if (~flag & ok).any() else None,
        "median_fold_flagged_after_drop": round(float(np.median(foldd[flag & ok])), 4) if (flag & ok).any() else None,
        "median_fold_clean_after_drop": round(float(np.median(foldd[~flag & ok])), 4) if (~flag & ok).any() else None,
        "max_fold_after_drop": round(float(np.nanmax(foldd)), 4),
        "n_flagged_where_warp_dropped_nothing": int(sum(
            1 for r in rows if r["severity"] and not r["warp_dropped"])),
    }
    print(json.dumps({"summary": summary, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()

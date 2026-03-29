"""EXP_0032: how many found-pair landmark sets are geometrically inconsistent, and does it
predict which garments the canonical map folds?

Usage: python tools/experiment_landmark_consistency.py [--all-pairs]
The seven scored pairs are the default; --all-pairs is a diagnostic view, not a publishable one.
"""
import argparse, glob, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import cv2, numpy as np
from denimtwin.canon.lmcheck import check_landmarks, worst_severity
from denimtwin.canon.warp import CanonicalMap


def build(pairs=None, all_pairs=False, tol_frac=0.01):
    """The report as a value, so tools/make_reports.py --check can detect it going stale."""
    return _run(argparse.Namespace(pairs=pairs or str(ROOT / "experiments/pairs"),
                                   all_pairs=all_pairs, tol_frac=tol_frac, usable_only=False))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(ROOT / "experiments/pairs"))
    ap.add_argument("--tol-frac", type=float, default=0.01)
    # The scored-pair filter is the DEFAULT, not an opt-in. It used to be `--usable-only`, so the
    # invocation in this file's own usage line silently produced a report over every directory on
    # disk, while the committed report and EXP_0032's NOTE described the seven scored pairs.
    ap.add_argument("--all-pairs", action="store_true",
                    help="include excluded and rejected directories (diagnostic only; not publishable)")
    ap.add_argument("--usable-only", action="store_true",
                    help=argparse.SUPPRESS)   # deprecated: this is now the default
    a = ap.parse_args()
    print(json.dumps(_run(a), indent=2))


def _run(a):
    # Resolved against the repository, never the working directory: a cwd-relative read of
    # exclude.txt silently yields an EMPTY exclude set when the tool is run from anywhere else,
    # and the excluded pairs (a legs-only crop, a back view, a TEST submission) then enter a
    # published result with no error raised. Missing is a hard failure for the same reason.
    ex = ROOT / "data/priors/exclude.txt"
    if not ex.exists():
        # A raise, not sys.exit. tools/make_reports.py calls build() in-process and classifies what
        # comes back; SystemExit is not an Exception, so it would tear the caller down instead of
        # being reported as this tool refusing to run. The refusal is unchanged, message included --
        # an empty exclude set silently admits the banned pairs into a published result.
        raise RuntimeError(f"missing {ex}: refusing to run with an empty exclude set")
    EXCLUDE = {l.split()[0] for l in ex.read_text().splitlines()
               if l.strip() and not l.startswith("#")} if ex.exists() else set()
    rows = []
    for f in sorted(glob.glob(f"{a.pairs}/*/*_lm.json")):
        p = Path(f); pid = p.parent.name; which = p.name.split("_")[0]
        note = p.parent / "NOTE.md"
        rejected = note.exists() and "rejected" in note.open().readline()
        if not a.all_pairs and (rejected or pid in EXCLUDE or not (p.parent / "modification.json").exists()):
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
    if not rows:
        # np.nanmax over the empty fold array raised "zero-size array to reduction operation" from
        # inside the summary, naming nothing. The landmark files this reads are TRACKED, so an empty
        # run is a damaged checkout, not the gitignored-evidence case -- said here in those words.
        n_dirs = len(glob.glob(f"{a.pairs}/*"))
        raise RuntimeError(
            f"no landmark set to check: none of the {n_dirs} director(ies) in {a.pairs} has a "
            f"*_lm.json beside a modification.json. Both are tracked in git, so a checkout with "
            f"none of them is damaged: restore it with `git checkout experiments/pairs`")
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
    return {"summary": summary, "rows": rows}


if __name__ == "__main__":
    main()

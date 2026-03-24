#!/usr/bin/env python3
"""Regenerate the derived reports that had no committed tool, and detect stale ones.

Review 7 found two holes that together let a whole cascade of published numbers go stale:

  1. Six reports carrying published numbers were produced by ad-hoc inline scripts during a
     session. Nothing in the repository could re-derive them, so nobody could tell whether they
     still described the data.
  2. `check_claims.py` validates NOTE-to-report. It cannot see report-to-DATA drift, so when
     EXP_0038 regenerated experiments/pairs (moving every pair's inseam_fraction, one of them by
     0.105) the reports kept their old numbers and `verify.py` stayed green while four experiments
     and the README published figures that no longer reproduced.

This closes both: every report below has a function here, `--check` regenerates each into memory
and diffs it against the committed file, and `verify.py` runs `--check` as a required gate.

    make_reports.py --check [--all]    # exit 1 if any report is stale
    make_reports.py --write [--all]    # regenerate in place
`--all` includes reports whose inputs are expensive comparison runs that may not be present.
"""
import argparse, glob, json, sys
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(Path(__file__).resolve().parent))   # sibling tools are importable as builders
# appended, not inserted: tools/ contains modules named `agents`, `compare`, `predict`, `bench`,
# `sentinel` -- names a future dependency could also claim. Ahead of stdlib they would win silently.


def _excluded():
    p = ROOT / "data/priors/exclude.txt"
    return {l.split()[0] for l in p.read_text().splitlines()
            if l.strip() and not l.startswith("#")} if p.exists() else set()


def scored_pairs(pairs=None):
    """The pairs the bench actually scores: accepted, not excluded, has a modification."""
    base = Path(pairs or (ROOT / "experiments/pairs"))
    ex = _excluded()
    out = []
    for m in sorted(glob.glob(str(base / "*/modification.json"))):
        d = Path(m).parent
        note = d / "NOTE.md"
        if note.exists() and "rejected" in note.open().readline():
            continue
        if d.name in ex:
            continue
        out.append(d)
    return out


def _mask(p):
    im = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
    return None if im is None else im > 127


def _iou(a, b):
    u = int((a | b).sum())
    return float((a & b).sum() / u) if u else float("nan")


def fringe_capable_pairs():
    rows = []
    for d in scored_pairs():
        mod = json.load(open(d / "modification.json"))
        et = mod.get("edge_treatment", "?")
        state = "after_wash" if "after_wash" in (d / "NOTE.md").read_text() else "after_cut"
        rows.append({"pair": d.name, "edge_treatment": et, "state": state,
                     "can_show_a_fringe": bool(et == "raw" and state == "after_wash")})
    s = {"n_pairs": len(rows),
         "n_raw_edge": sum(r["edge_treatment"] == "raw" for r in rows),
         "n_after_wash": sum(r["state"] == "after_wash" for r in rows),
         "n_can_show_a_fringe": sum(r["can_show_a_fringe"] for r in rows)}
    return {"summary": s, "rows": rows}


def prediction_vs_croponly_masks(product="experiments/pairs_predict_post0038"):
    rows = []
    for od in sorted(glob.glob(str(ROOT / product / "*/cmp"))):
        od = Path(od)
        pred = _mask(od.parent / "pred_median_mask.png")
        keep = _mask(od / "keep_mask.png")
        if pred is None or keep is None or pred.shape != keep.shape:
            continue
        u = int((pred | keep).sum())
        rows.append({"pair": od.parent.name,
                     "iou_pred_vs_keep": round(_iou(pred, keep), 5),
                     "pred_only_px": int((pred & ~keep).sum()),
                     "keep_only_px": int((keep & ~pred).sum()),
                     "sym_diff_pct_of_union": round(100 * ((pred & ~keep).sum() + (keep & ~pred).sum()) / u, 4)})
    s = {"n_pairs": len(rows),
         "median_iou_pred_vs_keep": round(float(np.median([r["iou_pred_vs_keep"] for r in rows])), 5),
         "max_keep_only_px": int(max(r["keep_only_px"] for r in rows)),
         "max_pred_only_px": int(max(r["pred_only_px"] for r in rows)),
         "median_sym_diff_pct": round(float(np.median([r["sym_diff_pct_of_union"] for r in rows])), 4),
         "n_pairs_bit_identical": int(sum(1 for r in rows if r["sym_diff_pct_of_union"] == 0))}
    return {"summary": s, "rows": rows}


def frac_predictor_vs_constant():
    m = json.load(open(ROOT / "reports/frac_predictor_scored.json"))
    b = json.load(open(ROOT / "reports/independent_null.json"))
    bd = {r["pair"]: r for r in b["rows"]}
    rows = []
    for r in m["rows"]:
        c = bd.get(r["pair"])
        if not c:
            continue
        rows.append({"pair": r["pair"], "true_frac": r["own_frac"],
                     "predictor_frac": r["loo_frac"], "constant_frac": c["loo_frac"],
                     "iou_predictor": r["iou_loo_null"], "iou_constant": c["iou_loo_null"],
                     "predictor_better": bool(r["iou_loo_null"] > c["iou_loo_null"])})
    s = {"n_pairs": len(rows),
         "mean_iou_predictor": round(sum(r["iou_predictor"] for r in rows) / len(rows), 4),
         "mean_iou_constant": round(sum(r["iou_constant"] for r in rows) / len(rows), 4),
         "n_pairs_predictor_better": sum(r["predictor_better"] for r in rows),
         "n_pairs_predictor_worse": sum(not r["predictor_better"] for r in rows)}
    s["predictor_beats_constant"] = s["mean_iou_predictor"] > s["mean_iou_constant"]
    return {"summary": s, "rows": rows}


def _ab(before_dir, after_dir, gated_flag="fringe mask ignored for the hem fit"):
    def pred(p):
        f = Path(p) / "cmp_median/metrics.json"
        if not f.exists():
            return None
        return {x["system"]: x for x in json.load(open(f))["rows"]}["prediction"]
    rows = []
    for d in scored_pairs():
        a, b = pred(ROOT / before_dir / d.name), pred(ROOT / after_dir / d.name)
        if not a or not b:
            continue
        gated = gated_flag in (ROOT / after_dir / d.name / "NOTE.md").read_text()
        rows.append({"pair": d.name, "gated": gated,
                     "sil_iou_before": round(a["sil_iou_vs_real"], 4),
                     "sil_iou_after": round(b["sil_iou_vs_real"], 4),
                     "hem_before": round(a["hem_chamfer"], 2), "hem_after": round(b["hem_chamfer"], 2),
                     "d_sil_iou": round(b["sil_iou_vs_real"] - a["sil_iou_vs_real"], 4),
                     "d_hem": round(b["hem_chamfer"] - a["hem_chamfer"], 2)})
    return rows


def fringe_gate_ab():
    rows = _ab("experiments/pairs_prefringegate", "experiments/pairs")
    A = np.array([[r["sil_iou_before"], r["sil_iou_after"], r["hem_before"], r["hem_after"]] for r in rows])
    s = {"n_pairs": len(rows), "n_gated": sum(r["gated"] for r in rows),
         "mean_sil_iou_before": round(float(A[:, 0].mean()), 4),
         "mean_sil_iou_after": round(float(A[:, 1].mean()), 4),
         "mean_hem_before": round(float(A[:, 2].mean()), 2),
         "mean_hem_after": round(float(A[:, 3].mean()), 2),
         "n_improved": sum(r["d_sil_iou"] > 0 for r in rows),
         "n_worsened": sum(r["d_sil_iou"] < 0 for r in rows),
         "n_unchanged": sum(r["d_sil_iou"] == 0 for r in rows),
         "best_hem_improvement_px": round(float(min(r["d_hem"] for r in rows)), 2),
         "worst_hem_regression_px": round(float(max(r["d_hem"] for r in rows)), 2)}
    s["mean_sil_iou_delta"] = round(s["mean_sil_iou_after"] - s["mean_sil_iou_before"], 4)
    s["mean_hem_delta"] = round(s["mean_hem_after"] - s["mean_hem_before"], 2)
    return {"summary": s, "rows": rows}


def waistband_landmark():
    from experiment_waistband_landmark import build
    return build(landmarks="recomputed")


def waistband_landmark_production():
    from experiment_waistband_landmark import build
    return build(landmarks="production")


def segmentation_provenance():
    # expensive: re-segments the seven before photographs with SAM, so it needs torch and the
    # checkpoint. Raises FileNotFoundError without them, which --check treats as a legitimate skip.
    from experiment_segmentation_provenance import build
    return build()


def registration_fold():
    from experiment_registration_fold import build
    return build()


def landmark_consistency():
    from experiment_landmark_consistency import build
    return build()


# report path -> (builder, expensive?)
REPORTS = {
    "reports/segmentation_provenance.json": (segmentation_provenance, True),
    "reports/registration_fold.json": (registration_fold, False),
    "reports/landmark_consistency.json": (landmark_consistency, False),
    "reports/waistband_landmark.json": (waistband_landmark, False),
    "reports/waistband_landmark_production.json": (waistband_landmark_production, False),
    "reports/fringe_capable_pairs.json": (fringe_capable_pairs, False),
    "reports/prediction_vs_croponly_masks.json": (prediction_vs_croponly_masks, False),
    "reports/frac_predictor_vs_constant.json": (frac_predictor_vs_constant, False),
    "reports/fringe_gate_ab.json": (fringe_gate_ab, True),
}


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--all", action="store_true", help="include reports with expensive inputs")
    a = ap.parse_args()
    stale, skipped, ok = [], [], []
    for rel, (fn, expensive) in REPORTS.items():
        if expensive and not a.all:
            skipped.append(rel); continue
        try:
            fresh = fn()
        except FileNotFoundError as e:
            # A missing INPUT is a legitimate reason not to check a report: the expensive A/B arms
            # are gitignored and absent in a fresh clone. Anything else is the builder being broken,
            # and that must fail -- it used to be swallowed as a skip with exit 0, so a builder that
            # raised left verify.py green while its report drifted arbitrarily far from the data.
            # That is the exact hole this module was written to close, reopened one level up.
            if expensive:
                skipped.append(f"{rel} (input missing: {e})")
                continue
            stale.append(f"{rel}: builder could not find an input it needs ({e})")
            continue
        except Exception as e:
            stale.append(f"{rel}: builder raised {type(e).__name__}: {e}")
            continue
        p = ROOT / rel
        if a.write:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(fresh, indent=2) + "\n")
            ok.append(rel); continue
        if not p.exists():
            stale.append(f"{rel}: MISSING"); continue
        cur = json.load(open(p))
        if cur.get("summary") != fresh.get("summary"):
            diffs = [k for k in set(list(cur.get("summary", {})) + list(fresh["summary"]))
                     if cur.get("summary", {}).get(k) != fresh["summary"].get(k)]
            stale.append(f"{rel}: summary differs on {sorted(diffs)}")
        else:
            ok.append(rel)
    for s in skipped:
        print(f"  skip  {s}")
    for s in ok:
        print(f"  ok    {s}")
    for s in stale:
        print(f"  STALE {s}")
    if stale:
        print(f"\n{len(stale)} report(s) no longer match the data. Run tools/make_reports.py --write "
              f"and update any NOTE that quotes them.")
        return 1
    print(f"\n{len(ok)} report(s) current, {len(skipped)} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

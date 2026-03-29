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

THREE OUTCOMES, NOT TWO. A report can fail to be re-derived for two completely different reasons and
this module used to conflate them. On a clean clone six reports came out STALE -- "the committed
numbers no longer match the data" -- when the truth was that the masks and scoring output they are
derived FROM are gitignored (data/external/README.md: only derived numbers enter this repository)
and simply absent. Two of the six did not even reach that message; they crashed on an empty rows
list and were reported as "builder raised", which reads exactly like a broken builder.

So every report now declares the inputs it is derived from, as `Need`s that point at the registry in
src/denimtwin/prereqs.py, and those are checked BEFORE the builder runs:

    ok           regenerated and it matches the committed file
    STALE        regenerated from inputs that were ALL present, and it does NOT match. Exit 1.
    UNAVAILABLE  an input is absent. The committed numbers were not re-derived: they are neither
                 confirmed nor refuted. Never printed as a pass; `--require-inputs` makes it exit 1.
    skip         not requested, because --all was not passed. Nothing else may use this word.

A declared need is a licence to exit 0, so it is spent only where absence is BY DESIGN, and two
rules keep it from becoming the next place a check quietly stops checking:

  * Committed inputs are never declared as needs. experiments/pairs/*/modification.json, and the two
    reports frac_predictor_vs_constant reads, are tracked in git; if they are gone the checkout is
    damaged, and that must stay loud rather than be excused as "input absent".
  * A builder that raises with all its declared inputs present is STALE, whatever it raised. That is
    the review-7 hole this module exists to close (exceptions swallowed as skips, exit 0) and the
    old `if expensive:` branch in the FileNotFoundError handler was it, reopened one level up.
"""
import argparse, glob, json, sys
from pathlib import Path
import cv2, numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(Path(__file__).resolve().parent))   # sibling tools are importable as builders
# appended, not inserted: tools/ contains modules named `agents`, `compare`, `predict`, `bench`,
# `sentinel` -- names a future dependency could also claim. Ahead of stdlib they would win silently.
from denimtwin import prereqs as P


class Need:
    """One input a report is derived FROM, and what its absence means.

    The join between a report and src/denimtwin/prereqs.py. `resource` names the registry entry that
    knows how to produce this input and what a run without it may still conclude -- one source of
    truth, so the command that regenerates a batch is written down once. `pattern` narrows the check
    to the exact file this builder opens where that is narrower than the resource's own probe:
    `pair_masks` probes amask.png, EXP_0033 measures its fold fraction over bmask.png, and the two
    come out of the same batch run.
    """

    __slots__ = ("resource", "pattern", "min_count", "why", "_how")

    def __init__(self, why, resource=None, pattern=None, min_count=None, how=None):
        if resource is None and pattern is None:
            raise ValueError("a Need must name a prereqs resource, a glob, or both")
        if resource is not None and resource not in P.RESOURCES:
            raise KeyError(f"unknown resource {resource!r}; declare it in src/denimtwin/prereqs.py")
        if resource is None and how is None:
            raise ValueError(f"need {pattern!r} names no resource, so it must say how to satisfy it")
        self.resource, self.pattern, self.why, self._how = resource, pattern, why, how
        if min_count is not None:
            self.min_count = min_count
        elif pattern is None:
            self.min_count = P.RESOURCES[resource].min_count
        else:
            self.min_count = 1

    @property
    def targets(self):
        return [self.pattern] if self.pattern else list(P.RESOURCES[self.resource].targets)

    @property
    def how(self):
        return self._how or P.RESOURCES[self.resource].how

    @property
    def absent_means(self):
        return P.RESOURCES[self.resource].absent_means if self.resource else self.why

    def found(self):
        if self.pattern is None:
            return P.RESOURCES[self.resource].found()
        return len(glob.glob(str(ROOT / self.pattern), recursive=True))

    def available(self):
        # No pattern: the registry's own probe decides, so a module or a checkpoint is asked about
        # in exactly the way conftest and verify.py ask about it.
        if self.pattern is None:
            return P.available(self.resource)
        return self.found() >= self.min_count

    def label(self):
        return ", ".join(self.targets)

    def describe(self):
        return f"{self.label()} (found {self.found()}, need {self.min_count}) -- {self.why}"


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
    if not rows:
        # Reached only if the pre-flight in main() found the inputs present and they are unusable
        # anyway -- a shape mismatch, an unreadable PNG. It used to be `max()` over an empty list:
        # "ValueError: max() arg is an empty sequence", from line 92, naming nothing.
        raise RuntimeError(
            f"no comparable pair under {product}: "
            f"{len(glob.glob(str(ROOT / product / '*/cmp')))} cmp/ director(ies) are there, but not "
            f"one of them has a pred_median_mask.png and a cmp/keep_mask.png that both load at the "
            f"same shape. Regenerate with: PAIRS_OUT={product} "
            f"python tools/run_pairs_batch.py --predict")
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
    if not rows:
        # Both inputs are git-tracked, so this is a damaged checkout, not an absent input. It is a
        # hard error for the same reason it is not a declared Need: nothing here may exit 0 on it.
        raise RuntimeError(
            "reports/frac_predictor_scored.json and reports/independent_null.json share no pair. "
            "Both are tracked in git; restore them with `git checkout reports/`.")
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


def fringe_gate_ab(before_dir="experiments/pairs_prefringegate", after_dir="experiments/pairs"):
    rows = _ab(before_dir, after_dir)
    if not rows:
        # It used to index a (0, ) array as if it were 2-D: "IndexError: too many indices for array",
        # from line 146, with no clue which of the two arms was the empty one.
        n_b = len(glob.glob(str(ROOT / before_dir / "*/cmp_median/metrics.json")))
        n_a = len(glob.glob(str(ROOT / after_dir / "*/cmp_median/metrics.json")))
        raise RuntimeError(
            f"the fringe-gate A/B has no pair scored in BOTH arms: {before_dir} has {n_b} "
            f"cmp_median/metrics.json, {after_dir} has {n_a}, and {len(scored_pairs())} pair(s) are "
            f"scoreable. Regenerate the arm with: PAIRS_OUT={before_dir} "
            f"python tools/run_pairs_batch.py")
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
    # checkpoint. Both are declared needs below, so a machine without them gets UNAVAILABLE -- not
    # a skip, and not a claim that the report is fine.
    from experiment_segmentation_provenance import build
    return build()


def registration_fold():
    from experiment_registration_fold import build
    return build()


def landmark_consistency():
    from experiment_landmark_consistency import build
    return build()


# The gitignored batch output every mask-derived report is built from. Declared once: the pattern is
# per-report (each builder opens a different file out of the same run) but the command that produces
# them, and the sentence that says what their absence means, come from prereqs.py.
def _pair_file(name, why, min_count=7):
    return Need(why, resource="pair_masks", pattern=f"experiments/pairs/*/{name}", min_count=min_count)


# report path -> (builder, expensive?, needs). `needs` is the inputs whose absence is BY DESIGN --
# gitignored evidence, optional dependencies, model weights. Committed inputs are deliberately not
# listed: see the module docstring.
REPORTS = {
    "reports/segmentation_provenance.json": (segmentation_provenance, True, (
        Need("the segmenter this experiment re-runs is a torch model", resource="torch"),
        Need("SamSegmenter is a thin wrapper over Meta's package", resource="segment_anything"),
        Need("the coarse before-mask is reconstructed by re-segmenting, so the weights must be here",
             resource="sam_checkpoint"),
        _pair_file("before_native.png", "the photograph the coarse segmentation is reconstructed from"),
        _pair_file("bmask.png", "the refined mask the reconstruction is compared against"),
        Need("the control arm of the A/B, scored by the bench",
             pattern="experiments/pairs_lmprov_control/*/cmp_median/metrics.json", min_count=7,
             how="PAIRS_OUT=experiments/pairs_lmprov_control python tools/run_pairs_batch.py"),
        Need("the refit arm of the A/B, scored by the bench",
             pattern="experiments/pairs_lmprov_refit/*/cmp_median/metrics.json", min_count=7,
             how="PAIRS_OUT=experiments/pairs_lmprov_refit PAIRS_REFIT_LM=1 "
                 "python tools/run_pairs_batch.py"),
    )),
    "reports/registration_fold.json": (registration_fold, False, (
        _pair_file("bmask.png", "the before-frame garment the fold fraction is measured over"),
    )),
    "reports/landmark_consistency.json": (landmark_consistency, False, (
        _pair_file("bmask.png", "the before mask each before_lm set is warped over"),
        _pair_file("amask.png", "the after mask each after_lm set is warped over"),
    )),
    "reports/waistband_landmark.json": (waistband_landmark, False, (
        _pair_file("bmask.png", "landmarks and waistband corners are recomputed on it"),
        _pair_file("amask.png", "it is warped into the before frame to make the scoring target"),
        _pair_file("pred_median_mask.png", "the prediction each arm's registered mask is scored against"),
    )),
    "reports/waistband_landmark_production.json": (waistband_landmark_production, False, (
        _pair_file("bmask.png", "the waistband correspondence is read off it"),
        _pair_file("amask.png", "it is warped into the before frame to make the scoring target"),
        _pair_file("pred_median_mask.png", "the prediction each arm's registered mask is scored against"),
    )),
    "reports/fringe_capable_pairs.json": (fringe_capable_pairs, False, ()),
    "reports/prediction_vs_croponly_masks.json": (prediction_vs_croponly_masks, False, (
        Need("the crop-only keep mask, one half of the comparison", resource="pair_predict_batch"),
        Need("the predicted mask, the other half",
             pattern="experiments/pairs_predict_post0038/*/pred_median_mask.png", min_count=7,
             resource="pair_predict_batch"),
    )),
    "reports/frac_predictor_vs_constant.json": (frac_predictor_vs_constant, False, ()),
    "reports/fringe_gate_ab.json": (fringe_gate_ab, True, (
        Need("the pre-gate arm of the A/B", resource="pair_prefringegate"),
        Need("the post-gate arm: the current bench scores", resource="pair_cmp_metrics"),
    )),
}

OK, STALE, UNAVAILABLE, NOT_REQUESTED = "ok", "stale", "unavailable", "not_requested"


def evaluate(rel, fn, expensive, needs, want_all, write):
    """Classify one report. The needs are checked BEFORE the builder runs, so an absent input can
    never arrive disguised as an exception.

    Every outcome carries the same keys -- `missing`, `patterns`, `how`, `absent_means` are empty
    lists when nothing is absent -- so a caller reading the --json file never has to branch on the
    status just to look at them."""
    if expensive and not want_all:
        return {"status": NOT_REQUESTED, "missing": [],
                "why": "not requested: its inputs are expensive to produce; pass --all"}
    absent = [n for n in needs if not n.available()]
    if absent:
        return {"status": UNAVAILABLE,
                "missing": [n.describe() for n in absent],
                "patterns": [t for n in absent for t in n.targets],
                "how": list(dict.fromkeys(n.how for n in absent)),
                "absent_means": list(dict.fromkeys(n.absent_means for n in absent)),
                "why": f"{len(absent)} of {len(needs)} declared input(s) are absent from this "
                       f"checkout, so this report was NOT re-derived. Its committed numbers are "
                       f"neither confirmed nor refuted here."}
    try:
        fresh = fn()
    except Exception as e:
        # Every declared input was present, so this is the builder, not the checkout.
        return {"status": STALE, "missing": [],
                "why": f"builder raised {type(e).__name__}: {e}"}
    p = ROOT / rel
    if write:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(fresh, indent=2) + "\n")
        return {"status": OK, "missing": [], "why": "regenerated and written"}
    if not p.exists():
        return {"status": STALE, "missing": [], "why": "MISSING"}
    cur = json.load(open(p))
    if cur.get("summary") != fresh.get("summary"):
        diffs = sorted(k for k in set(list(cur.get("summary", {})) + list(fresh["summary"]))
                       if cur.get("summary", {}).get(k) != fresh["summary"].get(k))
        return {"status": STALE, "missing": [], "why": f"summary differs on {diffs}"}
    return {"status": OK, "missing": [], "why": "re-derived from its inputs and unchanged"}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--all", action="store_true", help="include reports with expensive inputs")
    ap.add_argument("--require-inputs", action="store_true",
                    help="exit 1 if any report's inputs are absent (a --profile full run cannot "
                         "issue a scientific pass over reports it never re-derived)")
    ap.add_argument("--json", metavar="PATH",
                    help="write the per-report status as JSON, so a caller can distinguish "
                         "'input absent' from 'numbers drifted' without parsing this output")
    a = ap.parse_args()

    results = {}
    for rel, (fn, expensive, needs) in REPORTS.items():
        v = {"missing": [], "patterns": [], "how": [], "absent_means": []}
        v.update(evaluate(rel, fn, expensive, needs, a.all, a.write))
        results[rel] = v
    of = lambda st: [r for r, v in results.items() if v["status"] == st]
    ok, stale, unavail, skipped = of(OK), of(STALE), of(UNAVAILABLE), of(NOT_REQUESTED)

    for rel in skipped:
        print(f"  skip  {rel} ({results[rel]['why']})")
    for rel in ok:
        print(f"  ok    {rel}")
    for rel in unavail:
        v = results[rel]
        print(f"  UNAVAIL {rel} (input absent: {v['missing'][0]})")
        for m in v["missing"][1:]:
            print(f"          also absent: {m}")
        for h in v["how"]:
            print(f"          satisfy with: {h}")
    for rel in stale:
        print(f"  STALE {rel}: {results[rel]['why']}")

    if a.json:
        out = dict(results)
        out["counts"] = {"total": len(results), "ok": len(ok), "stale": len(stale),
                         "unavailable": len(unavail), "not_requested": len(skipped)}
        jp = Path(a.json)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    verb = "written" if a.write else "current"
    if unavail:
        print(f"\n{len(unavail)} report(s) were NOT re-derived: an input they are built from is "
              f"absent from this checkout. This is not a pass -- their committed numbers were "
              f"neither confirmed nor refuted by this run.")
        for rel in unavail:
            for s in results[rel]["absent_means"]:
                print(f"  {rel}: {s}")
    if a.require_inputs and unavail:
        print(f"\n--require-inputs: {len(unavail)} report(s) could not be re-derived. Every missing "
              f"input, and the command that produces it:")
        for rel in unavail:
            print(f"  {rel}")
            for m in results[rel]["missing"]:
                print(f"      {m}")
            for h in results[rel]["how"]:
                print(f"      satisfy with: {h}")
    if stale:
        print(f"\n{len(stale)} report(s) no longer match the data. Run tools/make_reports.py --write "
              f"and update any NOTE that quotes them.")
    # Both blocks are printed before either decides the exit code: a run that is failing on drift
    # should still tell you what it could not check at all.
    if stale or (a.require_inputs and unavail):
        return 1
    print(f"\n{len(ok)} report(s) {verb}, {len(unavail)} unavailable (input absent), "
          f"{len(skipped)} not requested")
    return 0


if __name__ == "__main__":
    sys.exit(main())

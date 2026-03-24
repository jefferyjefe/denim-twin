"""EXP_0042: the before photograph is segmented twice, and nothing records which one a landmark came from.

`run_pair.py` segments the before photo coarsely, derives landmarks from that mask, and then -- only
if `autolm` found >= 14 landmarks -- re-segments with those landmarks as prompts and keeps the
REFINED mask while keeping the COARSE landmarks. The comment cites EXP_0004 ("recomputing them on
the refined mask regressed pair1"); that note does not contain the claim and its pair no longer
exists, so the reason for the current behaviour is not recoverable. EXP_0041 measured the cost: the
two segmentations disagree by up to 45 px, and that disagreement carried EXP_0040's headline result.

The result here is the A/B, run through the real pipeline on both arms. Everything else is context
for it, and the first draft of this experiment had four measurements that could not support their
claims -- a boundary-distance "fit" metric that is minimised by matching provenance in EITHER
direction (so an arm that recomputes nothing reproduces 97% of it), a leave-one-out residual
compared across arms whose evaluated points move, a third arm that is the first arm for any
statistic not involving the mask, and a top-row shift read off the raw mask rather than the row
`autolm` actually anchors on. They are gone rather than caveated.

What is measured:

  gate        -- which pairs refinement even RUNS on. It is gated on `len(landmarks) >= 14`, and 2 of
                 the 7 scored pairs are under it. Those two are not evidence that refinement is
                 harmless; they are evidence that it did not happen. The denominator is 5.
  refinement  -- on the treated pairs: what the second segmentation does to the mask. Its direction
                 is the cleanest thing here and the first draft did not report it.
  landmarks   -- how far the two landmark sets end up apart, per landmark and both coordinates.
  drift       -- how far the bench's ground truth WOULD move if the refined landmarks were adopted.
                 Conditional, not a statement that the committed ground truth is unstable.
  ab          -- the A/B: both arms through `run_pairs_batch.py`, scored by the bench's own metric.

The coarse mask is not stored, so it is reconstructed (`segment_garment_coarse` on
`before_native.png`, uprighted by the same rule). `segment_garment_coarse` is deterministic, the
reconstruction reproduces `before_lm.json` exactly on 7 of 7 pairs, and on the 2 pairs refinement
skipped it reproduces `bmask.png` bit-for-bit. On the 5 treated pairs the MASK has no independent
check -- only the landmarks derived from it do.

Usage: python tools/experiment_segmentation_provenance.py
       [--ab-control experiments/pairs_lmprov_control --ab-refit experiments/pairs_lmprov_refit]
Needs models/sam_vit_b_01ec64.pth; raises FileNotFoundError without it so make_reports can skip.
"""
import argparse, glob, json, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.append(str(Path(__file__).resolve().parent))
import cv2, numpy as np
from denimtwin.canon import upright as U
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon.register import SURVIVING, _tps
from denimtwin.canon.waistband import clean_mask, top_edge_row
from experiment_waistband_landmark import iou, paired, scored_pairs, warp_mask

CKPT = ROOT / "models" / "sam_vit_b_01ec64.pth"
REFINE_MIN_LANDMARKS = 14          # run_pair.py's gate; the denominator of everything below


def coarse_before_mask(seg, d):
    """The before mask as `run_pair` first segmented it, before landmark-prompted refinement.

    `run_pair` segments the pre-upright photograph and uprights the mask afterwards, so this does
    the same -- uprighting an already-uprighted image is a second correction (EXP_0028)."""
    from denimtwin.seg.sam import segment_garment_coarse
    native = cv2.imread(str(d / "before_native.png"))
    if native is None:
        raise FileNotFoundError(f"{d}/before_native.png")
    m, _, _ = segment_garment_coarse(seg, native)
    if m is None:
        return None
    _, m_up, _ = U.upright(native, m, deadband=0.0)
    return m_up


def anchor_row(mask):
    """The row `autolm` anchors every landmark on -- `top_edge_row(clean_mask(m))`, not the raw
    mask's first non-empty row. The first draft used the raw row and it pointed at the wrong pair:
    +55 px on a garment whose anchor moved 4 px, -6 px on the one whose landmarks moved 45."""
    return top_edge_row(clean_mask(mask))


def load_arm(dirname):
    """Bench metrics for one batch arm, honouring exclude.txt and rejected NOTEs as the bench does."""
    ex = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
          if l.strip() and not l.startswith("#")}
    out = {}
    for f in sorted(glob.glob(str(Path(dirname) / "*/cmp_median/metrics.json"))):
        pid = Path(f).parents[1].name
        note = Path(f).parents[1] / "NOTE.md"
        if pid in ex or (note.exists() and note.open().readline().startswith("# PAIR — rejected")):
            continue
        r = {x["system"]: x for x in json.load(open(f))["rows"]}
        if "prediction" in r:
            out[pid] = r["prediction"]
    return out


def build(pairs=None, ab_control=None, ab_refit=None):
    return _run(argparse.Namespace(
        pairs=pairs or str(ROOT / "experiments/pairs"), verbose=False,
        ab_control=ab_control or str(ROOT / "experiments/pairs_lmprov_control"),
        ab_refit=ab_refit or str(ROOT / "experiments/pairs_lmprov_refit")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(ROOT / "experiments/pairs"))
    ap.add_argument("--ab-control", default=str(ROOT / "experiments/pairs_lmprov_control"))
    ap.add_argument("--ab-refit", default=str(ROOT / "experiments/pairs_lmprov_refit"))
    ap.add_argument("--out", default=str(ROOT / "reports/segmentation_provenance.json"))
    ap.add_argument("--quiet", dest="verbose", action="store_false", default=True)
    a = ap.parse_args()
    res = _run(a)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps(res["summary"], indent=1))


def _run(a):
    if not CKPT.exists():
        raise FileNotFoundError(f"{CKPT} (SAM weights); this experiment re-segments the before photos")
    from denimtwin.seg.sam import SamSegmenter
    seg = SamSegmenter()

    rows, skipped = [], []
    for d in scored_pairs(a.pairs):
        try:
            stored = json.load(open(d / "before_lm.json"))["landmarks"]
            refined = cv2.imread(str(d / "bmask.png"), cv2.IMREAD_GRAYSCALE) > 127
        except Exception as e:
            skipped.append({"pair": d.name, "why": f"missing artefact: {type(e).__name__}"}); continue
        crs = coarse_before_mask(seg, d)
        if crs is None or crs.shape != refined.shape:
            skipped.append({"pair": d.name, "why": "coarse re-segmentation failed or changed shape"}); continue

        lm_coarse, _ = landmarks_from_mask(crs)
        lm_refined, _ = landmarks_from_mask(refined)
        # the reconstruction check, stated for what it is: agreement on POINTS. A missing key is
        # recorded as a failed reconstruction rather than raised.
        exact = (set(lm_coarse) == set(stored)
                 and all(tuple(lm_coarse[k]) == tuple(int(v) for v in stored[k]) for k in stored))
        treated = len(stored) >= REFINE_MIN_LANDMARKS

        shared = [n for n in SURVIVING if n in lm_coarse and n in lm_refined]
        disp = {n: [int(lm_coarse[n][0]) - int(lm_refined[n][0]),
                    int(lm_coarse[n][1]) - int(lm_refined[n][1])] for n in shared}
        out = {"pair": d.name, "n_landmarks": len(stored), "refinement_ran": bool(treated),
               "reconstruction_landmark_exact": bool(exact),
               "reconstruction_mask_identical": bool(np.array_equal(crs, refined)),
               "refinement": {
                   "iou_coarse_refined": iou(crs, refined),
                   "area_ratio": round(float(refined.sum()) / max(int(crs.sum()), 1), 4),
                   "anchor_row_shift_px": anchor_row(refined) - anchor_row(crs)},
               "landmark_displacement": disp,
               "max_abs_displacement_px": max((max(abs(v[0]), abs(v[1])) for v in disp.values()), default=0)}

        # drift: how far the ground truth would move IF the refined landmarks were adopted. The
        # committed ground truth is not moving; this is the size of the change on offer.
        try:
            lma = json.load(open(d / "after_lm.json"))["landmarks"]
            amask = cv2.imread(str(d / "amask.png"), cv2.IMREAD_GRAYSCALE) > 127
            ms = []
            for lmb in (lm_coarse, lm_refined):
                names = [n for n in SURVIVING if n in lmb and n in lma]
                A = np.array([lma[n] for n in names], np.float32)
                B = np.array([lmb[n] for n in names], np.float32)
                ms.append(warp_mask(_tps(B, A), amask, refined.shape))
            out["drift_iou_if_adopted"] = iou(ms[0], ms[1])
        except Exception as e:
            out["drift_iou_if_adopted"] = None
        rows.append(out)
        if a.verbose:
            print(f"{d.name}: n_lm {len(stored):2d} refined={treated}  IoU "
                  f"{out['refinement']['iou_coarse_refined']}  area x{out['refinement']['area_ratio']}  "
                  f"anchor {out['refinement']['anchor_row_shift_px']:+3d}  maxdisp "
                  f"{out['max_abs_displacement_px']:3d}  drift {out['drift_iou_if_adopted']}", file=sys.stderr)

    summary = {"n_pairs": len(rows), "skipped": skipped}
    if rows:
        summary.update(_summarise(rows))
        summary["ab"] = _ab(a.ab_control, a.ab_refit, rows)
    return {"summary": summary, "pairs": rows}


def _summarise(rows):
    tre = [r for r in rows if r["refinement_ran"]]
    s = {"reconstruction_landmark_exact_on": sum(r["reconstruction_landmark_exact"] for r in rows),
         "refine_min_landmarks": REFINE_MIN_LANDMARKS,
         "gate": {"n_treated": len(tre), "n_skipped_by_gate": len(rows) - len(tre),
                  "landmark_counts": {r["pair"]: r["n_landmarks"] for r in rows},
                  # the two pairs the gate skips are bit-identical by construction, not by luck:
                  # nothing re-segmented them. Any statistic that averages them in is diluted.
                  "mask_identical_on_untreated":
                      all(r["reconstruction_mask_identical"] for r in rows if not r["refinement_ran"]),
                  "mask_identical_on_treated":
                      sum(r["reconstruction_mask_identical"] for r in tre)}}
    if tre:
        ar = np.array([r["refinement"]["area_ratio"] for r in tre], float)
        io = np.array([r["refinement"]["iou_coarse_refined"] for r in tre], float)
        an = np.array([r["refinement"]["anchor_row_shift_px"] for r in tre], float)
        mx = np.array([r["max_abs_displacement_px"] for r in tre], float)
        s["refinement_on_treated"] = {
            "n": len(tre),
            "iou_median": round(float(np.median(io)), 4), "iou_min": round(float(np.min(io)), 4),
            # refinement never shrinks the mask. That one-sidedness is the mechanism: the coarse
            # landmarks are anchored on a systematically smaller silhouette than everything
            # downstream uses.
            "area_ratio_range": [round(float(ar.min()), 4), round(float(ar.max()), 4)],
            "n_area_ratio_below_1": int((ar < 1.0).sum()),
            "anchor_row_shift_px": [int(x) for x in an],
            "max_abs_displacement_px": [int(x) for x in mx],
            "max_displacement_over_all_pairs": int(mx.max())}
        dr = [r["drift_iou_if_adopted"] for r in tre if r["drift_iou_if_adopted"] is not None]
        if dr:
            s["drift_if_adopted"] = {"median": round(float(np.median(dr)), 4),
                                     "min": round(float(np.min(dr)), 4)}
    return s


def _ab(ctl_dir, refit_dir, rows):
    """The A/B, from two full batch runs. Absent arms are reported as absent, not silently skipped."""
    A, B = load_arm(ctl_dir), load_arm(refit_dir)
    common = sorted(set(A) & set(B))
    if not common:
        return {"available": False,
                "why": f"no comparable pairs in {ctl_dir} and {refit_dir}; regenerate with "
                       "PAIRS_OUT=<dir> [PAIRS_REFIT_LM=1] tools/run_pairs_batch.py",
                "n_control": len(A), "n_refit": len(B)}
    treated = {r["pair"] for r in rows if r["refinement_ran"]}
    out = {"available": True, "n_pairs": len(common), "pairs": common,
           "n_treated": len(treated & set(common))}
    for m, higher_better in (("sil_iou_vs_real", True), ("hem_chamfer", False)):
        d = np.array([B[p][m] - A[p][m] for p in common], float)
        dt = np.array([B[p][m] - A[p][m] for p in common if p in treated], float)
        out[m] = {
            "control_mean": round(float(np.mean([A[p][m] for p in common])), 4),
            "refit_mean": round(float(np.mean([B[p][m] for p in common])), 4),
            "all_pairs": paired(d), "treated_only": paired(dt),
            "higher_is_better": higher_better,
            "n_better": int((d > 0).sum() if higher_better else (d < 0).sum()),
            "n_worse": int((d < 0).sum() if higher_better else (d > 0).sum()),
            "n_tied": int((d == 0).sum()),
            "per_pair": {p: round(float(B[p][m] - A[p][m]), 4) for p in common}}
    # the mechanistic check: the ties must be exactly the pairs the refinement gate skipped
    tied = {p for p in common if B[p]["sil_iou_vs_real"] == A[p]["sil_iou_vs_real"]}
    out["ties_are_exactly_the_untreated_pairs"] = bool(tied == (set(common) - treated))
    out["tied_pairs"] = sorted(tied)
    return out


if __name__ == "__main__":
    main()

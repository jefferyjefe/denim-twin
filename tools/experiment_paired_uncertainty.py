"""EXP_0034b: the PAIRED test -- can the bench resolve product path vs crop-only at all?

EXP_0034 perturbed the ground truth and rescored one prediction: that measures how uncertain a
single bench number is (SD of the mean 0.011-0.030). It does NOT answer whether a DIFFERENCE
between two methods is resolvable, because both methods are scored against the SAME ground truth,
so the registration error is common to both and largely cancels in the difference. Treating the
unpaired spread as the error bar on a difference would overstate the case.

This does it correctly: for each draw it perturbs the ground truth ONCE, rescores BOTH the product
prediction and the crop-only null against that same perturbed truth, and takes the difference.
The SD of that difference is the real resolution limit of the comparison.

Usage: python tools/experiment_paired_uncertainty.py --product experiments/pairs_predict_dropdegen
"""
import argparse, glob, json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import cv2, numpy as np
from denimtwin.canon.register import _tps, SURVIVING
from experiment_groundtruth_uncertainty import per_landmark_heldout, warp_mask, iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="experiments/pairs")
    ap.add_argument("--product", default="experiments/pairs_predict_dropdegen")
    ap.add_argument("--draws", type=int, default=40)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--null-dir", default=None,
                    help="compare against <dir>/<pid>/pred_median_mask.png instead of the crop-only "
                         "keep mask. Use experiments/pairs_loonull for the INDEPENDENT null (EXP_0034); "
                         "the default crop-only null is built from the model's own cut line and so "
                         "cannot differ from it by more than the fringe.")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    rows = []
    for od in sorted(glob.glob(f"{a.product}/*/cmp")):
        od = Path(od); pid = od.parent.name
        src = Path(a.pairs) / pid
        try:
            lmb = json.load(open(od.parent / "before_lm.json"))["landmarks"]
            lma = json.load(open(src / "after_lm.json"))["landmarks"]
            amask = cv2.imread(str(src / "amask.png"), cv2.IMREAD_GRAYSCALE) > 127
            pred = cv2.imread(str(od.parent / "pred_median_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
            kp = (Path(a.null_dir) / pid / "pred_median_mask.png") if a.null_dir else (od / "keep_mask.png")
            keep = cv2.imread(str(kp), cv2.IMREAD_GRAYSCALE) > 127
        except Exception:
            continue
        if pred.shape != keep.shape:
            continue
        names = [n for n in SURVIVING if n in lma and n in lmb]
        if len(names) < 5:
            continue
        A = np.array([lma[n] for n in names], np.float32)
        B = np.array([lmb[n] for n in names], np.float32)
        errs = per_landmark_heldout(A, B)
        diffs = []; p_i = []; k_i = []
        for _ in range(a.draws):
            th = rng.uniform(0, 2 * np.pi, len(B))
            Bj = (B + np.stack([np.cos(th), np.sin(th)], 1) * (errs[:, None] * a.scale)).astype(np.float32)
            try:
                t = warp_mask(_tps(Bj, A), amask, pred.shape)
            except Exception:
                continue
            ip, ik = iou(pred, t), iou(keep, t)
            if np.isfinite(ip) and np.isfinite(ik):
                p_i.append(ip); k_i.append(ik); diffs.append(ip - ik)
        if not diffs:
            continue
        d = np.array(diffs)
        base_t = warp_mask(_tps(B, A), amask, pred.shape)
        rows.append({"pair": pid,
                     "iou_product_baseline": round(iou(pred, base_t), 4),
                     "iou_null_baseline": round(iou(keep, base_t), 4),
                     "diff_baseline": round(iou(pred, base_t) - iou(keep, base_t), 5),
                     "diff_mean": round(float(d.mean()), 5),
                     "diff_sd": round(float(d.std()), 5),
                     "product_sd_unpaired": round(float(np.std(p_i)), 5),
                     "draws": len(d)})
        print(f"{pid} product-croponly {rows[-1]['diff_baseline']:+.5f} "
              f"paired SD {rows[-1]['diff_sd']:.5f} (unpaired product SD {rows[-1]['product_sd_unpaired']:.5f})",
              file=sys.stderr)
    sd = np.array([r["diff_sd"] for r in rows], float)
    db = np.array([r["diff_baseline"] for r in rows], float)
    unp = np.array([r["product_sd_unpaired"] for r in rows], float)
    summary = {"n_pairs": len(rows), "draws": a.draws, "scale": a.scale, "null": a.null_dir or "crop-only",
               "bench_diff": round(float(db.mean()), 5),
               "sd_of_bench_diff_paired": round(float(np.sqrt((sd ** 2).sum()) / len(sd)), 5) if len(sd) else None,
               "sd_of_bench_diff_unpaired": round(float(np.sqrt((unp ** 2).sum()) / len(unp)), 5) if len(unp) else None}
    summary["cancellation_factor"] = (round(summary["sd_of_bench_diff_unpaired"] / summary["sd_of_bench_diff_paired"], 1)
                                      if summary.get("sd_of_bench_diff_paired") else None)
    print(json.dumps({"summary": summary, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()

"""EXP_0034: how much of the bench number is ground-truth noise?

The bench scores a prediction against `real_mask.png` -- the real after-photo's mask warped into
the before frame by the after->before registration TPS (register.py). EXP_0033 showed that TPS does
not fold, but its LEAVE-ONE-OUT landmark residual is 7.9-76.8 px (median 27.9) on the seven scored
pairs. That residual is the registration's own error: it is how far the map misses a landmark it
was not shown. The ground truth is therefore not a fixed mask -- it is a mask with an uncertainty.

This resamples that uncertainty. For each pair it perturbs the before-frame landmarks by their own
per-landmark held-out errors (random directions, same magnitudes), refits the TPS, re-warps the
real after-mask, and rescores the SAME UNCHANGED prediction against each perturbed ground truth.
The spread of the resulting IoU is the error bar on the bench, and any method difference smaller
than it is not measurable with these pairs -- no matter how many times it is re-run.

Usage: python tools/experiment_groundtruth_uncertainty.py [--draws 50] [--seed 0]
"""
import argparse, glob, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import cv2, numpy as np
from denimtwin.canon.register import _tps, SURVIVING


def per_landmark_heldout(A, B):
    """Per-landmark leave-one-out error (px) of the after->before TPS, in the BEFORE frame."""
    n = len(A); errs = []
    for i in range(n):
        keep = np.arange(n) != i
        if keep.sum() < 4:
            errs.append(float("nan")); continue
        t = _tps(A[keep], B[keep])
        _, m = t.applyTransformation(np.ascontiguousarray(A[i:i + 1], np.float32)[None])
        errs.append(float(np.linalg.norm(m[0][0] - B[i])))
    return np.array(errs, float)


def warp_mask(t_b2a, amask, shape):
    H, W = shape
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    pts = np.stack([gx.ravel(), gy.ravel()], 1); out = np.empty_like(pts)
    for i in range(0, len(pts), 200_000):
        _, m = t_b2a.applyTransformation(np.ascontiguousarray(pts[i:i + 200_000])[None])
        out[i:i + 200_000] = m[0]
    mx, my = out[:, 0].reshape(H, W), out[:, 1].reshape(H, W)
    return cv2.remap(amask.astype(np.uint8) * 255, mx, my, cv2.INTER_NEAREST,
                     borderMode=cv2.BORDER_CONSTANT) > 127


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="experiments/pairs")
    ap.add_argument("--draws", type=int, default=50)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--scale", type=float, default=1.0,
                    help="multiply the per-landmark error magnitudes; --scale 0 is the null: it must "
                         "reproduce the baseline IoU exactly, which is what proves the harness itself "
                         "adds no noise")
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    ex = Path("data/priors/exclude.txt")
    EXCLUDE = {l.split()[0] for l in ex.read_text().splitlines()
               if l.strip() and not l.startswith("#")} if ex.exists() else set()
    rows = []
    for d in sorted(glob.glob(f"{a.pairs}/*")):
        d = Path(d); pid = d.name
        note = d / "NOTE.md"
        if (note.exists() and "rejected" in note.open().readline()) or pid in EXCLUDE \
           or not (d / "modification.json").exists():
            continue
        try:
            lmb = json.load(open(d / "before_lm.json"))["landmarks"]
            lma = json.load(open(d / "after_lm.json"))["landmarks"]
            amask = cv2.imread(str(d / "amask.png"), cv2.IMREAD_GRAYSCALE) > 127
            pred = cv2.imread(str(d / "pred_median_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
        except Exception:
            continue
        names = [n for n in SURVIVING if n in lma and n in lmb]
        if len(names) < 5:
            continue
        A = np.array([lma[n] for n in names], np.float32)
        B = np.array([lmb[n] for n in names], np.float32)
        errs = per_landmark_heldout(A, B)
        base = warp_mask(_tps(B, A), amask, pred.shape)
        ious = []
        for _ in range(a.draws):
            th = rng.uniform(0, 2 * np.pi, len(B))
            Bj = B + np.stack([np.cos(th), np.sin(th)], 1) * (errs[:, None] * a.scale)
            try:
                ious.append(iou(pred, warp_mask(_tps(Bj.astype(np.float32), A), amask, pred.shape)))
            except Exception:
                pass
        ious = np.array([x for x in ious if np.isfinite(x)])
        rows.append({"pair": pid, "n_landmarks": len(names),
                     "heldout_px_median": round(float(np.nanmedian(errs)), 2),
                     "iou_baseline": round(iou(pred, base), 4),
                     "iou_mean": round(float(ious.mean()), 4),
                     "iou_sd": round(float(ious.std()), 4),
                     "iou_p05": round(float(np.percentile(ious, 5)), 4),
                     "iou_p95": round(float(np.percentile(ious, 95)), 4),
                     "draws": int(len(ious))})
        print(f"{pid} IoU {rows[-1]['iou_baseline']:.4f}  under registration noise "
              f"{rows[-1]['iou_mean']:.4f} +/- {rows[-1]['iou_sd']:.4f} "
              f"[{rows[-1]['iou_p05']:.4f}, {rows[-1]['iou_p95']:.4f}]", file=sys.stderr)
    sds = np.array([r["iou_sd"] for r in rows], float)
    means = np.array([r["iou_mean"] for r in rows], float)
    summary = {"n_pairs": len(rows), "draws": a.draws, "seed": a.seed, "scale": a.scale,
               "median_pair_iou_sd": round(float(np.median(sds)), 4),
               "max_pair_iou_sd": round(float(sds.max()), 4) if len(sds) else None,
               "sd_of_bench_mean": round(float(np.sqrt((sds ** 2).sum()) / len(sds)), 4) if len(sds) else None,
               "bench_mean_iou": round(float(means.mean()), 4) if len(means) else None}
    print(json.dumps({"summary": summary, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()

"""EXP_0034: the crop-only null is not independent of the model.

`compare.py:42` builds `null:crop-only` from the `--keep` mask it is handed, and
`score_predict.py` hands it `{od}/keep_mask.png` -- PREDICT's OWN keep mask. So the "null" crops
the photo at the cut line the model predicted. With `--wash none` the fringe depth is 0.0 px on
every pair (`below_render_resolution: True`), so the prediction and the null can differ only by
fringe rendering, i.e. not at all: measured directly, IoU(pred, keep) has median 0.99954, the null
never keeps a pixel the prediction drops, and on 2691c1a8d0 the two masks are bit-identical.

"The product path ties the crop-only null" therefore says almost nothing about the model. It is a
statement that a cut rendered without fringe equals the same cut rendered without fringe.

A null must not see the thing it is a null for. This one places the cut at the leave-one-out
median inseam fraction of the OTHER pairs: the best guess available with no information about the
garment being scored. If the product path cannot beat that, the per-garment cut placement is
carrying no signal.

Usage: python tools/experiment_independent_null.py [--product experiments/pairs_predict_dropdegen]
"""
import argparse, glob, json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import cv2, numpy as np


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(ROOT / "experiments/pairs"))
    ap.add_argument("--product", default=str(ROOT / "experiments/pairs_predict_dropdegen"))
    ap.add_argument("--out", default=str(ROOT / "experiments/pairs_loonull"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    ex = ROOT / "data/priors/exclude.txt"
    EXCLUDE = {l.split()[0] for l in ex.read_text().splitlines()
               if l.strip() and not l.startswith("#")} if ex.exists() else set()

    fracs = {}
    for d in sorted(glob.glob(f"{a.pairs}/*/modification.json")):
        pid = Path(d).parent.name
        note = Path(d).parent / "NOTE.md"
        if (note.exists() and "rejected" in note.open().readline()) or pid in EXCLUDE:
            continue
        f = json.load(open(d)).get("inseam_fraction")
        if f is not None:
            fracs[pid] = float(f)

    rows = []
    for pid, own in sorted(fracs.items()):
        others = [v for k, v in fracs.items() if k != pid]
        loo = float(np.median(others))
        src = Path(a.pairs) / pid
        od = Path(a.out) / pid
        before = src / "before_native.png"
        if not before.exists():
            before = src / "before_used.png"
        r = subprocess.run([sys.executable, str(ROOT / "tools/predict.py"), "--image", str(before),
                            "--out", str(od), "--state", "after_cut", "--wash", "none",
                            "--edge-treatment", "raw", "--canonical-inverse", "exact",
                            "--inseam-fraction", f"{loo:.4f}"], capture_output=True, text=True)
        if r.returncode != 0:
            rows.append({"pair": pid, "error": (r.stdout + r.stderr).strip().splitlines()[-1][:120]})
            print(pid, "FAIL", rows[-1]["error"], file=sys.stderr)
            continue
        # score the LOO-null mask against the SAME ground truth the product run was scored on
        cmp_dir = Path(a.product) / pid / "cmp"
        try:
            truth = cv2.imread(str(cmp_dir / "real_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
            prod = cv2.imread(str(Path(a.product) / pid / "pred_median_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
            null = cv2.imread(str(od / "pred_median_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
        except Exception as e:
            rows.append({"pair": pid, "error": str(e)}); continue
        if null is None or truth is None or prod is None or null.shape != truth.shape:
            rows.append({"pair": pid, "error": f"shape mismatch {None if null is None else null.shape} vs {truth.shape}"})
            print(pid, "SHAPE", rows[-1]["error"], file=sys.stderr)
            continue
        rows.append({"pair": pid, "own_frac": round(own, 4), "loo_frac": round(loo, 4),
                     "iou_product": round(iou(prod, truth), 4),
                     "iou_loo_null": round(iou(null, truth), 4),
                     "advantage": round(iou(prod, truth) - iou(null, truth), 4)})
        print(f"{pid} product {rows[-1]['iou_product']:.4f}  LOO-null {rows[-1]['iou_loo_null']:.4f}  "
              f"advantage {rows[-1]['advantage']:+.4f}  (own frac {own:.3f} vs LOO {loo:.3f})", file=sys.stderr)

    ok = [r for r in rows if "advantage" in r]
    adv = np.array([r["advantage"] for r in ok], float)
    summary = {"n_pairs": len(ok), "n_failed": len(rows) - len(ok),
               "mean_iou_product": round(float(np.mean([r["iou_product"] for r in ok])), 4) if ok else None,
               "mean_iou_loo_null": round(float(np.mean([r["iou_loo_null"] for r in ok])), 4) if ok else None,
               "mean_advantage": round(float(adv.mean()), 4) if ok else None,
               "n_pairs_product_wins": int((adv > 0).sum()) if ok else None}
    print(json.dumps({"summary": summary, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()

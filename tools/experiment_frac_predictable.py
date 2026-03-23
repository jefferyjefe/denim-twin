"""EXP_0035: is the inseam fraction predictable from the before photo at all?

EXP_0034 restated Gate 1: can the pipeline CHOOSE an inseam fraction, rather than being handed one
measured off the after-photo, and beat the leave-one-out median baseline (0.7278 IoU)? Before
building a predictor on seven samples, this asks whether there is anything to predict.

Six garment features are available from the before mask and landmarks alone. The honest protocol is
nested leave-one-out: hold out a pair, choose the best feature AND fit the model on the other six,
then predict the held-out one. Choosing the feature on all seven and reporting its fit is the
leakage that makes a null result look like a discovery -- with 7 points and 6 features, the best
r^2 in-sample is nearly guaranteed to look encouraging.

Baseline: predict the median fraction of the other six (exactly what the LOO null renders).

Usage: python tools/experiment_frac_predictable.py
"""
import glob, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
import cv2, numpy as np

FEATURES = ("aspect", "waist_w_over_h", "hip_over_waist", "crotch_frac", "leg_over_h", "area_frac")


def choose_feature(X, y, tr):
    """Best-correlating feature, computed ONLY on the rows `tr` selects.

    Extracted so the leave-one-out discipline is testable behaviourally. It previously lived inline
    and was guarded by a test that grepped the source for `X[k][tr], y[tr]` -- a substring that also
    appears in the polyfit line below, so the guard passed even with the selection reading all rows
    (review 7). tests/test_frac_predictable.py now feeds this a case where including the held-out
    point flips the answer.
    """
    r2 = {}
    for k in X:
        xk, yk = X[k][tr], y[tr]
        if np.std(xk) < 1e-12:
            r2[k] = -1.0
            continue
        r2[k] = float(np.corrcoef(xk, yk)[0, 1] ** 2)
    return max(r2, key=r2.get)


def features(d):
    lm = json.load(open(d / "before_lm.json"))["landmarks"]
    m = cv2.imread(str(d / "bmask.png"), cv2.IMREAD_GRAYSCALE) > 127
    ys, xs = np.nonzero(m)
    H, W = ys.max() - ys.min(), xs.max() - xs.min()
    g = lm.get
    ww = g("waist_right")[0] - g("waist_left")[0]
    hw = g("hip_right")[0] - g("hip_left")[0]
    cy, wy = g("crotch")[1], g("waist_left")[1]
    hem = min([v[1] for k, v in lm.items() if k.startswith("hem_")], default=int(ys.max()))
    return {"aspect": H / max(W, 1), "waist_w_over_h": ww / max(H, 1),
            "hip_over_waist": hw / max(ww, 1), "crotch_frac": (cy - wy) / max(H, 1),
            "leg_over_h": (hem - cy) / max(H, 1), "area_frac": float(m.mean())}


def main():
    ex = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
          if l.strip() and not l.startswith("#")}
    rows = []
    for p in sorted(glob.glob(str(ROOT / "experiments/pairs/*/modification.json"))):
        d = Path(p).parent
        if "rejected" in (d / "NOTE.md").open().readline() or d.name in ex:
            continue
        f = json.load(open(p)).get("inseam_fraction")
        if f is None:
            continue
        rows.append({"pair": d.name, "frac": float(f), **features(d)})
    y = np.array([r["frac"] for r in rows])
    X = {k: np.array([r[k] for r in rows]) for k in FEATURES}
    n = len(y)

    insample = {k: float(np.corrcoef(X[k], y)[0, 1] ** 2) for k in FEATURES}
    best_insample = max(insample, key=insample.get)

    pred_model, pred_base, chosen = [], [], []
    for i in range(n):
        tr = np.arange(n) != i
        k = choose_feature(X, y, tr)          # feature choice happens INSIDE the fold
        chosen.append(k)
        b, a = np.polyfit(X[k][tr], y[tr], 1)
        pred_model.append(float(np.clip(b * X[k][i] + a, 0.0, 1.0)))
        pred_base.append(float(np.median(y[tr])))
    pred_model, pred_base = np.array(pred_model), np.array(pred_base)
    mae_m, mae_b = float(np.abs(pred_model - y).mean()), float(np.abs(pred_base - y).mean())

    out = {"summary": {
        "n_pairs": n,
        "target_sd": round(float(y.std(ddof=1)), 4),
        "best_in_sample_feature": best_insample,
        "best_in_sample_r2": round(insample[best_insample], 4),
        "loo_mae_model": round(mae_m, 4),
        "loo_mae_median_baseline": round(mae_b, 4),
        "model_beats_baseline": bool(mae_m < mae_b),
        "mae_ratio_model_over_baseline": round(mae_m / mae_b, 3),
        "n_folds_choosing_each_feature": {k: chosen.count(k) for k in sorted(set(chosen))},
    }, "in_sample_r2": {k: round(v, 4) for k, v in insample.items()},
        "rows": [{**r, "loo_pred_model": round(float(pm), 4), "loo_pred_baseline": round(float(pb), 4)}
                 for r, pm, pb in zip(rows, pred_model, pred_base)]}
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

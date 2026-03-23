"""EXP_0040: where uprighting costs 443d1d4658 its silhouette IoU (it is not the hem).

EXP_0038 fixed this pair's hem (27.67 -> 7.54 px) by gating a spurious fringe mask out of the hem
fit, but left a residual: with uprighting ON the pair scores IoU 0.898 against the 0.918 that
uprighting OFF gives, even though the hem is now BETTER with uprighting on. So uprighting costs it
something outside the hem line.

Four arms are compared (uprighting on/off x EXP_0038 fix on/off). Uprighting OFF is identical with
and without the fix -- with no uprighting SAM produces no fringe mask, so the gate has nothing to
gate -- which isolates uprighting as the only variable.

Emits:
  bands      -- IoU decomposed into six vertical bands of the garment, per arm
  waist      -- where autolm places the waist line as a fraction of garment height, per arm/photo
  smear      -- observed waist shift against the width*sin(rotation) prediction
  crosspair  -- waist-correspondence mismatch against band-0 IoU over all seven scored pairs

Usage: python tools/experiment_upright_waistband.py --on DIR --off DIR
"""
import argparse, glob, json, math, re
from pathlib import Path
import cv2, numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
if not (ROOT / "data/priors/exclude.txt").exists():      # running from outside tools/
    ROOT = Path.cwd()


def _band_iou(d, nb=6):
    pred = cv2.imread(str(Path(d) / "pred_median_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
    real = cv2.imread(str(Path(d) / "real_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
    both = pred | real
    ys = np.nonzero(both.any(axis=1))[0]
    y0, y1 = int(ys.min()), int(ys.max())
    out = []
    for i in range(nb):
        a = y0 + int((y1 - y0) * i / nb)
        b = y0 + int((y1 - y0) * (i + 1) / nb)
        p, r = pred[a:b], real[a:b]
        u = int((p | r).sum())
        out.append({"band": i, "union_px": u,
                    "iou": round(float((p & r).sum() / u), 4) if u else None,
                    "pred_only": int((p & ~r).sum()), "real_only": int((r & ~p).sum())})
    u = int((pred | real).sum())
    return out, round(float((pred & real).sum() / u), 4)


def _waist(d, which):
    mf = "bmask.png" if which == "before" else "amask.png"
    lf = "before_lm.json" if which == "before" else "after_lm.json"
    m = cv2.imread(str(Path(d) / mf), cv2.IMREAD_GRAYSCALE) > 127
    lm = json.load(open(Path(d) / lf))["landmarks"]
    ys = np.nonzero(m.any(axis=1))[0]
    t, b = int(ys.min()), int(ys.max())
    wy = lm["waist_left"][1]
    return {"top": t, "bottom": b, "height": b - t, "waist_y": wy, "depth_px": wy - t,
            "waist_width": lm["waist_right"][0] - lm["waist_left"][0],
            "depth_frac": round((wy - t) / max(b - t, 1), 4)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", required=True)
    ap.add_argument("--off", required=True)
    ap.add_argument("--pairs", default=None)
    a = ap.parse_args()
    if a.pairs is None:
        a.pairs = str(ROOT / "experiments/pairs")

    bands, waist = {}, {}
    for lab, d in (("upright_on", a.on), ("upright_off", a.off)):
        bs, tot = _band_iou(d)
        bands[lab] = {"overall_iou": tot, "bands": bs}
        waist[lab] = {w: _waist(d, w) for w in ("before", "after")}

    note = (Path(a.on) / "NOTE.md").read_text()
    rot = {"before": float(re.search(r"before: rotated (-?[\d.]+)°", note).group(1)),
           "after": float(re.search(r"after: rotated (-?[\d.]+)°", note).group(1))}
    smear = {}
    for w in ("before", "after"):
        obs = waist["upright_on"][w]["depth_px"] - waist["upright_off"][w]["depth_px"]
        full = waist["upright_on"][w]["waist_width"] * abs(math.sin(math.radians(rot[w])))
        smear[w] = {"rotation_deg": rot[w], "observed_shift_px": obs,
                    "predicted_full_smear_px": round(full, 1),
                    "fraction_of_full_smear": round(obs / full, 3) if full else None}

    ex = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
          if l.strip() and not l.startswith("#")}
    cross = []
    for p in sorted(glob.glob(f"{a.pairs}/*/modification.json")):
        d = Path(p).parent
        if "rejected" in (d / "NOTE.md").open().readline() or d.name in ex:
            continue
        try:
            wb, wa = _waist(d, "before"), _waist(d, "after")
            bs, _ = _band_iou(d)
        except Exception:
            continue
        cross.append({"pair": d.name, "waist_frac_before": wb["depth_frac"],
                      "waist_frac_after": wa["depth_frac"],
                      "mismatch_pp": round(100 * abs(wa["depth_frac"] - wb["depth_frac"]), 2),
                      "band0_iou": bs[0]["iou"]})
    # the systematic part: where does the REGISTERED after-garment's top land relative to the
    # prediction's? Band 0 is the region ABOVE every registration landmark (SURVIVING tops out at
    # the waist), so it is pure TPS extrapolation on every pair.
    resid = {}
    rf = ROOT / "reports/registration_fold.json"
    if rf.exists():
        resid = {q["pair"]: q["heldout_resid_px"] for q in json.load(open(rf))["rows"]}
    for c in cross:
        d = Path(a.pairs) / c["pair"]
        pred = cv2.imread(str(d / "pred_median_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
        real = cv2.imread(str(d / "real_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
        c["top_offset_px"] = int(np.nonzero(real.any(axis=1))[0].min()) - int(np.nonzero(pred.any(axis=1))[0].min())
        c["heldout_resid_px"] = resid.get(c["pair"])
        bm = cv2.imread(str(d / "bmask.png"), cv2.IMREAD_GRAYSCALE) > 127
        lm = json.load(open(d / "before_lm.json"))["landmarks"]
        ys = np.nonzero(bm.any(axis=1))[0]
        c["pct_above_top_landmark"] = round(100 * (lm["waist_left"][1] - int(ys.min())) / max(int(ys.max()) - int(ys.min()), 1), 2)

    x = np.array([c["mismatch_pp"] for c in cross], float)
    y = np.array([c["band0_iou"] for c in cross], float)
    off = np.array([c["top_offset_px"] for c in cross], float)
    r = float(np.corrcoef(x, y)[0, 1]) if len(x) > 2 else float("nan")
    n_pos = int((off > 0).sum())
    sign_p = float(stats.binomtest(n_pos, len(off), 0.5).pvalue) if len(off) else float("nan")
    have = [c for c in cross if c["heldout_resid_px"] is not None]
    rr = np.array([c["heldout_resid_px"] for c in have], float)
    ro = np.array([abs(c["top_offset_px"]) for c in have], float)
    above = np.array([c["pct_above_top_landmark"] for c in cross], float)

    b_on = bands["upright_on"]["bands"]
    b_off = bands["upright_off"]["bands"]
    deltas = [round((b_on[i]["iou"] or 0) - (b_off[i]["iou"] or 0), 4) for i in range(len(b_on))]
    worst = int(np.argmin(deltas))
    summary = {
        "pair": "443d1d4658",
        "iou_upright_off": bands["upright_off"]["overall_iou"],
        "iou_upright_on": bands["upright_on"]["overall_iou"],
        "band_iou_deltas_on_minus_off": deltas,
        "worst_band": worst,
        "worst_band_delta": deltas[worst],
        "n_bands_worse_by_over_0_05": int(sum(1 for d_ in deltas if d_ < -0.05)),
        "waist_frac_before_off": waist["upright_off"]["before"]["depth_frac"],
        "waist_frac_before_on": waist["upright_on"]["before"]["depth_frac"],
        "waist_frac_after_off": waist["upright_off"]["after"]["depth_frac"],
        "waist_frac_after_on": waist["upright_on"]["after"]["depth_frac"],
        # percent mirrors, because the NOTE quotes percentages and a claim must compare like with like
        "waist_pct_before_off": round(100 * waist["upright_off"]["before"]["depth_frac"], 2),
        "waist_pct_before_on": round(100 * waist["upright_on"]["before"]["depth_frac"], 2),
        "waist_pct_after_off": round(100 * waist["upright_off"]["after"]["depth_frac"], 2),
        "waist_pct_after_on": round(100 * waist["upright_on"]["after"]["depth_frac"], 2),
        "smear_fraction_before": smear["before"]["fraction_of_full_smear"],
        "smear_fraction_after": smear["after"]["fraction_of_full_smear"],
        "crosspair_corr_mismatch_vs_band0_iou": round(r, 3),
        "top_offset_median_px": float(np.median(off)),
        "top_offset_min_px": float(off.min()),
        "top_offset_max_px": float(off.max()),
        "top_offset_n_positive": n_pos,
        "top_offset_n_pairs": len(off),
        "top_offset_sign_test_p": round(sign_p, 4),
        "corr_resid_vs_abs_top_offset": round(float(np.corrcoef(rr, ro)[0, 1]), 3) if len(rr) > 2 else None,
        "corr_top_offset_vs_band0_iou": round(float(np.corrcoef(np.abs(off), y)[0, 1]), 3),
        "corr_pct_above_landmark_vs_band0_iou": round(float(np.corrcoef(above, y)[0, 1]), 3),
        "extrapolation_amount_explains_band0": False,
        "crosspair_generalises": False,
        "crosspair_smallest_mismatch_pair": min(cross, key=lambda c: c["mismatch_pp"])["pair"],
        "crosspair_worst_band0_pair": min(cross, key=lambda c: c["band0_iou"])["pair"],
    }
    print(json.dumps({"summary": summary, "bands": bands, "waist": waist,
                      "smear": smear, "crosspair": cross}, indent=2))


if __name__ == "__main__":
    main()

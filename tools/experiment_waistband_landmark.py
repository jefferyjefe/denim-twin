"""EXP_0041: give registration the waistband edge as a correspondence, and see what that shows.

EXP_0040 ended on a lead. `register.SURVIVING` tops out at the waist landmarks, `autolm` places
those 2% of the garment height *below* the top edge, so the waistband is registered by pure
thin-plate-spline extrapolation -- and the waistband is the one band uprighting costs IoU on. The
proposal was to give the fit the waistband edge, which survives cutting unchanged.

This measures it. The verdict is that the correspondence changes nothing, but the route there
overturned more than the treatment did, so the measurements are laid out in the order that matters:

  provenance -- FIRST, because it invalidates the rest if ignored. `before_lm.json` and `bmask.png`
                come from different segmentations of the same photograph (`run_pair.py:150` refines
                the before mask and deliberately keeps the coarse landmarks -- EXP_0004). Reading a
                new correspondence off `bmask.png` and joining it to `before_lm.json` mixes the two.
  top_offset -- EXP_0040's headline, re-measured with landmarks and mask from ONE segmentation.
  gap        -- how far the control fit puts the waistband corners from where they are, with the
                two controls that make the number mean something: matched CARDINALITY (a five-point
                jackknife) and matched REACH (support with the neighbouring waist landmarks removed,
                so the corner faces the same denuded neighbourhood a held-out landmark does).
  resid      -- leave-one-out error over the landmarks NO arm moves, with each arm's own
                top-of-garment points in support. Quoted with the paired uncertainty and a sign test,
                and with a displaced-correspondence null, because it is the primary metric.
  iou        -- LAST, and prediction-DEPENDENT. The registered after-mask is the ground truth, so an
                arm that warps it toward the prediction scores better without being more correct.
                Worse: `pred_median_mask.png` is a pixel subset of `bmask.png` and shares its top row
                on every pair, so a correspondence read off `bmask.png` is read off the artefact that
                defines the scoring target's silhouette. Band 0 especially cannot carry a claim
                (`docs/GATES.md` baseline rule -- the `null:crop-only` structure).

Arms:
  control   `SURVIVING` as it stands
  add       `control` + waistband_left/center/right on the top edge
  replace   the three waist landmarks moved up onto the top edge (hull grows, count does not)
  null      `add` with each waistband point displaced by a random vector of the measured gap length

Usage: python tools/experiment_waistband_landmark.py [--draws 25] [--seed 0]
                                                     [--landmarks recomputed|production]
"""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import cv2, numpy as np
from scipy import stats
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon.register import _tps, SURVIVING
from denimtwin.canon.waistband import NAMES as WB, waistband_corners

WAIST = ("waist_left", "waist_center", "waist_right")


def excluded():
    ex = ROOT / "data/priors/exclude.txt"
    if not ex.exists():
        sys.exit(f"missing {ex}: refusing to run with an empty exclude set")
    return {l.split()[0] for l in ex.read_text().splitlines() if l.strip() and not l.startswith("#")}


def scored_pairs(pairs_dir):
    ex = excluded()
    for d in sorted(Path(pairs_dir).glob("*")):
        if not d.is_dir() or d.name in ex:
            continue
        note = d / "NOTE.md"
        if note.exists() and "rejected" in note.open().readline():
            continue
        if not (d / "modification.json").exists():
            continue
        yield d


def warp_mask(t_b2a, amask, shape):
    """AFTER-frame mask into the BEFORE frame, exactly as register.warp_after_to_before does it."""
    H, W = shape
    gx, gy = np.meshgrid(np.arange(W, dtype=np.float32), np.arange(H, dtype=np.float32))
    pts = np.stack([gx.ravel(), gy.ravel()], 1); out = np.empty_like(pts)
    for i in range(0, len(pts), 200_000):
        _, m = t_b2a.applyTransformation(np.ascontiguousarray(pts[i:i + 200_000])[None])
        out[i:i + 200_000] = m[0]
    mx, my = out[:, 0].reshape(H, W), out[:, 1].reshape(H, W)
    return cv2.remap(amask.astype(np.uint8) * 255, mx, my, cv2.INTER_NEAREST,
                     borderMode=cv2.BORDER_CONSTANT) > 127


def map_pts(A, B, pts):
    """Map AFTER-frame points into the BEFORE frame with the after->before TPS fitted on (A, B)."""
    t = _tps(np.asarray(A, np.float32), np.asarray(B, np.float32))
    _, m = t.applyTransformation(np.ascontiguousarray(pts, np.float32)[None])
    return np.asarray(m[0], float)


def loo_errors(A, B, names, support=None):
    """Leave-one-out error (px) for each of `names`, with optional always-present extra support.

    NOTE what this does and does not control. The evaluated points are identical across arms; the
    support differs in BOTH geometry and cardinality (5 points for `control`/`replace`, 8 for
    `add`), so an arm with more support is not being handicapped for it. That is the comparison this
    experiment wants -- "does the fit get better when given this correspondence" -- but it is not a
    like-for-like conditioning test, and the null arm is what separates the two."""
    A, B = np.asarray(A, np.float32), np.asarray(B, np.float32)
    sa, sb = (np.zeros((0, 2), np.float32), np.zeros((0, 2), np.float32)) if support is None else \
             (np.asarray(support[0], np.float32), np.asarray(support[1], np.float32))
    errs = {}
    for i, n in enumerate(names):
        keep = np.arange(len(A)) != i
        fa, fb = np.vstack([A[keep], sa]), np.vstack([B[keep], sb])
        if len(fa) < 4:
            errs[n] = float("nan"); continue
        errs[n] = float(np.linalg.norm(map_pts(fa, fb, A[i:i + 1])[0] - B[i]))
    return errs


def reach(B, pts):
    """Distance from each point to its nearest support point, in px. The number that decides whether
    two held-out errors are comparable: a correspondence 8 px from a landmark is not being
    extrapolated to in any sense a landmark 140 px from its neighbours is."""
    return [float(np.min(np.linalg.norm(np.asarray(B, float) - np.asarray(p, float), axis=1))) for p in pts]


def top_row(mask):
    ys = np.nonzero(np.asarray(mask).any(axis=1))[0]
    return int(ys.min()) if len(ys) else None


def iou(a, b):
    u = int((a | b).sum())
    return round(float((a & b).sum() / u), 4) if u else None


def band0_iou(pred, real, nb=6):
    both = pred | real
    ys = np.nonzero(both.any(axis=1))[0]
    if not len(ys):
        return None
    y0, y1 = int(ys.min()), int(ys.max())
    return iou(pred[y0:y0 + int((y1 - y0) / nb)], real[y0:y0 + int((y1 - y0) / nb)])


def paired(d):
    """Mean, paired SEM, sigma, wins and a two-sided sign test for a per-pair difference array.

    EXP_0033's rule: on a method difference the paired uncertainty is the only honest one. Applied
    to every difference this experiment reports, not just the IoU -- the first draft quoted a bare
    mean for the primary residual and read a 0.24-sigma coin flip as a result."""
    d = np.asarray(d, float)
    n = len(d)
    sem = float(d.std(ddof=1) / np.sqrt(n)) if n > 1 else float("nan")
    nz = int((d != 0).sum())
    out = {"n": n, "mean": round(float(d.mean()), 5), "median": round(float(np.median(d)), 5),
           "sem_paired": round(sem, 5) if np.isfinite(sem) else None,
           "n_positive": int((d > 0).sum()), "n_negative": int((d < 0).sum()),
           "sign_test_p": round(float(stats.binomtest(int((d > 0).sum()), nz, 0.5).pvalue), 4) if nz else None}
    out["sigma"] = round(float(d.mean() / sem), 2) if (np.isfinite(sem) and sem > 0) else None
    return out


def build(pairs=None, draws=25, seed=0, landmarks="recomputed", verbose=False):
    """The whole experiment as a value, so `make_reports.py --check` can detect it going stale.
    Deterministic: the null arm draws from a seeded generator."""
    return _run(argparse.Namespace(pairs=pairs or str(ROOT / "experiments/pairs"), draws=draws,
                                   seed=seed, landmarks=landmarks, verbose=verbose))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default=str(ROOT / "experiments/pairs"))
    ap.add_argument("--draws", type=int, default=25, help="random displacements for the null arm")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default=str(ROOT / "reports/waistband_landmark.json"))
    ap.add_argument("--quiet", dest="verbose", action="store_false", default=True)
    ap.add_argument("--landmarks", choices=("recomputed", "production"), default="recomputed",
                    help="`production` reads before_lm.json/after_lm.json as the pipeline wrote them. "
                         "For the BEFORE photo those came from the COARSE mask while bmask.png is the "
                         "refined one, so a correspondence read off bmask.png would be measured on a "
                         "different segmentation from the landmarks it joins. `recomputed` puts every "
                         "point on the stored masks. Both are reported; the primary run is recomputed.")
    a = ap.parse_args()
    res = _run(a)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps(res["summary"], indent=1))


def _run(a):
    rng = np.random.default_rng(a.seed)
    rows, skipped = [], []
    for d in scored_pairs(a.pairs):
        try:
            lmb_prod = json.load(open(d / "before_lm.json"))["landmarks"]
            lma_prod = json.load(open(d / "after_lm.json"))["landmarks"]
            bmask = cv2.imread(str(d / "bmask.png"), cv2.IMREAD_GRAYSCALE) > 127
            amask = cv2.imread(str(d / "amask.png"), cv2.IMREAD_GRAYSCALE) > 127
            pred = cv2.imread(str(d / "pred_median_mask.png"), cv2.IMREAD_GRAYSCALE) > 127
        except Exception as e:
            skipped.append({"pair": d.name, "why": f"missing artefact: {type(e).__name__}"}); continue
        if not (bmask.any() and amask.any() and pred.any()):
            skipped.append({"pair": d.name, "why": "an empty mask"}); continue
        lmb_rec, _ = landmarks_from_mask(bmask)
        lma_rec, _ = landmarks_from_mask(amask)

        # --- provenance: how far the stored landmarks are from what the stored masks give ---
        shared = [n for n in SURVIVING if n in lmb_prod and n in lmb_rec and n in lma_prod and n in lma_rec]
        prov = {"before": {n: [int(lmb_prod[n][0]) - int(lmb_rec[n][0]),
                               int(lmb_prod[n][1]) - int(lmb_rec[n][1])] for n in shared},
                "after": {n: [int(lma_prod[n][0]) - int(lma_rec[n][0]),
                              int(lma_prod[n][1]) - int(lma_rec[n][1])] for n in shared}}
        prov["before_max_abs_px"] = max((max(abs(v[0]), abs(v[1])) for v in prov["before"].values()), default=0)
        prov["after_max_abs_px"] = max((max(abs(v[0]), abs(v[1])) for v in prov["after"].values()), default=0)

        lmb, lma = (lmb_rec, lma_rec) if a.landmarks == "recomputed" else (lmb_prod, lma_prod)
        names = [n for n in SURVIVING if n in lma and n in lmb]
        if len(names) < 5:
            skipped.append({"pair": d.name, "why": f"only {len(names)} shared landmarks"}); continue
        wb_b, wb_a = waistband_corners(bmask), waistband_corners(amask)
        if wb_b is None or wb_a is None:
            skipped.append({"pair": d.name, "why": "no usable waistband row"}); continue
        idx = [names.index(n) for n in WAIST if n in names]   # by NAME: SURVIVING's order is not WB's
        if len(idx) != 3:
            skipped.append({"pair": d.name, "why": "not all three waist landmarks present"}); continue

        bys = np.nonzero(bmask.any(axis=1))[0]
        height_px = int(bys.max() - bys.min())
        A = np.array([lma[n] for n in names], np.float32)          # after frame
        B = np.array([lmb[n] for n in names], np.float32)          # before frame
        WA = np.array([wb_a[n] for n in WB], np.float32)
        WB_ = np.array([wb_b[n] for n in WB], np.float32)
        ei = [i for i, n in enumerate(names) if n not in WAIST]

        # --- the gap, with BOTH controls ---
        mapped = map_pts(A, B, WA)
        gap_px = [float(np.linalg.norm(mapped[i] - WB_[i])) for i in range(3)]
        dy = [float(mapped[i][1] - WB_[i][1]) for i in range(3)]   # +ve: control puts the top too LOW
        base_loo = loo_errors(A, B, names)
        jack = []
        for i in range(len(A)):                                    # matched CARDINALITY: five points
            keep = np.arange(len(A)) != i
            mj = map_pts(A[keep], B[keep], WA)
            jack.append(float(np.mean([np.linalg.norm(mj[k] - WB_[k]) for k in range(3)])))
        mrm = map_pts(A[ei], B[ei], WA)                            # matched REACH: waist points dropped
        gap_reach = float(np.mean([np.linalg.norm(mrm[k] - WB_[k]) for k in range(3)]))
        # the construction term: autolm puts the waist landmark int(0.02*h) below the top edge of EACH
        # garment's own height, and the before garment is the taller one, so dy > 0 even for a perfect map
        d_b = float(np.mean(B[idx][:, 1] - WB_[:, 1]))
        d_a = float(np.mean(A[idx][:, 1] - WA[:, 1]))
        gap = {"per_corner_px": [round(x, 2) for x in gap_px],
               "mean_px": round(float(np.mean(gap_px)), 2),
               "mean_dy_px": round(float(np.mean(dy)), 2),
               "jackknife_mean_px": round(float(np.mean(jack)), 2),
               "reach_matched_mean_px": round(gap_reach, 2),
               "reach_waistband_px": round(float(np.median(reach(B, WB_))), 1),
               "reach_loo_px": round(float(np.median([
                   np.min(np.linalg.norm(np.delete(B, i, 0) - B[i], axis=1)) for i in range(len(B))])), 1),
               "waist_depth_before_px": round(d_b, 1), "waist_depth_after_px": round(d_a, 1),
               "construction_dy_px": round(d_b - d_a, 2),
               "loo_control_mean_px": round(float(np.nanmean(list(base_loo.values()))), 2),
               "loo_control_per_landmark": {k: round(v, 2) for k, v in base_loo.items()}}

        arms = {"control": (A, B, None), "add": (A, B, (WA, WB_))}
        Ar, Br = A.copy(), B.copy()
        for j, i in enumerate(idx):
            Ar[i], Br[i] = WA[j], WB_[j]
        arms["replace"] = (Ar, Br, None)

        out = {"pair": d.name, "n_landmarks": len(names), "landmarks": names, "height_px": height_px,
               "landmark_provenance": prov, "gap": gap,
               # the scoring target is built FROM bmask: pred is a pixel subset of it and shares its
               # top row. A correspondence read off bmask is therefore read off the artefact that
               # defines what the arms are scored against -- recorded so no reader has to take the
               # band-0 column on trust (docs/GATES.md baseline rule).
               "scoring_target": {"pred_is_subset_of_bmask": bool((pred & ~bmask).sum() == 0),
                                  "pred_top_equals_bmask_top": top_row(pred) == top_row(bmask)},
               "arms": {}}
        for lab, (AA, BB, sup) in arms.items():
            fa = AA if sup is None else np.vstack([AA, sup[0]])
            fb = BB if sup is None else np.vstack([BB, sup[1]])
            try:
                real = warp_mask(_tps(fb, fa), amask, pred.shape)
            except Exception as e:
                out["arms"][lab] = {"error": f"{type(e).__name__}: {e}"}; continue
            top_a = {"control": A[idx], "add": np.vstack([A[idx], WA]), "replace": WA}[lab]
            top_b = {"control": B[idx], "add": np.vstack([B[idx], WB_]), "replace": WB_}[lab]
            loo_c = loo_errors(A[ei], B[ei], [names[i] for i in ei], support=(top_a, top_b))
            tr, tp = top_row(real), top_row(pred)
            out["arms"][lab] = {
                "iou": iou(pred, real), "band0_iou": band0_iou(pred, real),
                "loo_common_mean_px": round(float(np.nanmean(list(loo_c.values()))), 2),
                "loo_common": {k: round(v, 2) for k, v in loo_c.items()},
                "real_top_row": tr, "pred_top_row": tp,
                "top_offset_px": (tr - tp) if (tr is not None and tp is not None) else None}

        # --- null: `add` with the correspondence displaced, scored on BOTH the IoU and the residual ---
        mag = float(np.mean(gap_px))
        n_iou, n_b0, n_loo = [], [], []
        for _ in range(a.draws):
            th = rng.uniform(0, 2 * np.pi, 3)
            Wn = (WB_ + np.stack([np.cos(th), np.sin(th)], 1) * mag).astype(np.float32)
            try:
                real = warp_mask(_tps(np.vstack([B, Wn]), np.vstack([A, WA])), amask, pred.shape)
                lc = loo_errors(A[ei], B[ei], [names[i] for i in ei],
                                support=(np.vstack([A[idx], WA]), np.vstack([B[idx], Wn])))
            except Exception:
                continue
            n_iou.append(iou(pred, real)); n_b0.append(band0_iou(pred, real))
            n_loo.append(float(np.nanmean(list(lc.values()))))
        if n_iou:
            v = np.array([x for x in n_iou if x is not None], float)
            b = np.array([x for x in n_b0 if x is not None], float)
            out["arms"]["null"] = {
                "iou_mean": round(float(v.mean()), 4), "iou_sd": round(float(v.std()), 4),
                "band0_iou_mean": round(float(b.mean()), 4) if len(b) else None,
                "loo_common_mean_px": round(float(np.mean(n_loo)), 2),
                "draws": len(n_iou), "displacement_px": round(mag, 2)}
        rows.append(out)
        if getattr(a, "verbose", False):
            print(f"{d.name}: gap {gap['mean_px']:6.2f} (reach-matched {gap_reach:7.2f}, loo "
                  f"{gap['loo_control_mean_px']:6.2f})  top_off {out['arms']['control']['top_offset_px']:+4d}  "
                  + "  ".join(f"{k} {v.get('iou')}" for k, v in out["arms"].items() if "iou" in v),
                  file=sys.stderr)

    summary = {"n_pairs": len(rows), "skipped": skipped, "landmarks": a.landmarks}
    if rows:
        summary.update(_summarise(rows))
    return {"summary": summary, "pairs": rows}


def _summarise(rows):
    g = np.array([r["gap"]["mean_px"] for r in rows], float)
    gj = np.array([r["gap"]["jackknife_mean_px"] for r in rows], float)
    gr = np.array([r["gap"]["reach_matched_mean_px"] for r in rows], float)
    l = np.array([r["gap"]["loo_control_mean_px"] for r in rows], float)
    dyv = np.array([r["gap"]["mean_dy_px"] for r in rows], float)
    cons = np.array([r["gap"]["construction_dy_px"] for r in rows], float)
    hgt = np.array([r["height_px"] for r in rows], float)
    s = {}
    s["gap"] = {
        "median_px": round(float(np.median(g)), 2),
        "jackknife_median_px": round(float(np.median(gj)), 2),
        "reach_matched_median_px": round(float(np.median(gr)), 2),
        "loo_median_px": round(float(np.median(l)), 2),
        "reach_waistband_median_px": round(float(np.median([r["gap"]["reach_waistband_px"] for r in rows])), 1),
        "reach_loo_median_px": round(float(np.median([r["gap"]["reach_loo_px"] for r in rows])), 1),
        # the direction actually claimed, tested one-sided in that direction (the first draft asked
        # whether the gap EXCEEDS the LOO error, got 0 of 7, and reported p = 1.0 as if it meant something)
        "n_loo_gt_jackknife": int((l > gj).sum()),
        "sign_test_loo_gt_jackknife_p": round(float(stats.binomtest(
            int((l > gj).sum()), len(l), 0.5, alternative="greater").pvalue), 4),
        "n_reach_matched_gt_loo": int((gr > l).sum()),
        "sign_test_reach_matched_gt_loo_p": round(float(stats.binomtest(
            int((gr > l).sum()), len(gr), 0.5, alternative="greater").pvalue), 4),
        "median_dy_px": round(float(np.median(dyv)), 2),
        "n_dy_positive": int((dyv > 0).sum()),
        "sign_test_dy_p": round(float(stats.binomtest(int((dyv > 0).sum()), len(dyv), 0.5).pvalue), 4),
        "construction_dy_median_px": round(float(np.median(cons)), 2),
        "corr_construction_vs_dy": round(float(np.corrcoef(cons, dyv)[0, 1]), 3),
        "height_px_range": [int(hgt.min()), int(hgt.max())],
    }
    # EXP_0040's own statistic, re-run here: the control arm's top-row offset
    off = np.array([r["arms"]["control"]["top_offset_px"] for r in rows], float)
    nz = int((off != 0).sum())
    s["control_top_offset"] = {
        "per_pair_px": [int(x) for x in off], "median_px": round(float(np.median(off)), 2),
        "n_positive": int((off > 0).sum()), "n_negative": int((off < 0).sum()),
        "n_zero": int((off == 0).sum()),
        "sign_test_p": round(float(stats.binomtest(int((off > 0).sum()), nz, 0.5).pvalue), 4) if nz else None}
    for lab in ("add", "replace"):
        have = [r for r in rows if lab in r["arms"] and r["arms"][lab].get("iou") is not None
                and r["arms"]["control"].get("iou") is not None]
        if not have:
            continue
        d_iou = np.array([r["arms"][lab]["iou"] - r["arms"]["control"]["iou"] for r in have], float)
        d_b0 = np.array([r["arms"][lab]["band0_iou"] - r["arms"]["control"]["band0_iou"] for r in have
                         if r["arms"][lab]["band0_iou"] is not None
                         and r["arms"]["control"]["band0_iou"] is not None], float)
        d_loo = np.array([r["arms"][lab]["loo_common_mean_px"] - r["arms"]["control"]["loo_common_mean_px"]
                          for r in have], float)
        hv = np.array([r["height_px"] for r in have], float)
        arm_iou = np.array([r["arms"][lab]["iou"] for r in have], float)
        ctl_iou = np.array([r["arms"]["control"]["iou"] for r in have], float)
        unpaired = float(np.sqrt(arm_iou.var(ddof=1) / len(arm_iou) + ctl_iou.var(ddof=1) / len(ctl_iou)))
        p_iou = paired(d_iou)
        s[lab] = {"d_iou": p_iou,
                  "d_iou_sem_unpaired": round(unpaired, 5),
                  "cancellation_factor": round(unpaired / p_iou["sem_paired"], 1)
                  if p_iou["sem_paired"] else None,
                  "d_band0": paired(d_b0) if len(d_b0) else None,
                  "d_loo_common": paired(d_loo),
                  # px errors scale with the garment, and these span 3.3x in height; the scale-free
                  # form is reported beside the px one because the two disagree in sign for `add`
                  "d_loo_common_frac_h": paired(d_loo / hv)}
    nulls = [r for r in rows if "null" in r["arms"] and "add" in r["arms"]
             and r["arms"]["add"].get("iou") is not None]
    if nulls:
        dn = np.array([r["arms"]["null"]["iou_mean"] - r["arms"]["control"]["iou"] for r in nulls], float)
        dnl = np.array([r["arms"]["null"]["loo_common_mean_px"] - r["arms"]["control"]["loo_common_mean_px"]
                        for r in nulls], float)
        da = np.array([r["arms"]["add"]["loo_common_mean_px"] - r["arms"]["null"]["loo_common_mean_px"]
                       for r in nulls], float)
        s["null"] = {"d_iou": paired(dn), "d_loo_common": paired(dnl),
                     "add_minus_null_loo_common": paired(da),
                     "displacement_px": [r["arms"]["null"]["displacement_px"] for r in nulls]}
    prov_b = np.array([r["landmark_provenance"]["before_max_abs_px"] for r in rows], float)
    prov_a = np.array([r["landmark_provenance"]["after_max_abs_px"] for r in rows], float)
    s["landmark_provenance"] = {
        "before_max_abs_px": [int(x) for x in prov_b], "after_max_abs_px": [int(x) for x in prov_a],
        "before_max_px": int(prov_b.max()), "after_max_px": int(prov_a.max()),
        "n_before_nonzero": int((prov_b != 0).sum())}
    s["scoring_target"] = {
        "n_pred_subset_of_bmask": sum(r["scoring_target"]["pred_is_subset_of_bmask"] for r in rows),
        "n_pred_top_equals_bmask_top": sum(r["scoring_target"]["pred_top_equals_bmask_top"] for r in rows)}
    return s


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""EXP_0025 — score the fringe renderer on hem roughness measured where the boundary was never resampled.

EXP_0017 compared each system's hem roughness against the real garment's, using the real mask **warped into the
prediction's frame**. EXP_0024 showed that warp is the same size as the result: rotating a finished-hem control makes
12 of 12 read as frayed at a median p90/waist of 0.00194, against EXP_0017's whole quantity of 0.00194 and its margin
of 0.00037. The artefact also has a direction — the real hem is measured as rougher than it is, so a system that
renders SOME roughness scores closer than one that renders none, which is exactly the comparison being made.

Roughness is scale-free (p90 divided by waist width), so the two sides do not need a shared frame: each can be
measured where nothing resampled it. `run_pair` now writes `amask_native.png`, the after mask as segmented, and
`compare.py` records `hem_rough_rel_real_native` from it.

    experiment_roughness_native.py [--pairs experiments/pairs] [--preset median]

Writes experiments/EXP_0025_roughness_native/result.json: the same sign test as EXP_0017, on both the warped and the
native measurement, so the two are directly comparable.
"""
import argparse, glob, json, math, os, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sign_p(b, w):
    n = b + w
    if n == 0: return 1.0
    k = max(b, w)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="experiments/pairs")
    ap.add_argument("--preset", default="median")
    ap.add_argument("--out", default="experiments/EXP_0025_roughness_native/result.json")
    a = ap.parse_args()
    excl = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
            if l.strip() and not l.startswith("#")}
    rows = []
    for f in sorted(glob.glob(str(ROOT / a.pairs / f"*/cmp_{a.preset}/metrics.json"))):
        pid = Path(f).parents[1].name
        note = Path(f).parents[1] / "NOTE.md"
        if pid in excl: continue
        if note.exists() and note.read_text().splitlines()[0].startswith("# PAIR — rejected"): continue
        r = {x["system"]: x for x in json.load(open(f))["rows"]}
        if "prediction" not in r: continue
        fin = lambda v: isinstance(v, (int, float)) and v == v
        rows.append({"pair": pid,
                     "real_warped": r["prediction"].get("hem_rough_rel_real"),
                     "real_native": r["prediction"].get("hem_rough_rel_real_native"),
                     "pred": r["prediction"].get("hem_rough_rel_pred"),
                     "crop": r["null:crop-only"].get("hem_rough_rel_pred"),
                     "noop": r["null:no-op"].get("hem_rough_rel_pred")})
    out = {"pairs": rows, "n_pairs": len(rows), "preset": a.preset, "source": a.pairs}
    for tag, key in (("warped", "real_warped"), ("native", "real_native")):
        use = [r for r in rows if all(isinstance(r[k], (int, float)) and r[k] == r[k] for k in (key, "pred", "crop"))]
        if not use:
            out[tag] = {"decidable": 0, "note": "no pair produced this measurement"}
            continue
        err = lambda r, sysk: abs(r[sysk] - r[key])
        wins = sum(1 for r in use if err(r, "pred") < err(r, "crop"))
        loss = sum(1 for r in use if err(r, "pred") > err(r, "crop"))
        ties = len(use) - wins - loss
        out[tag] = {"decidable": len(use), "wins": wins, "losses": loss, "ties": ties,
                    "p_two_sided": sign_p(wins, loss),
                    "mean_err_prediction": sum(err(r, "pred") for r in use) / len(use),
                    "mean_err_crop_only": sum(err(r, "crop") for r in use) / len(use),
                    "mean_real": sum(r[key] for r in use) / len(use)}
    out["real_hem_reads_zero_natively"] = sum(1 for r in rows if r["real_native"] == 0.0)
    out["real_hem_measurable_natively"] = sum(1 for r in rows
                                              if isinstance(r["real_native"], (int, float))
                                              and r["real_native"] == r["real_native"] and r["real_native"] > 0)
    # how much rougher does the warp make the real hem look?
    both = [r for r in rows if all(isinstance(r[k], (int, float)) and r[k] == r[k] for k in ("real_warped", "real_native"))]
    if both:
        out["warp_inflation"] = {
            "n": len(both),
            "mean_real_warped": sum(r["real_warped"] for r in both) / len(both),
            "mean_real_native": sum(r["real_native"] for r in both) / len(both),
            "pairs_where_warped_reads_rougher": sum(1 for r in both if r["real_warped"] > r["real_native"]),
            "pairs_where_native_reads_rougher": sum(1 for r in both if r["real_native"] > r["real_warped"])}
    (ROOT / a.out).parent.mkdir(parents=True, exist_ok=True)
    (ROOT / a.out).write_text(json.dumps(out, indent=1))
    for tag in ("warped", "native"):
        d = out[tag]
        if not d.get("decidable"): print(f"{tag:8s} no decidable pairs"); continue
        print(f"{tag:8s} n={d['decidable']}  prediction {d['mean_err_prediction']:.5f} vs crop-only "
              f"{d['mean_err_crop_only']:.5f}  {d['wins']}-{d['losses']}-{d['ties']}  p={d['p_two_sided']:.3f}"
              f"  (mean real roughness {d['mean_real']:.5f})")
    if both:
        w = out["warp_inflation"]
        print(f"warp inflation: real hem reads {w['mean_real_warped']:.5f} warped vs {w['mean_real_native']:.5f} "
              f"native ({w['pairs_where_warped_reads_rougher']} of {w['n']} pairs rougher after the warp)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

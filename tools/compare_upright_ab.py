#!/usr/bin/env python3
"""EXP_0022 Part B — the A/B the tuning rule asks for: does removing the 8-degree upright deadband help?

Reads two batch runs made with `PAIRS_UPRIGHT=8.0` (the frozen baseline) and `PAIRS_UPRIGHT=0.0` (always upright)
and reports, per pair and in aggregate, what changed. Pairs are matched by id; a pair that only one arm could score
is reported separately rather than dropped silently.

    compare_upright_ab.py --a experiments/pairs_upright8 --b experiments/pairs_upright0 [--preset median]
"""
import argparse, glob, json, os, statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS = ["sil_iou_vs_real", "hem_chamfer", "dE_edge_band_vs_real", "fringe_iou_vs_real"]
HIGHER_IS_BETTER = {"sil_iou_vs_real": True, "hem_chamfer": False, "dE_edge_band_vs_real": False,
                    "fringe_iou_vs_real": True}

EXCLUDE = {l.split()[0] for l in (ROOT / "data/priors/exclude.txt").read_text().splitlines()
           if l.strip() and not l.startswith("#")}


def load(dirname, preset, honour_exclude=True):
    """EXP_0016 was recomputed after review 6 found it scored two pairs `exclude.txt` bans. Honoured here by default."""
    out = {}
    for f in sorted(glob.glob(str(ROOT / dirname / f"*/cmp_{preset}/metrics.json"))):
        pid = Path(f).parents[1].name
        note = Path(f).parents[1] / "NOTE.md"
        if note.exists() and note.read_text().splitlines()[0].startswith("# PAIR — rejected"): continue
        if honour_exclude and pid in EXCLUDE: continue
        d = json.load(open(f)); r = {x["system"]: x for x in d["rows"]}
        if "prediction" not in r: continue
        rot = []
        if note.exists():
            rot = [l.strip("- ").strip() for l in note.read_text().splitlines() if "rotated" in l and "upright" in l]
        out[pid] = {"metrics": r, "rotations": rot, "reg_resid": d.get("registration_residual_px")}
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="experiments/pairs_upright8", help="baseline arm (deadband 8)")
    ap.add_argument("--b", default="experiments/pairs_upright0", help="candidate arm (always upright)")
    ap.add_argument("--preset", default="median")
    ap.add_argument("--out", default="experiments/EXP_0022_upright_threshold/result.json")
    ap.add_argument("--include-excluded", action="store_true", help="score pairs data/priors/exclude.txt bans (do not)")
    args = ap.parse_args()
    A, B = load(args.a, args.preset, not args.include_excluded), load(args.b, args.preset, not args.include_excluded)
    both = sorted(set(A) & set(B))
    res = {"arm_a": args.a, "arm_b": args.b, "preset": args.preset, "excluded": sorted(EXCLUDE),
           "honoured_exclude": not args.include_excluded,
           "n_a": len(A), "n_b": len(B), "n_both": len(both),
           "only_a": sorted(set(A) - set(B)), "only_b": sorted(set(B) - set(A)),
           "pairs_rotated_in_b_only": [p for p in both if B[p]["rotations"] and not A[p]["rotations"]],
           "per_pair": {}, "means": {}, "sign_test": {}}
    for p in both:
        res["per_pair"][p] = {m: [A[p]["metrics"]["prediction"].get(m), B[p]["metrics"]["prediction"].get(m)]
                              for m in METRICS}
        res["per_pair"][p]["rotated_a"] = A[p]["rotations"]; res["per_pair"][p]["rotated_b"] = B[p]["rotations"]
    for m in METRICS:
        a = [A[p]["metrics"]["prediction"].get(m) for p in both]
        b = [B[p]["metrics"]["prediction"].get(m) for p in both]
        pairs = [(x, y) for x, y in zip(a, b) if isinstance(x, (int, float)) and isinstance(y, (int, float))
                 and x == x and y == y]
        if not pairs: continue
        better = sum(1 for x, y in pairs if (y > x) == HIGHER_IS_BETTER[m] and y != x)
        worse = sum(1 for x, y in pairs if (y < x) == HIGHER_IS_BETTER[m] and y != x)
        res["means"][m] = {"a": st.mean(x for x, _ in pairs), "b": st.mean(y for _, y in pairs), "n": len(pairs)}
        res["sign_test"][m] = {"b_better": better, "b_worse": worse, "tied": len(pairs) - better - worse,
                               "p_two_sided": _sign_p(better, worse)}
    out = ROOT / args.out; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, indent=1))
    print(f"pairs scored: {len(A)} baseline, {len(B)} candidate, {len(both)} in both")
    print(f"rotated only in the candidate arm: {res['pairs_rotated_in_b_only']}")
    print(f"\n| metric | deadband 8 (baseline) | always upright | better / worse / tied | sign p |")
    print("|---|---|---|---|---|")
    for m in METRICS:
        if m not in res["means"]: continue
        M, S = res["means"][m], res["sign_test"][m]
        print(f"| {m} | {M['a']:.4f} | {M['b']:.4f} | {S['b_better']} / {S['b_worse']} / {S['tied']} | {S['p_two_sided']:.3f} |")
    return 0

def _sign_p(b, w):
    n = b + w
    if n == 0: return 1.0
    from math import comb
    k = max(b, w)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)

if __name__ == "__main__":
    raise SystemExit(main())

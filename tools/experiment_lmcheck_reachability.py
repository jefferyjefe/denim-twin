"""Which of lmcheck's nine ordering rules can actually fire on AUTOMATIC landmarks?

EXP_0032 noted that `crotch above the hips` is structurally unreachable for auto landmarks, because
`autolm` searches for the crotch in `range(hip_y, bot)` and so can never return a crotch above the
hips. Review 7 pointed out that this undercounts badly. `landmarks_from_mask` derives most of these
landmarks from `_row_extent`, which returns (min_x, max_x) in order, so the left/right and
inside-out orderings are true by construction too.

This measures it two ways: a fuzz over synthetic garments, and deliberately constructed cases for
the rules the fuzz cannot reach. A rule that no input can violate is not coverage, and a check whose
rules are mostly unreachable should say so rather than count them.

    experiment_lmcheck_reachability.py [--trials 400]
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon.lmcheck import check_landmarks, _ORDER


def _fuzz(trials, seed=0):
    rng = np.random.default_rng(seed)
    fired, n = set(), 0
    for _ in range(trials):
        H, W = int(rng.integers(200, 420)), int(rng.integers(150, 380))
        m = np.zeros((H, W), bool)
        wl, wr, top = int(W * 0.15), int(W * 0.85), int(H * 0.05)
        m[top:int(H * 0.35), wl:wr] = True
        gap = int(rng.integers(0, 40))
        for side in (0, 1):
            x0 = wl + side * (wr - wl - int(W * 0.3))
            for y in range(int(H * 0.3), int(H * rng.uniform(0.6, 0.95))):
                sh = int((y - H * 0.3) * rng.uniform(-0.25, 0.25))
                m[y, max(0, x0 + sh):min(W, x0 + int(W * 0.3) + sh)] = True
        if gap:
            m[int(H * 0.35):, W // 2 - gap // 2:W // 2 + gap // 2] = False
        try:
            lm, _ = landmarks_from_mask(m)
        except Exception:
            continue
        if len(lm) < 6:
            continue
        n += 1
        for f in check_landmarks(lm):
            if f["severity"] == "inverted":
                fired.add(f["why"])
    return fired, n


def _constructed():
    """Shorts with no between-leg gap and legs of unequal length: the crotch falls back to the
    bottom of the mask (the LONGER leg's tip), so the SHORT leg's hem is strictly above it.

    Both mirrorings are built. Testing only one would reach only one of the two hem rules and make
    the other look unreachable -- the same undercount this experiment exists to correct.

    Only the LEFT-hem rule turns out to be reachable, and the asymmetry is real rather than an
    artefact of the construction: autolm slices the left leg as `slice(0, cyx)` (excluding the
    crotch column) and the right as `slice(cyx, W)` (including it), so the right sub-mask can absorb
    a column of the longer left leg and take its lower hem row. Give the legs a clean centre gap
    instead and autolm finds a real crotch above both hems, so neither rule fires.
    """
    out = set()
    for short_side in ("left", "right"):
        H, W = 200, 300
        m = np.zeros((H, W), bool)
        m[10:80, 40:260] = True
        lo, hi = (150, 190) if short_side == "left" else (190, 150)
        m[80:lo, 40:150] = True
        m[80:hi, 150:260] = True
        lm, _ = landmarks_from_mask(m)
        out |= {f["why"] for f in check_landmarks(lm) if f["severity"] == "inverted"}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=400)
    a = ap.parse_args()
    fuzzed, n = _fuzz(a.trials)
    built = _constructed()
    reachable = sorted(fuzzed | built)
    rules = [w for _, _, _, w in _ORDER]
    unreachable = [w for w in rules if w not in reachable]
    print(json.dumps({"summary": {
        "n_rules": len(rules),
        "n_reachable_on_auto_path": len(reachable),
        "n_unreachable_on_auto_path": len(unreachable),
        "reachable": reachable,
        "n_fuzz_garments": n,
        "n_reached_by_fuzz_alone": len(fuzzed),
    }, "unreachable_rules": unreachable}, indent=2))


if __name__ == "__main__":
    main()

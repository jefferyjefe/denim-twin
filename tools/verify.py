#!/usr/bin/env python3
"""One command that says whether the repository is in a publishable state.

The checks existed; nothing ran them together, and CI ran three of them with `|| true` so they
could not fail. Two defects reached the README that way -- a headline comparison that was void
(EXP_0034) and a scope check that flagged the line declaring its own ban and was therefore
ignored. This is the gate: every check, one exit code, and a table saying which one broke.

    tools/verify.py [--fast] [--no-bench]

    --fast      skip the pair bench (the slow one)
    --no-bench  same, kept explicit for CI
Exit 1 if any REQUIRED check fails. Advisory checks are reported but never fail the run.
"""
import argparse, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY_ = sys.executable

# (name, argv, required, what a failure means)
CHECKS = [
    ("tests", [PY_, "-m", "pytest", "-q", "tests"], True,
     "a behaviour changed or a guard test caught a regression"),
    ("claims", [PY_, "tools/check_claims.py"], True,
     "a number quoted in a NOTE, the README or docs/ no longer matches the artefact it came from"),
    ("scope", [PY_, "tools/scope_check.py"], True,
     "a file reaches past its phase gate, or names a treatment banned in year one"),
    ("sentinel", [PY_, "tools/sentinel.py"], True, "a sentinel invariant broke"),
    ("protocol", [PY_, "tools/protocol_audit.py"], False, "a capture protocol drifted from its spec"),
    ("bench", [PY_, "tools/bench.py"], False,
     "a pair metric moved; two regressions against 443d1d4658 are documented and expected"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip the bench")
    ap.add_argument("--no-bench", action="store_true")
    a = ap.parse_args()
    skip = {"bench"} if (a.fast or a.no_bench) else set()

    rows, failed = [], 0
    for name, argv, required, meaning in CHECKS:
        if name in skip:
            rows.append((name, "SKIP", 0.0, required, "")); continue
        t0 = time.time()
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        dt = time.time() - t0
        ok = r.returncode == 0
        if not ok and required:
            failed += 1
        tail = (r.stdout + r.stderr).strip().splitlines()
        rows.append((name, "OK" if ok else ("FAIL" if required else "WARN"), dt, required,
                     "" if ok else (meaning + " | " + (tail[-1][:100] if tail else "no output"))))

    w = max(len(r[0]) for r in rows)
    print()
    for name, status, dt, required, why in rows:
        tag = "" if required else " (advisory)"
        print(f"  {status:5s} {name:{w}s}{tag}  {dt:5.1f}s")
        if why:
            print(f"        {why}")
    print(f"\n{'FAILED' if failed else 'OK'}: {failed} required check(s) failing"
          f" of {sum(1 for r in rows if r[3] and r[1] != 'SKIP')} run.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

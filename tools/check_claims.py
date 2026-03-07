#!/usr/bin/env python3
"""Check every experiment's quoted numbers against the artefacts they came from.

Four of the twelve findings in review 6 were the same mistake: a number was written into a NOTE, and then the code or
data underneath it changed. This makes that mistake fail loudly. Each experiment may carry a `claims.json`:

    [
      {"claim": "after-wash samples in the prior = 2",
       "note_regex": "\\\\| after-wash samples in the prior \\\\| \\\\d+ \\\\| \\\\*\\\\*(\\\\d+)\\\\*\\\\*",
       "source": "data/priors/fringe.json", "path": "n_after_wash_combined"},
      {"claim": "9 high-resolution controls, 0 rough",
       "note_regex": "controls \\\\(waist [^|]*\\\\) \\\\| (\\\\d+) \\\\|",
       "source": "reports/fringe_methods/controls_roughness.json", "count": {"verdict": "any"}}
    ]

`note_regex` pulls the number the NOTE claims (first capture group); `source` + `path` (dotted, may index lists) or
`count` pulls what the artefact says. A claim whose source is missing is reported as UNVERIFIABLE, not as a pass.

    check_claims.py [--experiments experiments] [--quiet]     # exit 1 if any claim fails
"""
import argparse, json, os, re, sys, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def dig(obj, path):
    for part in path.split("."):
        if part == "": continue
        if isinstance(obj, list):
            obj = obj[int(part)]
        else:
            if part not in obj: raise KeyError(f"{part} not in {list(obj)[:6]}")
            obj = obj[part]
    return obj

def check_one(exp_dir, c):
    note = Path(exp_dir) / "NOTE.md"
    claimed = None
    if c.get("note_regex"):
        if not note.exists(): return "UNVERIFIABLE", "no NOTE.md", None, None
        m = re.search(c["note_regex"], note.read_text())
        if not m: return "FAIL", "the NOTE no longer states this claim in the expected form", None, None
        if not m.groups():
            # A regex with no capture group can only confirm the sentence is still there; the number then has to come
            # from `claimed`. Without this the tool raised IndexError and reported nothing at all.
            if "claimed" not in c:
                return "UNVERIFIABLE", "note_regex has no capture group and the claim carries no 'claimed' value", None, None
            claimed = str(c["claimed"])
        else:
            claimed = m.group(1)
    else:
        claimed = str(c.get("claimed"))
    src = ROOT / c["source"]
    if not src.exists(): return "UNVERIFIABLE", f"missing artefact {c['source']}", claimed, None
    data = json.load(open(src))
    try:
        if "count" in c:
            rows = dig(data, c.get("path", "")) if c.get("path") else data
            if isinstance(rows, dict): rows = list(rows.values())     # a mapping of id -> record counts its values
            spec = c["count"]
            actual = sum(1 for r in rows if isinstance(r, dict)
                         and all(r.get(k) == v for k, v in spec.items() if v != "any"))
        else:
            actual = dig(data, c["path"])
    except Exception as e:
        return "UNVERIFIABLE", f"cannot read {c.get('path')}: {type(e).__name__} {e}", claimed, None
    tol = c.get("tol")
    try:
        a, b = float(claimed), float(actual)
        ok = abs(a - b) <= (tol if tol is not None else 1e-9)
    except (TypeError, ValueError):
        ok = str(claimed).strip() == str(actual).strip()
    return ("OK" if ok else "FAIL"), "", claimed, actual

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiments", default=str(ROOT / "experiments"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    rows, bad = [], 0
    for cf in sorted(glob.glob(os.path.join(a.experiments, "*", "claims.json"))):
        exp = os.path.basename(os.path.dirname(cf))
        for c in json.load(open(cf)):
            status, why, claimed, actual = check_one(os.path.dirname(cf), c)
            rows.append((exp, c["claim"], status, claimed, actual, why))
            if status == "FAIL": bad += 1
    if not rows:
        print("no claims.json files found"); return 0
    w = max(len(r[0]) for r in rows)
    for exp, claim, status, claimed, actual, why in rows:
        if a.quiet and status == "OK": continue
        line = f"{status:13s} {exp:{w}s}  {claim}"
        if status != "OK": line += f"   [note says {claimed}, artefact says {actual}] {why}"
        print(line)
    print(f"\n{sum(1 for r in rows if r[2]=='OK')} ok, {bad} failed, "
          f"{sum(1 for r in rows if r[2]=='UNVERIFIABLE')} unverifiable, {len(rows)} claims")
    return 1 if bad else 0

if __name__ == "__main__": sys.exit(main())

#!/usr/bin/env python3
"""Scope-creep / gate check. docs/GATES_STATUS.json records which gates have passed.
Flags files whose phase gate hasn't passed and banned topics. Exit 1 on violation."""
import json, re, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
status = json.loads((ROOT / "docs/GATES_STATUS.json").read_text())
passed = {k for k, v in status.items() if v.get("passed")}
RULES = [  # (path regex, required gate)
    (r"src/denimtwin/(mesh|geom3d|sim|cloth)/", "gate_2"),
    (r"src/denimtwin/(fray|procedural)/", "gate_4"),
    (r"src/denimtwin/(learned|neural|render)/", "gate_5"),
    (r"src/denimtwin/uncertainty/", "gate_6"),
]
BANNED = re.compile(r"\b(bleach|acid wash|dye(ing)?|chemical)\b", re.I)
files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split()
viol = []
for f in files:
    for pat, gate in RULES:
        if re.search(pat, f) and gate not in passed: viol.append(f"{f}: requires {gate} (not passed)")
    if f.startswith("src/") and f.endswith(".py"):
        t = (ROOT / f).read_text(errors="ignore")
        if BANNED.search(t): viol.append(f"{f}: mentions year-two-banned treatment ({BANNED.search(t).group(0)})")
print("gates passed:", sorted(passed) or "none")
if viol: print("SCOPE VIOLATIONS:"); [print(" -", v) for v in viol]; sys.exit(1)
print("scope: OK")

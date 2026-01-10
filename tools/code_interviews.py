#!/usr/bin/env python3
"""Interview coder (deterministic part): parse discovery/INTERVIEWS.md table into JSON for the agent to code."""
import json, re, sys
from pathlib import Path
t = (Path(__file__).resolve().parents[1] / "discovery/INTERVIEWS.md").read_text()
rows = [l for l in t.splitlines() if l.startswith("|") and not l.startswith("| #") and not set(l) <= set("|- ")]
hdr = [h.strip() for h in re.findall(r"\|([^|]*)", [l for l in t.splitlines() if l.startswith("| #")][0])]
out = [dict(zip(hdr, [c.strip() for c in re.findall(r"\|([^|]*)", r)])) for r in rows]
print(json.dumps(out, indent=1)); print(f"{len(out)} interviews", file=sys.stderr)

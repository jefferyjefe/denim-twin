#!/usr/bin/env python3
"""Compile the skeleton of this week's note from git log + experiments + audits. Agent fills the questions."""
import subprocess, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
today = dt.date.today(); week = today.isocalendar()[1]
out = ROOT / "notes/weekly" / f"{today.year}-W{week:02d}.md"
log = subprocess.run(["git", "log", "--since=7.days", "--pretty=format:- %ad %s", "--date=short"], cwd=ROOT, capture_output=True, text=True).stdout
exps = "\n".join(f"- {p.parent.name}" for p in sorted(ROOT.glob("experiments/*/NOTE.md")))
def run(t): r = subprocess.run([sys.executable, str(ROOT / "tools" / t)], capture_output=True, text=True); return r.stdout.strip()[-1500:]
body = f"""# Week {week} — {today}

## Commits this week
{log or '- none'}

## Experiments on record
{exps or '- none'}

## Sentinel
```
{run('sentinel.py')}
```
## Protocol audit
```
{run('protocol_audit.py')}
```
## Scope check
```
{run('scope_check.py')}
```

## Review questions (fill in)
- What measurable uncertainty did we reduce this week?
- Which assumption failed?
- Physical matching improved, or only attractiveness?
- Is the next experiment testing one clear hypothesis?
- Are data and results reproducible?
- Is scope expanding without evidence?

## Next action
"""
out.write_text(body); print(out)

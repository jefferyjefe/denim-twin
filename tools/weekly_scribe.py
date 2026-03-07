#!/usr/bin/env python3
"""Compile the skeleton of this week's note from git log + experiments + audits. Agent fills the questions.

The generated part lives between two markers. Anything a person wrote outside them is preserved: this tool used to
`write_text` the whole file, so running it destroyed every hand-written weekly note it had ever been used to start.
"""
import subprocess, sys, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
today = dt.date.today(); week = today.isocalendar()[1]
out = ROOT / "notes/weekly" / f"{today.year}-W{week:02d}.md"
log = subprocess.run(["git", "log", "--since=7.days", "--pretty=format:- %ad %s", "--date=short"], cwd=ROOT, capture_output=True, text=True).stdout
exps = "\n".join(f"- {p.parent.name}" for p in sorted(ROOT.glob("experiments/*/NOTE.md")))
def run(t): r = subprocess.run([sys.executable, str(ROOT / "tools" / t)], capture_output=True, text=True); return r.stdout.strip()[-1500:]
BEGIN, END = "<!-- weekly-scribe:begin -->", "<!-- weekly-scribe:end -->"
body = f"""{BEGIN}
## Generated summary (weekly_scribe.py — edits here are overwritten)

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
{END}
"""
HEADER = f"""# Week {week} — {today}

## Hypothesis
## Setup
## Result
## Interpretation
## Next action

"""
prev = out.read_text() if out.exists() else ""
if BEGIN in prev and END in prev:
    merged = prev[:prev.index(BEGIN)] + body.strip() + prev[prev.index(END) + len(END):]
elif prev.strip():
    # an older note with no markers: keep every word of it and append the generated block
    merged = prev.rstrip() + "\n\n" + body
else:
    merged = HEADER + body
out.write_text(merged); print(out)

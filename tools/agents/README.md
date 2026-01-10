# Agents

| Agent | Where | Cadence | Writes to | Script it interprets |
|---|---|---|---|---|
| Reviewer-on-push | cloud routine | daily 06:00 UTC | branch `agent/reviewer/<date>` + `tests/review_*.py` | pytest |
| Data sentinel | cloud routine | daily 05:00 UTC | `reports/sentinel/` on main | `tools/sentinel.py` |
| Protocol-drift auditor | cloud routine | daily 05:15 UTC | `reports/protocol/` on main | `tools/protocol_audit.py` |
| Null-baseline enforcer | cloud routine | daily 05:45 UTC | experiment `NOTE.md` (branch) | `tools/null_baselines.py` |
| Reproducibility runner | cloud routine | Mon 05:30 UTC | `reports/repro/` on main | fresh install + pytest + baseline |
| Weekly scribe + scope | cloud routine | Sun 22:00 UTC | `notes/weekly/` on main | `tools/weekly_scribe.py`, `tools/scope_check.py` |
| Literature watcher | cloud routine | Mon 07:00 UTC | `docs/LITERATURE.md` (branch) | `tools/arxiv_watch.py` |
| Blinded judge | cloud routine | Sat 06:00 UTC | `reports/judge/` on main | `tools/judge_pairs.py` |
| Calibration auditor | cloud routine (disabled until Phase 7) | Mon 06:30 UTC | `reports/calibration/` | `tools/calibration_audit.py` |
| Interview coder | cloud routine (disabled, run on demand) | — | `discovery/CODED.md` (branch) | `tools/code_interviews.py` |
| Capture-QA watcher | local launchd | every 5 min | `<garment>/qa_report.md`, macOS notification | `tools/capture_watch.py` |
| Harvest curator | local launchd | hourly | `data/external/curated.jsonl` | `tools/curate_harvest.py` |
| Image harvester | cloud routine | hourly :07 | `data/external/manifest.jsonl` on main | `tools/harvest_images.py` |

Rules: only the harvester and report-only agents write to `main`, and only under `reports/`, `notes/`, or
`data/external/`. Anything touching `src/`, `tools/`, `tests/`, `docs/` goes to an `agent/*` branch.
Local plists live in `ops/`; install with `cp ops/*.plist ~/Library/LaunchAgents/ && launchctl load ...`.

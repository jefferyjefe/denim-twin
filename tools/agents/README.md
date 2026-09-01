# Agents

| Agent | Where | Cadence | Writes to | Script it interprets |
|---|---|---|---|---|
| Reviewer-on-push | cloud routine | daily 06:00 UTC | branch `agent/reviewer/<step>` + `tests/review_*.py` | pytest |
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
| Tutorial-pair finder | cloud routine | daily 04:30 UTC | `data/external/pairs.jsonl` on main | `tools/tutorial_pairs.py` |
| Image harvester | cloud routine (DISABLED — local curator does this) | — | `data/external/manifest.jsonl` on main | `tools/harvest_images.py` |

Rules: only the harvester and report-only agents write to `main`, and only under `reports/`, `notes/`, or
`data/external/`. Anything touching `src/`, `tools/`, `tests/`, `docs/` goes to an `agent/*` branch.
Local plists live in `ops/`; install with `cp ops/*.plist ~/Library/LaunchAgents/ && launchctl load ...`.

## Status: ALL cloud routines DISABLED
Every cloud run (including a no-tool smoke test) stalls after "Claude Code process started" with no transcript
events. A no-tool smoke test also never produced a transcript event, so every routine was disabled to stop stuck sessions piling up. Re-enable in https://claude.ai/code/routines if the environment is fixed. GitHub Actions (`.github/workflows/tests.yml`) now runs the test suite on every push.
Local launchd jobs (ops/*.plist) are the working automation: capture-QA (5 min), harvest curator (hourly),
**pairs-daily (03:30 local)** = ingest submissions → fetch/validate pairs → batch → report → fringe prior → commit.

## Routine IDs (manage at https://claude.ai/code/routines/<id>)
| Routine | ID |
|---|---|
| image harvester | trig_01AQvsxTVdex78gcVMBXNL4m |
| tutorial-pair finder | trig_01XDext6pGACUVPjrRTwVncX |
| reviewer-on-push | trig_017oUcXhFVpZ1tqDs4Q59kJ8 |
| data sentinel | trig_01WRD4vwwZjUcyWniTCSAmDm |
| protocol-drift auditor | trig_01LavJrSp3MDGBNNmUzvYmjH |
| null-baseline enforcer | trig_01PeumY4Tz7QW27oDvavdUfN |
| reproducibility runner | trig_01Xbrw1EDu8zt7LaPSrhm4hG |
| weekly scribe + scope | trig_01JJXahpEtP4n7ZAJwQpcK65 |
| literature watcher | trig_01H3sUKwjhXtZx7kFRQgFFdp |
| blinded judge | trig_01GzekSgMVrQ3A7bQtuCoYwh |
| calibration auditor (disabled) | trig_01CqPLREYDdBE5nJu9He77s9 |
| interview coder (disabled) | trig_019t2n8VSkP6pAaCsB2p6xmf |

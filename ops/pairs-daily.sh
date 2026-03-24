#!/bin/sh
# The nightly pairs batch, with the two guards the inline launchd command did not have.
#
# com.denimtwin.pairs-daily runs its whole sequence as one inline shell string in the plist, at
# 03:30, unattended, ending in `git add … && git commit && git push`. Four things are wrong with
# that, and all four fired on 2026-08-30:
#
#  1. It runs against the WORKING TREE, not against a commit. That night the tree held an
#     uncommitted change to tools/run_pair.py, so the job regenerated eight pair directories with
#     code that exists in no commit and was about to push the output. That is review 7's finding --
#     artefacts whose producer cannot be re-derived -- automated and self-pushing.
#  2. It never runs tools/verify.py. Regenerating experiments/pairs is exactly what invalidated four
#     reports in EXP_0038; make_reports.py --check is the thing that notices, and it was not run.
#  3. fit_fringe.py rewrites data/priors/fringe.json, the tracked prior every prediction depends on.
#     tests/test_tools_do_not_touch_tracked_data.py exists because that already happened once.
#  4. `git pull --rebase` and `git push` run unattended over whatever local commits exist.
#
# This script keeps the work and refuses the commit when the preconditions are not met. Point the
# plist's ProgramArguments at it instead of the inline string.
set -eu
cd "$(dirname "$0")/.."
PY=.venv/bin/python

# (1) refuse to run against uncommitted code. Data and derived artefacts may be dirty; the things
#     that PRODUCE them may not, or the output cannot be attributed to anything in history.
if ! git diff --quiet HEAD -- src tools; then
    echo "pairs-daily: refusing -- uncommitted changes under src/ or tools/:"
    git diff --name-only HEAD -- src tools
    exit 3
fi

git pull -q --rebase
$PY tools/ingest_submissions.py || true
$PY tools/tutorial_pairs.py --fetch 200 --research-use || true
$PY tools/validate_pairs.py
$PY tools/run_pairs_batch.py
$PY tools/report_pairs.py > experiments/pairs/REPORT.md
$PY tools/fit_fringe.py                      # rewrites the tracked prior, deliberately, on this path
$PY tools/make_gallery.py
$PY tools/bench.py > experiments/pairs/BENCH.md

# (2) the gate. A batch that moved the pair artefacts can invalidate any report derived from them.
if ! $PY tools/verify.py --no-bench; then
    echo "pairs-daily: batch ran, verify.py FAILED -- not committing. Inspect and fix by hand."
    exit 4
fi

git add experiments/pairs/BENCH.md data/external/pairs.jsonl data/external/pairs_validation.jsonl \
        experiments/pairs/SUMMARY.md experiments/pairs/REPORT.md experiments/pairs/*/NOTE.md \
        reports data/priors 2>/dev/null || true
git commit -qm "pairs-daily: batch, report, prior" && git push -q

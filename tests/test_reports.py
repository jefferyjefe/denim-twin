"""The two reporting scripts must run -- and must run over evidence, not over an empty glob.

WHAT THIS USED TO PROVE: that each script exits 0 and contains a string literal.

  * `assert r.returncode == 0 and "# pairs:" in r.stdout` matched `# pairs: 0 (preset median)`
    exactly as happily as an eleven-pair table, and 0 is what `tools/report_pairs.py` prints on any
    clean clone: it aggregates `experiments/pairs/*/cmp_<preset>/metrics.json`, and every `cmp_`
    directory is gitignored. The one number the report exists to produce was the one number the
    assertion could not see.
  * `assert "n" in pr and "insufficient" in pr` asserted that `tools/fit_fringe.py` has a
    `prior = {"n": ..., "insufficient": ...}` literal in it. It writes both keys unconditionally,
    for n == 0 as readily as for n == 6.

WHAT THEY PROVE NOW: each parses the actual count out of the tool's own output and asserts a floor
on it, so "the report ran" can no longer stand in for "the report had something to report". Each
declares the evidence it needs, so a checkout without it reports UNAVAILABLE rather than a pass --
and they are two tests rather than one because they need different things. The pair table needs the
gitignored scoring output; the prior needs only the committed per-pair records, and must keep
running in CI where those are all there is.
"""
import json, os, re, subprocess, sys, tempfile

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

#: The scored bench is seven pairs: eleven found, four banned by data/priors/exclude.txt. Same floor
#: the real-mask tests in tests/test_waistband.py hold, and the same count prereqs.py declares as
#: pair_cmp_metrics.min_count. Below it, the aggregate numbers in experiments/pairs/BENCH.md are
#: being averaged over fewer pairs than this repository says they are.
MIN_SCORED_PAIRS = 7

#: fit_fringe reads committed records (NOTE.md, landmarks.json, measure.json) and then applies one
#: quality bar that reads the gitignored cmp_median/metrics.json -- a filter that can only ever
#: REMOVE rows. Seven pairs qualify without it, six with it, so six is the floor that holds both in
#: a clean clone and in a full checkout, and it is a floor on real pairs either way.
MIN_PRIOR_PAIRS = 6


@pytest.mark.needs("pair_cmp_metrics")
def test_report_pairs_tabulates_the_whole_scored_bench():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/report_pairs.py")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    m = re.search(r"^# pairs: (\d+) \(preset ", r.stdout, re.M)
    assert m, f"report_pairs.py printed no '# pairs: N' header:\n{r.stdout}"
    n = int(m.group(1))
    assert n >= MIN_SCORED_PAIRS, (
        f"the pair table covers {n} pairs; the bench is {MIN_SCORED_PAIRS}. Either the scoring batch "
        f"is incomplete (PAIRS_OUT=experiments/pairs python tools/run_pairs_batch.py) or pairs have "
        f"been banned without the reports that quote this table being redone.")
    # The header is a print statement; the table is the report. Counting the rows keeps the count
    # honest -- a header that says 7 over an empty table is the same defect in a new place.
    ids = re.findall(r"^\| ([0-9a-f]{10}) \|", r.stdout, re.M)
    assert len(ids) == n and len(set(ids)) == n, (
        f"header claims {n} pairs, table has {len(ids)} rows ({len(set(ids))} distinct)")
    assert "## Means" in r.stdout, "no aggregate block: the table was too short to average"


@pytest.mark.needs("pair_runs")
def test_fit_fringe_writes_a_prior_over_the_pairs_that_qualify():
    # --out-dir, not the tracked path: this test used to rewrite data/priors/fringe.json as a side effect, so
    # running the suite silently replaced the prior every prediction depends on with whatever the local pair
    # artefacts happened to say (and in a fresh clone, with an empty one).
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/fit_fringe.py"), "--out-dir", td],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        pr = json.load(open(os.path.join(td, "fringe.json")))
    assert "n" in pr and "insufficient" in pr
    assert pr["n"] == len(pr["pairs"]), f"n={pr['n']} but {len(pr['pairs'])} pair rows were written"
    assert pr["n"] >= MIN_PRIOR_PAIRS, (
        f"the prior was fitted over {pr['n']} pairs. Below {MIN_PRIOR_PAIRS} the tool ran but had "
        f"nothing to fit, and a prior over no pairs is not a prior -- check that "
        f"experiments/pairs/*/landmarks.json survived the checkout.")
    # EXP_0015/0016: no depth measurement in this project has passed a control, so the prior ships
    # flagged. n crossing 5 must not quietly clear that flag -- the flag is about the measurement,
    # not the sample size.
    assert pr["insufficient"] is True, (
        "the fringe prior declared itself sufficient. No depth measurement here has passed a "
        "control (EXP_0015/0016); if that changed, it changed in an experiment, not in a test.")


def test_report_pairs_runs_and_reports_an_empty_bench_as_empty(tmp_path):
    """The hermetic half: the tool executes, resolves its paths, and says zero when there is zero.

    The test above is the one that checks the NUMBERS, and it needs the gitignored scoring output, so
    in a clean clone `tools/report_pairs.py` stopped being executed at all -- a script that had run on
    every CI build now ran on none, and an ImportError or a path bug in it would reach a release
    unnoticed. This runs it against an empty directory, which is cheap, deterministic, and available
    everywhere.

    It asserts the ZERO CASE EXPLICITLY rather than asserting a substring that both cases satisfy.
    That substring is precisely how the original test managed to pass over an empty glob for months:
    `"# pairs:" in stdout` is true of `# pairs: 0` and of `# pairs: 11`, so it could not tell the
    difference between the report working and the report having nothing to report."""
    empty = tmp_path / "no_pairs"
    empty.mkdir()
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/report_pairs.py")],
                       cwd=ROOT, capture_output=True, text=True,
                       env=dict(os.environ, PAIRS_OUT=str(empty)))
    assert r.returncode == 0, r.stderr[-2000:]
    m = re.search(r"# pairs: (\d+)", r.stdout)
    assert m, f"no '# pairs: N' header in the output:\n{r.stdout[:500]}"
    assert int(m.group(1)) == 0, (
        f"pointed at an empty directory the report claims {m.group(1)} pairs; it is reading "
        f"something other than PAIRS_OUT")
    assert "## Means" not in r.stdout, (
        "a means block was computed over zero pairs; the aggregate must be omitted, not invented")

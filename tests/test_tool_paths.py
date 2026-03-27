"""Tools must read the repository, not the working directory.

Three experiment tools resolved `data/priors/exclude.txt` against `Path.cwd()`. Run from anywhere
but the repository root that read produced an EMPTY exclude set -- silently, with no error -- and the
four excluded pairs (a legs-only crop, a back view, a folded graphic, a two-garment after photo)
entered the result. A fourth tool went further and reassigned ROOT to `Path.cwd()` when it could not
find the file, which turns "run from the wrong place" into "read a different repository".

Two of the same tools also made the scored-pair filter an OPT-IN flag while their committed reports
had been generated WITH it, so re-running them the documented way would have silently replaced a
seven-pair report with a thirteen-pair one.
"""
import glob, json, os, re, subprocess, sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLS = sorted(glob.glob(os.path.join(ROOT, "tools", "*.py")))


def _src(f):
    return open(f).read()


def test_no_tool_reads_a_data_path_relative_to_the_working_directory():
    bad = []
    for f in TOOLS:
        for m in re.finditer(r'Path\(\s*"(data/|experiments/|reports/|docs/)', _src(f)):
            bad.append(f"{os.path.relpath(f, ROOT)}: Path(\"{m.group(1)}...\")")
    assert not bad, "resolve these against ROOT, not the cwd:\n" + "\n".join(bad)


def test_no_tool_falls_back_to_the_working_directory_for_root():
    bad = [os.path.relpath(f, ROOT) for f in TOOLS if re.search(r"ROOT\s*=\s*Path\.cwd\(\)", _src(f))]
    assert not bad, f"ROOT must be derived from __file__: {bad}"


def test_a_repo_relative_directory_default_is_always_joined_to_root():
    """Two conventions are allowed and both are cwd-independent: an absolute default built from ROOT,
    or a repo-relative default that every use joins to ROOT (`glob(str(ROOT / a.pairs / ...))`).
    What is not allowed is a relative default used raw, which silently reads whatever happens to sit
    beside the caller."""
    bad = []
    for f in TOOLS:
        src = _src(f)
        if not re.search(r'default="(experiments|data|reports)/', src):
            continue
        if not re.search(r'ROOT\s*/\s*(?!")[A-Za-z_]', src):
            bad.append(os.path.relpath(f, ROOT))
    assert not bad, f"relative directory default never joined to ROOT in: {bad}"


# Both parametrised tests below drive these two tools for real. registration_fold measures a TPS over
# the before-frame GARMENT MASK, so in a checkout without masks it reports 0 pairs: the filter test
# degenerates to "assert 0 < 0" (a red test saying nothing about the filter it guards) and the
# foreign-cwd test degenerates to comparing two empty summaries (a green test saying nothing at all).
# landmark_consistency reads committed JSON and is checkable anywhere, so it stays unconditional.
PAIR_TOOLS = [
    pytest.param("experiment_registration_fold.py", marks=pytest.mark.needs("pair_masks")),
    "experiment_landmark_consistency.py",
]


@pytest.mark.parametrize("tool", PAIR_TOOLS)
def test_the_tool_gives_the_same_answer_from_a_foreign_working_directory(tool, tmp_path):
    """The static checks above can be satisfied by a tool that is still cwd-sensitive some other way.
    This runs it for real from a directory that contains nothing."""
    def run(cwd):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", tool)],
                           cwd=cwd, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        return json.loads(r.stdout)["summary"]
    assert run(ROOT) == run(str(tmp_path))


@pytest.mark.parametrize("tool", PAIR_TOOLS)
def test_the_scored_pair_filter_is_the_default_not_an_opt_in(tool):
    """`--all-pairs` must widen the set. If the default already included everything, the committed
    report would not be the one the obvious invocation reproduces."""
    def run(*args):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", tool), *args],
                           cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, r.stderr[-2000:]
        return json.loads(r.stdout)
    n = "n_pairs" if "fold" in tool else "n_sets"
    assert run()["summary"][n] < run("--all-pairs")["summary"][n], \
        "the default is not filtering; the committed report is not what a plain run produces"


def test_every_registered_report_reproduces_the_file_on_disk():
    """tools/make_reports.py --check is a required gate in verify.py, but only over the reports it
    knows about. This asserts the registry is not silently empty or shrinking."""
    src = _src(os.path.join(ROOT, "tools", "make_reports.py"))
    registered = re.findall(r'"(reports/[^"]+\.json)":', src)
    assert len(registered) >= 8, f"only {len(registered)} reports have builders: {registered}"
    for rel in registered:
        assert os.path.exists(os.path.join(ROOT, rel)), f"{rel} is registered but not committed"

"""A tool that writes into `data/` must let the caller say where, and a test run must not leave tracked data modified.

`tests/test_reports.py` ran `tools/fit_fringe.py` with no arguments, and the tool writes `data/priors/fringe.json` —
the prior every prediction depends on. So running the suite silently replaced it with whatever the local pair
artefacts happened to say that minute (and in a fresh clone with no scored pairs, with an empty one). It was found by
noticing an unexplained `M data/priors/fringe.json` in `git status` after a green test run.
"""
import json, os, shutil, subprocess, sys, tempfile
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PRIORS = os.path.join(ROOT, "data/priors")


def test_fit_fringe_writes_where_it_is_told_and_nowhere_else():
    before = {f: (os.path.getmtime(os.path.join(PRIORS, f)), open(os.path.join(PRIORS, f), "rb").read())
              for f in os.listdir(PRIORS) if f.endswith(".json")}
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/fit_fringe.py"), "--out-dir", td],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        assert os.path.exists(os.path.join(td, "fringe.json")), "nothing was written to --out-dir"
    after = {f: (os.path.getmtime(os.path.join(PRIORS, f)), open(os.path.join(PRIORS, f), "rb").read())
             for f in os.listdir(PRIORS) if f.endswith(".json")}
    changed = [f for f in before if f not in after or after[f][1] != before[f][1]]
    rewritten = [f for f in before if f in after and after[f][0] != before[f][0]]
    assert not changed, f"--out-dir was given and the tracked prior changed anyway: {changed}"
    assert not rewritten, f"--out-dir was given and these tracked files were rewritten: {rewritten}"


def test_the_prior_the_repo_ships_is_valid_json_with_its_provenance_fields():
    """Whatever regenerates it, the committed prior must still be the thing predict.py reads."""
    pr = json.load(open(os.path.join(PRIORS, "fringe.json")))
    for k in ("n", "insufficient", "pairs"):
        assert k in pr, f"the committed prior has no '{k}'"
    assert isinstance(pr["pairs"], list)

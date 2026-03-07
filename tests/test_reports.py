import subprocess, sys, os, json
ROOT = os.path.join(os.path.dirname(__file__), "..")
def test_report_and_prior_scripts_run():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/report_pairs.py")], capture_output=True, text=True); assert r.returncode == 0 and "# pairs:" in r.stdout
    # --out-dir, not the tracked path: this test used to rewrite data/priors/fringe.json as a side effect, so
    # running the suite silently replaced the prior every prediction depends on with whatever the local pair
    # artefacts happened to say (and in a fresh clone, with an empty one).
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/fit_fringe.py"), "--out-dir", td],
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stdout + r.stderr
        pr = json.load(open(os.path.join(td, "fringe.json"))); assert "n" in pr and "insufficient" in pr

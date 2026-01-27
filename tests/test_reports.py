import subprocess, sys, os, json
ROOT = os.path.join(os.path.dirname(__file__), "..")
def test_report_and_prior_scripts_run():
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/report_pairs.py")], capture_output=True, text=True); assert r.returncode == 0 and "# pairs:" in r.stdout
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/fit_fringe.py")], capture_output=True, text=True); assert r.returncode == 0
    pr = json.load(open(os.path.join(ROOT, "data/priors/fringe.json"))); assert "n" in pr and "insufficient" in pr

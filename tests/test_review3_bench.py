"""Review 3: bench.py baseline handling."""
import os, sys, json, subprocess, shutil
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def make_root(tmp, pairs):
    r = os.path.join(tmp, "root"); os.makedirs(os.path.join(r, "tools")); os.makedirs(os.path.join(r, "data/priors")); os.makedirs(os.path.join(r, "experiments/pairs"))
    shutil.copy(os.path.join(ROOT, "tools/bench.py"), os.path.join(r, "tools/bench.py")); open(os.path.join(r, "data/priors/exclude.txt"), "w").write("")
    for pid, m in pairs.items():
        d = os.path.join(r, "experiments/pairs", pid, "cmp_median"); os.makedirs(d); open(os.path.join(r, "experiments/pairs", pid, "NOTE.md"), "w").write("# PAIR — auto pipeline\n")
        json.dump({"rows": [dict(system="prediction", **m)]}, open(os.path.join(d, "metrics.json"), "w"))
    return r

def bench(r, *args): return subprocess.run([sys.executable, os.path.join(r, "tools/bench.py"), *args], capture_output=True, text=True)

def test_freeze_with_no_pairs_writes_an_empty_baseline_that_passes_everything(tmp_path):
    # bench.py:16-17 -- `--freeze` has no guard: an empty run (all pairs rejected / wrong PAIRS_OUT) freezes `{}`,
    # after which any regression passes (exit 0) because nothing is tracked. The gate is silently disabled.
    r = make_root(str(tmp_path), {}); assert bench(r, "--freeze").returncode == 0
    r2 = os.path.join(r, "experiments/pairs", "p1", "cmp_median"); os.makedirs(r2); open(os.path.join(r, "experiments/pairs/p1/NOTE.md"), "w").write("# PAIR\n")
    json.dump({"rows": [dict(system="prediction", sil_iou_vs_real=0.1, hem_chamfer=500.0, fringe_iou_vs_real=0.0)]}, open(os.path.join(r2, "metrics.json"), "w"))
    p = bench(r); assert p.returncode != 0, ("terrible metrics pass against an empty baseline:", p.stdout)

def test_freeze_over_a_worse_run_is_accepted_silently(tmp_path):
    # bench.py:16 -- refreezing when the current run REGRESSES vs the existing baseline succeeds with no warning/exit code.
    good = {"p1": dict(sil_iou_vs_real=0.9, hem_chamfer=5.0, fringe_iou_vs_real=0.5)}
    r = make_root(str(tmp_path), good); assert bench(r, "--freeze").returncode == 0
    json.dump({"rows": [dict(system="prediction", sil_iou_vs_real=0.5, hem_chamfer=50.0, fringe_iou_vs_real=0.1)]}, open(os.path.join(r, "experiments/pairs/p1/cmp_median/metrics.json"), "w"))
    p = bench(r, "--freeze")
    assert p.returncode != 0 or "REGRESSION" in p.stdout or "regress" in p.stdout.lower(), p.stdout

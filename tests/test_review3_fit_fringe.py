"""Review 3: fit_fringe.py reads 'depth' from NOTE.md, which run_pair.py prints in mm when --mm-per-px is given
(run_pair.py:166 `fringe_depth_px*mmpp`), and divides it by the waist width in PX (fit_fringe.py:19,31)."""
import os, sys, json, subprocess, shutil
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def make_root(tmp):
    r = os.path.join(tmp, "root"); os.makedirs(os.path.join(r, "tools")); os.makedirs(os.path.join(r, "data/external")); os.makedirs(os.path.join(r, "experiments/pairs"))
    shutil.copy(os.path.join(ROOT, "tools/fit_fringe.py"), os.path.join(r, "tools/fit_fringe.py")); open(os.path.join(r, "data/external/pairs.jsonl"), "w").write("")
    return r

def pair(r, pid, depth_str, scale):
    d = os.path.join(r, "experiments/pairs", pid); os.makedirs(d)
    open(os.path.join(d, "NOTE.md"), "w").write(f"# PAIR — auto pipeline\n\nflags: none\nbefore: x_before.jpg\nafter: x_after_wash.jpg\nscale: {scale}\n"
                                              f"hem fit: left: angle 0.0°, depth {depth_str}, right: angle 0.0°, depth {depth_str}\n")
    json.dump({"before_used": {"waist_left": (100, 10), "waist_right": (300, 10)}}, open(os.path.join(d, "landmarks.json"), "w"))

def test_depth_in_mm_is_divided_by_waist_in_px(tmp_path):
    r = make_root(str(tmp_path))
    pair(r, "px_pair", "40", "UNKNOWN (1.0 placeholder; mm values are px)")     # 40 px fringe, waist 200 px
    pair(r, "mm_pair", "40 px", "given")                                       # SAME geometry; NOTE now prints px even when a scale is given
    p = subprocess.run([sys.executable, os.path.join(r, "tools/fit_fringe.py")], capture_output=True, text=True); assert p.returncode == 0, p.stderr
    pr = json.load(open(os.path.join(r, "data/priors/fringe.json"))); rel = {x["pair"]: x["depth_rel"] for x in pr["pairs"]}
    assert abs(rel["px_pair"] - rel["mm_pair"]) < 1e-9, rel                    # identical garments must give identical depth/waist

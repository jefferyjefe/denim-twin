"""Review 3: run_pairs_batch.py argument plumbing (stubbed run_pair.py / scale_from_coin.py record their argv)."""
import os, sys, json, subprocess, shutil, hashlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STUB_RUN = "import sys, json, os\nargs = sys.argv[1:]; od = args[args.index('--out') + 1]; os.makedirs(od, exist_ok=True)\njson.dump(args, open(os.path.join(od, 'argv.json'), 'w'))\n"
STUB_COIN = "import sys, json, os\njson.dump(sys.argv[1:], open(os.environ['COIN_ARGV'], 'w')); print(json.dumps({'mm_per_px': 1.73, 'confidence': 0.375}))\n"

def make_root(tmp, scale_ref="none", scale_detail="", crop=None):
    r = os.path.join(tmp, "root")
    for d in ("tools", "data/external/pair_images", "data/priors"): os.makedirs(os.path.join(r, d))
    os.symlink(os.path.join(ROOT, "src"), os.path.join(r, "src"))
    shutil.copy(os.path.join(ROOT, "tools/run_pairs_batch.py"), os.path.join(r, "tools/run_pairs_batch.py"))
    open(os.path.join(r, "tools/run_pair.py"), "w").write(STUB_RUN); open(os.path.join(r, "tools/scale_from_coin.py"), "w").write(STUB_COIN)
    url = "https://example.org/p"; pid = hashlib.sha1(url.encode()).hexdigest()[:10]
    ims = [{"url": "https://example.org/b.jpg", "role": "before"}, {"url": "https://example.org/a.jpg", "role": "after_cut"}]
    if crop: ims[0]["crop"] = crop
    files = []
    import numpy as np, cv2
    for im in ims:
        f = f"{pid}_{im['role']}_{hashlib.sha1(im['url'].encode()).hexdigest()[:8]}.jpg"; files.append(f)
        cv2.imwrite(os.path.join(r, "data/external/pair_images", f), np.full((300, 200, 3), 180, np.uint8))
    open(os.path.join(r, "data/external/pairs.jsonl"), "w").write(json.dumps({"page_url": url, "images": ims, "scale_ref": scale_ref, "scale_detail": scale_detail}) + "\n")
    open(os.path.join(r, "data/external/pairs_validation.jsonl"), "w").write(json.dumps({"page_url": url, "status": "usable", "title": "t",
        "images": [{"file": files[0], "role": "before", "tag": "whole_garment_flat"}, {"file": files[1], "role": "after_cut", "tag": "whole_garment_flat"}]}) + "\n")
    return r, pid

def run(r, env=None):
    e = dict(os.environ, **(env or {})); return subprocess.run([sys.executable, os.path.join(r, "tools/run_pairs_batch.py")], capture_output=True, text=True, env=e, cwd=r)

def test_state_is_only_passed_with_the_prior(tmp_path):
    # run_pairs_batch.py:44 -- `--state <kind>` is added only when PAIRS_USE_PRIOR is set. Without it run_pair.py defaults
    # to after_wash (run_pair.py:24), so an after_cut pair gets intervals.jsonl stratum=after_wash (feeds
    # calibration_audit per-stratum coverage) and modification.json wash.cycles=1 / edge_treatment=hand_frayed.
    r, pid = make_root(str(tmp_path)); p = run(r); assert p.returncode == 0, p.stderr
    argv = json.load(open(os.path.join(r, "experiments/pairs", pid, "argv.json")))
    assert "--state" in argv and argv[argv.index("--state") + 1] == "after_cut", argv

def test_coin_scale_runs_on_the_cropped_image_without_a_mask_and_accepts_weak_detections(tmp_path):
    # run_pairs_batch.py:35-41 -- scale_from_coin.py is called on the CROPPED before image (the crop may have removed the
    # coin) with no --mask (rivets/buttons on the garment are candidates) and any confidence > 0.3 is accepted silently
    # as mm_per_px. tests/review3_scale.py shows a jeans button with no coin scores 0.375.
    r, pid = make_root(str(tmp_path), scale_ref="coin", scale_detail="US quarter", crop=[0.0, 0.0, 0.5, 1.0])
    coin_argv = os.path.join(str(tmp_path), "coin_argv.json"); p = run(r, {"COIN_ARGV": coin_argv}); assert p.returncode == 0, p.stderr
    argv = json.load(open(os.path.join(r, "experiments/pairs", pid, "argv.json")))
    if os.path.exists(coin_argv):
        ca = json.load(open(coin_argv)); assert "--mask" in ca, ("coin detector run with no garment mask on", ca)
    assert "--mm-per-px" not in argv, ("confidence 0.375 accepted as metric scale:", argv)

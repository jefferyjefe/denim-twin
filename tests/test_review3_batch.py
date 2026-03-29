"""Review 3: run_pairs_batch.py argument plumbing (a stubbed run_pair.py / scale_from_coin.py record their argv).

Coin detection has MOVED out of this batch runner. It used to shell out to scale_from_coin.py itself, on the
CROPPED before image, with no --mask, and accept any confidence > 0.3 as metric scale. It now passes `--coin <key>`
down to run_pair.py, which runs the detector after segmentation with `--mask bmask.png` and takes the number only
when the detector itself says `accepted` (run_pair.py:172-178; scale_from_coin.py:36-44 does the rejecting).
The tests below follow the behaviour to where it went rather than guarding the address it left.
"""
import os, re, sys, json, subprocess, shutil, hashlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STUB_RUN = "import sys, json, os\nargs = sys.argv[1:]; od = args[args.index('--out') + 1]; os.makedirs(od, exist_ok=True)\njson.dump(args, open(os.path.join(od, 'argv.json'), 'w'))\n"
# A stub that records the fact and the argv of any scale_from_coin.py call. The batch runner must never make one.
STUB_COIN = "import sys, json, os\njson.dump(sys.argv[1:], open(os.environ['COIN_ARGV'], 'w')); print(json.dumps({'mm_per_px': 1.73, 'confidence': 0.375, 'accepted': True}))\n"

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

def test_the_batch_hands_the_coin_type_down_and_never_a_coin_derived_scale(tmp_path):
    """Retargeted. The test that stood here asserted, inside `if os.path.exists(coin_argv):`, that the batch ran the
    coin detector with a --mask. That branch can no longer be entered: `grep scale_from_coin tools/run_pairs_batch.py`
    finds nothing, so $COIN_ARGV is never written, the STUB_COIN fixture was dead, and the only surviving assertion
    (`"--mm-per-px" not in argv`) held for a runner that does no scale work at all. A conditional that cannot execute
    is not a guard.

    What the batch still owns is the plumbing: with `scale_ref: coin` and no recorded mm_per_px it must hand run_pair
    the coin TYPE and let the masked detector downstream decide, and it must not smuggle a raw number of its own.
    Where the detection itself is now guarded is the test below."""
    r, pid = make_root(str(tmp_path), scale_ref="coin", scale_detail="US quarter", crop=[0.0, 0.0, 0.5, 1.0])
    coin_argv = os.path.join(str(tmp_path), "coin_argv.json")

    # The sentinel is only evidence if it can fire, so prove the stub writes it before asserting it did not.
    probe = subprocess.run([sys.executable, os.path.join(r, "tools/scale_from_coin.py"), "x", "--coin", "us_quarter"],
                           capture_output=True, text=True, env=dict(os.environ, COIN_ARGV=coin_argv))
    assert probe.returncode == 0 and os.path.exists(coin_argv), (probe.returncode, probe.stderr)
    os.remove(coin_argv)

    p = run(r, {"COIN_ARGV": coin_argv}); assert p.returncode == 0, p.stderr
    assert not os.path.exists(coin_argv), (
        "run_pairs_batch.py ran the coin detector itself again. Detection belongs to run_pair.py, which runs it on "
        "the segmented before frame with --mask; run here it sees the whole garment, rivets and buttons included: "
        + open(coin_argv).read())

    argv = json.load(open(os.path.join(r, "experiments/pairs", pid, "argv.json")))
    assert "--mm-per-px" in argv or "--coin" in argv, ("a coin pair reached run_pair with no scale information", argv)
    assert "--mm-per-px" not in argv, ("a coin-derived scale was passed as a fact rather than left to the "
                                       "detector's own accept/reject:", argv)
    assert argv[argv.index("--coin") + 1] == "us_quarter", ("scale_detail 'US quarter' must resolve to a coin key", argv)
    # ... and on the CROPPED before image, flagged as cropped, since the crop may have removed the coin.
    assert os.path.basename(argv[argv.index("--before") + 1]) == "cropped_before.png", argv
    assert "before" in argv[argv.index("--cropped") + 1].split(","), argv


def test_the_coin_detector_refuses_the_unmasked_frame_the_batch_used_to_hand_it(tmp_path):
    """The behaviour the dead branch above was trying to guard, at the place it now lives: a bright round button on
    the garment is exactly what an unmasked detector sells as a coin, and the mask is what stops it.

    Same adversarial input as tests/test_review3_scale.py, but that test asks whether the detection is *accepted*;
    this one asks whether the --mask run_pair passes actually removes the candidate, which is the property the batch
    runner used to violate by passing no mask at all."""
    import numpy as np, cv2
    img = np.full((600, 800, 3), 185, np.uint8)
    img = np.clip(img.astype(int) + np.random.default_rng(0).integers(-6, 6, img.shape), 0, 255).astype(np.uint8)
    cv2.rectangle(img, (250, 80), (550, 520), (95, 85, 110), -1)          # the garment
    cv2.circle(img, (400, 200), 20, (215, 215, 225), -1)                  # a bright round button ON it
    cv2.circle(img, (400, 200), 20, (120, 120, 130), 2)
    gmask = np.zeros((600, 800), np.uint8); cv2.rectangle(gmask, (250, 80), (550, 520), 255, -1)
    f, mf = str(tmp_path / "button.png"), str(tmp_path / "gmask.png")
    cv2.imwrite(f, img); cv2.imwrite(mf, gmask)

    def detect(*args):
        q = subprocess.run([sys.executable, os.path.join(ROOT, "tools/scale_from_coin.py"), f, "--coin", "us_quarter", *args],
                           capture_output=True, text=True)
        return q.returncode, json.loads(q.stdout)

    # Unmasked, the button IS taken for a quarter -- this is the input that must not reach an accepting detector.
    rc, d = detect("--allow-unmasked")
    assert (rc, d["accepted"]) == (0, True) and d["mm_per_px"] > 0, d

    # Handed no mask at all -- the way run_pairs_batch.py used to call it -- it refuses instead of guessing.
    rc, d = detect()
    assert rc != 0 and d["accepted"] is False and "mask" in d["reject_reason"], d

    # Handed the garment mask -- the way run_pair.py calls it -- the button is not even a candidate.
    rc, d = detect("--mask", mf)
    assert rc != 0 and d.get("mm_per_px") is None and d.get("error"), (
        "a candidate inside the garment mask was still offered as a coin", d)

    # And that masked call is what run_pair.py makes, gated on the detector's own verdict.
    src = open(os.path.join(ROOT, "tools/run_pair.py")).read()
    call = re.search(r"scale_from_coin\.py\"[^\n]*", src)
    assert call and '"--mask"' in call.group(0), ("run_pair.py no longer masks the garment before coin detection", call)
    assert re.search(r'd_\.get\("accepted"\)[^\n]*a\.mm_per_px = ', src), \
        "run_pair.py no longer gates the coin scale on the detector's `accepted` verdict"

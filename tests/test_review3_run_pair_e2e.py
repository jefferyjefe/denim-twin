"""Review 3: run tools/run_pair.py end to end on synthetic images with SAM/CLIP stubbed out (no model load).
Each test spawns a subprocess with a sitecustomize-style stub injected via a runner script."""
import os, sys, json, subprocess, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src")); sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2, pytest
from test_canon import synthetic_jeans
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RUNNER = textwrap.dedent("""
    import sys, types, runpy, numpy as np
    def colour_mask(img): return ~((np.abs(img.astype(int) - 180) < 12).all(axis=2))
    sam = types.ModuleType("denimtwin.seg.sam")
    class SamSegmenter:
        def __init__(self, *a, **k): pass
        def segment(self, img, landmarks=None, **k): return colour_mask(img), 0.9
    sam.SamSegmenter = SamSegmenter
    sam.segment_garment_coarse = lambda seg, img, **k: (colour_mask(img), 0.9, {"area": float(colour_mask(img).mean()), "border_frac": 0.0})
    import os, cv2
    def segment_fringe(seg, img, m, **k):                       # fringe hint = the thread pixels drawn by make_pair, in the image's own frame
        h = os.environ.get("FRINGE_HINT"); f = cv2.imread(h, 0) if h else None
        return (f > 127) & m if f is not None and f.shape == m.shape else None
    sam.segment_fringe = segment_fringe
    clip = types.ModuleType("denimtwin.seg.clipgate"); clip.whole_garment_probability = lambda img: 0.5
    sys.modules["denimtwin.seg.sam"] = sam; sys.modules["denimtwin.seg.clipgate"] = clip
    sys.argv = [sys.argv[1]] + sys.argv[2:]; runpy.run_path(sys.argv[0], run_name="__main__")
""")

def make_pair(tmp, tilt_deg=0.0):
    img, mask, lm = synthetic_jeans(jitter=0); cm = CanonicalMap(lm)
    after, removed, keep = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.4), background_fill=(180, 180, 180))
    # fringe threads below the cut on the after-photo so a nonzero fringe depth is measured (colour split)
    cut_y = int(np.nonzero(removed)[0].min()); ys, xs = np.nonzero(removed)
    hint = np.zeros(mask.shape, np.uint8)
    for x in range(int(xs.min()) + 4, int(xs.max()) - 4, 6):
        col = np.nonzero(removed[:, x])[0]
        if len(col): after[col.min(): col.min() + 30, x] = (90, 50, 30); hint[col.min(): col.min() + 30, x] = 255
    cv2.imwrite(os.path.join(tmp, "fringe_hint.png"), hint)
    before = img
    if tilt_deg:
        h, w = img.shape[:2]; M = cv2.getRotationMatrix2D((w / 2, h / 2), tilt_deg, 1.0)
        before = cv2.warpAffine(img, M, (w, h), borderValue=(180, 180, 180))
    bp, ap = os.path.join(tmp, "before.png"), os.path.join(tmp, "after.png"); cv2.imwrite(bp, before); cv2.imwrite(ap, after)
    return bp, ap, lm

def run(tmp, args):
    r = open(os.path.join(tmp, "runner.py"), "w"); r.write(RUNNER); r.close()
    env = dict(os.environ, FRINGE_HINT=os.path.join(tmp, "fringe_hint.png"))
    p = subprocess.run([sys.executable, r.name, os.path.join(ROOT, "tools", "run_pair.py")] + args, capture_output=True, text=True, cwd=tmp, env=env)
    return p

def test_intervals_lo_hi_are_in_mm_while_median_is_in_px(tmp_path):
    # run_pair.py:184 -- without --prior, lo/hi = depth_mm*0.5 / depth_mm*1.5 but 'median' and 'real' are depth_px.
    # With --mm-per-px 0.5 the interval [0.25*d, 0.75*d] no longer contains its own median (metric says fringe_depth_px).
    tmp = str(tmp_path); bp, ap, lm = make_pair(tmp)
    p = run(tmp, ["--before", bp, "--after", ap, "--out", os.path.join(tmp, "out"), "--mm-per-px", "0.5"])
    assert p.returncode == 0, p.stdout[-2000:] + p.stderr[-2000:]
    iv = json.loads(open(os.path.join(tmp, "out", "intervals.jsonl")).readline())
    assert iv["median"] > 5, ("test premise: a fringe depth must have been measured", iv)
    assert iv["lo"] <= iv["median"] <= iv["hi"], iv

def test_manual_landmarks_are_not_transformed_into_the_uprighted_frame(tmp_path):
    # run_pair.py:56-71,102 -- images are rotated to upright (and collage-split) AFTER the manual --before-lm JSON was
    # annotated on the ORIGINAL photo; the landmarks are used and written (before_lm.json, fed to compare.py) unchanged.
    tmp = str(tmp_path); bp, ap, lm = make_pair(tmp, tilt_deg=20.0)
    # landmarks of the tilted photo, in ITS frame (what annotate_landmarks.py would produce)
    h, w = 900, 600; M = cv2.getRotationMatrix2D((w / 2, h / 2), 20.0, 1.0)
    lm_t = {n: [float(v) for v in (M @ np.array([x, y, 1.0]))] for n, (x, y) in lm.items()}
    json.dump({"landmarks": lm_t}, open(os.path.join(tmp, "blm.json"), "w"))
    ctrl = run(tmp, ["--before", bp, "--after", ap, "--out", os.path.join(tmp, "ctrl")])
    assert ctrl.returncode == 0, ("control (auto landmarks) must pass", ctrl.stdout[-1500:])
    p = run(tmp, ["--before", bp, "--after", ap, "--out", os.path.join(tmp, "out"), "--before-lm", os.path.join(tmp, "blm.json")])
    assert p.returncode == 0, ("correct manual landmarks (original frame) make the run fail: " + p.stdout[-600:])
    assert any("rotated" in f for f in open(os.path.join(tmp, "out", "NOTE.md")).read().splitlines()[2:3]), "test premise: upright must have rotated"
    used = json.load(open(os.path.join(tmp, "out", "before_lm.json")))["landmarks"]
    bmask = cv2.imread(os.path.join(tmp, "out", "bmask.png"), 0) > 127
    for n in ("waist_left", "hem_left_outer", "hem_right_outer"):
        x, y = used[n]; assert bmask[int(y), int(x)], f"{n} at {used[n]} is outside the (rotated) garment mask"

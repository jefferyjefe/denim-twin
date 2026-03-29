"""Regression tests from the 2026-08-28 adversarial review (each originally demonstrated a bug)."""
import sys, os, json, subprocess
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2, pytest
from denimtwin.eval import identity as I
from denimtwin.canon.warp import CanonicalMap
from denimtwin.canon.landmarks import CANONICAL, LANDMARKS
from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
from denimtwin.capture.quality import check_image
from test_canon import synthetic_jeans

ROOT = os.path.join(os.path.dirname(__file__), "..")

def test_delta_e_is_cie76_not_opencv_uint8_lab():
    # identity.py:23-25 -- cvtColor on uint8 gives L in [0,255], a/b offset 128. CIE76 white->black is 100.
    w = np.full((4, 4, 3), 255, np.uint8); k = np.zeros((4, 4, 3), np.uint8)
    assert abs(I.unchanged_color_delta_e(w, k, np.ones((4, 4), bool)) - 100.0) < 1.0

def test_warp_identity_landmarks_is_identity():
    # warp.py:31-36 -- coarse grid spans [0, W+step] but is resized onto [0, W): ~0.8% scale + ~2.5px offset.
    W, H = 1000, 1500
    lm = {n: (CANONICAL[n][0] * W, CANONICAL[n][1] * H) for n in LANDMARKS}
    cm = CanonicalMap(lm, (W, H))
    img = np.zeros((H, W, 3), np.uint8)
    img[1400:1403] = 255                      # a stripe near the hem
    out = cm.image_to_canon(img)
    ys = np.nonzero(out[:, 50, 0] > 127)[0]
    assert abs(ys.mean() - 1401.0) < 1.0     # observed: ~1393

def test_ssim_does_not_leak_cut_region_into_keep_region():
    # identity.py:11-18 -- SSIM windows straddling the keep boundary see the modified region.
    rng = np.random.default_rng(1)
    img = rng.integers(0, 255, (64, 64, 3), np.uint8)
    keep = np.ones((64, 64), bool); keep[20:44, 20:44] = False   # non-rectangular keep (hole)
    pred = img.copy(); pred[~keep] = 0                            # only the cut region touched
    assert I.unchanged_ssim(pred, img, keep) > 0.999              # observed: 0.95

@pytest.mark.needs("external_images")
def test_feature_retention_penalises_translation():
    # identity.py:35-46 -- ratio-test matches are never checked for spatial consistency;
    # a prediction shifted 40 px still 'retains' ~80% of features.
    # The harvested set is gitignored, so this was pytest.skip("harvested image not present").
    # Declared as a prerequisite instead; a named file that is missing while the set IS present is a
    # broken checkout, not absent evidence, so that case now fails rather than opting out.
    real = cv2.imread(os.path.join(ROOT, "data/external/images/commons_c2024708ca53.jpg"))
    assert real is not None, ("data/external/images is present but commons_c2024708ca53.jpg is not; "
                              "re-run the harvest or update this test's subject")
    real = cv2.resize(real, (800, int(800 * real.shape[0] / real.shape[1])))
    shifted = np.roll(real, 40, axis=1)
    assert I.feature_retention(shifted, real, np.ones(real.shape[:2], bool)) < 0.2

def test_cut_removes_garment_pixels_below_hem_landmarks():
    # cut2d.py:17-18 / landmarks.py hem y=0.98 -- garment pixels that map outside the 1000x1500
    # canonical raster (only 2% margin below the hem) get BORDER_CONSTANT=0 -> never removed.
    img, mask, lm = synthetic_jeans(jitter=0)
    ylo = int(lm["hem_left_outer"][1]); cols = np.nonzero(mask[ylo - 1])[0]
    img[ylo:ylo + 40, cols] = (90, 50, 30); mask[ylo:ylo + 40, cols] = True   # true hem 40 px below the clicks
    cm = CanonicalMap(lm)
    _, removed, _ = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=0.35))
    assert removed[ylo + 31:].sum() == mask[ylo + 31:].sum()   # observed: 0 of 2151 removed

def test_quality_detects_light_wash_on_light_background(tmp_path):
    # quality.py:51 -- foreground = |gray - bg| > 40. Both registered garments are 'light' wash.
    im = np.full((1000, 1000), 200, np.uint8); cv2.rectangle(im, (200, 100), (800, 900), 170, -1)
    im = np.clip(im + np.random.default_rng(0).normal(0, 6, im.shape), 0, 255).astype(np.uint8)
    p = tmp_path / "light.png"; cv2.imwrite(str(p), im)
    r = check_image(str(p))
    assert r.foreground_fraction > 0.3, r.reasons   # observed: 0.0 -> 'foreground too small'

def _check_capture(cwd, *args):
    """Run tools/check_capture.py --json and return (returncode, stdout, [report dicts]).

    The tool's contract: one JSON report per image on stdout, exit 1 iff some image was judged
    unusable and 0 otherwise. Any other exit -- or an empty stdout -- means it crashed.
    """
    res = subprocess.run([sys.executable, os.path.join(ROOT, "tools/check_capture.py"), "--json", *args],
                         cwd=str(cwd), capture_output=True, text=True)
    assert "Traceback" not in res.stderr, f"check_capture.py crashed (rc={res.returncode}):\n{res.stderr[-2000:]}"
    assert res.returncode in (0, 1), f"unexpected exit {res.returncode}:\n{res.stderr[-2000:]}"
    reports = [json.loads(l) for l in res.stdout.splitlines() if l.strip()]
    assert reports, f"no report on stdout (rc={res.returncode}):\n{res.stderr[-2000:]}"
    return res.returncode, res.stdout, reports


def test_check_capture_runs_from_any_cwd(tmp_path):
    # check_capture.py:3-12 -- the default --board was relative to the cwd, not to the repo, so the tool
    # could only find protocol/charuco_board.json when it happened to be run from the repository root.
    # The original guard here asserted only `"FileNotFoundError" not in res.stderr`, which a tool that
    # dies of `NameError: name 'os' is not defined` before parsing a single argument also satisfies --
    # and that is exactly what the tool did (line 4 called __import__("os") without binding the name).
    # So this now asserts the exit status and the tool's actual output.
    board_png = os.path.join(ROOT, "protocol/charuco_board.png")

    # (1) The board image really is a board, and the tool finds the board SPEC through its default,
    #     from a directory that contains nothing. 70 corners are detectable in that render.
    rc, out, [rep] = _check_capture(tmp_path, board_png)
    assert rep["board_corners"] >= 12, ("the default --board did not resolve from a foreign cwd", rep)
    assert rep["mm_per_px"] and rep["mm_per_px"] > 0, ("no scale recovered from the board", rep)
    # It is a bare board on white, not a garment capture, so the tool is expected to reject it -- with
    # its documented exit 1 and a stated reason, not with a stack trace.
    assert rc == 1 and rep["ok"] is False and rep["reasons"], rep

    # (2) cwd-independence proper: the same invocation from the repo root gives the same verdict.
    #     Compared as text because the report carries NaNs, which never compare equal to themselves.
    assert _check_capture(ROOT, board_png)[:2] == (rc, out)

    # (3) The exit status carries information: a capture that passes every check exits 0. Without this
    #     the checks above would also hold for a tool that always failed every image.
    good = tmp_path / "good.png"
    im = np.full((1200, 900, 3), 230, np.uint8)
    im[150:1050, 200:700] = np.random.default_rng(0).integers(60, 190, (900, 500, 3)).astype(np.uint8)
    cv2.imwrite(str(good), im)
    rc2, _, [ok_rep] = _check_capture(tmp_path, "--no-board", "good.png")
    assert (rc2, ok_rep["ok"], ok_rep["reasons"]) == (0, True, []), ok_rep

@pytest.mark.needs("network")
def test_openverse_query_returns_results():
    # harvest_images.py:30 -- page_size=50 is rejected (401) for anonymous requests; every Openverse
    # call fails, the error is swallowed as a warning, manifest has 0 openverse records.
    #
    # This is a LIVE call to api.openverse.org, and until it was marked it made one on every run of
    # the deterministic suite -- so the suite's result depended on a third party's uptime and rate
    # limiter, and a green CI run had quietly reached the internet. It is a real integration check
    # and worth keeping; it is not a unit test, and it now says so. Run it with
    # DENIMTWIN_ALLOW_NETWORK=1 pytest tests/test_review_fixes.py -k openverse
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import harvest_images as H
    try:
        recs = list(H.openverse("denim jeans"))
    except Exception as e:
        if "429" in str(e) or "urlopen" in str(e).lower() or "timed out" in str(e).lower():
            pytest.skip(f"openverse unavailable: {e}")
        pytest.fail(f"openverse() raised: {e}")
    assert len(recs) > 0


def test_inseam_fraction_is_canonical_not_image_space():
    """EXP_0014 finding 1: `modification.inseam_fraction` is documented as a canonical coordinate; run_pair used to
    measure it in image y between the crotch and hem landmarks, which differs by up to 0.21 of the leg."""
    import numpy as np
    from denimtwin.canon.warp import CanonicalMap
    from denimtwin.canon.landmarks import inseam_fraction_to_canonical_y
    from denimtwin.canon.cut2d import cut_mask_canon, apply_cut
    from test_canon import synthetic_jeans
    img, mask, lm = synthetic_jeans(jitter=4, seed=3)
    cm = CanonicalMap(lm)
    for want in (0.2, 0.5, 0.8):
        _, removed, _ = apply_cut(img, mask, cm, cut_mask_canon((cm.W, cm.H), inseam_fraction=want))
        pts = np.array([(x, np.nonzero(removed[:, x])[0].min()) for x in range(removed.shape[1]) if removed[:, x].any()], np.float32)
        cy = cm.points_to_canon(pts)[:, 1] / cm.H
        y0, y1 = inseam_fraction_to_canonical_y(0.0), inseam_fraction_to_canonical_y(1.0)
        got = float(np.clip((float(np.median(cy)) - y0) / (y1 - y0), 0, 1))
        assert abs(got - want) < 0.02, (want, got)      # the recorded number round-trips to the requested cut

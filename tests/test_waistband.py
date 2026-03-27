"""The top-edge rule moved out of autolm into canon/waistband.py, and must still be the same rule.

Every test here compares the two implementations on REAL masks, and every real mask in this
repository is gitignored -- it is traced from an all-rights-reserved photograph. Without them these
tests used to fail with "assert 0 >= 7", which reads as a broken refactor and is nothing of the
kind. They now declare the evidence they need, so a checkout without it reports UNAVAILABLE and a
--profile full run refuses to pass at all. The thresholds themselves are untouched: they are what
makes the comparison meaningful, and a run that has the masks must still clear them.

EXP_0041 needed the garment's top edge as a registration correspondence. `autolm` already computed
it, inline, to place the waist landmarks; copying the rule would have left two versions to drift, so
it moved to `canon/waistband.py` and `autolm` calls it. Nothing about the landmarks may change as a
result -- these tests are what says so.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import glob, json
import numpy as np
import cv2
import pytest

from denimtwin.canon.autolm import landmarks_from_mask
from denimtwin.canon.waistband import clean_mask, top_edge_row, waistband_corners, NAMES

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _reference_top(mask):
    """The rule exactly as autolm carried it before the move, transcribed from git history.

    A test that only called the new function would pass whatever the new function did. This is the
    old code, kept so the two implementations can be compared on real data."""
    m0 = np.asarray(mask).astype(bool)
    k = max(int(0.03 * m0.shape[1]), 3)
    m = cv2.morphologyEx(m0.astype(np.uint8), cv2.MORPH_OPEN, np.ones((k, k), np.uint8)).astype(bool)
    if m.sum() < 0.5 * m0.sum():
        m = m0
    ys = np.nonzero(m)[0] if m.ndim == 1 else np.nonzero(m.any(axis=1))[0]
    widths = m.sum(axis=1)
    bot, y0 = int(ys.max()), int(ys.min())
    n30 = max(int(0.30 * (bot - y0)), 3)
    top30 = widths[y0: y0 + n30].astype(int)
    wref = top30.max()
    prev = np.concatenate([[0], top30[:-1]])
    jumps = np.nonzero(top30 - prev >= 0.3 * wref)[0]
    if len(jumps):
        return int(y0 + jumps.max())
    return int(y0 + np.nonzero(top30 >= 0.5 * wref)[0].min())


def _accepted(d):
    """A rejected pair directory can hold artefacts from different runs beside each other -- a known,
    documented defect (`docs/BACKLOG.md`: run_pair.py writes *_used.png before the sane() gates, and
    660bef67bf and 85d48013a2 are in that state). Nothing scores them, and their landmarks do not
    describe their masks, so they cannot say anything about a refactor."""
    n = os.path.join(d, "NOTE.md")
    return not (os.path.exists(n) and "rejected" in open(n).readline())


def _took_jump_branch(m):
    """True when top_edge_row's first rule fires. A transcription of its condition, deliberately
    separate from the implementation so the measurement is not the code marking its own homework."""
    ys = np.nonzero(m.any(axis=1))[0]
    widths = m.sum(axis=1)
    bot, y0 = int(ys.max()), int(ys.min())
    top30 = widths[y0: y0 + max(int(0.30 * (bot - y0)), 3)].astype(int)
    prev = np.concatenate([[0], top30[:-1]])
    return bool(len(np.nonzero(top30 - prev >= 0.3 * top30.max())[0]))


def _pair_masks(limit=None):
    fs = [f for f in sorted(glob.glob(os.path.join(ROOT, "experiments", "pairs", "*", "?mask.png")))
          if _accepted(os.path.dirname(f))]
    return fs[:limit] if limit else fs


def _all_masks():
    """Every mask artefact in experiments/, including the pairs_* variant batches. The refactor has
    to be a no-op on all of them, not just on the seven pairs the bench scores."""
    return sorted(glob.glob(os.path.join(ROOT, "experiments", "**", "*mask*.png"), recursive=True))


@pytest.mark.needs("experiment_masks")
def test_the_moved_rule_is_the_old_rule_on_every_real_mask():
    n = 0
    for f in _all_masks():
        m = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        if m is None or not (m > 127).any():
            continue
        m = m > 127
        assert top_edge_row(clean_mask(m)) == _reference_top(m), f"top edge moved on {f}"
        n += 1
    assert n > 3000, f"only {n} masks compared; this test is meant to cover the whole of experiments/"


@pytest.mark.needs("experiment_masks")
def test_the_fallback_branch_is_the_one_that_actually_runs():
    """EXP_0040 and the first draft of EXP_0041 both described the width-jump rule as *the* top-edge
    detector. It fires on a small minority of real masks; the half-width fallback does the work.
    Measured here rather than restated, so the claim cannot go stale in prose."""
    jump = fallback = 0
    for f in _all_masks():
        m = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        if m is None or not (m > 127).any():
            continue
        if _took_jump_branch(clean_mask(m > 127)):
            jump += 1
        else:
            fallback += 1
    assert jump + fallback > 3000
    assert fallback > 5 * jump, (
        f"the width-jump rule now fires on {jump} of {jump + fallback} masks. It used to be the "
        "minority path, and canon/waistband.py's docstring says so -- update it.")


def test_run_pair_uses_the_shared_cleaning_rule():
    """The acceptance gate in run_pair.sane() and the landmarks in autolm must clean the mask the
    same way, or a pair is admitted under one cleaning and measured under another."""
    src = open(os.path.join(ROOT, "tools", "run_pair.py")).read()
    assert "from denimtwin.canon.waistband import clean_mask" in src
    assert "mo = clean_mask(mask)" in src
    assert "MORPH_OPEN" not in src, "run_pair.py has its own copy of the cleaning rule again"


def test_the_moved_rule_is_the_old_rule_on_random_masks():
    """Synthetic rectangles-plus-noise all take the JUMP branch (a rectangle's first row is already
    full width), which is the branch real masks almost never take -- so this covers the half of the
    rule the mask corpus does not. `test_the_moved_rule_is_the_old_rule_on_every_real_mask` covers
    the other half on 3000+ real masks, and the two together exercise both."""
    rng = np.random.default_rng(0)
    checked = 0
    for _ in range(300):
        H, W = int(rng.integers(40, 200)), int(rng.integers(40, 200))
        m = np.zeros((H, W), bool)
        y0, y1 = sorted(rng.integers(0, H, 2))
        x0, x1 = sorted(rng.integers(0, W, 2))
        m[y0:y1 + 1, x0:x1 + 1] = True
        m |= rng.random((H, W)) < 0.02
        if not m.any():
            continue
        assert top_edge_row(clean_mask(m)) == _reference_top(m)
        checked += 1
    assert checked > 200, "the generator produced too few usable masks to make this meaningful"


@pytest.mark.needs("pair_masks")
def test_autolm_landmarks_are_unchanged_by_the_move():
    """The point of the move: `landmarks_from_mask` must still return what it returned."""
    n = 0
    for d in sorted(glob.glob(os.path.join(ROOT, "experiments", "pairs", "*"))):
        lm, mask = os.path.join(d, "after_lm.json"), os.path.join(d, "amask.png")
        if not (os.path.exists(lm) and os.path.exists(mask)) or not _accepted(d):
            continue
        n += 1
        # the AFTER mask is the one the pipeline never re-segments, so its stored landmarks are
        # exactly what autolm produced from the stored mask (EXP_0041 measured the before photo's
        # coarse-vs-refined disagreement separately: 0 px on every after photo, up to 31 px before)
        rec, _ = landmarks_from_mask(cv2.imread(mask, cv2.IMREAD_GRAYSCALE) > 127)
        stored = json.load(open(lm))["landmarks"]
        for k, v in stored.items():
            if k in rec:
                assert tuple(rec[k]) == tuple(int(x) for x in v), f"{os.path.basename(d)} {k} moved"
    assert n >= 7, f"only {n} accepted pairs exercised this"


@pytest.mark.needs("pair_masks")
def test_waistband_corners_sit_on_the_top_edge_and_span_the_garment():
    """Alone among the tests in this file, this one used to prove nothing at all.

    `_pair_masks()` globs gitignored artefacts, every assertion here lives inside the loop over it,
    and there was no count afterwards -- so on a checkout without the masks the body executed zero
    times and the test reported PASSED. Its three siblings already got this right (`assert n > 3000`,
    `assert n >= 7`); it now does the same, so absent masks say UNAVAILABLE and a run that HAS them
    has to show it checked at least the seven-pair bench. No threshold below changed."""
    n = 0
    for f in _pair_masks():
        m = cv2.imread(f, cv2.IMREAD_GRAYSCALE) > 127
        if not m.any():
            continue
        c = waistband_corners(m)
        assert c is not None and set(c) == set(NAMES)
        cm = clean_mask(m)
        top = top_edge_row(cm)
        ys = {p[1] for p in c.values()}
        assert len(ys) == 1 and top <= ys.pop() <= top + 10, f"corners left the top edge on {f}"
        assert c["waistband_left"][0] < c["waistband_center"][0] < c["waistband_right"][0]
        n += 1
    assert n >= 7, f"only {n} masks exercised this"


def test_waistband_corners_refuses_an_empty_mask():
    assert waistband_corners(np.zeros((20, 20), bool)) is None


@pytest.mark.needs("pair_masks")
def test_the_corners_are_above_the_waist_landmarks_they_would_join():
    """The whole premise of EXP_0041: the new correspondence is outside the existing hull."""
    n = 0
    for f in _pair_masks():
        m = cv2.imread(f, cv2.IMREAD_GRAYSCALE) > 127
        if not m.any():
            continue
        lm, _ = landmarks_from_mask(m)
        c = waistband_corners(m)
        if "waist_left" not in lm or c is None:
            continue
        assert c["waistband_left"][1] <= lm["waist_left"][1], f"top edge is below the waist on {f}"
        n += 1
    assert n >= 7, f"only {n} masks exercised this"

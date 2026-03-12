"""Every ACCEPTED pair directory must be internally consistent (EXP_0032).

run_pair.py writes before_used.png/after_used.png BEFORE the sane() gates that can FAIL the pair,
so a directory re-run and then rejected keeps fresh _used images beside stale masks and
predictions from an earlier accepted run. Two directories are in exactly that state
(660bef67bf, 85d48013a2); both are marked rejected and nothing scores them.

This guards the case that would actually hurt: an ACCEPTED directory whose artefacts disagree,
which would silently pair a photo with a mask of a different photo.
"""
import glob, os
import cv2
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
PAIRS = os.path.join(ROOT, "experiments", "pairs")
GROUPS = [("before_used.png", "bmask.png"), ("after_used.png", "amask.png"),
          ("before_used.png", "keep_mask.png"), ("before_used.png", "removed_mask.png"),
          ("before_used.png", "pred_median.png"), ("before_used.png", "pred_median_mask.png"),
          ("before_used.png", "real.png"), ("before_used.png", "real_mask.png")]


def _accepted():
    out = []
    for d in sorted(glob.glob(os.path.join(PAIRS, "*"))):
        note = os.path.join(d, "NOTE.md")
        if not os.path.isdir(d) or not os.path.exists(note):
            continue
        with open(note) as f:
            if "rejected" in f.readline():
                continue
        out.append(d)
    return out


@pytest.mark.skipif(not glob.glob(os.path.join(PAIRS, "*", "NOTE.md")),
                    reason="pair artefacts are untracked (copyrighted source images)")
@pytest.mark.parametrize("d", _accepted() or [None], ids=lambda d: os.path.basename(d) if d else "none")
def test_accepted_pair_dir_artefacts_have_matching_shapes(d):
    if d is None:
        pytest.skip("no accepted pair directories present")
    bad = []
    for a, b in GROUPS:
        pa, pb = os.path.join(d, a), os.path.join(d, b)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            continue
        ia = cv2.imread(pa, cv2.IMREAD_GRAYSCALE)
        ib = cv2.imread(pb, cv2.IMREAD_GRAYSCALE)
        if ia is None or ib is None:
            continue
        if ia.shape != ib.shape:
            bad.append(f"{a}{ia.shape} != {b}{ib.shape}")
    assert not bad, f"{os.path.basename(d)} artefacts disagree: " + "; ".join(bad)


def test_score_predict_still_skips_rejected_pairs():
    """The only reason the two inconsistent directories are harmless. If this filter is ever
    removed, a rejected garment's stale artefacts enter the bench."""
    src = open(os.path.join(ROOT, "tools", "score_predict.py")).read()
    assert 'if "rejected" in open(f"{src}/NOTE.md").readline(): continue' in src

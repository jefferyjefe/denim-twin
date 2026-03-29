"""Every ACCEPTED pair directory must be internally consistent (EXP_0032).

run_pair.py writes before_used.png/after_used.png BEFORE the sane() gates that can FAIL the pair,
so a directory re-run and then rejected keeps fresh _used images beside stale masks and
predictions from an earlier accepted run. Two directories are in exactly that state
(660bef67bf, 85d48013a2); both are marked rejected and nothing scores them.

This guards the case that would actually hurt: an ACCEPTED directory whose artefacts disagree,
which would silently pair a photo with a mask of a different photo.

WHAT THIS USED TO PROVE: nothing, on any checkout that had not run the batch. The skipif below
tested for `experiments/pairs/*/NOTE.md`, which is COMMITTED, while every artefact it stands proxy
for (before_used.png, bmask.png, after_used.png, amask.png, keep_mask.png, removed_mask.png,
pred_median.png, pred_median_mask.png, real.png, real_mask.png) is gitignored -- they are traced
from all-rights-reserved photographs. So the guard never fired, `if not (exists(pa) and exists(pb)):
continue` dropped all eight groups, `bad` stayed empty, and `assert not bad` reported PASSED having
opened zero images. Two further `if ia is None or ib is None: continue` widened the hole in the
other direction: a png that was PRESENT but corrupt -- the one defect this test could uniquely
catch -- was also waved through.

WHAT IT PROVES NOW: the artefacts are declared as a prerequisite, so a checkout without them says
UNAVAILABLE (and a --profile full run refuses to pass at all) instead of reporting a green
comparison of nothing. When they ARE here, every group is required to have been compared: the
prerequisite probe only asks whether masks exist at all, so a half-written batch would still satisfy
it -- the per-directory count below is what makes that fail loudly rather than quietly shrink the
test. And an unreadable png is now a failure, because a corrupt artefact is a defect that is
present, not evidence that is absent.
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


@pytest.mark.needs("pair_masks")
@pytest.mark.parametrize("d", _accepted() or [None], ids=lambda d: os.path.basename(d) if d else "none")
def test_accepted_pair_dir_artefacts_have_matching_shapes(d):
    # NOTE.md is committed, so an empty accepted set means the checkout is damaged, not that the
    # evidence is merely absent. That is a failure; it used to be a skip, which is how a broken
    # checkout could report green.
    assert d is not None, ("no accepted pair directory found. experiments/pairs/*/NOTE.md is "
                           "COMMITTED -- if it is missing, restore it: git checkout experiments/pairs")
    bad, checked = [], []
    for a, b in GROUPS:
        pa, pb = os.path.join(d, a), os.path.join(d, b)
        if not (os.path.exists(pa) and os.path.exists(pb)):
            continue
        ia = cv2.imread(pa, cv2.IMREAD_GRAYSCALE)
        ib = cv2.imread(pb, cv2.IMREAD_GRAYSCALE)
        # Present but unreadable is a corrupt artefact -- a real defect in this directory. It used
        # to `continue`, which turned the strongest signal this test can see into silence.
        for name, img in ((a, ia), (b, ib)):
            if img is None:
                bad.append(f"{name} is present but cv2 could not decode it")
        if ia is None or ib is None:
            continue
        checked.append((a, b))
        if ia.shape != ib.shape:
            bad.append(f"{a}{ia.shape} != {b}{ib.shape}")
    assert not bad, f"{os.path.basename(d)} artefacts disagree: " + "; ".join(bad)
    # The floor that stops this passing over an empty directory. An accepted pair carries the whole
    # artefact set; anything less is an interrupted or partly-deleted run, and the comparison this
    # test claims to have made was not made.
    missing = [f"{a}+{b}" for a, b in GROUPS if (a, b) not in checked]
    assert len(checked) == len(GROUPS), (
        f"{os.path.basename(d)} is accepted but only {len(checked)} of {len(GROUPS)} artefact pairs "
        f"could be compared; never compared: {', '.join(missing)}. An accepted directory with a "
        f"missing artefact is an incomplete run, not absent evidence -- re-run the batch for it.")


def test_score_predict_still_skips_rejected_pairs():
    """The only reason the two inconsistent directories are harmless. If this filter is ever
    removed, a rejected garment's stale artefacts enter the bench."""
    src = open(os.path.join(ROOT, "tools", "score_predict.py")).read()
    assert 'if "rejected" in open(f"{src}/NOTE.md").readline(): continue' in src

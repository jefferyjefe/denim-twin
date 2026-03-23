"""The crop-only null cannot score above zero on fringe IoU (review 7).

`fringe_iou(pred, real, keep, garment)` scores `pred & ~keep` against `real & ~keep`. The crop-only
null's predicted silhouette IS `keep` (tools/compare.py builds it that way), so its fringe set is
`keep & ~keep` = empty and its IoU is identically 0.00 regardless of the real fringe.

"The fringe render beats the null, 0.17 against 0.00" was therefore never a comparison. This pins
the property so the claim cannot come back.
"""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from denimtwin.eval.geometry import fringe_iou

ROOT = os.path.join(os.path.dirname(__file__), "..")


def test_croponly_fringe_iou_is_identically_zero():
    rng = np.random.default_rng(0)
    for _ in range(200):
        g = rng.random((60, 60)) > 0.2
        keep = g & (np.arange(60)[:, None] < rng.integers(20, 50))
        real = g & (rng.random((60, 60)) > 0.5)
        assert fringe_iou(keep, real, keep, g) == 0.0


def test_a_prediction_rendering_below_the_cut_can_score():
    """Sanity: the metric is not simply always zero -- the test above has content."""
    g = np.ones((60, 60), bool)
    keep = np.arange(60)[:, None] < 40
    real = np.arange(60)[:, None] < 50
    assert fringe_iou(g, real, keep, g) > 0


def test_report_pairs_honours_the_exclusion_list():
    """It averaged 11 pairs of which 4 are banned -- the third time this repo was caught doing
    that. The table is what the tuning rule requires attached to a commit."""
    src = open(os.path.join(ROOT, "tools", "report_pairs.py")).read()
    assert "data/priors/exclude.txt" in src
    assert "if pid in EXCLUDE and not INCLUDE_EXCLUDED" in src


def test_report_pairs_does_not_offer_croponly_as_a_baseline():
    src = open(os.path.join(ROOT, "tools", "report_pairs.py")).read()
    assert "NOT a baseline the prediction can be said to beat" in src
    assert "prediction − crop-only deltas" not in src, "the void delta is being headlined again"

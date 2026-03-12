"""canon/lmcheck: geometric consistency of a landmark set (EXP_0032)."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pytest
from denimtwin.canon.lmcheck import check_landmarks, worst_severity

GOOD = {
    "waist_left": (100, 0), "waist_right": (300, 0),
    "hip_left": (90, 100), "hip_right": (310, 100),
    "crotch": (200, 200),
    "hem_left_outer": (90, 400), "hem_left_inner": (170, 400),
    "hem_right_inner": (230, 400), "hem_right_outer": (310, 400),
}


def test_a_consistent_garment_is_clean():
    assert check_landmarks(GOOD) == []
    assert worst_severity([]) is None


def test_crotch_above_the_hips_is_inverted():
    lm = {**GOOD, "crotch": (200, 40)}          # well above hip_left's y=100
    f = check_landmarks(lm)
    assert worst_severity(f) == "inverted"
    assert any(x["why"] == "crotch above the hips" and x["severity"] == "inverted" for x in f)


def test_coincident_inner_hems_are_degenerate_not_inverted():
    """The 2b0123d732/4bfef03bd7 failure: legs photographed touching, so the two inner hem
    landmarks land a pixel apart. That is a collapsed region, not an impossible garment."""
    lm = {**GOOD, "hem_left_inner": (200, 400), "hem_right_inner": (201, 400)}
    f = check_landmarks(lm)
    assert worst_severity(f) == "degenerate"
    assert any(x["pair"] == ("hem_left_inner", "hem_right_inner") for x in f)


def test_swapped_legs_are_inverted():
    lm = {**GOOD, "hem_left_inner": (230, 400), "hem_right_inner": (170, 400)}
    assert worst_severity(check_landmarks(lm)) == "inverted"


def test_missing_landmarks_are_skipped_not_reported():
    """Shorts legitimately have no knees; absence must not read as a violation."""
    lm = {k: v for k, v in GOOD.items() if not k.startswith("hem_right")}
    assert check_landmarks(lm) == []


def test_tolerance_matches_warp_min_sep_frac():
    """What lmcheck calls degenerate is what CanonicalMap(drop_degenerate=True) would drop,
    so the two cannot drift apart silently."""
    import inspect
    from denimtwin.canon.warp import CanonicalMap
    default = inspect.signature(CanonicalMap.__init__).parameters["min_sep_frac"].default
    assert inspect.signature(check_landmarks).parameters["tol_frac"].default == default


def test_empty_and_tiny_inputs_do_not_raise():
    assert check_landmarks({}) == []
    assert check_landmarks({"crotch": (1, 1)}) == []


def test_auto_landmarks_can_never_report_an_inverted_crotch():
    """EXP_0032: autolm searches for the crotch in range(hip_y, bot), so an AUTO crotch can
    never sit above the hips. This documents that the rule is live only for manual landmarks --
    if autolm ever changes to search upward, this test should be revisited, not deleted."""
    src = open(os.path.join(os.path.dirname(__file__), "..", "src",
                            "denimtwin", "canon", "autolm.py")).read()
    assert "for y in range(yh, bot)" in src

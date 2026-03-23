"""Uprighting costs 443d1d4658 its waistband, not its hem (EXP_0040)."""
import json, os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r():
    p = os.path.join(ROOT, "reports", "upright_waistband.json")
    if not os.path.exists(p):
        pytest.skip("upright_waistband.json not generated")
    return json.load(open(p))["summary"]


def test_the_loss_is_in_the_waistband_band_not_the_hem():
    s = _r()
    d = s["band_iou_deltas_on_minus_off"]
    assert s["worst_band"] == 0, "the worst band is no longer the waistband"
    assert s["n_bands_worse_by_over_0_05"] == 1, "the loss is no longer confined to one band"
    assert abs(d[-1]) < 0.05, "the hem band moved materially; EXP_0040's framing needs revisiting"


def test_uprighting_pushes_the_waist_line_down_on_both_photos():
    """The mechanism's first checked prediction."""
    s = _r()
    assert s["waist_pct_before_on"] > s["waist_pct_before_off"]
    assert s["waist_pct_after_on"] > s["waist_pct_after_off"]


def test_the_shift_is_a_consistent_fraction_of_the_predicted_smear():
    """The mechanism's quantitative prediction: the detector fires partway through an edge smeared
    over width*sin(theta), so the same fraction should appear on two photos with different widths
    and different rotations. If these diverge, the smearing account is wrong."""
    s = _r()
    b, a = s["smear_fraction_before"], s["smear_fraction_after"]
    assert 0.3 < b < 1.0 and 0.3 < a < 1.0
    assert abs(b - a) < 0.1, f"smear fractions diverged ({b} vs {a}); the account does not hold"


def test_the_mechanism_is_recorded_as_not_generalising():
    """The cross-pair claim is FALSE and must stay marked false: r = +0.177 with the wrong sign, and
    the smallest-mismatch pair is also the worst band-0 pair. This project's recurring failure is a
    real effect published with an unchecked general mechanism."""
    s = _r()
    assert s["crosspair_generalises"] is False
    assert abs(s["crosspair_corr_mismatch_vs_band0_iou"]) < 0.4
    assert s["crosspair_smallest_mismatch_pair"] == s["crosspair_worst_band0_pair"]


def test_every_pair_is_displaced_downward():
    """The systematic finding, and the one thing n=7 can establish well: the registered after-garment
    begins BELOW the garment it is scored against on every pair, same direction, p = 0.0156. If a new
    pair breaks the run, the sign test no longer holds and EXP_0040's headline must be re-derived."""
    s = _r()
    assert s["top_offset_n_positive"] == s["top_offset_n_pairs"], "the displacement is no longer unanimous"
    assert s["top_offset_sign_test_p"] < 0.05
    assert s["top_offset_median_px"] > 0


def test_the_displacement_behaves_like_registration_error():
    s = _r()
    assert s["corr_resid_vs_abs_top_offset"] > 0.5, "residual no longer predicts the displacement"
    assert s["corr_top_offset_vs_band0_iou"] < -0.4, "displacement no longer predicts waistband IoU"


def test_the_magnitude_is_recorded_as_unexplained():
    """Two accounts for the SIZE of the effect were tested and both fail. The note must keep saying
    so -- a real measurement with an unchecked mechanism attached is this project's recurring bug."""
    s = _r()
    assert s["extrapolation_amount_explains_band0"] is False
    assert abs(s["corr_pct_above_landmark_vs_band0_iou"]) < 0.4
    note = open(os.path.join(ROOT, "experiments", "EXP_0040_upright_waistband", "NOTE.md")).read()
    assert "unexplained" in note


def test_registration_still_has_no_landmark_above_the_waist():
    """The structural claim: band 0 is outside the landmark hull because SURVIVING tops out at the
    waist. If a waistband-edge correspondence is ever added, this test should fail and EXP_0040's
    lead has been acted on."""
    from importlib import util
    src = open(os.path.join(ROOT, "src", "denimtwin", "canon", "register.py")).read()
    assert "SURVIVING = [\"waist_left\", \"waist_center\", \"waist_right\"" in src
    assert "waistband" not in src.split("SURVIVING")[1].split("]")[0]


def test_the_note_says_the_cross_pair_account_does_not_generalise():
    note = open(os.path.join(ROOT, "experiments", "EXP_0040_upright_waistband", "NOTE.md")).read()
    assert "across pairs it explains nothing" in note


def test_autolm_still_detects_the_top_by_a_width_jump():
    """The mechanism rests on this implementation detail. If autolm changes to a rotation-robust
    detector, EXP_0040's account no longer describes the code and should be re-measured."""
    src = open(os.path.join(ROOT, "src", "denimtwin", "canon", "autolm.py")).read()
    assert "jumps = np.nonzero(top30 - prev >= 0.3 * wref)[0]" in src

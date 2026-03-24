"""EXP_0041: the waistband correspondence was measured and not adopted, and EXP_0040 was corrected.

Each test names the finding it guards. The point of this file is that a change which overturns one
fails here, rather than silently leaving a NOTE describing a repository that has moved on.
"""
import json, os

ROOT = os.path.join(os.path.dirname(__file__), "..")


def _r(name="waistband_landmark"):
    p = os.path.join(ROOT, "reports", f"{name}.json")
    # deliberately not a skip: this report has a builder in tools/make_reports.py and verify.py runs
    # `--check --all`, so a missing file is a broken repository, not an absent optional artefact.
    assert os.path.exists(p), f"{name}.json is missing; run tools/make_reports.py --write --all"
    return json.load(open(p))["summary"]


def test_the_correspondence_was_not_adopted():
    src = open(os.path.join(ROOT, "src", "denimtwin", "canon", "register.py")).read()
    surviving = src.split("SURVIVING")[1].split("]")[0]
    assert "waistband" not in surviving, \
        "SURVIVING gained a waistband landmark; EXP_0041 measured that as neutral-to-worse"


def test_autolm_does_not_emit_the_waistband_corners():
    """`run_pair.py` branches on len(landmarks) >= 14 to refine the before mask. Emitting three more
    landmarks from autolm would flip that branch on pairs sitting just under it, so the measurement
    would also be a change to the thing measured."""
    src = open(os.path.join(ROOT, "src", "denimtwin", "canon", "autolm.py")).read()
    assert "waistband_left" not in src


def test_exp0040s_sign_test_does_not_survive_matched_segmentation():
    """The correction. If this ever reproduces, EXP_0040's banner has to come off."""
    matched, mixed = _r()["control_top_offset"], _r("waistband_landmark_production")["control_top_offset"]
    assert mixed["n_positive"] == 7 and mixed["sign_test_p"] < 0.05, \
        "the production configuration no longer reproduces EXP_0040; re-derive the correction"
    assert matched["n_negative"] >= 1, "no pair displaces upward any more"
    assert matched["sign_test_p"] > 0.05, \
        "the matched-segmentation sign test became significant; EXP_0040's correction needs revisiting"


def test_the_pair_that_flips_is_the_pair_with_the_provenance_gap():
    """The causal link the correction rests on. Without it the two facts are only adjacent."""
    r = json.load(open(os.path.join(ROOT, "reports", "waistband_landmark.json")))
    worst = max(r["pairs"], key=lambda p: p["landmark_provenance"]["before_max_abs_px"])
    assert worst["arms"]["control"]["top_offset_px"] <= 0, \
        "the worst-provenance pair no longer displaces the wrong way; re-derive EXP_0040's correction"


def test_the_waistband_is_not_an_unconstrained_region():
    """The reason the treatment cannot help: the correspondence is next to a landmark that exists."""
    g = _r()["gap"]
    assert g["reach_waistband_median_px"] < 0.25 * g["reach_loo_median_px"], \
        "the waistband corner is no longer close to an existing landmark; EXP_0041's account changes"


def test_the_gap_comparison_reverses_when_reach_is_matched():
    """Both orderings must be reported. Quoting only the first is the error the first draft made."""
    g = _r()["gap"]
    assert g["n_loo_gt_jackknife"] == 7, "matched-cardinality ordering changed"
    assert g["n_reach_matched_gt_loo"] == 7, "matched-reach ordering changed"
    assert g["reach_matched_median_px"] > g["loo_median_px"] > g["jackknife_median_px"]


def test_the_downward_displacement_is_mostly_arithmetic():
    """autolm places the waist landmark at 2% of EACH garment's own height, so a perfect map still
    lands the mapped corner low. The sign test is not evidence about registration."""
    g = _r()["gap"]
    assert g["corr_construction_vs_dy"] > 0.5
    assert g["construction_dy_median_px"] > 0.5 * g["median_dy_px"], \
        "the construction term stopped dominating; the sign test may mean something again"


def test_add_does_nothing_and_replace_is_worse():
    s = _r()
    assert abs(s["add"]["d_loo_common"]["sigma"]) < 1.0, \
        "the add arm now has a measurable effect on the residual; the verdict needs revisiting"
    assert s["add"]["d_loo_common"]["mean"] * s["add"]["d_loo_common_frac_h"]["mean"] < 0, \
        "the add arm's px and scale-free residuals agree in sign now; it may be a real effect"
    assert s["replace"]["d_loo_common"]["sigma"] > 1.5 and s["replace"]["d_loo_common"]["n_positive"] >= 6
    for arm in ("add", "replace"):
        assert abs(s[arm]["d_iou"]["sigma"]) < 2.0, f"{arm} now moves IoU"


def test_the_correspondence_is_real_but_redundant():
    """The null on the PRIMARY metric, not just on the IoU. A displaced point does real damage, so
    the true one carrying no benefit is redundancy rather than the measurement being blind."""
    n = _r()["null"]
    assert n["d_loo_common"]["mean"] > 5.0, "displacing the correspondence stopped hurting"
    assert n["add_minus_null_loo_common"]["n_negative"] == 7, \
        "the true correspondence no longer beats the displaced one on every pair"
    assert n["add_minus_null_loo_common"]["sigma"] < -1.5


def test_the_band0_column_is_not_usable_as_a_baseline():
    """docs/GATES.md baseline rule: the scoring target must not be derived from the artefact the
    treatment is read off. It is, on every pair, so band 0 carries no claim in either run."""
    t = _r()["scoring_target"]
    assert t["n_pred_subset_of_bmask"] == 7
    assert t["n_pred_top_equals_bmask_top"] == 7
    note = open(os.path.join(ROOT, "experiments", "EXP_0041_waistband_landmark", "NOTE.md")).read()
    assert "cannot carry a claim" in note


def test_the_provenance_gap_is_before_only_and_never_zero_everywhere():
    p = _r()["landmark_provenance"]
    assert p["after_max_px"] == 0, "the after photo is now re-segmented too; the control is not clean"
    assert p["before_max_px"] >= 1, "the coarse/refined disagreement vanished; re-derive the warning"
    assert p["n_before_nonzero"] >= 1


def test_every_scored_pair_is_present_and_none_dropped_silently():
    """The tuning rule needs >= 5 usable pairs. A pair vanishing into `skipped` would shrink the
    evidence without failing anything -- the earlier version of this assertion was a tautology."""
    s = _r()
    assert s["skipped"] == [], f"pairs dropped out: {s['skipped']}"
    assert s["n_pairs"] == 7, f"{s['n_pairs']} pairs, expected the 7 scored ones"


def test_the_note_records_how_the_experiment_went_wrong_first():
    """This project's recurring failure is publishing a comparison whose controls do not control.
    The first draft of this note did it twice; the note keeps that rather than quietly fixing it."""
    note = open(os.path.join(ROOT, "experiments", "EXP_0041_waistband_landmark", "NOTE.md")).read()
    assert "went wrong first" in note and "8× difference in reach" in note

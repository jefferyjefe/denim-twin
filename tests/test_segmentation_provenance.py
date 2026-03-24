"""EXP_0042: the before photo is segmented twice; matching the two is worth +0.03 IoU and is not adopted.

These pin the findings and, more importantly, the framing. The first version of this experiment
reported four measurements that could not support their claims, and each of those is guarded here so
it cannot come back without someone reading why it was removed.
"""
import json, os

ROOT = os.path.join(os.path.dirname(__file__), "..")
NOTE = os.path.join(ROOT, "experiments", "EXP_0042_segmentation_provenance", "NOTE.md")


def _s():
    p = os.path.join(ROOT, "reports", "segmentation_provenance.json")
    # not a skip: the report is committed. It has an EXPENSIVE builder (it re-segments with SAM), so
    # make_reports --check may skip re-deriving it, but the file itself must be here.
    assert os.path.exists(p), "segmentation_provenance.json is missing; run " \
                              "tools/experiment_segmentation_provenance.py"
    return json.load(open(p))["summary"]


def test_the_refinement_gate_is_the_denominator():
    """Two pairs are under run_pair.py's >= 14 landmark gate, so refinement never runs on them.
    Averaging them in dilutes every statistic; the first draft did exactly that."""
    g = _s()["gate"]
    assert g["n_treated"] + g["n_skipped_by_gate"] == _s()["n_pairs"]
    assert g["n_skipped_by_gate"] == 2, "the gate now skips a different number of pairs; re-derive"
    assert g["mask_identical_on_untreated"], \
        "an untreated pair's mask changed, which should be impossible -- SAM is no longer deterministic"


def test_refinement_only_ever_grows_the_mask():
    """The mechanism. If refinement starts shrinking masks, the account of why the coarse landmarks
    sit low no longer holds."""
    r = _s()["refinement_on_treated"]
    assert r["n_area_ratio_below_1"] == 0
    assert r["area_ratio_range"][0] >= 1.0


def test_the_disagreement_is_large_on_at_least_one_pair():
    r = _s()["refinement_on_treated"]
    assert r["max_displacement_over_all_pairs"] >= 40, \
        "the coarse/refined landmark gap shrank; EXP_0041's and EXP_0042's warnings need re-deriving"


def test_the_ab_ties_are_exactly_the_pairs_the_gate_skipped():
    """The mechanism check the result rests on, and it is stronger than the 1.4 sigma: where the two
    segmentations are the same object, the two arms are bit-identical runs."""
    ab = _s()["ab"]
    assert ab["available"], ab.get("why")
    assert ab["ties_are_exactly_the_untreated_pairs"], \
        f"the ties are {ab['tied_pairs']}, which is no longer the untreated set"


def test_the_ab_improves_iou_and_costs_hem():
    """Both directions, because the second is why this is not adopted."""
    ab = _s()["ab"]
    assert ab["sil_iou_vs_real"]["treated_only"]["mean"] > 0.01
    assert ab["sil_iou_vs_real"]["n_better"] > ab["sil_iou_vs_real"]["n_worse"]
    assert ab["hem_chamfer"]["treated_only"]["mean"] > 0, \
        "the hem regression vanished -- if that holds up, the case against adopting is gone and " \
        "docs/GATES.md's EXP_0022 precedent applies; re-read EXP_0042's verdict"


def test_it_is_not_adopted():
    """The flag exists and is off. Turning it on is a pipeline change under the tuning rule."""
    src = open(os.path.join(ROOT, "tools", "run_pair.py")).read()
    assert "--refit-landmarks-after-refine" in src
    assert 'p.add_argument("--refit-landmarks-after-refine", action="store_true"' in src, \
        "the flag is no longer a store_true default-off option; EXP_0042 did not support adopting it"
    assert "Not adopted" in open(NOTE).read()


def test_the_pair_directory_records_which_segmentation_its_landmarks_came_from():
    """The cheap half of the fix, which IS adopted: a pair directory can now answer the question that
    took a full re-segmentation to answer here."""
    src = open(os.path.join(ROOT, "tools", "run_pair.py")).read()
    assert '"before_landmark_source"' in src and '"before_coarse"' in src


def test_the_note_records_the_four_measurements_it_removed():
    """This project's recurring failure is publishing a comparison whose controls do not control.
    Four of them were caught here before publication; the note keeps them so they are not rebuilt."""
    note = open(NOTE).read()
    for phrase in ("fit\" metric", "loo_common", "tautological zero", "raw mask instead of"):
        assert phrase in note, f"the note no longer explains why it dropped: {phrase}"


def test_the_reason_for_the_current_behaviour_is_recorded_as_unrecoverable():
    """run_pair.py cites EXP_0004 for a claim EXP_0004 does not make. If someone adds it back to that
    note, this should fail and EXP_0042's framing should be revisited."""
    e4 = os.path.join(ROOT, "experiments", "EXP_0004_auto_pipeline_pair1", "NOTE.md")
    if os.path.exists(e4):
        t = open(e4).read().lower()
        assert "refine" not in t or "landmark" not in t.split("refine")[0][-200:], \
            "EXP_0004 now discusses refinement; EXP_0042 says its claim is not there"
    assert "not recoverable" in open(NOTE).read()

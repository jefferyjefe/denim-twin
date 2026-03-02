"""The fringe prior must never present a rule's output, or an unvalidated measurement, as evidence (review 5, #3/#6)."""
import json, os
ROOT = os.path.join(os.path.dirname(__file__), "..")
PRIOR = json.load(open(os.path.join(ROOT, "data/priors/fringe.json")))

def test_the_prior_declares_itself_unvalidated_and_insufficient_whatever_the_counts():
    assert PRIOR["validated"] is False
    assert PRIOR["insufficient"] is True, "insufficient is a validation statement, not a sample count"
    assert "not evidence" in PRIOR["measurement_method"] or PRIOR["measurement_method"].startswith("none")
    assert len(PRIOR.get("validation_note", "")) > 80

def test_every_row_shows_both_the_rule_output_and_the_raw_measurement():
    for r in PRIOR["pairs"]:
        assert "depth_px_measured" in r and "depth_rel_measured" in r, r
        if abs(r["depth_px"] - r["depth_px_measured"]) > 1e-9:
            assert r.get("rule_applied"), f"{r['pair']}: depth differs from the measurement with no rule recorded"

def test_the_published_after_cut_depths_are_visibly_rule_output():
    """Finished hems are forced to 0 and unwashed raw cuts capped: legitimate, as long as it is not called a
    measurement. Four cuffed pairs measured 1.9-4.0 px and publish 0.0."""
    ruled = [r for r in PRIOR["pairs"] if r.get("rule_applied")]
    assert ruled, "no rules applied at all — has fit_fringe stopped recording them?"
    for r in ruled:
        assert r["depth_px_measured"] >= 0.0 and r["rule_applied"]

def test_a_sourced_assumption_exists_and_carries_its_caveat():
    ad = PRIOR.get("assumed_depth")
    assert ad and ad["value_mm"] > 0 and ad["source_pair"]
    assert "arrest" in ad["caveat"].lower() or "stop" in ad["caveat"].lower()

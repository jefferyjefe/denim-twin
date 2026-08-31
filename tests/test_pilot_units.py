"""Unit tests for the pieces the scenario suite exercises only end to end."""
import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from denimtwin.pilot import cutspec as CUT      # noqa: E402
from denimtwin.pilot import hem as HEM          # noqa: E402
from denimtwin.pilot import plan as PLAN        # noqa: E402
from denimtwin.pilot import qa as QA            # noqa: E402
from denimtwin.pilot import qa_primitives as Q  # noqa: E402
from denimtwin.pilot import spec as SPEC        # noqa: E402
from denimtwin.pilot.store import Store, setup_hash, diff_planned_actual   # noqa: E402


# -- the shipped specification loads, which is what the gate enumerates from ------------------

def test_shipped_specification_loads_and_cross_checks():
    s = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    assert s.shots and s.regions and s.features
    assert not s.cross_check()


def test_specification_refuses_an_unknown_feature_key(tmp_path):
    src = ROOT / "protocol" / "shotplan"
    for f in ("shotplan.schema.json", "regions.schema.json", "regions.json"):
        (tmp_path / f).write_text((src / f).read_text())
    doc = json.loads((src / "shotplan.json").read_text())
    doc["shots"][0]["necessity"] = "conditional"
    doc["shots"][0]["conditional_on"] = "has_a_feature_nobody_declared"
    (tmp_path / "shotplan.json").write_text(json.dumps(doc))
    with pytest.raises(SPEC.SpecError) as e:
        SPEC.load(tmp_path / "shotplan.json")
    assert "could never activate" in str(e.value)


# -- the condition language -------------------------------------------------------------------

def test_unanswered_feature_raises_rather_than_evaluating_false():
    with pytest.raises(SPEC.SpecError):
        SPEC.evaluate("has_coin_pocket", {})
    assert SPEC.evaluate("has_coin_pocket", {"has_coin_pocket": True}) is True
    assert SPEC.evaluate("n_repairs > 0", {"n_repairs": 0}) is False


def test_unanswered_question_that_would_drop_a_shot_defaults_to_present():
    spec = type("S", (), {"features": [
        {"key": "has_coin_pocket", "type": "bool", "unanswered_means": "present"},
        {"key": "has_zip_fly", "type": "bool", "unanswered_means": "absent"},
        {"key": "n_repairs", "type": "count", "unanswered_means": "present"}]})()
    f, unanswered, blocking = PLAN.resolve_features(spec, {})
    assert f["has_coin_pocket"] is True, "silence must not delete a photograph"
    assert f["n_repairs"] == 1, "'how many' unanswered means at least one until told otherwise"
    assert f["has_zip_fly"] is False
    assert set(unanswered) == {"has_coin_pocket", "has_zip_fly", "n_repairs"}


# -- roll-up ------------------------------------------------------------------------------------

def test_no_checks_is_unavailable_not_pass():
    assert QA.roll_up([]) == QA.UNAVAILABLE


@pytest.mark.parametrize("outcomes,expect", [
    ([QA.PASS], QA.PASS),
    ([QA.PASS, QA.HUMAN], QA.HUMAN),
    ([QA.HUMAN, QA.UNAVAILABLE], QA.UNAVAILABLE),
    ([QA.UNAVAILABLE, QA.RETAKE], QA.RETAKE),
])
def test_roll_up_precedence(outcomes, expect):
    assert QA.roll_up([QA.Check("c%d" % i, o, "") for i, o in enumerate(outcomes)]) == expect


# -- relay and tilt verdicts --------------------------------------------------------------------

def test_relay_verdict_never_passes_without_the_interior_comparison():
    a = {"cx": 10.0, "cy": 10.0, "angle_deg": 5.0, "bbox": [0, 0, 50, 90]}
    b = {"cx": 30.0, "cy": 10.0, "angle_deg": 9.0, "bbox": [0, 0, 50, 90]}
    o, _d, _e = Q.relay_verdict(a, b, 0.3, interior_ncc=None, operator_confirmed=True)
    assert o == QA.UNAVAILABLE


def test_relay_verdict_rejects_the_same_creases():
    a = {"cx": 10.0, "cy": 10.0, "angle_deg": 5.0, "bbox": [0, 0, 50, 90]}
    b = {"cx": 30.0, "cy": 10.0, "angle_deg": 9.0, "bbox": [0, 0, 50, 90]}
    o, _d, _e = Q.relay_verdict(a, b, 0.3, interior_ncc=0.99, operator_confirmed=True)
    assert o == QA.RETAKE


def test_relay_verdict_needs_the_operator_even_when_geometry_agrees():
    a = {"cx": 10.0, "cy": 10.0, "angle_deg": 5.0, "bbox": [0, 0, 50, 90]}
    b = {"cx": 30.0, "cy": 10.0, "angle_deg": 9.0, "bbox": [0, 0, 50, 90]}
    o, _d, _e = Q.relay_verdict(a, b, 0.3, interior_ncc=0.1, seconds_apart=120,
                                operator_confirmed=False)
    assert o == QA.HUMAN


def test_tilt_verdict_without_a_board_is_unavailable():
    assert Q.tilt_verdict(None)[0] == QA.UNAVAILABLE
    assert Q.tilt_verdict(1.0)[0] == QA.PASS
    assert Q.tilt_verdict(1.5)[0] == QA.RETAKE


def test_principal_axis_angles_wrap_at_180_degrees():
    assert Q._angle_delta(179.0, 1.0) == pytest.approx(2.0)


# -- the cut construction -----------------------------------------------------------------------

def test_a_leg_that_does_not_taper_needs_no_offset():
    s = CUT.compute(target_inseam_cm=15.0, original_inseam_cm=80.0, thigh_cm=44.0,
                    leg_opening_cm=44.0)
    assert s["outseam_offset_mm"] == pytest.approx(0.0, abs=1e-6)
    assert s["cut_angle_deg"] == pytest.approx(0.0, abs=1e-6)


def test_more_taper_means_more_offset():
    offs = [CUT.compute(target_inseam_cm=15.0, original_inseam_cm=80.0, thigh_cm=t,
                        leg_opening_cm=40.0)["outseam_offset_mm"] for t in (42, 50, 60, 70)]
    assert offs == sorted(offs) and offs[0] < offs[-1]


def test_a_cut_longer_than_the_garment_is_refused():
    with pytest.raises(CUT.CutSpecError):
        CUT.compute(target_inseam_cm=90.0, original_inseam_cm=80.0, thigh_cm=60.0,
                    leg_opening_cm=40.0)


def test_swapped_thigh_and_opening_are_refused():
    with pytest.raises(CUT.CutSpecError):
        CUT.compute(target_inseam_cm=15.0, original_inseam_cm=80.0, thigh_cm=40.0,
                    leg_opening_cm=60.0)


# -- the hem loop ---------------------------------------------------------------------------------

def test_macros_advance_by_the_usable_arc_so_the_loop_has_no_gap():
    g = HEM.HemGeometry.from_leg_opening("left", 20.0)
    cov = g.coverage([m["index"] for m in g.macros()])
    assert cov["complete"] and cov["n_gaps"] == 0
    # and the count follows the usable arc, not the full one
    assert len(g.macros()) == int(-(-g.circumference_mm // g.usable_arc_mm))


def test_a_wider_leg_needs_more_macros():
    assert HEM.required_macro_count(17) < HEM.required_macro_count(25)


def test_a_macro_whose_usable_arc_is_negative_is_refused():
    with pytest.raises(ValueError):
        HEM.HemGeometry("left", 400.0, arc_mm=20.0, edge_margin_mm=15.0)


# -- the store ------------------------------------------------------------------------------------

def test_the_log_vocabulary_is_closed(tmp_path):
    s = Store(tmp_path / "DENIM_0000")
    with pytest.raises(ValueError):
        s.append("something_new", {})


def test_actual_wash_settings_never_replace_planned_ones(tmp_path):
    s = Store(tmp_path / "DENIM_0000")
    s.append("wash_planned", {"water_temp_c": 30.0, "spin_rpm": 1200})
    s.append("wash_actual", {"water_temp_c": 40.0, "spin_rpm": 1200})
    st, _ = s.fold()
    assert st["wash_planned"]["water_temp_c"] == 30.0
    assert st["wash_actual"]["water_temp_c"] == 40.0
    d = diff_planned_actual(st["wash_planned"], st["wash_actual"])
    assert [x["field"] for x in d] == ["water_temp_c"]


def test_setup_hash_ignores_float_representation_but_not_values():
    a = setup_hash({"height_cm": 82.5, "lens": "main"})
    b = setup_hash({"lens": "main", "height_cm": 82.50000000000001})
    c = setup_hash({"lens": "main", "height_cm": 82.6})
    assert a == b and a != c

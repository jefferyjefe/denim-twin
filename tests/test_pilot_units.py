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

def test_leg_opening_is_a_full_circumference_not_a_folded_one():
    """The repository's own convention, stated in every record.json.

    from_leg_opening doubled it again -- true of the tape reading, and exactly why the stored value
    is already doubled -- so a 40 cm opening described an 801 mm loop and demanded eleven macros
    where six cover it, while cutspec halved the same field and disagreed about the same garment.
    """
    g = HEM.HemGeometry.from_leg_opening("left", 40.0)
    assert g.circumference_mm == pytest.approx(400.0)


def test_a_post_cut_loop_is_sized_from_the_cut_not_the_original_hem():
    """A jorts cut lands high on the leg, where the leg is wider. Sizing the cut hem's series from
    the original opening under-counts the macros, and under-counting leaves gaps in the fray
    profile -- the direction that loses the measurement."""
    g = HEM.HemGeometry.from_cut_spec("left", {"predicted_hem_circumference_cm": 56.0},
                                      leg_opening_cm=40.0)
    assert g.circumference_mm == pytest.approx(560.0)
    assert len(g.macros()) > len(HEM.HemGeometry.from_leg_opening("left", 40.0).macros())


def test_macros_advance_by_the_usable_arc_so_the_loop_has_no_gap():
    g = HEM.HemGeometry.from_leg_opening("left", 40.0)
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


# -- before/after coverage -----------------------------------------------------------------------

def test_matched_pairs_span_states_and_companions_do_not():
    """A link between two shots in the same state is not a before/after pair.

    Counting same-state links as matched pairs inflates the tally and, worse, hides the pairs that
    are genuinely missing: a region with no later-state frame looks covered because some same-state
    link filled the count.
    """
    s = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    order = {st["state"]: st["order"] for st in s.states}
    pairs, companions = s.matched_pairs(), s.companion_pairs()
    assert pairs and companions, "the plan should contain both kinds"
    for a, b in pairs:
        assert order[s.by_id[a]["state"]] < order[s.by_id[b]["state"]], (a, b)
    for a, b in companions:
        assert order[s.by_id[a]["state"]] == order[s.by_id[b]["state"]], (a, b)
    assert not set(pairs) & {tuple(sorted(c)) for c in companions}


def test_every_region_that_survives_the_cut_and_changes_with_washing_has_a_later_frame():
    """The requirement, asked of the regions rather than of the links.

    A region that declares no links declares none missing, so asking the links whether they are
    complete cannot find this. Regions the cut removes are exempt: their after-state evidence lives
    on the offcut, because the garment no longer has them.
    """
    s = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    # This assertion used to be `not s.unmatched_changing_regions()`, and it passed for two years
    # because the function could not return anything: it skipped every region carrying
    # can_change_by_cut, which is every region in question. With that fixed, 39 regions really do
    # have no post-wash frame -- and whether each NEEDS one is a judgement about the protocol,
    # which depends on where the cut lands and belongs to the owner.
    #
    # What is a fact about the document, and is therefore what this enforces: every one of them has
    # been LOOKED AT. A region with neither a later frame nor a recorded decision is an omission
    # nobody has considered, and the wash is a one-way door.
    undeclared = s.undeclared_changing_regions()
    assert not undeclared, (
        "%d region(s) change with washing, are photographed before it, have no frame in any later "
        "state, and carry no entry in postwash_coverage_decisions: %s"
        % (len(undeclared), undeclared[:10]))
    assert s.unmatched_changing_regions(), (
        "unmatched_changing_regions() returns nothing at all. It did that for two years because a "
        "flag suppressed every candidate; a detector that cannot report is not a passing check.")


# -- the offcut alternation ------------------------------------------------------------------------

def test_offcut_assignment_alternates_across_garments(tmp_path):
    from denimtwin.pilot import offcut as OFF
    import json as _json

    def mk(gid, leg=None):
        d = tmp_path / gid
        d.mkdir()
        (d / "record.json").write_text(_json.dumps({
            "garment_id": gid,
            "offcut_wash": ({leg: OFF.WITH_GARMENT,
                             ("R" if leg == "L" else "L"): OFF.SEPARATE_LOAD} if leg else None)}))
    mk("DENIM_0001", "L")
    mk("DENIM_0002", "R")
    mk("DENIM_0003")
    a = OFF.next_assignment(str(tmp_path), "DENIM_0003")
    assert a["with_garment"]["leg"] == "L", "must alternate away from DENIM_0002's R"
    assert a["other"]["leg"] == "R"
    assert OFF.check_alternation(str(tmp_path))["alternating"]


def test_a_broken_alternation_is_detected(tmp_path):
    from denimtwin.pilot import offcut as OFF
    import json as _json
    for gid, leg in (("DENIM_0001", "L"), ("DENIM_0002", "R"), ("DENIM_0003", "R")):
        d = tmp_path / gid
        d.mkdir()
        (d / "record.json").write_text(_json.dumps({
            "garment_id": gid,
            "offcut_wash": {leg: OFF.WITH_GARMENT,
                            ("R" if leg == "L" else "L"): OFF.SEPARATE_LOAD}}))
    r = OFF.check_alternation(str(tmp_path))
    assert not r["alternating"] and r["breaks"], r


def test_a_garment_that_cannot_be_machine_washed_changes_what_the_second_offcut_is_for(tmp_path):
    from denimtwin.pilot import offcut as OFF
    a = OFF.next_assignment(str(tmp_path), "DENIM_0009", garment_machine_washable=False)
    assert a["other"]["condition"] == OFF.GARMENT_CONDITION
    assert "care label" in a["note"]


# -- the ghost overlay -----------------------------------------------------------------------------

def test_the_later_half_of_a_matched_pair_is_offered_its_earlier_image(tmp_path):
    """And it is labelled a capture aid, because that is the whole constraint on it.

    The overlay exists so the operator can reproduce a framing. It must never become evidence, so
    the only thing that travels with it is a URL and a sentence saying what it is not.
    """
    import os
    from denimtwin.pilot import webapp
    from denimtwin.pilot.selftest import Bench

    spec = SPEC.load(ROOT / "protocol" / "shotplan" / "shotplan.json")
    b = Bench(tmp_path, spec, "DENIM_0003")
    b.open_session(); b.freeze_rig(); b.answer_features(); b.measure()
    shots, _ = b.activated()
    byid = {x["shot_id"]: x for x in shots}
    pairs = [p for p in spec.matched_pairs() if p[0] in byid and p[1] in byid]
    assert pairs, "the plan should declare cross-state matched pairs"
    earlier, later = pairs[0]
    b.add(byid[earlier], 1, b.synth_for(byid[earlier], 1))
    ordered = PLAN.order(spec, shots, state=byid[later]["state"])
    for e in ordered:
        if e["shot_id"] == later:
            break
        b.add(byid[e["shot_id"]], e["rep"], b.synth_for(byid[e["shot_id"]], e["rep"]))
    sess = webapp.Session(tmp_path, os.path.join(str(tmp_path), "garments"),
                          ROOT / "protocol" / "shotplan" / "shotplan.json",
                          ROOT / "protocol" / "charuco_board.json")
    snap = sess.snapshot("DENIM_0003", state_filter=byid[later]["state"])
    assert snap["next"]["shot_id"] == later
    ghost = snap["ghost"]
    assert ghost and ghost["shot_id"] == earlier
    assert "never evidence" in ghost["note"]
    assert ghost["url"].startswith("/photo?p=DENIM_0003/")


# -- what may enter the repository -------------------------------------------------------------------

def test_the_raw_capture_log_is_gitignored_and_the_sanitised_one_is_not():
    """The local log carries full EXIF, which on a phone includes GPS.

    data/external/README.md already says only derived numbers enter this repository and .gitignore
    keeps the photographs out. Their coordinates have to be kept out too, and the sanitised
    projection is the only form that may be committed.
    """
    # The RULES, not the prose: the comment above them names the sanitised file, and matching on
    # raw text would read that explanation as a rule.
    rules = [ln.strip() for ln in (ROOT / ".gitignore").read_text().splitlines()
             if ln.strip() and not ln.strip().startswith("#")]
    assert "data/garments/**/pilot/manifest.jsonl" in rules
    assert not [r for r in rules if "sanitised" in r], (
        "the sanitised manifest is the committable form; ignoring it would leave nothing to commit")


def test_sanitisation_drops_location_tags_and_absolute_paths(tmp_path):
    from denimtwin.pilot.manifest import Manifest, sanitise_exif
    m = Manifest(tmp_path / "manifest.jsonl")
    m.append("capture", {"shot_id": "A.B", "rep": 1, "path": "images/before/x.jpg",
                         "exif": {"Make": "Apple", "GPSLatitude": "51.5",
                                  "GPSInfo": {"1": "N"}, "DateTimeOriginal": "2026:08:31 10:00:00"}})
    out, problems = m.sanitised(tmp_path)
    assert not problems
    exif = out[0]["payload"]["exif"]
    assert "Make" in exif, "rig-relevant tags still belong in the committable form"
    # DateTimeOriginal used to be asserted PRESENT here. It is now dropped, and this line is the
    # reason the change is visible rather than silent: manifest.sanitised.json is the one pilot
    # file that is deliberately not gitignored, this repository does not put calendar dates in the
    # records it commits, and a shutter time is also a statement about where its operator was on a
    # given evening. It is still read from the file and still corroborates the log -- in the
    # private, gitignored manifest.jsonl, which keeps the full EXIF.
    assert "DateTimeOriginal" not in exif and "DateTime" not in exif
    assert not [k for k in exif if str(k).startswith("GPS")]
    assert sanitise_exif({"GPSLatitude": 1, "Model": "x"}) == {"Model": "x"}


def test_an_unevaluable_gate_does_not_share_an_exit_code_with_a_typo():
    """UNAVAILABLE is 3, because argparse owns 2.

    A gate blocked because a condition could not RUN and a gate that was never run because the
    command was mistyped call for opposite responses -- fix the system, versus fix the command --
    and a caller that sees the same number for both will pick one of them at random.
    """
    import subprocess
    src = (ROOT / "tools" / "pilot.py").read_text()
    assert "OK, FAIL, UNAVAILABLE = 0, 1, 3" in src, \
        "UNAVAILABLE must not be 2; argparse exits 2 on a usage error"
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "pilot.py"), "gate",
                        "DENIM_0001", "not_a_gate"], capture_output=True, text=True)
    assert r.returncode == 2, "a usage error is argparse's 2, and nothing else may claim it"


def test_the_actual_wash_is_written_once(tmp_path):
    """A correction that overwrites is indistinguishable from the wash never having deviated."""
    st = Store(tmp_path / "DENIM_0001")
    plan = {"machine": "Miele", "cycle": "cottons 30", "water_temp_c": 30.0}
    st.append("wash_planned", plan, operator="t")
    st.append("wash_actual", dict(plan, water_temp_c=42.0), operator="t")
    st.append("wash_actual", dict(plan), operator="tidier")
    state, _ = st.fold()
    assert state["wash_actual"]["water_temp_c"] == 42.0
    assert len(state["wash_actual_rewrites"]) == 1


def test_a_threshold_no_check_can_evaluate_fails_the_specification():
    """A number nothing compares anything to reads, to an auditor, as a threshold being enforced."""
    ruler_macro = {"shot_id": "X.Y.Z", "scale_reference": "ruler", "camera_angle": "macro_perpendicular",
                   "quality": {"max_mm_per_px": 0.15}}
    found = dict(QA.quality_is_evaluable(ruler_macro))
    assert "max_mm_per_px" in found, "a ruler-scaled shot carries no board, so nothing can produce it"
    boarded = dict(ruler_macro, scale_reference="charuco_board")
    assert "max_mm_per_px" not in dict(QA.quality_is_evaluable(boarded))

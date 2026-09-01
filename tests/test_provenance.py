"""The rights gate, tested the only way a gate can be: by trying to get past it.

`tools/validate_provenance.py` decides whether a sample may be used as physical before/after
evidence. A gate like that fails in one direction that matters -- it lets something through -- so
almost every test below builds a record that SHOULD be refused and asserts on the reason code, not
on the boolean. A refusal for the wrong reason is a rule that is not doing its job and would stop
working the moment the accidental reason went away.

Two more properties are load-bearing and get their own tests:

  * The positive control. A rule that refuses everything is trivially "safe" and useless, and it
    would pass every negative test in this file. `test_a_clean_controlled_pair_is_eligible` is what
    stops the gate from degenerating into that.
  * `training_eligible` is derived, never read. A record that asserts its own eligibility is
    rejected -- in both directions, because a record that under-claims is still a record whose
    stored verdict nobody recomputed.

Fully hermetic: no torch, no checkpoint, no photograph, no network. Fixtures are inline dicts.
"""
import copy
import importlib.util
import json
import os
import pathlib

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_spec = importlib.util.spec_from_file_location(
    "validate_provenance", os.path.join(ROOT, "tools", "validate_provenance.py"))
VP = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(VP)

SCHEMA = json.load(open(os.path.join(ROOT, "data/schemas/provenance.schema.json")))
MANIFEST = os.path.join(ROOT, "data/external/provenance.jsonl")


# --------------------------------------------------------------------------- fixtures
def controlled_pair():
    """The one shape that is supposed to get through: this project's own capture of one garment,
    photographed before and after under protocol/PROTOCOL.md. All rights reserved because the
    project holds them, and derivatives permitted for the same reason -- written down."""
    return {
        "record_id": "garment:DENIM_9999",
        "sample_kind": "before_after_pair",
        "pair_type": "controlled_physical",
        "exact_garment": "verified",
        "exact_garment_basis": "one physical garment, cut and rephotographed by the project; "
                               "garment id carried through data/garments/DENIM_9999/record.json",
        "rights": {
            "license_id": "ALL-RIGHTS-RESERVED",
            "license_url": None,
            "license_statement": "photographed by the project; no licence granted to anyone else",
            "attribution": "denim-twin project",
            "rights_holder": "denim-twin project",
            "redistributable": False,
            "derivatives_allowed": True,
            "commercial_use_allowed": True,
            "derivatives_basis": "the project holds the copyright in its own capture-protocol "
                                 "photographs",
        },
        "provenance": {
            "source": "denim-twin capture protocol",
            "source_url": None,
            "retrieved_at": "step",
            "method": "protocol/PROTOCOL.md capture, before / immediate-after / post-wash",
            "recorded_in": "data/garments/DENIM_9999/record.json",
        },
    }


def licensed_pair():
    """The other eligible shape: someone else's pair, under a licence that actually permits it."""
    r = controlled_pair()
    r["record_id"] = "licensed:example0001"
    r["pair_type"] = "licensed_physical"
    r["exact_garment_basis"] = "the licensor's written statement identifies both photographs as " \
                               "one garment, and the serial-numbered hang tag is legible in both"
    r["rights"] = {
        "license_id": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "license_statement": "CC BY 4.0",
        "attribution": "A. Photographer, CC BY 4.0",
        "rights_holder": "A. Photographer",
        "redistributable": True,
        "derivatives_allowed": True,
        "commercial_use_allowed": True,
        "derivatives_basis": None,
    }
    r["provenance"] = {
        "source": "example.invalid",
        "source_url": "https://example.invalid/pair/1",
        "retrieved_at": "step",
        "method": "manual web review",
        "recorded_in": "data/external/provenance.jsonl",
    }
    return r


def codes(reasons):
    return {r.split(":", 1)[0] for r in reasons}


def schema_errors(rec):
    import jsonschema
    return [e.message for e in jsonschema.Draft202012Validator(SCHEMA).iter_errors(rec)]


# ------------------------------------------------------------------ the positive control
def test_a_clean_controlled_pair_is_eligible():
    """Without this the entire file is satisfied by `return False, ['no']`."""
    rec = controlled_pair()
    assert schema_errors(rec) == []
    assert VP.consistency_errors(rec) == []
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert eligible, reasons
    assert reasons == []


def test_a_clean_licensed_pair_is_eligible():
    rec = licensed_pair()
    assert VP.validate_record(rec, SCHEMA) == []
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert eligible, reasons


# ---------------------------------------------------------------- one test per rule
def test_a_synthetic_edit_is_never_physical_evidence():
    rec = controlled_pair()
    rec["pair_type"] = "synthetic_edit"
    rec["synthetic"] = {"generator": "an image model", "edit_description": "hem repainted as frayed"}
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "synthetic_edit" in codes(reasons), reasons


def test_a_weak_visual_pair_is_never_physical_evidence():
    rec = controlled_pair()
    rec["pair_type"] = "weak_visual"
    rec["exact_garment"] = "not_verified"
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "weak_visual" in codes(reasons), reasons


def test_a_physical_pair_whose_garment_was_never_verified_is_refused():
    rec = controlled_pair()
    rec["exact_garment"] = "not_verified"
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "exact_garment_not_verified" in codes(reasons), reasons


def test_a_physical_pair_of_two_known_different_garments_is_refused_by_name():
    """'known_different' must not collapse into the same message as 'not_verified': one is an
    unanswered question and the other is an answered one, and a report that cannot tell them apart
    cannot tell a reviewer which records are worth chasing."""
    rec = controlled_pair()
    rec["exact_garment"] = "known_different"
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "exact_garment_known_different" in codes(reasons), reasons
    assert "exact_garment_not_verified" not in codes(reasons), reasons


def test_a_single_image_is_refused_however_good_its_licence():
    rec = licensed_pair()
    rec["sample_kind"] = "single_image"
    rec["pair_type"] = "weak_visual"
    rec["exact_garment"] = "not_verified"
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "not_a_pair" in codes(reasons), reasons


def test_a_sample_whose_licence_forbids_derivatives_is_refused():
    """Masks, crops and renders are derivative works, so ND is not a partial permission."""
    rec = licensed_pair()
    rec["rights"].update(license_id="CC-BY-ND-4.0", license_statement="CC BY-ND 4.0",
                         license_url="https://creativecommons.org/licenses/by-nd/4.0/",
                         derivatives_allowed=False)
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "derivatives_not_allowed" in codes(reasons), reasons


def test_all_rights_reserved_without_a_written_basis_is_refused():
    rec = controlled_pair()
    rec["rights"]["derivatives_basis"] = None
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "all_rights_reserved_without_derivatives_basis" in codes(reasons), reasons


def test_all_rights_reserved_is_never_redistributable():
    """This one is a DEFECT in the record, not a verdict about the sample: the record asserts a
    permission the licence field says was never granted."""
    rec = controlled_pair()
    rec["rights"]["redistributable"] = True
    errs = VP.consistency_errors(rec)
    assert any("redistributable" in e for e in errs), errs
    assert VP.validate_record(rec, SCHEMA) != []


def test_an_undetermined_licence_grants_nothing():
    rec = licensed_pair()
    rec["rights"].update(license_id="UNDETERMINED", license_statement="Public domain",
                         license_url=None, redistributable=False, derivatives_allowed=False,
                         commercial_use_allowed=False)
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "license_undetermined" in codes(reasons), reasons


def test_an_undetermined_licence_may_not_be_the_source_of_a_permission():
    rec = licensed_pair()
    rec["rights"].update(license_id="UNDETERMINED", license_statement="Public domain",
                         license_url=None)
    errs = VP.consistency_errors(rec)
    assert any("UNDETERMINED" in e and "derivatives_allowed" in e for e in errs), errs


def test_an_attribution_licence_with_no_attribution_string_is_refused():
    rec = licensed_pair()
    rec["rights"]["attribution"] = None
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "attribution_missing" in codes(reasons), reasons


def test_a_creator_contributed_pair_without_recorded_consent_is_refused():
    rec = controlled_pair()
    rec["pair_type"] = "creator_contributed_physical"
    rec["consent"] = {"obtained": False, "contributor": "a person",
                      "consent_record": "outreach/consent/none.md", "consent_date": "step",
                      "scope": "research_only"}
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "consent_missing" in codes(reasons), reasons


def test_a_creator_contributed_pair_with_consent_is_eligible():
    rec = controlled_pair()
    rec["pair_type"] = "creator_contributed_physical"
    rec["consent"] = {"obtained": True, "contributor": "a person",
                      "consent_record": "outreach/consent/a-person.md",
                      "consent_date": "step", "scope": "research_and_publication"}
    assert VP.validate_record(rec, SCHEMA) == []
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert eligible, reasons


def test_withdrawn_consent_removes_eligibility():
    rec = controlled_pair()
    rec["pair_type"] = "creator_contributed_physical"
    rec["consent"] = {"obtained": True, "contributor": "a person",
                      "consent_record": "outreach/consent/a-person.md",
                      "consent_date": "step", "scope": "research_only", "withdrawn": True}
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "consent_withdrawn" in codes(reasons), reasons


def test_a_verified_claim_with_no_stated_basis_is_rejected():
    rec = controlled_pair()
    rec["exact_garment_basis"] = None
    assert any("basis" in e for e in VP.consistency_errors(rec))
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible
    assert "exact_garment_basis_missing" in codes(reasons), reasons


def test_every_refusal_reason_names_a_code_and_a_sentence():
    """A reason of the form '<code>: <sentence>' is what lets a report group refusals and a human
    read one. A bare code is unreadable; a bare sentence is ungroupable."""
    rec = controlled_pair()
    rec.update(sample_kind="single_image", pair_type="weak_visual", exact_garment="not_verified")
    rec["rights"].update(derivatives_allowed=False, derivatives_basis=None)
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert not eligible and len(reasons) >= 3
    for r in reasons:
        code, _, sentence = r.partition(": ")
        assert code and " " not in code, r
        assert len(sentence.split()) >= 5, r


# ------------------------------------------------- a file may not assert its own eligibility
def test_a_record_claiming_it_is_eligible_when_the_rule_refuses_is_rejected():
    rec = controlled_pair()
    rec["exact_garment"] = "not_verified"          # the rule refuses this
    rec["training_eligible"] = True                # the file says otherwise
    errs = VP.validate_record(rec, SCHEMA)
    assert any("training_eligible" in e for e in errs), errs
    assert any("exact_garment_not_verified" in e for e in errs), errs


def test_a_record_claiming_it_is_ineligible_when_the_rule_allows_is_also_rejected():
    """Disagreement in either direction is the same defect: a stored verdict nobody recomputed."""
    rec = controlled_pair()
    rec["training_eligible"] = False
    errs = VP.validate_record(rec, SCHEMA)
    assert any("training_eligible" in e for e in errs), errs


def test_a_record_that_agrees_with_the_rule_is_still_accepted():
    rec = controlled_pair()
    rec["training_eligible"] = True
    assert VP.validate_record(rec, SCHEMA) == []


# --------------------------------------------------------------- the schema refuses malformity
@pytest.mark.parametrize("mutate,expect", [
    (lambda r: r.pop("record_id"), "record_id"),
    (lambda r: r.pop("pair_type"), "pair_type"),
    (lambda r: r.pop("rights"), "rights"),
    (lambda r: r.pop("provenance"), "provenance"),
    (lambda r: r.pop("exact_garment"), "exact_garment"),
    (lambda r: r.pop("sample_kind"), "sample_kind"),
    (lambda r: r.pop("exact_garment_basis"), "exact_garment_basis"),
    (lambda r: r["rights"].pop("license_id"), "license_id"),
    (lambda r: r["rights"].pop("redistributable"), "redistributable"),
    (lambda r: r["rights"].pop("derivatives_allowed"), "derivatives_allowed"),
    (lambda r: r["rights"].pop("commercial_use_allowed"), "commercial_use_allowed"),
    (lambda r: r["rights"].pop("attribution"), "attribution"),
    (lambda r: r["rights"].pop("license_url"), "license_url"),
    (lambda r: r["rights"].pop("license_statement"), "license_statement"),
    (lambda r: r["provenance"].pop("source"), "source"),
    (lambda r: r["provenance"].pop("source_url"), "source_url"),
    (lambda r: r["provenance"].pop("retrieved_at"), "retrieved_at"),
    (lambda r: r["provenance"].pop("method"), "method"),
    (lambda r: r["provenance"].pop("recorded_in"), "recorded_in"),
])
def test_the_schema_requires_every_field_whose_absence_would_let_a_sample_through(mutate, expect):
    rec = controlled_pair()
    mutate(rec)
    errs = schema_errors(rec)
    assert errs, f"removing {expect} left a valid record"
    assert any(expect in e for e in errs), errs


def test_exact_garment_may_not_be_a_bare_boolean():
    """The whole point of the tri-state. `true`/`false` would make 'nobody checked' indistinguishable
    from 'checked and it is a different garment'."""
    for value in (True, False, None, "unknown", "yes"):
        rec = controlled_pair()
        rec["exact_garment"] = value
        assert schema_errors(rec), f"exact_garment={value!r} was accepted"


def test_an_unknown_pair_type_is_refused():
    rec = controlled_pair()
    rec["pair_type"] = "found_on_the_internet"
    assert schema_errors(rec)


def test_an_undeclared_field_is_refused_at_every_level():
    """additionalProperties is false deliberately. An unrecognised key is either a typo of a real
    one -- so the constraint it was meant to record is silently absent -- or a rights fact no code
    reads, which is worse: it makes a record look considered when nothing considered it."""
    for path in ([], ["rights"], ["provenance"]):
        rec = controlled_pair()
        target = rec
        for k in path:
            target = target[k]
        target["definitely_ok_to_use"] = True
        assert schema_errors(rec), f"an undeclared field was accepted under {path or ['<root>']}"


def test_a_licence_that_is_not_an_spdx_identifier_or_a_sentinel_is_refused():
    for lic in ("free to use", "cc-by", "CC BY 4.0", "public domain", "", "CC-BY-9.9"):
        rec = licensed_pair()
        rec["rights"]["license_id"] = lic
        assert schema_errors(rec), f"license_id={lic!r} was accepted"


def test_a_bespoke_written_agreement_is_expressible_as_an_spdx_licenseref():
    """Without this a real, negotiated licence would have to be recorded as ALL-RIGHTS-RESERVED or
    UNDETERMINED, and the gate would refuse the one category of sample it is meant to admit."""
    rec = licensed_pair()
    rec["rights"]["license_id"] = "LicenseRef-denim-twin-contributor"
    rec["rights"]["license_statement"] = "bespoke research licence, filed in outreach/"
    assert schema_errors(rec) == []
    eligible, reasons = VP.evaluate_eligibility(rec)
    assert eligible, reasons


def test_a_creator_contributed_record_must_carry_a_consent_block():
    rec = controlled_pair()
    rec["pair_type"] = "creator_contributed_physical"
    assert any("consent" in e for e in schema_errors(rec))


def test_a_synthetic_record_must_say_what_generated_it():
    rec = controlled_pair()
    rec["pair_type"] = "synthetic_edit"
    assert any("synthetic" in e for e in schema_errors(rec))


def test_a_malformed_retrieved_at_is_refused():
    for bad in ("yesterday", "last summer", "not-a-step", ""):
        rec = controlled_pair()
        rec["provenance"]["retrieved_at"] = bad
        assert schema_errors(rec), f"retrieved_at={bad!r} was accepted"


def test_a_single_image_may_not_claim_a_physical_pair_type():
    rec = controlled_pair()
    rec["sample_kind"] = "single_image"
    errs = VP.consistency_errors(rec)
    assert any("single_image" in e for e in errs), errs


def test_a_weak_visual_pair_may_not_also_claim_a_verified_garment():
    """The two fields would then say opposite things, and whichever one a consumer read first would
    decide the outcome."""
    rec = controlled_pair()
    rec["pair_type"] = "weak_visual"
    errs = VP.consistency_errors(rec)
    assert any("weak_visual" in e for e in errs), errs


# ------------------------------------------------------------------- the committed manifest
def _manifest_records():
    assert os.path.exists(MANIFEST), (
        "data/external/provenance.jsonl is committed and must be present; without it this gate "
        "decides nothing and every test below would pass by having no data to check")
    recs, errs = VP.load_manifest(pathlib.Path(MANIFEST))
    assert errs == [], errs
    return [r for _, r in recs]


def test_the_committed_manifest_validates():
    recs = _manifest_records()
    assert recs, "the committed manifest is empty; the gate would pass vacuously"
    bad = {}
    for r in recs:
        errs = VP.validate_record(r, SCHEMA)
        if errs:
            bad[r.get("record_id", "?")] = errs
    assert not bad, json.dumps(bad, indent=1)[:4000]


def test_the_committed_manifest_has_unique_record_ids():
    ids = [r["record_id"] for r in _manifest_records()]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    assert not dupes, dupes


def test_no_committed_record_asserts_its_own_eligibility():
    """The field is legal in the schema so that an imported record cannot hide it; the manifest this
    project maintains has no business carrying it."""
    claimed = [r["record_id"] for r in _manifest_records() if "training_eligible" in r]
    assert not claimed, claimed


def test_every_eligible_record_in_the_manifest_meets_the_rule_by_hand():
    """Restating the rule against the committed data, as an invariant rather than a count -- so it
    keeps holding when real controlled pairs land, instead of failing the day they do."""
    for r in _manifest_records():
        eligible, _ = VP.evaluate_eligibility(r)
        if not eligible:
            continue
        assert r["sample_kind"] == "before_after_pair", r["record_id"]
        assert r["pair_type"] in VP.PHYSICAL_PAIR_TYPES, r["record_id"]
        assert r["exact_garment"] == "verified", r["record_id"]
        assert r["rights"]["derivatives_allowed"] is True, r["record_id"]


def test_no_all_rights_reserved_record_claims_redistribution():
    for r in _manifest_records():
        if r["rights"]["license_id"] == "ALL-RIGHTS-RESERVED":
            assert r["rights"]["redistributable"] is False, r["record_id"]


def test_the_manifest_covers_every_hand_curated_sample():
    """The gate is only a gate if nothing walks around it. A pair in data/external/pairs.jsonl with
    no provenance record is a sample whose rights nobody decided.

    Scoped to the hand-curated sets on purpose. The harvest queue grows on a schedule with nobody in
    the loop; asserting on it here would turn an automated fetch into a red build, and the pressure
    that produces is to auto-generate rights records, which is the comment-nobody-reads failure this
    whole gate replaces. The queue is covered by the next test instead, and by the fact that a
    sample with no record is refused by absence."""
    expected = VP.expected_record_ids()
    assert expected, "no known samples were found; this test would pass vacuously"
    have = {r["record_id"] for r in _manifest_records()}
    missing = sorted(k for k in expected if k not in have)
    assert not missing, (
        "these samples have no provenance record -- add one to data/external/provenance.jsonl "
        "(source of each shown):\n"
        + "\n".join(f"  {k}  <- {expected[k]}" for k in missing))


def test_a_sample_with_no_provenance_record_is_refused_by_absence(tmp_path):
    """The reason the harvest queue can be reported rather than enforced. Eligibility is a property
    of a record; there is no path by which an unrecorded sample acquires one."""
    have = {r["record_id"] for r in _manifest_records()}
    assert "harvest:commons_no_such_image" not in have
    eligible_ids = set()
    for r in _manifest_records():
        if VP.evaluate_eligibility(r)[0]:
            eligible_ids.add(r["record_id"])
    assert eligible_ids <= have

    # ...and an unrecorded queue entry does not quietly become a hard failure of --strict either,
    # which is what would push someone into generating records instead of writing them.
    out = tmp_path / "report.json"
    assert VP.main(["--manifest", MANIFEST, "--quiet", "--strict", "--json", str(out)]) == 0
    got = json.loads(out.read_text())
    assert got["uncovered"] == [], got["uncovered"]
    assert "unrecorded_harvest" in got


def test_the_harvest_queue_is_keyed_the_same_way_as_the_manifest():
    """If the two disagreed on how to name an image, coverage would report every queue entry as
    unrecorded forever and the report would be noise nobody reads."""
    queue = VP.harvested_record_ids()
    assert queue, "no harvested images were found; this test would pass vacuously"
    have = {r["record_id"] for r in _manifest_records()}
    assert have & set(queue), "no harvested image in the manifest matches a queue id: the id "\
                              "schemes have drifted apart"


def test_the_committed_manifest_records_the_found_pairs_as_all_rights_reserved():
    """Every tutorial pair page in this repository states copyright and grants nothing. If one of
    them is ever recorded as freely licensed, that is a claim that needs the page to have changed."""
    pairs = [r for r in _manifest_records() if r["record_id"].startswith("pair:")]
    assert pairs, "no found-pair records in the manifest"
    for r in pairs:
        assert r["rights"]["license_id"] == "ALL-RIGHTS-RESERVED", r["record_id"]
        assert r["rights"]["license_statement"].strip(), r["record_id"]
        assert r["provenance"]["recorded_in"] == "data/external/pairs.jsonl", r["record_id"]


def test_the_validator_refuses_an_empty_manifest_instead_of_reporting_a_clean_run(tmp_path):
    """An empty input is the failure mode data/priors/exclude.txt was hardened against: the run goes
    green because there was nothing to check, and every consumer reads green as permission."""
    empty = tmp_path / "provenance.jsonl"
    empty.write_text("")
    assert VP.main(["--manifest", str(empty), "--quiet"]) == 1


def test_the_validator_exits_nonzero_on_a_bad_record(tmp_path):
    rec = controlled_pair()
    rec["exact_garment"] = "not_verified"
    rec["training_eligible"] = True
    p = tmp_path / "provenance.jsonl"
    p.write_text(json.dumps(rec) + "\n")
    assert VP.main(["--manifest", str(p), "--quiet"]) == 1


def test_the_validator_exits_zero_on_the_committed_manifest():
    assert VP.main(["--manifest", MANIFEST, "--quiet"]) == 0


def test_the_validator_reports_refusal_codes_in_its_json_output(tmp_path):
    out = tmp_path / "provenance_report.json"
    assert VP.main(["--manifest", MANIFEST, "--quiet", "--json", str(out)]) == 0
    got = json.loads(out.read_text())
    assert got["n_records"] == len(_manifest_records())
    assert got["n_invalid"] == 0
    assert got["refusals_by_code"], "a manifest with ineligible records reported no reasons"
    assert set(got["refusals_by_code"]) <= {
        "not_a_pair", "synthetic_edit", "weak_visual", "exact_garment_not_verified",
        "exact_garment_known_different", "exact_garment_basis_missing", "derivatives_not_allowed",
        "all_rights_reserved_without_derivatives_basis", "license_undetermined",
        "attribution_missing", "consent_missing", "consent_withdrawn",
    }, got["refusals_by_code"]


def test_the_rule_is_a_pure_function_of_the_record():
    """It reads no file, no environment and no clock, so a verdict is reproducible from the record
    alone -- which is what makes the manifest auditable by someone who is not running this code."""
    rec = licensed_pair()
    before = copy.deepcopy(rec)
    VP.evaluate_eligibility(rec)
    VP.evaluate_eligibility(rec)
    assert rec == before
    assert VP.evaluate_eligibility(rec) == VP.evaluate_eligibility(copy.deepcopy(rec))

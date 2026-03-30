#!/usr/bin/env python3
"""Validate data/external/provenance.jsonl and DERIVE, per sample, whether it may be trained on.

Nothing in this repository decided eligibility on rights grounds before this file existed. Every
found pair in data/external/pairs.jsonl carries a `license_or_terms` string that says, in prose,
"all rights reserved" -- and tools/run_pairs_batch.py consumed all of them anyway, because a string
no code reads is a comment. Review 2 recorded exactly that (tests/test_review2_licensing.py) and it
stayed recorded.

Three things are separated here, because collapsing any two of them is how an ineligible sample
gets in:

  * SCHEMA errors -- the record does not say what it must say. data/schemas/provenance.schema.json.
  * CONSISTENCY errors -- the record says two things that cannot both be true (an all-rights-reserved
    image that is also redistributable; a "verified" same-garment claim on a pair whose own type
    means "not verified"). These are defects in the record, not verdicts about the sample.
  * ELIGIBILITY -- a derivation, never a field. `evaluate_eligibility` returns (eligible, reasons)
    and the reasons are the point: a refusal that cannot say why is indistinguishable from a bug.

A record MAY carry `training_eligible`, and if it does the value is recomputed and the record is
rejected on any disagreement, in either direction. A file may not assert its own eligibility --
that is the whole reason eligibility is derived rather than stored.

Read-only. stdlib + jsonschema only, so it runs in the hermetic CI environment where torch,
open_clip and every photograph are absent. It never opens an image and never touches the network.

    validate_provenance.py [--manifest PATH] [--json OUT] [--strict] [--quiet]

    --strict  additionally require COVERAGE of the hand-maintained candidate sets: every pair in
              data/external/pairs.jsonl, every control and unpaired candidate, and every garment
              with photographs must have a provenance record. Those files change only when a person
              edits them, so an uncovered entry there is someone's unfinished work.

              The harvest QUEUE (data/external/manifest.jsonl, labelled by tools/curate_harvest.py)
              is reported separately and does not fail the run. It grows on a schedule with no human
              in the loop, and a hand-written rights record auto-generated for every machine-added
              search hit would be provenance theatre. Nothing is lost by that: absence of a record
              is already refusal. A consumer asks this manifest whether a sample may be used, and a
              sample with no record has no eligibility to lose.
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.parse
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "data/schemas/provenance.schema.json"
DEFAULT_MANIFEST = ROOT / "data/external/provenance.jsonl"

#: pair_type values that assert a real, physical before/after of one garment. The two that are not
#: here -- synthetic_edit and weak_visual -- are not weaker evidence, they are different kinds of
#: thing, and neither can ever stand in for a photograph of a garment that was actually cut.
PHYSICAL_PAIR_TYPES = frozenset({
    "controlled_physical", "creator_contributed_physical", "licensed_physical",
})

#: Licence families whose own terms contradict a permission the record might claim. Used only for
#: CONSISTENCY -- the record's booleans are what the rest of the code reads, and these catch a
#: boolean that the licence it names cannot support.
_ND_LICENSES = frozenset({
    "CC-BY-ND-2.0", "CC-BY-ND-3.0", "CC-BY-ND-4.0",
    "CC-BY-NC-ND-2.0", "CC-BY-NC-ND-3.0", "CC-BY-NC-ND-4.0",
})
_NC_LICENSES = frozenset({
    "CC-BY-NC-2.0", "CC-BY-NC-3.0", "CC-BY-NC-4.0",
    "CC-BY-NC-SA-2.0", "CC-BY-NC-SA-3.0", "CC-BY-NC-SA-4.0",
    "CC-BY-NC-ND-2.0", "CC-BY-NC-ND-3.0", "CC-BY-NC-ND-4.0",
})
#: Licences that require attribution to be complied with. A BY licence with no recorded attribution
#: string is a licence this project cannot honour, whatever its other permissions say.
_ATTRIBUTION_REQUIRED = frozenset(
    {l for l in _NC_LICENSES | _ND_LICENSES if l.startswith("CC-BY")}
    | {"CC-BY-2.0", "CC-BY-2.5", "CC-BY-3.0", "CC-BY-4.0",
       "CC-BY-SA-2.0", "CC-BY-SA-2.5", "CC-BY-SA-3.0", "CC-BY-SA-4.0",
       "GFDL-1.2-only", "GFDL-1.3-only"}
)

SENTINEL_LICENSES = frozenset({"ALL-RIGHTS-RESERVED", "UNDETERMINED"})


# --------------------------------------------------------------------------- the rule
def evaluate_eligibility(rec):
    """Is this sample admissible as physical before/after evidence, and if not, why not?

    Returns (eligible: bool, reasons: list[str]). `reasons` is empty exactly when eligible, and
    every entry is "<code>: <sentence>" so that a report can group by code and a human can read the
    sentence. Every failing rule is reported, not just the first -- a record with three problems
    that is fixed one round-trip at a time is a record nobody fixes.

    "Eligible" here means one specific thing: usable as evidence about what physically happens to a
    garment. It is NOT a statement that the sample is useless otherwise -- a CC0 photograph of a
    single pair of jeans is ineligible under this rule and still perfectly good as a segmentation
    prior. docs/DATA_ELIGIBILITY.md says which uses this gate governs.
    """
    reasons = []
    rights = rec.get("rights") or {}
    pair_type = rec.get("pair_type")
    license_id = rights.get("license_id")

    # 1. A lone photograph is not a before/after pair, however good its licence is. There is no
    #    second image for it to be evidence of change against.
    if rec.get("sample_kind") != "before_after_pair":
        reasons.append(
            "not_a_pair: sample_kind is %r; physical evidence about a modification is a before/after "
            "pair, and a single image cannot show a change." % (rec.get("sample_kind"),))

    # 2. A generated or edited image is never physical evidence. It shows what a model or an editor
    #    produced, which is the thing under test, not a measurement of it.
    if pair_type == "synthetic_edit":
        reasons.append(
            "synthetic_edit: a generated or edited image is never admissible as physical evidence; "
            "it records what a generator did, not what a garment did.")

    # 3. A visually similar pair is a pair of pictures, not a pair of states of one garment. Two
    #    different pairs of jeans differ for reasons that have nothing to do with the cut.
    if pair_type == "weak_visual":
        reasons.append(
            "weak_visual: the two images are not verified to show the same garment, so any measured "
            "difference confounds the modification with the difference between two garments.")

    # 4. For the pair types that DO claim a real garment, the claim has to have been checked.
    #    'not_verified' is the common case for anything found on the web and it is not a near-miss:
    #    an unverified same-garment assumption is the confound in rule 3 wearing a better label.
    if pair_type in PHYSICAL_PAIR_TYPES:
        eg = rec.get("exact_garment")
        if eg == "known_different":
            reasons.append(
                "exact_garment_known_different: the before and after images are known to show "
                "different garments.")
        elif eg != "verified":
            reasons.append(
                "exact_garment_not_verified: exact_garment is %r, and a physical pair type asserts "
                "one garment in two states; that has to be established, not assumed." % (eg,))
        elif not (rec.get("exact_garment_basis") or "").strip():
            # Belt and braces with the consistency check below: a 'verified' with no stated basis
            # must never be able to reach an eligible verdict by any path.
            reasons.append(
                "exact_garment_basis_missing: exact_garment is 'verified' with no basis recorded; "
                "a verification nobody wrote down is not a verification.")

    # 5. Masks, canonicalised crops, landmark overlays and renders are all derivative works. A
    #    sample whose licence forbids derivatives cannot be used at all, not even privately.
    if rights.get("derivatives_allowed") is not True:
        reasons.append(
            "derivatives_not_allowed: every artefact this pipeline produces from an image -- masks, "
            "crops, overlays, renders -- is a derivative work, so derivatives_allowed must be true.")

    # 6. ALL-RIGHTS-RESERVED grants nothing. It can still be eligible, but only when some OTHER
    #    basis explains the permission -- normally that the project itself holds the copyright --
    #    and that basis has to be written down rather than assumed by whoever reads the record next.
    if license_id == "ALL-RIGHTS-RESERVED" and not (rights.get("derivatives_basis") or "").strip():
        reasons.append(
            "all_rights_reserved_without_derivatives_basis: the source grants no rights, so a "
            "permission to make derivatives has to come from somewhere else and rights.derivatives_"
            "basis has to say from where.")

    # 7. UNDETERMINED means the recorded statement is not a licence at all. No permission can be
    #    inferred from a rights statement nobody has resolved into one.
    if license_id == "UNDETERMINED":
        reasons.append(
            "license_undetermined: the source's rights statement is not a licence identifier, so no "
            "permission follows from it; resolve it to an SPDX id or leave the sample out.")

    # 8. A BY-family licence is conditional on attribution. Without a recorded attribution string
    #    the condition cannot be met, so the grant does not apply.
    if license_id in _ATTRIBUTION_REQUIRED and not (rights.get("attribution") or "").strip():
        reasons.append(
            "attribution_missing: %s grants rights only on condition of attribution and no "
            "attribution string was recorded." % (license_id,))

    # 9. A person's own before/after photographs need that person's recorded, current agreement --
    #    and consent that was withdrawn is consent that is gone.
    if pair_type == "creator_contributed_physical":
        consent = rec.get("consent") or {}
        if consent.get("obtained") is not True:
            reasons.append(
                "consent_missing: a creator-contributed pair requires recorded consent from the "
                "contributor; consent.obtained is not true.")
        elif consent.get("withdrawn") is True:
            reasons.append(
                "consent_withdrawn: the contributor withdrew consent, so the sample is no longer "
                "usable regardless of what was agreed before.")

    return (not reasons), reasons


# --------------------------------------------------------------- record-level consistency
def consistency_errors(rec):
    """Ways a record can contradict itself. These are DEFECTS, not verdicts: the record is wrong and
    has to be fixed, and reporting them as mere ineligibility would let a wrong record sit forever
    looking like a correctly-refused one."""
    errs = []
    rights = rec.get("rights") or {}
    lic = rights.get("license_id")
    # `licensed_physical` is a claim that a licence permits this use. ALL-RIGHTS-RESERVED and
    # UNDETERMINED are the two values that say no such licence is known -- the first because the
    # source grants nothing, the second because what was recorded is not a licence at all. Either
    # one under this pair type is a contradiction, and it was reachable: a scraped copyrighted blog
    # pair could be made ELIGIBLE by writing pair_type licensed_physical and asserting the boolean
    # permissions beside it, because rule 6 only required the free-text derivatives_basis to be
    # non-empty and nothing cross-checked the two fields against each other.
    if rec.get("pair_type") == "licensed_physical" and lic in ("ALL-RIGHTS-RESERVED", "UNDETERMINED"):
        errs.append(
            f"pair_type 'licensed_physical' asserts a licence permitting this use, but license_id is "
            f"{lic!r}, which is the value for 'no such licence is known'. Either record the licence "
            f"that was actually granted, or use the pair type that is true.")
    pair_type = rec.get("pair_type")

    if lic == "ALL-RIGHTS-RESERVED" and rights.get("redistributable") is True:
        errs.append("license_id is ALL-RIGHTS-RESERVED but redistributable is true; the source "
                    "grants no right to republish the image")
    if lic == "UNDETERMINED":
        for k in ("redistributable", "derivatives_allowed", "commercial_use_allowed"):
            if rights.get(k) is True:
                errs.append(f"license_id is UNDETERMINED but {k} is true; an unresolved rights "
                            f"statement cannot be the source of a permission")
    if lic in _ND_LICENSES and rights.get("derivatives_allowed") is True:
        errs.append(f"{lic} is a NoDerivatives licence but derivatives_allowed is true")
    if lic in _NC_LICENSES and rights.get("commercial_use_allowed") is True:
        errs.append(f"{lic} is a NonCommercial licence but commercial_use_allowed is true")
    if lic not in SENTINEL_LICENSES and lic is not None and not (rights.get("license_statement") or "").strip():
        errs.append("license_statement is empty; the recorded licence has no audit trail")

    if rec.get("exact_garment") == "verified" and not (rec.get("exact_garment_basis") or "").strip():
        errs.append("exact_garment is 'verified' but exact_garment_basis is empty; a verification "
                    "with no stated basis is an unbacked claim")
    if rec.get("exact_garment") == "verified" and pair_type == "weak_visual":
        errs.append("pair_type 'weak_visual' means the same-garment claim was NOT verified, so "
                    "exact_garment cannot be 'verified'; pick the pair type that is true")
    if rec.get("sample_kind") == "single_image" and pair_type in PHYSICAL_PAIR_TYPES:
        errs.append(f"sample_kind 'single_image' cannot carry pair_type {pair_type!r}: a pair type "
                    f"describes two images of one garment, and there is only one image here")
    if rec.get("sample_kind") == "before_after_pair" and pair_type == "weak_visual" \
            and rec.get("exact_garment") == "verified":
        errs.append("a verified same-garment pair is not weak_visual")
    return errs


def validate_record(rec, schema):
    """Everything wrong with one record: schema, self-contradiction, and a mis-declared verdict."""
    errs = [e.message for e in
            sorted(jsonschema.Draft202012Validator(schema).iter_errors(rec),
                   key=lambda e: [str(p) for p in e.path])]
    if errs:
        # Consistency and eligibility read fields the schema has not vouched for yet; deriving a
        # verdict from a malformed record would report nonsense with the authority of a decision.
        return errs
    errs += consistency_errors(rec)
    eligible, reasons = evaluate_eligibility(rec)
    if "training_eligible" in rec and rec["training_eligible"] != eligible:
        errs.append(
            f"training_eligible is recorded as {rec['training_eligible']!r} but the rule derives "
            f"{eligible!r}. A file may not assert its own eligibility. Derived reasons: "
            + ("; ".join(reasons) if reasons else "(none -- the record is eligible)"))
    return errs


# ------------------------------------------------------------------------------ loading
def load_manifest(path):
    """Records with their line numbers. A malformed line is a hard error, not a skipped line."""
    out, errs = [], []
    if not path.exists():
        return out, [f"manifest not found: {path}"]
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append((i, json.loads(line)))
        except json.JSONDecodeError as e:
            errs.append(f"line {i}: not valid JSON ({e})")
    return out, errs


# ---------------------------------------------------------------------------- coverage
def _sha1(s, n):
    return hashlib.sha1(s.encode()).hexdigest()[:n]


def _jsonl(rel):
    p = ROOT / rel
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


def expected_record_ids():
    """Samples a PERSON added to this repository, keyed the way the pipeline already keys them.

    The id schemes are not invented here: they are the ones tools/tutorial_pairs.py,
    tools/ingest_unpaired.py and tools/harvest_images.py use to name files on disk, so a provenance
    record joins to the artefact it describes by construction rather than by hope.

    Everything in here is hand-curated: a found pair, a control, an unpaired candidate, a garment
    that has actually been photographed. Each appears because somebody decided it should, which is
    why an entry with no provenance record is unfinished work rather than a race with a scheduler.
    """
    expected = {}
    for r in _jsonl("data/external/pairs.jsonl"):
        expected["pair:" + _sha1(r["page_url"], 10)] = "data/external/pairs.jsonl"
    for rel, ns in (("data/external/control_candidates.jsonl", "control"),
                    ("data/external/unpaired_candidates.jsonl", "unpaired")):
        for r in _jsonl(rel):
            expected[f"{ns}:" + _sha1(r["image_url"], 10)] = rel
    # A captured garment becomes a sample the moment photographs of it exist. Until then there is
    # nothing to have rights in, which is why the two intake records in data/garments do not appear.
    for rec_path in sorted(ROOT.glob("data/garments/*/record.json")):
        rec = json.loads(rec_path.read_text())
        if any(rec.get(k) for k in ("before_image_paths", "immediate_after_image_paths",
                                    "post_wash_image_paths")):
            expected["garment:" + rec["garment_id"]] = str(rec_path.relative_to(ROOT))
    return expected


def harvested_record_ids():
    """The harvest queue: images tools/harvest_images.py found and tools/curate_harvest.py labelled.

    Reported, never required. This set grows on a schedule with nobody in the loop, so making it a
    hard gate would either block the harvest or invite auto-generated rights records -- and an
    auto-generated rights record is exactly the comment-that-nobody-reads this file exists to
    replace. Absence of a provenance record is already refusal: a consumer asks the manifest whether
    a sample may be used, and a sample with no record has nothing to be eligible with.
    """
    by_file = {}
    for r in _jsonl("data/external/manifest.jsonl"):
        ext = os.path.splitext(urllib.parse.urlparse(r["url"]).path)[1] or ".jpg"
        by_file[f"{r['source']}_{_sha1(r['url'], 12)}{ext}"] = r
    out = {}
    for c in _jsonl("data/external/curated.jsonl"):
        r = by_file.get(c["file"])
        if r is not None:
            out[f"harvest:{r['source']}_{_sha1(r['url'], 12)}"] = "data/external/curated.jsonl"
    return out


# --------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--json", dest="json_out", default=None,
                    help="write a machine-readable report here")
    ap.add_argument("--strict", action="store_true",
                    help="also require every HAND-CURATED sample (found pairs, controls, unpaired "
                         "candidates, photographed garments) to have a provenance record; the "
                         "harvest queue is reported but does not fail the run")
    ap.add_argument("--quiet", action="store_true", help="print only failures and the summary")
    a = ap.parse_args(argv)

    schema = json.loads(SCHEMA_PATH.read_text())
    records, load_errs = load_manifest(Path(a.manifest))

    for e in load_errs:
        print("MANIFEST ERROR:", e)

    # An empty manifest would make every downstream "is this sample eligible?" question pass by
    # having nothing to answer. data/priors/exclude.txt taught this repository that a silently empty
    # input is worse than a missing one; refuse rather than report a vacuous green.
    if not records and not load_errs:
        print(f"REFUSING: {a.manifest} contains no records. An empty provenance manifest does not "
              f"mean 'everything is fine', it means nothing has been decided -- and every consumer "
              f"of this gate would read the resulting clean exit as permission.")
        return 1

    bad = 0
    seen = {}
    eligible_ids, refusals = [], {}
    for lineno, rec in records:
        rid = rec.get("record_id", f"<line {lineno}>")
        errs = validate_record(rec, schema)
        if rid in seen and isinstance(rid, str):
            errs.append(f"duplicate record_id, first seen on line {seen[rid]}")
        seen[rid] = lineno
        if errs:
            bad += 1
            print(f"{rid}:")
            for e in errs:
                print("   -", e)
            continue
        eligible, reasons = evaluate_eligibility(rec)
        if eligible:
            eligible_ids.append(rid)
        for r in reasons:
            refusals.setdefault(r.split(":", 1)[0], []).append(rid)
        if not a.quiet:
            verdict = "ELIGIBLE" if eligible else "ineligible"
            why = "" if eligible else "  <- " + "; ".join(r.split(":", 1)[0] for r in reasons)
            print(f"{rid}: ok  [{rec['pair_type']}/{rec['sample_kind']}] {verdict}{why}")

    uncovered, unrecorded_harvest = {}, {}
    if a.strict:
        uncovered = {k: v for k, v in expected_record_ids().items() if k not in seen}
        for rid, src in sorted(uncovered.items()):
            print(f"UNCOVERED: {rid} is recorded in {src} but has no provenance record")
        unrecorded_harvest = {k: v for k, v in harvested_record_ids().items() if k not in seen}
        for rid in sorted(unrecorded_harvest):
            print(f"note: {rid} is in the harvest queue with no provenance record, so it is "
                  f"refused by absence and may not be used until one is written")

    n_bad = bad + len(load_errs) + len(uncovered)
    print(f"\n{len(records)} record(s): {len(records) - bad} valid, {bad} invalid, "
          f"{len(eligible_ids)} training-eligible")
    for code in sorted(refusals):
        print(f"  refused for {code}: {len(refusals[code])}")
    if a.strict:
        print(f"  coverage: {len(uncovered)} hand-curated sample(s) with no provenance record; "
              f"{len(unrecorded_harvest)} harvest-queue image(s) unrecorded (refused by absence)")

    if a.json_out:
        out = Path(a.json_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({
            "manifest": os.path.relpath(a.manifest, ROOT),
            "n_records": len(records),
            "n_invalid": bad,
            "n_eligible": len(eligible_ids),
            "eligible_record_ids": sorted(eligible_ids),
            "refusals_by_code": {k: len(v) for k, v in sorted(refusals.items())},
            "uncovered": sorted(uncovered),
            "unrecorded_harvest": sorted(unrecorded_harvest),
            "strict": bool(a.strict),
        }, indent=1) + "\n")

    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())

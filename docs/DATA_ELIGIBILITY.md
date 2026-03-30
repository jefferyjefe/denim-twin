# Data eligibility — which samples may be trained on, and who decides

Before this document existed, nothing in the repository decided eligibility on rights grounds.
Every found pair in `data/external/pairs.jsonl` carries a `license_or_terms` string, every one of
those strings says some version of "all rights reserved", and the batch runner consumed all of them
anyway — because a string no code reads is a comment. Review 2 wrote that down
(`tests/test_review2_licensing.py`) and it stayed written down.

The gate is now three files:

| file | role |
| --- | --- |
| `data/schemas/provenance.schema.json` | what a sample record must say |
| `data/external/provenance.jsonl` | one record per sample |
| `tools/validate_provenance.py` | validates the records and **derives** eligibility from them |

Run it: `python tools/validate_provenance.py` (read-only, offline, stdlib + `jsonschema` only).

`--strict` adds a coverage check over the **hand-curated** sets — every pair in
`data/external/pairs.jsonl`, every control and unpaired candidate, every garment that has actually
been photographed. Those files change only when a person edits them, so an entry with no provenance
record there is unfinished work. The **harvest queue** (`manifest.jsonl`, labelled by
`tools/curate_harvest.py`) is reported separately and does not fail the run: it grows on a schedule
with nobody in the loop, and auto-generating a rights record for every machine-added search hit
would be provenance theatre — the same comment-nobody-reads this gate replaces. Nothing is lost by
that, because **absence of a record is refusal**: eligibility is a property of a record, and a
sample nobody recorded has none to lose.

## The five pair types

A `pair_type` says how the pair came to exist. It is not a quality score; the types are different
kinds of thing, and the difference is what the rule is about.

- **`controlled_physical`** — this project photographed one garment before and after, under
  `protocol/PROTOCOL.md`. The same-garment claim is true by construction, and the project holds the
  copyright in its own photographs.
- **`creator_contributed_physical`** — a real person's real before/after pair, contributed with
  consent. The licence field alone does not make these usable: a person's photographs of their own
  clothes need that person's recorded, current agreement.
- **`licensed_physical`** — a real before/after pair obtained under a licence that permits this use.
  A licence negotiated in writing rather than picked off a shelf is recorded with an SPDX
  `LicenseRef-` identifier pointing at the filed agreement, not squeezed into a sentinel.
- **`synthetic_edit`** — a generated or edited image. **Never admissible as physical evidence**, and
  therefore excluded from every physical-accuracy evaluation in this project. A synthetic edit
  records what a generator did; the question under test is what a garment does. Using one as
  evidence would be scoring a model against another model's output and reporting the number as a
  measurement of cloth.
- **`weak_visual`** — a visually similar pair, or a lone photograph, **not verified** to show the
  same garment. This is the honest home for everything found on the web whose same-garment claim
  rests on the page author's narration rather than on anything checked. It is also where a single
  image goes: a photograph with no second photograph is not a pair of any type.

`sample_kind` runs alongside and says whether the record describes a `before_after_pair` or a
`single_image`. The two are not redundant — a single image can be an excellent segmentation prior
or a negative control, and can never be before/after evidence, however good its licence is.

## `exact_garment` is a tri-state, not a boolean

`verified` / `not_verified` / `known_different`.

A boolean would have to record "nobody checked" as `false`, which is indistinguishable from
"checked, and they are different garments" — or it would default to `true`, which is worse. The
common case for anything harvested is that nobody checked, and that case has to be visible.
`exact_garment_basis` says how the value was arrived at, and a `verified` with an empty basis is
rejected as a defect: a verification nobody wrote down is not a verification.

## The eligibility rule, in plain words

`training_eligible` is **derived, never stored**. `evaluate_eligibility()` in
`tools/validate_provenance.py` returns `(eligible, reasons)`; `reasons` is empty exactly when the
sample is eligible, and every entry reads `<code>: <sentence>` so a refusal always says why. All
failing rules are reported, not just the first.

A sample is eligible as physical before/after evidence only when **all** of these hold:

1. It is a pair. A single image cannot show a change. → `not_a_pair`
2. It is not a synthetic edit. → `synthetic_edit`
3. It is not `weak_visual`. Two pictures of two garments differ for reasons that have nothing to do
   with the modification, so any measured difference is confounded. → `weak_visual`
4. Its `exact_garment` is `verified` — an unverified same-garment assumption is rule 3 wearing a
   better label — and the verification has a written basis.
   → `exact_garment_not_verified`, `exact_garment_known_different`, `exact_garment_basis_missing`
5. `derivatives_allowed` is true. Masks, canonicalised crops, landmark overlays and renders are all
   derivative works, so a NoDerivatives licence is not a partial permission — it blocks the sample
   entirely, including private use. → `derivatives_not_allowed`
6. If the licence is `ALL-RIGHTS-RESERVED`, some other basis for making derivatives is written down.
   The sentinel means the source granted nothing, so the permission has to come from somewhere else
   — normally that the project itself holds the copyright — and `rights.derivatives_basis` has to
   say from where. → `all_rights_reserved_without_derivatives_basis`
7. The licence is not `UNDETERMINED`. That sentinel means the recorded rights statement is not a
   licence identifier at all — a public-domain *status* claim, a licence family with no version, a
   site footer — and no permission follows from an unresolved statement.
   → `license_undetermined`
8. If the licence requires attribution, an attribution string was recorded. A BY licence grants its
   rights *on condition of* attribution; with nothing to attribute, the condition cannot be met.
   → `attribution_missing`
9. If the pair is creator-contributed, consent was obtained and has not been withdrawn.
   → `consent_missing`, `consent_withdrawn`

**What "eligible" does and does not mean.** It means: admissible as evidence about what physically
happens to a garment. It does **not** mean the sample is otherwise useless — a freely licensed
photograph of one pair of jeans is ineligible under this rule and is still perfectly good as a
segmentation prior or pretraining material. The rule governs physical evidence; the licence fields
next to it govern everything else, which is why `commercial_use_allowed` is recorded and
deliberately kept **out** of the rule: this is a research project, and a NonCommercial licence does
not block research use. It is recorded so that a later commercial question has an answer already on
file instead of re-litigating every record.

**Two things a record may not do.** It may not assert its own eligibility: if a record carries
`training_eligible`, the validator recomputes it and rejects any disagreement *in either direction*
— an under-claim is still a stored verdict nobody recomputed. And it may not contradict itself: an
`ALL-RIGHTS-RESERVED` sample that is also `redistributable`, an `UNDETERMINED` licence that is
somehow the source of a permission, a `weak_visual` pair with a `verified` garment, a `single_image`
carrying a physical pair type. Those are defects in the record, reported separately from
ineligibility, because a wrong record must not be able to sit forever looking like a correctly
refused one.

## What the committed manifest currently says

The seed records were derived from what the repository already had —
`data/external/pairs.jsonl`, `control_candidates.jsonl`, `unpaired_candidates.jsonl` and the
harvested images that `curated.jsonl` admitted to the working set — carrying across the licence,
attribution, URL and retrieval facts recorded there and inventing none. Nothing was downloaded.

The result is that **no sample in the repository is currently eligible as physical evidence**, and
that is the honest answer rather than a disappointing one:

- every found tutorial pair states copyright and grants nothing, so it is `ALL-RIGHTS-RESERVED`
  with no basis for derivatives;
- no found pair has had its same-garment claim checked, so `exact_garment` is `not_verified` — the
  vision pass in `data/external/pairs_validation.jsonl` classifies image *role*, never identity;
- the controls, the unpaired candidates and the harvested images are single photographs, so they
  are priors and controls and can never be before/after evidence;
- the two garments in `data/garments/` have no photographs yet, so there is no controlled pair to
  record.

Run `tools/validate_provenance.py` for the current tally rather than trusting a number written here.

Where a harvested image's recorded rights statement does not name one licence — `Public domain`,
`PDM`, `No restrictions`, `Attribution`, a licence family with no version — it is recorded as
`UNDETERMINED` with the verbatim statement preserved in `license_statement`. Several of those are
probably freer than the sentinel implies. Guessing which SPDX identifier the source *meant* would
be inventing a permission, and this file exists to stop that.

## How to add a record

1. Work out the truth first. Which pair type is it *actually*? Was the same-garment claim checked,
   or narrated? What does the source's rights statement literally say?
2. Append one JSON object per line to `data/external/provenance.jsonl`, with:
   - `record_id` — `<namespace>:<local-id>`, where the local id is the identifier the rest of the
     pipeline already uses for that sample: `sha1(page_url)[:10]` for a tutorial pair (the prefix of
     its files under `data/external/pair_images`), `sha1(image_url)[:10]` for a control or unpaired
     candidate, `<source>_sha1(url)[:12]` for a harvested image, the garment id for a captured
     garment. A provenance record that cannot be joined to the artefact it describes gates nothing.
   - `sample_kind`, `pair_type`, `exact_garment`, `exact_garment_basis`.
   - `rights` — `license_id` (an SPDX identifier, a `LicenseRef-` identifier, or one of the two
     sentinels), `license_url`, the verbatim `license_statement`, `attribution`, `rights_holder`,
     and the three booleans. Booleans describe what the **licence** permits; this project's own
     policy is stricter than any of them (`data/external/README.md`: only derived numbers enter the
     repository, no photograph is ever committed) and the two are recorded separately so a strict
     policy is never mistaken for a permission the licence did not give.
   - `provenance` — `source`, `source_url`, `retrieved_at`, `method`, and `recorded_in`: the
     repo-relative file the facts were carried across from, so every field can be checked against a
     committed source rather than believed.
   - `consent` for a creator-contributed pair; `synthetic` for a synthetic edit. The schema requires
     each of them for its pair type.
   - **not** `training_eligible`. It is derived.
3. Run `python tools/validate_provenance.py`. Fix what it names.
4. If a fact is not recorded anywhere, say so — `UNDETERMINED`, `not_verified`, `null` with the
   verbatim statement kept — rather than filling the field with the most likely answer. An
   empty-but-correct manifest is worth more than a populated fictional one.

Never download an image to add a record, and never commit one. The manifest holds facts *about*
photographs; the photographs stay where they are.

# Project status — what is true, what is untested, and what is not claimed

This is the single current source of truth for the project's capability. It is maintained; it is not
a log.

Two other documents look like this one and are not:

- `docs/STATUS.md` is a **step historical log**. Its entries are left as written, with correction
  banners on top, because a record you edit is not a record. Read it for how the project got here.
- `experiments/*/NOTE.md` are **experiment records**, likewise never rewritten. When a later
  experiment overturns an earlier one, the earlier NOTE gets a banner naming the one that overturned
  it, and `tools/experiment_index.py` keeps `experiments/README.md` pointing at both.

Numbers live in `README.md` and in the experiment NOTEs, where `tools/check_claims.py` binds each
one to the artefact it came from and fails the build if the two drift apart. This document
deliberately quotes none of them, so that it cannot rot independently of them.

---

## The two verifications, and why they are not interchangeable

```
python tools/verify.py --profile ci      # hermetic:  no torch, no weights, no photos, no network
python tools/verify.py --profile full    # scientific: everything, over real garment evidence
```

### What a clean-CI pass proves

`--profile ci` is what runs in GitHub Actions on a fresh checkout. That checkout contains no garment
photographs, no masks, no model weights and no credentials — all of them are gitignored, because
`data/external/README.md` permits only derived *numbers* into the repository, and a mask traced from
an all-rights-reserved photograph is a derivative work of it.

A green clean-CI run means:

- the deterministic tests pass without PyTorch, without the SAM checkpoint, without a single
  photograph or mask, and **without touching the network** (`tests/conftest.py` blocks outbound
  sockets for the whole session, so a test that reaches the internet fails loudly instead of
  quietly depending on a third party's uptime);
- every number quoted in the README, the docs and the experiment NOTEs still matches the artefact it
  was derived from (`tools/check_claims.py`);
- every data record validates against its schema, and every **hand-curated sample** -- the found
  tutorial pairs, the controls, the unpaired photos, and every harvested image actually downloaded
  -- has a provenance record whose rights, pair type and exact-garment status are explicit and
  machine-checked (`tools/validate_provenance.py`, `docs/DATA_ELIGIBILITY.md`). The rest of
  `data/external/manifest.jsonl` is a harvest *queue* of image metadata that was never fetched;
  those rows carry no provenance record and are therefore ineligible by absence, which is the
  intended default and not the same as having been checked;
- no file has reached past its phase gate or named a treatment banned in year one
  (`tools/scope_check.py`);
- the sentinel invariants hold, the experiment index is current, and every report whose inputs are
  committed still reproduces from them.

**A green clean-CI run proves nothing whatsoever about physical prediction accuracy.** No garment was
measured. `tools/verify.py` prints that sentence itself, at the end of every ci-profile run, so a
green tick cannot be quoted as a scientific result by anyone who read the output.

### What a full verification proves

`--profile full` additionally runs everything that needs real evidence: the segmentation path, the
pair bench, the mask-derived reports and every test that compares an algorithm against a real
photograph.

It is the profile that can **refuse**. Each check declares the evidence it needs in
`src/denimtwin/prereqs.py`; if any of it is absent, `verify.py` names every missing artefact, prints
the exact command that would satisfy it, and exits **2** — a distinct code from 1, because "we could
not run this" and "this failed" are different sentences and demand opposite responses (go and take a
photograph, versus go and fix the code). Under this profile a test whose declared evidence is missing
is a **failure**, not a skip: a scientific claim may not be issued over data that is not there.

A full pass is still bounded by what those checks measure. It is not a claim that the system predicts
denim.

---

## What works

- **Product path** (`tools/predict.py`) — one flat-lay photo plus a cut specification produces three
  renders, a pixel diff, the cut as structured parameters, and a fringe-depth interval. No after-photo
  and no ground truth required. It runs end to end and every number it emits is labelled with where
  it came from.
- **Evaluation path** (`tools/run_pair.py`) — before + after photo → mask → landmarks → canonical warp
  → cut → fringe → registration of the real after-photo → scoring against null baselines, one command
  per pair, with bad inputs rejected by reason rather than silently.
- **Batch, aggregation and priors** — `run_pairs_batch.py`, `report_pairs.py`, `fit_fringe.py`
  (leave-one-out, scale-free).
- **Data intake** — found-pair manifest with a CLIP role check, a GitHub issue form and
  `ingest_submissions.py` for contributed pairs, and a rights/provenance manifest that gates
  training-eligibility (`docs/DATA_ELIGIBILITY.md`).
- **Verification** — one command, one exit code, two honestly separated profiles.

## What is validated

Validated here means: measured, reproducible from committed inputs, and bound to a claim check.

- The **geometric and numerical machinery**: canonical round-trip, landmark stability, registration
  fold detection, the cut and wash transforms, the fringe gate, the null baselines, unit handling and
  interval provenance. These have regression tests, and where a test compares against real masks it
  now declares that dependency rather than passing vacuously without them.
- The **negative results**, which are the most reliable findings the project has. In particular
  fringe *depth* is not measurable from this evidence (EXP_0015/0016), and the long-published
  "dead heat with crop-only" comparison was void — the null was built from the model's own keep mask,
  so the prediction was being compared with itself (EXP_0034). Both are recorded in the README and
  their NOTEs with the numbers attached.

## What is experimental

- **Interval calibration.** The product path emits an 80% fringe-depth interval that is **not
  calibrated**. Treat it as a range, not a probability.
- **Template v1**, the boundary-Chamfer refinement — mixed A/B, opt-in only.
- **Registration on shorts**, which is underdetermined: the leave-one-out residual is large enough
  that per-pair conclusions drawn from it should not be trusted without a second method.
- Anything reached through `--wash median`, which alters kept pixels by design and therefore falls
  outside the gate that says nothing outside the cut changes.

## What is synthetic

- The wash and fringe **renders** are generated imagery, not photographs of a washed garment.
- Samples ingested through `tools/editgarment_adapter.py` (see `docs/EDITGARMENT.md`) are labelled
  `pair_type: synthetic_edit`, which `tools/validate_provenance.py` derives as never
  training-eligible. A generated "after" image is evidence about a generator, not about denim.
  Note what this does and does not currently do: the rule *derives* the refusal, and
  `tests/test_editgarment_adapter.py` runs the real gate over real adapter output to prove it. It
  is not yet *enforced at the point of consumption* -- `tools/run_pairs_batch.py` still selects
  pairs from `pairs_validation.jsonl` without consulting the manifest. Wiring that in would today
  exclude the entire found-pair set (all 131 records derive ineligible, correctly), which would
  stop every existing experiment from reproducing, so it is deliberately a separate, argued change
  rather than a side effect of this one. Until it lands, the manifest is a validated gate that
  nothing downstream reads.
- Tests that need a garment silhouette build one in-process. A synthetic mask is a fine way to test
  that a transform is arithmetically correct and is **not** a substitute for a real one; the tests
  that need real masks say so.

## What is blocked by missing physical data

This is the project's actual bottleneck, and it is a data problem rather than a code problem.

- **No controlled physical pair exists yet.** Nobody has photographed one specific pair of jeans,
  cut it, washed it once under `protocol/PROTOCOL.md`, and photographed it again. Every pair the
  system has been scored on is a *found* tutorial pair: two photographs that are probably, but not
  verifiably, the same garment, under uncontrolled lighting, at unknown scale.
- Because of that, **exact-garment status is `not_verified` for the entire found-pair set**, and the
  provenance manifest refuses those samples training-eligibility on exactly that ground.
- Consequently: no claim in this repository about *physical* prediction accuracy is supported. The
  measured comparisons say the pipeline renders a **supplied** cut height well. They do not say the
  system knows where to cut, because the cut height is measured from the real after-photo.

## The next real-world milestone

**One controlled physical pair, captured end to end under the frozen protocol** — the same garment,
photographed before, cut, washed once, photographed after, with a scale reference in frame and the
capture QA checks passing.

That single pair is worth more than any number of found pairs, because it is the first sample whose
`exact_garment` status can honestly be `verified`, and it is the first evidence that could make a
`--profile full` run mean what it says. Until it exists, the honest summary of this project is: the
machinery is built and tested, and the physics is unmeasured.

Contributions of real before/after pairs are welcome — see `CONTRIBUTING_PAIRS.md`.

---

## Reproducing this

`docs/REPRODUCIBILITY.md` has the exact commands and the pinned environments for both profiles.

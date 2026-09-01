# denim-twin — one-page research brief (DRAFT)

**Question.** Can a system reconstruct a specific pair of denim jeans from
consumer phone images and predict how that exact garment will look after
being cut into jorts and washed once?

**Why it's hard.** Identity preservation, geometry reconstruction, topological
editing, material modeling, physical validation, calibrated uncertainty.
Generative editors change the garment; apparel CAD assumes patterns and
measured materials.

**Approach.** Hybrid: geometry controls what changes, a procedural/physical
model constrains the outcome, a learned residual adds detail only in the
affected region. Every prediction is scored against the real modified garment.

**What I own.** Capture pipeline, paired dataset (50 garments, garment-level
splits, locked test set), annotations, baselines, evaluation infrastructure.

**Where I need guidance.** Simulation-ready garment reconstruction from
flat-lay captures; physically meaningful evaluation of raw-edge fraying.

**Ask.** A 30-minute meeting; potential independent study or collaboration.

**Status (this step).** Working 2D pipeline: phone/found photo → SAM garment mask → mask-derived landmarks →
canonical TPS space → cut (angled, per leg) → procedural fringe (density band, SAM-segmented fringe on real
after-photos) → registration of the real after-photo → metrics vs null baselines (no-op, crop-only). On 6 found
before/after pairs the cut geometry is reproduced automatically (silhouette IoU 0.75–0.95, hem error 7–31 px);
nothing outside the cut changes (Gate 2). Fringe depth is *not yet* predictable held-out (1 real fray pair; EXP_0008)
and prediction intervals are uncalibrated (EXP_0009). Data channel: found tutorial pairs are exhausted (32 pages →
7 usable); a contributor pipeline (GitHub issue form with a coin for scale) is live and verified. 51 tests, CI,
three adversarial reviews. Repo: https://github.com/jefferyjefe/denim-twin (docs/STATUS.md, docs/PLAN_PROGRESS.md).

**Specific questions.** (1) Registration of a re-laid cut garment onto its uncut photo with ≤6 surviving landmarks:
TPS + SIFT gives 50–160 px leave-one-out residual on 500-px images — what is the right non-rigid registration prior
for a flat-laid garment? (2) A landmark model for flat-laid jeans from ~50 silhouettes: statistical shape model vs
learned detector with so little data? (3) What minimal measurement of a frayed hem (depth profile? thread density?)
would a textile scientist consider a valid target?

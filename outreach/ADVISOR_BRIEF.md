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

**Status.** [update after pilot: N garments captured, first cut/wash, baseline metrics]

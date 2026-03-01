# denim-twin

A material-aware digital twin for a specific pair of denim jeans.

**Frozen research question (v1):**

> Can a system reconstruct a specific pair of denim jeans from consumer phone
> images and predict how that exact garment will look after being cut into
> jorts and washed once?

Scope v1: denim only, straight cuts, raw hems, one standardized wash/dry cycle.

**Data (online-only variant, see charter amendment):** found tutorial pairs (`data/external/pairs.jsonl`),
CC-licensed unpaired images (`manifest.jsonl`), and crowd-sourced pairs — **[contribute yours](CONTRIBUTING_PAIRS.md)**.

See `docs/CHARTER.md` for the full project charter, `protocol/PROTOCOL.md`
for the physical experimental protocol, and `docs/PLAN.md` for the 12-month plan.

## Layout

    docs/         charter, plan, literature map, risk register
    protocol/     capture / cut / wash / measurement procedures (frozen before data collection)
    data/         garments/<GARMENT_ID>/ records; schemas/ for validation
    src/          python package `denimtwin`
    tools/        scripts: new garment, validate record, capture checker
    experiments/  one directory per experiment, each with a NOTE.md
    notes/weekly/ weekly experiment notes (hypothesis / setup / result / next)
    outreach/     advisor brief, slides

## Setup

    python3 -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt

## Models
Download the SAM ViT-B checkpoint (375 MB, not in git):

    mkdir -p models && curl -L -o models/sam_vit_b_01ec64.pth https://dl.fbaipublicfiles.com/segment_anything/sam_vit_b_01ec64.pth


## Predict on a new pair of jeans (the product path)
One flat-lay photo plus a cut specification; no after-photo, no ground truth needed:

    python tools/predict.py --image jeans.jpg --out out/ --inseam-fraction 0.35 --wash median
    python tools/predict.py --image jeans.jpg --out out/ --target-inseam-cm 12 --coin us_quarter --angle-deg 6

Writes three renders (conservative / median / aggressive), `diff.png` (exactly which pixels changed),
`modification.json` (the cut as structured parameters) and `prediction.json` (interval + provenance).
Put a coin in the frame if you want any answer in centimetres.

## Status (2026-08-29, honest)
- Product path (`tools/predict.py`): one photo + a cut spec → three renders + an 80% fringe-depth interval, every
  number labelled with where it came from. It runs end-to-end; its fringe prior has **n=3**, its intervals are
  **not calibrated** (EXP_0009 coverage 0/10), and — since EXP_0015 — its fringe depth rests on **no validated
  measurement at all**. The outputs say so.
- Evaluation path (`tools/run_pair.py`): before + after photo → mask → landmarks → canonical warp → cut → fringe →
  register the real after-photo → score against null baselines. One command per pair; bad inputs rejected with a reason.
- On 11 usable found pairs, mean silhouette IoU: **0.768 product path** (what a user gets), 0.819 evaluation path
  (which reads the real after-photo), 0.507 no-op — so the cut *is* reproduced, but the honest number is the first one
  (EXP_0014). **Fringe measurement is broken** (EXP_0015): SAM's prompted "fringe" mask returns the bottom third of the
  fabric, and a direct thread measurement, though visually correct, scores a cuffed hem the same as a frayed one. Every
  fringe number in the repo predates that check. The **fringe render** is invisible to silhouette IoU (0.768 vs 0.771 crop-only) but does beat it on the
  fringe-specific metric (fringe IoU 0.17 vs 0.00) — that measures overlap with a fringe whose depth was read off the
  after-photo, and held out through the prior it is still not predictive (EXP_0008); wash shrinkage cannot even be measured from found photos (EXP_0013). Appearance parameters stay frozen
  until ≥5 new pairs (`docs/GATES.md` tuning rule).
- Data: 32 found tutorial pages → 6 cut pairs + 1 fray pair; that channel is exhausted (EXP_0005/0007).
  Contributed after-wash photos with a coin in frame are the only lever left (`CONTRIBUTING_PAIRS.md`).
- Automation: local launchd jobs work (`ops/`); cloud routines never executed in this environment (`tools/agents/README.md`).
- Tests: 99 + 1 xfail (`pytest -q tests`), CI green; fresh-clone verified without ML deps (`reports/repro/`).

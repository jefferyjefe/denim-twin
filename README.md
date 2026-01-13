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

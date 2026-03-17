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
  number labelled with where it came from. It runs end-to-end; its intervals are **not calibrated**, and its fringe
  depth rests on **no validated measurement at all** — depth was withdrawn as evidence after five reviews (EXP_0015).
  The only sourced fray depth is 12.7 mm, from a tutorial that stitched a stop 1/2 in above the cut and reported the
  fray reaching it after one wash. Every prediction says all of this in its own output.
- Evaluation path (`tools/run_pair.py`): before + after photo → mask → landmarks → canonical warp → cut → fringe →
  register the real after-photo → score against null baselines. One command per pair; bad inputs rejected with a reason.
- On the 7 pairs `data/priors/exclude.txt` allows, mean silhouette IoU: **0.823 product path** (what a user gets),
  0.857 evaluation path (which reads the real after-photo), and 0.823 crop-only null. **That last comparison is
  void** (EXP_0034): `compare.py` builds the crop-only null from the `--keep` mask it is handed, and `score_predict.py`
  hands it *predict's own* keep mask, so the "null" crops at the cut line the model predicted. The bench runs
  `--wash none`, every prediction records `fringe_depth.median = 0.0`, and the two masks are consequently the same
  object — median IoU 0.99954, the null never keeps a pixel the prediction drops, and on one pair they are
  bit-identical. The "dead heat with cropping" reported here for months was the prediction compared with itself.
  Against a null that does **not** see the model — the cut placed at the leave-one-out median inseam fraction of the
  other pairs — the product path scores **0.8232 against 0.7278, an advantage of +0.0954 (±0.0197, 4.8σ), winning 6
  of 7**. That is not evidence the system predicts where to cut: its only per-garment input is the inseam fraction,
  and `run_pair.py:263` measures that from the real after-photo. It shows the pipeline renders a *supplied* cut
  height far better than not knowing it. Silhouette IoU is still dominated by the kept region both systems copy
  pixel-for-pixel. (EXP_0027/0028, recomputed twice: EXP_0014's 0.768/0.819/0.771
  was over 11 pairs, four of which `exclude.txt` bans, and the harness was uprighting each photo a second time.)
  The remaining 0.857-against-0.823 gap is **not** the cut specification and **not** the renderer: hand the product
  path the exact cut region and it **matches** the evaluation path (0.8735 against 0.8750, EXP_0028/0029). What it
  lacks is knowledge of where the cut goes. Separately, `canon/warp.py` fitted two independent TPS maps, so
  image→canonical→image was off by a median of 10.7 px over the garment — fixed by iteration (0.02 px), though **no
  production path used that direction**, so it changed 0 pixels (EXP_0030). What *does* reach the pipeline is the
  forward map **folding** — over 40.1% and 37.2% of two of the seven garments — which `predict.py` now detects and
  refuses above 20%, with a re-shoot instruction. On the found-pair set that is 2 of 7 garments refused. **Fringe DEPTH is not measurable here** (EXP_0015/0016): SAM's prompted mask returns the bottom third of the fabric;
  a direct thread measurement returns garment-mask error, displaced shadows and patterned floors as "fringe"; and
  resolution does not help, because the mask-error floor scales with the image. Depth is therefore no longer used as
  evidence anywhere. **Hem roughness** (`eval/hem_texture.py`) is the fray signal that does survive its control —
  0 false positives on 9 high-resolution finished-hem garments *in one photograph each*, reliable above ~600–1000 px
  of waistband (EXP_0016) — but **that result does not survive a re-capture**: re-encoding the same photo flips the
  verdict on 6 of 16 photos and makes 2 of those 9 controls read frayed (EXP_0021). `p90 > 0` is exactly
  `rough_fraction > 0.10`, so the detection limit is a fray touching a tenth of the hem, against finished hems that
  already deviate on up to 7.3% of columns. The fringe renderer's score on it is **retracted, twice** (EXP_0017): the
  comparison measured the real hem on a mask warped into the prediction's frame, and that warp inflates its roughness
  six-fold. Measured where nothing resampled it, **6 of the 7 real hems read exactly zero** — at 241-389 px of
  waistband they are below the resolution the statistic needs, so there was never a signal to score against
  (EXP_0025). The **fringe render** is invisible to silhouette IoU (0.768 vs 0.771 crop-only — and that crop-only
  figure is one of the void comparisons above) but does beat it on the fringe-specific metric (fringe IoU 0.17 vs 0.00) — that measures overlap with a fringe whose depth was read off the
  after-photo, and held out through the prior it is still not predictive (EXP_0008); wash shrinkage cannot even be measured from found photos (EXP_0013). Appearance parameters stay frozen
  until ≥5 new pairs (`docs/GATES.md` tuning rule).
- Data: 32 found tutorial pages → 6 cut pairs + 1 fray pair; that channel is exhausted (EXP_0005/0007).
  Contributed after-wash photos with a coin in frame are the only lever left (`CONTRIBUTING_PAIRS.md`).
- Camera tilt (EXP_0022/0023): the pipeline now uprights every photo (`canon/upright.py`), not only those tilted more
  than 8°, and it reads the **near-vertical** principal axis — reading the long axis meant a flat-laid pair of shorts
  (wider than tall) came back at ~±88° and was never corrected at all. Effect on repeatability: the shape ratios' swing
  at 8° of tilt goes **29.6% → 0.5%**. On the pairs: IoU 0.8365 → 0.8566, hem error 13.3 → 7.9 px, with **one pair
  regressing past the bench tolerance** (443d1d4658) — recorded, not tuned away. EXP_0037 confirmed the cause exactly
  (disabling uprighting on that pair reproduces the frozen baseline: IoU 0.9180 against 0.918, hem 8.92 against
  8.916 px) and **disconfirmed the mechanism this line used to give**. "Because before and after are uprighted
  independently" predicts that the relative rotation between the two photos drives the error; it does not
  (**r = +0.092**, and `2b0123d732` at 23.5° of relative rotation — nearly three times this pair's 8.4° — has the
  second-*best* hem error in the set). A hem-angle-symmetry diagnostic was tried and fails the same way
  (r = +0.213). The mechanism is **currently unknown**, and uprighting stays on: it is justified by a directly
  measured defect and improves the mean, and one pair does not outweigh that.
- **Fray scores are not trustworthy at the precision they were quoted (EXP_0024).** Hem roughness counts pixel-scale
  deviations of the hem boundary, and rotating a mask creates them: at 8°, 12 of 12 finished-hem controls read as
  frayed, median false p90/waist 0.00194 — the size of EXP_0017's whole quantity and five times its margin. The real
  mask is warped into the prediction's frame and the prediction is not, so the artefact points the same way as the
  result. `hem_roughness(resampled=True)` now marks such numbers `valid_for_fray: false`. EXP_0016's 0-false-positive
  control result is unaffected: those masks were never resampled.
- Segmentation and repeatability (EXP_0021): **consensus segmentation** (`--seg consensus`, now on both `run_pair.py`
  and `predict.py`) is the setting that survives a re-capture. Change nothing but a photo's JPEG quality or exposure
  and SAM's best-scoring mask returns a *different object* on 16 of 96 tries; consensus does so on 0, and when it is
  unsure it refuses and says which filter refused. The one same-garment pair in the dataset agrees to 8% on rise/waist
  under consensus, against 4.58x on waist width under best-score — the EXP_0018 Gate 1 failure was segmentation.
  What is **not** repeatable is one level up: the landmark heuristic loses >5% at 1–8° of camera tilt (an exact
  silhouette loses 33% at 8°), and the fray verdict flips on 6 of 16 photos under a JPEG re-encode — including 2 of
  the 9 finished-hem controls. Every number comes from a *simulated* re-capture and therefore **bounds our error from
  above**; two real photographs of one garment would settle it, and we have never had a pair.
- Automation: local launchd jobs work (`ops/`); cloud routines never executed in this environment (`tools/agents/README.md`).
- Tests: 247 + 6 xfail (`pytest -q tests`), CI green; fresh-clone verified without ML deps (`reports/repro/`).
  Reviews 2–6's findings are all in the suite; the review-5/6 files were local-only until EXP_0021 and are now tracked.

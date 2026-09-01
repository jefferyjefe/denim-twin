> **CORRECTED step 16 (review 6).** The first version was computed on a subject set that included two pairs banned
> by the project's own `data/priors/exclude.txt` — one of them excluded for having *two overlapping garments in the
> after photo*, precisely the failure this experiment is about — and on web samples a later, stricter wash-count gate
> removed. `tools/experiment_resolution.py` now honours `exclude.txt`. Everything below is recomputed and some
> conclusions changed. The reviewer verified the original *arithmetic*; the fault was in what it was computed on.

# EXP_0016 — resolution, and a fray signal that survives its control

EXP_0015 ended with "fringe depth cannot tell a frayed hem from a cuffed one". Two follow-up questions: is that a
resolution problem, and is there a different observable that does work? Method: take the same photos, re-segment and
re-measure at scales 1.0 → 0.15, split into **frayed** (raw cut, washed) and **control**
(cuffed/hemmed, which cannot have a fringe). After the exclusions the clean set is **2 frayed and 3 control
garments** — 25 measurements, but few subjects.

## 1. Resolution does not rescue the depth measurement
The hoped-for asymmetry was "the mask-boundary floor is a fixed few pixels while the fringe scales with resolution".
Fitting depth against waist width across all scales says otherwise:

    frayed  depth_px = 0.0082 * waist_px + 0.38   (r = 0.96, n = 11 rows / 2 garments)
    control depth_px = 0.0047 * waist_px + 0.88   (r = 0.79, n = 14 rows / 3 garments)

**The floor scales too**, at 58% of the signal's rate: both are proportional to the image, because the error comes
from SAM's mask and not from the sensor. Resolution buys roughly a factor 1.7 in signal-to-floor and no more. Before
the correction this looked like 80% and no separation at all; with the banned pairs dropped the separation is real but
small (0.0035 of waist width) between lines fitted to 2 and 3 garments. Either way it does not rescue depth as a
measurement — EXP_0015 Part F withdrew it for independent reasons.

## 2. Hem roughness does separate them
A finished hem is a *smooth curve*: its mask boundary deviates from its own local median by nothing at all. A frayed
hem is jagged over a few pixels. `eval/hem_texture.hem_roughness` measures exactly that (p90 of |y − median-filtered y|
over the hem region, window 6% of waist width). At native resolution:

| garment | group | waist px | roughness p90 |
|---|---|---|---|
| pair:f542c57cec | frayed | 2801 | **9.0 px** |
| web:c2a0e6e4 | frayed | 1406 | 3.0 |
| web:eac3449d | frayed | 1078 | 3.0 |
| web:b0576a16 | frayed | 874 | 4.0 |
| pair:f9c0e56308 | frayed | 911 | 1.0 |
| pair:4bfef03bd7 | frayed | 334 | 1.0 |
| web:821bfe4c | frayed | 1433 | 0.0 (miss) |
| web:35bda9db | frayed | 375 | 0.0 (miss) |
| pair:8d9f0df4ad | **control** | 914 | **0.0** |
| pair:443d1d4658 | **control** | 357 | **0.0** |
| pair:2b0123d732 | **control** | 290 | **0.0** |

Across all 61 (garment, scale) measurements: **0 false positives on controls (0/14)**, and frayed detection rises with
resolution —

| waist width in the photo | frayed detected | control false positives |
|---|---|---|
| < 300 px | 2/17 | 0/9 |
| 300–600 px | 6/13 | 0/3 |
| 600–1000 px | **9/10** | 0/2 |
| 1000–1600 px | 3/5 | 0/0 |
| > 1600 px | 2/2 | 0/0 |

So roughness is **specific but resolution-limited**. After the correction the clean subject set is 2 frayed and 3
control garments, far too few for the per-band table to carry weight; it is kept only to show the shape of the effect.
The durable specificity evidence is the high-resolution control set in the addendum, measured with consensus
segmentation rather than with these masks.

## What this changes
- **The contributor ask becomes a number.** A whole-garment photo is useful for fray if the waistband spans ≥ ~800 px
  (any phone shot from ~1 m does this); the hem close-up remains the reliable route. *(Stated in `CONTRIBUTING_PAIRS.md`
  as of this correction — review 6 caught that the earlier note claimed this before it was written there.)*
- **Fray detection is possible today; fray *depth* is not.** We can say "this hem is frayed" (0 false positives) well
  before we can say "the fringe is 4 mm deep". Any near-term claim should be about presence and roughness, not depth.
- No parameter was fitted to this data: the window (6% of waist) and hem region (lower 40%) are fixed and were chosen
  before the split was examined. n is 8 frayed and 3–4 control garments — enough to falsify "depth works", not enough
  to calibrate roughness. A high-resolution control set is being harvested to test the 0-false-positive claim harder.

## Caveats
The controls are cuffed garments from the paired set and are systematically lower-resolution than the frayed set; the
zero-false-positive result therefore rests on 14 measurements over waist 31–914 px, not on high-resolution controls.
That is the single most important gap in this experiment.

## Addendum (same day) — high-resolution controls, and the gate they forced
The caveat above ("the controls are systematically lower-resolution than the frayed set") was the right thing to worry
about. Nine finished-hem (all *hemmed*, turned-and-topstitched) denim shorts flat-lays at 2048–2500 px were harvested
specifically as controls, and measured:

| (consensus segmentation, no gate) | photos | measured | called rough (false positives) |
|---|---|---|---|
| high-resolution finished hems (waist 994–1366 px) | 9 | 9 | **0** |
| frayed + washed (harvested) | 7 | 7 | 4 |

**Two of the nine initially read as frayed (p90 4.0 px each — an earlier draft said "4 and 8"), and they were
segmentation failures, not hems.** Both
photos are of strongly patterned/bleached denim where SAM dropped large blobs of the leg; the roughness sat exactly on
the ragged edges of those holes. That is a false positive of the kind that would have quietly become "fray detected"
in a contributor pipeline.

A contour-compactness gate was introduced here to refuse those two masks (3.96 and 4.05 against ≤ 2.10 for every other
photo) — and **it has since been removed**. Review 6 showed compactness is a *garment-shape* statistic, not a mask-quality
one: an exact, noise-free silhouette scores 2.33 for shorts and **3.95 for full-length jeans**, so the threshold refused
the project's own subject; and because a frayed outline is longer, compactness rises with fray depth (2.33 → 4.13 as
notch depth goes 0 → 16 px), making the "gate" a silent fray-depth cutoff. It was a rule read off 21 photos, and it was
wrong.

What replaced it is **consensus segmentation** (EXP_0019), which fixes the two broken masks at source. Measured that
way: **0 of 9 high-resolution controls read as frayed, with no gate at all, and 4 of 7 frayed garments are detected.**

One class remains untested: every high-resolution control is a *hemmed* edge. A rolled cuff casts a fold shadow that a
flat hem does not, and no cuffed flat-lay above 1200 px could be found (retail shoots hemmed; cuffed examples live on
sewing blogs at lower resolution).

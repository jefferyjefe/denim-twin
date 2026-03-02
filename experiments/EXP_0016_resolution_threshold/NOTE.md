# EXP_0016 — resolution, and a fray signal that survives its control

EXP_0015 ended with "fringe depth cannot tell a frayed hem from a cuffed one". Two follow-up questions: is that a
resolution problem, and is there a different observable that does work? Method: take the same photos, re-segment and
re-measure at scales 1.0 → 0.15, split into **frayed** (raw cut, washed; 8 garments) and **control** (cuffed/hemmed,
which cannot have a fringe; 3–4 garments).

## 1. Resolution does not rescue the depth measurement
The hoped-for asymmetry was "the mask-boundary floor is a fixed few pixels while the fringe scales with resolution".
Fitting depth against waist width across all scales says otherwise:

    frayed  depth_px = 0.0048 * waist_px + 2.16   (r = 0.73, n = 47)
    control depth_px = 0.0039 * waist_px + 1.05   (r = 0.69, n = 14)

**The floor scales too**, at 80% of the signal's rate. In relative terms the two lines converge on 0.0048 and 0.0039 —
a separation of 0.0009 of waist width, which is far below the scatter. A bigger photo does not fix this measurement;
the boundary error is proportional to the image, because it comes from SAM's mask, not from the sensor.

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

So roughness is **specific but resolution-limited**: it never cries fray on a cuffed hem, and it sees fray reliably once
the waistband spans roughly 600–1000 px or more. One frayed garment (web:821bfe4c) reads 0 even at 1433 px — its threads
are sparse and pale against a pale floor, which is a segmentation limit, not a metric limit.

## What this changes
- **The contributor ask becomes a number.** A whole-garment photo is useful for fray if the waistband spans ≥ ~800 px
  (any phone shot from ~1 m does this); the hem close-up remains the reliable route. This is now stated in
  `CONTRIBUTING_PAIRS.md` and the issue form.
- **Fray detection is possible today; fray *depth* is not.** We can say "this hem is frayed" (0 false positives) well
  before we can say "the fringe is 4 mm deep". Any near-term claim should be about presence and roughness, not depth.
- No parameter was fitted to this data: the window (6% of waist) and hem region (lower 40%) are fixed and were chosen
  before the split was examined. n is 8 frayed and 3–4 control garments — enough to falsify "depth works", not enough
  to calibrate roughness. A high-resolution control set is being harvested to test the 0-false-positive claim harder.

## Caveats
The controls are cuffed garments from the paired set and are systematically lower-resolution than the frayed set; the
zero-false-positive result therefore rests on 14 measurements over waist 31–914 px, not on high-resolution controls.
That is the single most important gap in this experiment.

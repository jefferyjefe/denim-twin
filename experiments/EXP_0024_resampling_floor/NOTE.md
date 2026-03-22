# EXP_0024 — Hem roughness measures the resampler

> **Partly superseded by EXP_0034.** The resampling result stands; any margin quoted here against
> the crop-only null does not — that null is built from the model's own keep mask.


Hem roughness is the only fray observable in this project that has ever passed a negative control: 0 false positives
on 9 high-resolution finished-hem garments (EXP_0016), and it is what EXP_0017 scores the fringe renderer on. It works
by measuring how far the garment's lower boundary deviates from its own local median, **in pixels**.

A binary mask rotated by anything other than a multiple of 90° has a boundary that steps up and down by a pixel.
That is the same quantity.

Every mask in the evaluation path is resampled at least once before this metric sees it. `tools/compare.py:28` warps
the real after-photo's mask into the prediction's frame (`warp_after_to_before`) — registration is a rotation and a
scale — and since EXP_0022/0023 the pipeline also uprights every photograph. The prediction's silhouette, by contrast,
is *synthesised* in that frame and carries no such artefact.

## The measurement (`tools/experiment_resample_floor.py`)

Twelve of the sixteen reference masks read p90 = 0 unrotated — a finished hem, no deviation anywhere. Rotate them and
nothing else:

| rotation | how many of the 12 now read FRAYED | median p90 / waist among those |
|---|---|---|
| 0.5° | 0 | — |
| 1° | 1 | 0.00201 |
| 2° | 3 | 0.00186 |
| 3° | 7 | 0.00185 |
| 5° | 11 | 0.00226 |
| **8°** | **12 of 12** | 0.00234 |

Bilinear resampling with a 0.5 threshold does not rescue it (28 of 72 readings fire instead of 34): the artefact is
the pixel grid, not the interpolation kernel.

## Why this matters more than it looks

The median false roughness a rotation creates is **0.00194** in units of p90 / waist width (34 of 72 readings fire; the rest leave the hem reading zero).

EXP_0017's headline is a mean |roughness error| of **0.00194** for the prediction against **0.00231** for the
crop-only null — a margin of 0.00037. **The artefact is the size of the whole quantity, and five times the margin.**

Worse, it has a direction. The real mask is warped and the prediction is not, so the real hem is measured as rougher
than it is. A system that renders *some* roughness therefore scores closer to it than one that renders none — and
"renders some roughness against a null that renders none" is exactly the comparison EXP_0017 makes. The artefact
points the same way as the result.

This does not prove EXP_0017's ordering is wrong. It shows the experiment cannot distinguish its result from its
resampler, which is the same thing as having no result at that precision.

## What changed
- `eval/hem_texture.hem_roughness` takes `resampled=`. It does not change the arithmetic; it marks the output
  `valid_for_fray: False` and says why, so a number computed on a warped mask can never be quoted as fray evidence
  by accident.
- `tools/compare.py` passes `resampled=True` for the real mask — the one that is warped — and every `metrics.json`
  now records `hem_rough_valid_for_fray: false`.
- EXP_0016's control result is **unaffected**: those nine controls were measured on masks straight out of
  segmentation, in their own frame, with no warp. That is exactly why they read zero.

## What this asks for next
The comparison needs both systems in the frame where the real mask was segmented, or both resampled identically.
Neither is a small change to `run_pair`, and neither should be attempted by adding a correction term to a metric that
is measuring a grid artefact.

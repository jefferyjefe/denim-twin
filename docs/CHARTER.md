# Project Charter — denim-twin

## Research question (FROZEN)

Can a system reconstruct a specific pair of denim jeans from consumer phone
images and predict how that exact garment will look after being cut into jorts
and washed once?

## Input specification

- Guided phone captures of flat-laid denim jeans on the controlled rig:
  - front + back overhead
  - four obliques per side
  - close-ups: hem, seams, pockets, existing distressing
  - care label
  - short motion clip (fabric lifted and released)
  - calibration board / fiducial in frame for metric scale
- User-defined cut: straight cut line in canonical garment coordinates, or a
  target inseam in cm.
- Wash/dry protocol: the single standardized cycle in `protocol/PROTOCOL.md`.

## Output specification

1. Immediate post-cut render (same view as capture).
2. Predicted post-wash render (median).
3. Uncertainty range: conservative / median / aggressive fray renders.
4. Difference map: exactly which pixels changed from the original capture.
5. Quantitative comparison against real post-modification captures
   (cut location, silhouette, unchanged-region identity, color, texture, fray).

## Claims v1 WILL make

- Preserves identity of the specific garment outside the modified region.
- Cut appears where the user requested (measured in mm).
- Post-wash raw hem prediction beats simple baselines on physical matching.
- Prediction intervals are calibrated.

## Claims v1 will NOT make

- Non-denim fabrics; arbitrary tailoring; bleach/dye/acid/chemical distressing;
  exact single-outcome guarantees; multi-month wear; sewing patterns;
  replacement of apparel CAD.

## Success after one year

Paired dataset ≥50 garments; reproducible protocol; identity-preserving
renderer; geometry-aware cut; material-conditioned fray prediction; calibrated
ranges; locked-test-set evaluation; baselines + ablations; demo; report.

## Principle

Build the smallest system that makes a falsifiable prediction, then compare it
with reality. Every added layer must improve the measured prediction.

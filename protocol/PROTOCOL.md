# Physical Experimental Protocol — v0.1 (DRAFT, freeze after pilot)

Fields marked `[FILL]` must be decided and written down before the first
garment is cut. Once frozen, any deviation is recorded in `protocol_deviations`.

## 0. Garment intake
1. Assign next ID `DENIM_NNNN` via `tools/new_garment.py`. IDs are permanent.
2. Record acquisition source, price, brand (optional), style.
3. Photograph care label; transcribe fiber composition and elastane %.
4. Measurements (cm, tape measure, garment flat, two readings each, record both):
   waist (flat, doubled), front rise, inseam (crotch seam to hem, inside leg),
   leg opening (flat, doubled), fabric thickness (mm, caliper, at lower leg
   single layer), mass (g, kitchen scale).
5. Annotate existing damage: location, type, size.

## 1. Capture rig
- Background: `[FILL]` (matte, non-reflective, solid color contrasting denim).
- Calibration board: printed ChArUco `[FILL: square size mm]`, placed in every frame.
- Lighting: two diffuse sources at ~45°, `[FILL: model/setting]`.
- Camera: `[FILL: phone model]`, overhead mount height `[FILL] cm`, locked exposure/WB.
- Lay protocol: garment front-up, waistband at top, legs `[FILL: spread / parallel, gap cm]`,
  smoothed by hand, no pins.

## 2. Capture set (per state: before / immediate-after / post-wash)
| shot_id | description |
|---|---|
| F00 | front overhead |
| B00 | back overhead |
| FL1–FL4 | front, left side obliques at ~30°, 4 positions along length |
| FR1–FR4 | front, right side obliques |
| BL1–BL4 / BR1–BR4 | back obliques |
| D01+ | details: each hem, each pocket, fly, existing damage (macro, with ruler) |
| LBL | care label |
| MOT | 5–10 s clip: lift lower leg ~10 cm, release |

Reject and retake if: garment cropped, uneven lighting, motion blur, board missing.

## 3. Cut definition
1. Define cut digitally: target inseam `[per garment]` cm, straight, perpendicular to inseam.
2. Transfer to garment: measure from crotch seam along inseam, mark both legs
   with fabric chalk, connect to outseam with straightedge.
3. Photograph marked garment (state `marked`).
4. Cut: legs cut **separately**, garment flat, tool `[FILL: fabric shears model]`,
   single continuous stroke where possible. Operator name recorded.
5. Capture state `immediate-after`.
6. Retain cut-off leg sections, labeled, for fabric measurements.

## 4. Wash / dry (FROZEN, one cycle)
- Machine: `[FILL: make/model, location]`
- Cycle: `[FILL: name]`, water temp `[FILL] °C`, spin `[FILL]`
- Detergent: `[FILL: brand]`, `[FILL] ml`
- Load: this garment + `[FILL: N standard filler towels]`
- Dryer: `[FILL: make/model]`, setting `[FILL]`, duration `[FILL] min`
- Conditioning: lay flat, room temp, `[FILL] hours` before capture.

## 5. Fray measurement (post-wash)
- Positions: every `[FILL: 2]` cm along each hem, front and back, starting at inseam.
- At each position, macro photo with ruler; measure:
  - fray depth: hem edge of intact weave → tip of longest thread (mm)
  - thread count within a `[FILL] mm` window
  - edge curl: max vertical lift of hem from flat surface (mm)
- Two annotators on ≥20% of garments; record both.

## 6. Repeatability (pilot only)
- Capture DENIM_0001 five times with full re-lay between captures; measure
  landmark consistency.
- Wash two pilot garments twice under identical protocol; measure fray-metric
  noise floor.

## 7. Offcut swatches (added 2026-08-28)
Retained lower-leg sections carry a raw edge identical to the garment's. Label each
`<GARMENT_ID>_OFFCUT_L` / `_R`, photograph before washing, then assign wash conditions:
- Default: one offcut follows the standard §4 protocol; the other follows the garment's
  actual wash condition (control for scrap-vs-garment equivalence).
- Garments whose care label forbids machine washing (e.g. painted prints) are washed per
  label; the standard-protocol data point comes from the offcut.
- Measure fray on offcuts exactly as in §5. Record `offcut_wash` in the garment record.

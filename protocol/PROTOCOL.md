# Physical Experimental Protocol — v0.1 (DRAFT, freeze after pilot)

Fields marked `[FILL]` must be decided and written down before the first
garment is cut. Once frozen, any deviation is recorded in `protocol_deviations`.

## 0. Garment intake
1. Assign next ID `DENIM_NNNN` via `tools/new_garment.py`. IDs are permanent.
2. Record acquisition source, price, brand (optional), style.
3. Photograph care label; transcribe fiber composition and elastane %.
4. Measurements (cm, tape, garment flat, two readings each; record both in `measurement_readings`,
   store the mean in `*_cm`): waist (top edge of waistband, flat ×2), front rise (crotch seam to top
   of waistband along the fly), back rise, inseam (crotch seam to hem, inside leg), thigh (2.5 cm
   below crotch, flat ×2), leg opening (hem, flat ×2), fabric thickness (mm, caliper closed under
   its own spring, single layer, lower leg, 3 spots averaged), mass (g, kitchen scale).
5. Annotate existing damage: location, type, size.

## 1. Capture rig
- Background: `[FILL]` (matte, non-reflective, solid color contrasting denim).
- Calibration board: printed ChArUco `[FILL: square size mm]`, placed in every frame.
- Lighting: two diffuse sources at ~45°, `[FILL: model/setting]`.
- Camera: `[FILL: phone model]`, overhead mount height `[FILL] cm`, locked exposure/WB.
- Lay protocol: garment front-up, waistband at top, legs `[FILL: spread / parallel, gap cm]`,
  smoothed by hand, no pins.
- Board placement: on the same surface plane as the garment, same corner of the frame every time.
  Reject rule for every shot: `board_corners >= 12` from `tools/check_capture.py`. Record `mm_per_px`
  and corner count in the garment record.
- Background: prefer a dark, matte, saturated colour (e.g. dark green) — light-wash denim on a light
  backdrop is hard to segment.

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
1. Define cut digitally: target inseam `[per garment]` cm. **Cut definition (frozen): a straight line
   perpendicular to the leg's centre line (midline between inseam and outseam) in the canonical
   frame, passing through the inseam at the target length.** This is what the software cuts; it is
   NOT 'square to the inseam'. Record both inseam and outseam lengths after cutting.
2. Transfer to garment: leg laid straight and flat; measure target length from crotch seam along the
   inseam and mark; measure the same distance from the crotch seam along the outseam **plus the
   digital outseam offset printed by the tool**; connect the two marks with a straightedge.
   A second person verifies both marks with a tape (tolerance ±3 mm) before cutting.
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
- Positions: every 2 cm around each hem loop, starting at the inseam seam and travelling toward
  the front of the leg first (front panel, then back panel). Positions numbered from 1.
- At each position, macro photo with ruler; measure:
  - fray depth: hem edge of intact weave → tip of longest thread within ±5 mm of the position (mm)
  - thread count within a `[FILL] mm` window
  - edge curl: garment laid front-up after §4 conditioning; max vertical lift of the hem edge from
    the surface within ±5 mm of the position (mm)
- Two annotators on ≥20% of garments; record both.

## 6. Repeatability (pilot only)
- Capture one pilot garment five times with full re-lay between captures; measure landmark
  consistency (any garment; DENIM_0002 preferred — DENIM_0001 is hand-wash-only).
- Wash two machine-washable pilot garments twice under identical protocol; measure
  fray-metric noise floor. Offcuts (§7) may serve as the repeat-wash samples.

## 7. Offcut swatches (added later)
Retained lower-leg sections carry a raw edge identical to the garment's. Label each
`<GARMENT_ID>_OFFCUT_L` / `_R`, photograph before washing, then assign wash conditions:
- Default: one offcut follows the standard §4 protocol **in the same load as the garment**; the
  other is washed in a separate standard load (repeat-wash noise sample). If the garment's wash
  deviates from §4, the second offcut follows the garment's condition instead (scrap-vs-garment
  control). Alternate which leg (L/R) gets which condition across garments to avoid confounding.
- Garments whose care label forbids machine washing (e.g. painted prints) are washed per
  label; the standard-protocol data point comes from the offcut.
- Measure fray on offcuts exactly as in §5. Record `offcut_wash` in the garment record.

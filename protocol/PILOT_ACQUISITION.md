# Pilot Acquisition List (5–6 garments)

Buy **used** where possible (Grailed / eBay / Depop / thrift). Record source and
price. Brand is a shopping aid only — material fields come from the care label
and physical measurement.

| Slot | Stratum | Candidate | Tests |
|---|---|---|---|
| 1 | Rigid 100% cotton, dark, heavyweight (~15 oz) | Momotaro 0705 / 0905 | clean heavyweight baseline |
| 2 | Rigid/low-stretch, light or faded, heavily worn | RRL slim/straight, washed or used | existing-fade preservation |
| 3 | High-stretch (≥2% elastane), skinny | Acne North/Peg, or Levi's 510/511 stretch | stretch behavior at cut |
| 4 | Painted / distressed / repaired details | Evisu painted seagull, or repaired used pair | logo/paint/damage preservation |
| 5 | Thin / lightweight (≤11 oz) | Naked & Famous Weird Guy lightweight or stretch selvedge | thin-fabric fray |
| 6 | Cheap control, medium wash | Thrifted Levi's 501 | what real users own |

Per garment on arrival: photograph care label, weigh, caliper thickness,
then `tools/new_garment.py` and fill `record.json`.

## Auxiliary data (not paired; priors only)
- DeepFashion2 for segmentation/landmark pretraining.
- Deep Fashion3D / CLOTH3D for template/3D priors.
- Marketplace listing photos only via official APIs or manual small sets (ToS).

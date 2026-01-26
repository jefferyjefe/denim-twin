# EXP_0006 — Measuring real fringe coverage profiles from found after-wash hems (negative result)

**Goal:** fit rawedge_v1's coverage_at_edge / falloff from real hems instead of guessing.
**Inputs:** It's Always Autumn (one-wash and several-wash hem close-ups), Magnolia Mamas after-wash, pair1's registered hem.
**Tool:** tools/measure_fringe.py (per-column fabric edge + fringe tip from Lab distances to top-rows 'body' and bottom-rows 'background').

| hem | depth px | coverage@edge | falloff k | verdict |
|---|---|---|---|---|
| IAA one-wash close-up | — | — | — | no edge found |
| IAA several-wash close-up | 12 | 0.007 | −2.1 | wrong (edge lands on the fringe tip) |
| Magnolia after-wash | 230 | 0.55 | −0.02 | wrong (entire image classified as fringe) |
| pair1 registered hem | 5 | 0.0 | −1.7 | wrong (black remap border read as background) |

## Read
Two-colour-reference segmentation is not enough: real hems have textured floors, shadows, indigo-and-white threads
and, for registered images, remap borders. Needs (a) a fabric/fringe/background classifier (SAM point prompts on the
hem, or CLIP-seg) and (b) an explicit hanging-direction estimate. Parked until there are more hem images;
rawedge_v1 keeps its guessed parameters, labelled as such.

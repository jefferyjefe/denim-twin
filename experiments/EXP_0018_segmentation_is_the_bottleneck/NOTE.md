# EXP_0018 — Segmentation, not the fray metric, is what actually limits us

Two photographs of the *same garment* were available in the harvested set (a front and a back view of one pair of
acid-wash cut-offs). Running the pipeline on both is the closest thing to Gate 1's "capture the same garment
repeatedly and measure consistency" that an online-only project can do. It failed, and the reason turned out to be the
foundation everything else stands on.

## The repeatability test
| photo | waist width found | rise/waist | hem roughness p90 |
|---|---|---|---|
| front (img_4536) | 874 px | 0.660 | 5.0 px |
| back (img_4540) | **191 px** | **1.424** | 0.0 px |

The back view returns a garment 4.6× narrower with a nonsense rise ratio. Looking at the overlay explains it: SAM
segmented **one back pocket**, not the shorts — a mask covering 4.4% of the frame, returned with score **0.906**.
Elsewhere in the same set, an earlier run segmented **the pale board above the garment** instead of the garment, at
score **0.992**. Both then produced fringe depths and roughness values, and both would have entered the prior.

**SAM's confidence does not detect this**, and neither does contour compactness (EXP_0016's gate), which only sees
ragged outlines — the wrong object can have a clean one.

## Automatic gates tried, and why each failed
| check | catches | fails on |
|---|---|---|
| mask area / width fraction | the pocket (4.4%) | nothing else |
| contour compactness > 3 | the two speckled masks in EXP_0016 | the pocket (1.75) and the board (2.96) both pass |
| denim colour fraction | the board (8% denim-coloured) | rejects legitimate pale/undyed denim (0%, 10%, 21% on real controls) |
| fabric texture vs backdrop | nothing reliably | ratio 1.54 and 2.43 on the two bad masks vs 2.01–3.43 on good ones — overlapping |
| leg topology (2 runs low) / crotch notch depth | nothing reliably | the board's ragged bottom scores a 0.157 "notch"; real garments span 0.039–0.230 |

No single-image heuristic we tried separates "this is the garment" from "this is a confident mistake".

## What we did instead
Human verification is now a **requirement for entering a prior**. `tools/mask_sheet.py` renders every mask over its
photo; `data/external/mask_verdicts.json` records, per file, the verdict *and what was seen*; `ingest_unpaired.py`
refuses anything unverified (`mask_unverified`) or rejected (`mask_rejected`). All seven harvested photos are now
verified — five good, one pocket-mask rejected, one is a full-length pair of jeans rather than shorts. At this dataset
size that costs a few minutes and removes a whole class of silent error; it will need automation before the dataset is
large, and that is a real research task, not an oversight.

## What this does to the earlier results
- The **prior's five unpaired samples all come from verified masks** — checked after the fact, and they pass.
- EXP_0016's roughness result is unaffected in direction (its controls were re-verified) but its precision claims
  inherit this: a metric computed on an unverified mask means nothing at all, whatever its own control says.
- Gate 1 remains **unmet**, and now for a stated reason: the pipeline is not repeatable across two photos of one
  garment, because segmentation is not repeatable. That is the honest blocker to write in the gate.

# EXP_0020 — Sixth adversarial review: what it broke, and what is left standing

Review 6 attacked the roughness metric, its gates, and the review-5 response: 26 failing tests, 12 findings. Several
demolished work written the same day. Recorded here because the pattern matters more than any single fix.

## Findings acted on
| # | finding | response |
|---|---|---|
| 1 | the **compactness gate is a garment-shape statistic**: an exact silhouette scores 2.33 (shorts) but **3.95 (full-length jeans)**, so the 3.0 bound refused the project's own subject; and compactness rises with fray depth (2.33 → 4.13 for 0 → 16 px notches), making the gate a silent fray cutoff | **gate removed**; compactness reported only. Broken masks are handled at source by consensus segmentation (EXP_0019) and human verification (EXP_0018) |
| 2 | **EXP_0017's numbers matched nothing in the artefacts** (11 pairs → 7 decidable; 0.91/1.27/1.55 px → 0.43/1.00/1.00; 6-3-2 at p=0.51 → 4-1-2 at p=0.375), and README and STATUS each quoted a different version again | experiment **retracted and restated**; all three documents corrected |
| 3 | **EXP_0016 was computed on two pairs `exclude.txt` bans** — one of them excluded for having two overlapping garments in the after photo, the exact failure the experiment is about | `experiment_resolution.py` honours `exclude.txt`; every number recomputed (the floor scales at 58% of the signal's rate, not 80%) |
| 4 | `p90 == 0` means "fewer than 10% of hem columns deviate", not "finished hem" | `rough_fraction` is reported alongside it everywhere, and the module says so |
| 5 | a smooth **scalloped** hem reads as fray at 1–2 px, inside the frayed garments' range | documented as an accepted limitation: this is a spatial-frequency statistic, not a fray detector |
| 6 | the `after_cut` prior was **five rule outputs served as a prior** (every value forced by the finished-hem rule), and the n<5 warning had become unreachable once pooling raised the counts | rule rows are excluded from the pool — `after_cut` is now n=0 and the prediction says so; the flag fires at n=0 and n<5 |
| 7 | the one-wash gate was added to the channel supplying 1 sample, not the one supplying 5; `"washes"` blocked a legitimate single-wash note; `"fray" not in note` accepted "did not fray" | gates moved to the real channel, polarity fixed, and **an explicit singular is now required** |
| 8 | `aliases_for` keyed on the raw URL, which Shopify `?v=` cache-busters and `_1024x1024` size suffixes defeat | URLs canonicalised (query dropped, size suffixes stripped) before matching |
| 11 | **nine all-rights-reserved retailer JPEGs were committed to git**, against this repo's own stated policy | untracked and gitignored within the hour; only derived numbers remain |

## The cost, stated plainly
Requiring an explicit "one wash" in the evidence takes the harvested unpaired channel from **7 candidates to 1 usable
sample**, and the after-wash prior from n=5 to **n=2**. That is not a regression; five of those pages simply never say
how many times they washed the garment, and this project predicts exactly one. The evidence was always this thin — the
gate stopped us rounding it up.

## What survived the attack
The reviewer verified, and could not break:
- **consensus segmentation** fixing all five known mask failures, and the compactness *separation* the removed gate
  originally rested on (3.96/4.05 against ≤2.10) — it is real, it just is not a validity test;
- **hem roughness on a real finished hem is extremely robust**: p90 stayed 0.0 across 19 perturbations — busy backdrops
  (σ 4/9/18), a garment-toned low-contrast backdrop, shadows flush with and 6/14 px below the hem, rotations to 30°,
  JPEG quality down to 12, and 15–30% hem occlusion;
- every regression fit and per-band table in EXP_0016 reproduced exactly from its own `rows.json` — the fault was the
  subject set, not the arithmetic.

## The lesson worth keeping
Four of the twelve findings are the same mistake: **a number was written into a note, and then the code or data it came
from changed underneath it.** `tests/test_exp0015_claims.py` was review 5's answer to that — it parses a note and checks
it against the artefacts it cites. It existed for one experiment. It now exists as
infrastructure: `tools/check_claims.py` re-derives each annotated claim from the artefact it cites, and
`tests/test_experiment_claims.py` runs it in the suite, so a note that drifts from its data fails CI. Six claims are
annotated today (EXP_0015, EXP_0018); the list grows with each experiment that quotes a number.

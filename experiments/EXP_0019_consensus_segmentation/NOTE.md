# EXP_0019 — Consensus segmentation: ask the prompts to agree instead of asking SAM how sure it is

EXP_0018 established that SAM's confidence is worthless as a validity signal (a back pocket at 0.906, a wall panel at
0.992, half a garment at 0.99) and that five automatic mask checks all fail on at least one real photo. This tries a
different question: not "how good is this mask?" but **"do independent prompts find the same object?"**

`seg/validate.segment_garment_consensus` runs 8 prompt-point sets, collects every plausible candidate, clusters them by
IoU ≥ 0.7, and returns the cluster found by the most *distinct prompt sets*, with `agreement` = that fraction. It can
refuse (`min_agreement`). Two boundary choices: `median` (per-pixel majority of the cluster) or `member` (the winning
cluster's highest-scoring single mask — identity from the vote, detail from one mask).

## It fixes every known failure
| photo | best-score mask | consensus |
|---|---|---|
| de6740d5b9 | **one back pocket** (4.4% of frame, score 0.906) | whole garment, agreement 1.00 |
| f41d64c01b | garment **plus the pale board above it** | garment only, agreement 0.62 |
| 00d0c4704c | **one leg** of the shorts | whole garment, agreement 1.00 |
| 7b0a1ceaaf | speckled, holes through the leg (compactness 3.96) | clean garment, compactness 1.62 |
| dbde5e4083 | speckled (compactness 4.05) | clean garment, compactness 1.70 |
Verified by eye on the overlays. On the photos whose best-score mask was already correct, consensus agrees with it at
IoU 0.98–0.995 — it changes what was broken and leaves what worked.

## Effect on the fray result (7 harvested frayed, 9 high-resolution finished-hem controls)
| segmentation | frayed detected | control false positives | needs the compactness gate? |
|---|---|---|---|
| best-score (EXP_0016) | 6/8 | 2/9 before the gate, 0/7 after | yes |
| consensus, `median` boundary | 3/7 | **0/9** | no — every mask scores 1.55–1.87 |
| consensus, `member` boundary | **4/7** | **0/9** | no |

The median boundary is the most robust mask and the *worst* for this measurement: averaging the cluster smooths exactly
the hem raggedness that fray detection reads. `member` keeps the vote's identity and one mask's detail, and is the
setting to use for texture work. Even so, sensitivity is lower than best-score's — a fair reading is that some of the
old 6/8 was boundary noise on masks that were partly wrong.

## Status
Consensus is implemented and tested (`tests/test_seg_consensus.py`) but **not yet wired into `run_pair`/`predict`** —
that changes every rendered output and every bench number, so it needs its own A/B against the frozen baseline. The
unpaired/measurement path is where the failures actually bit, and human mask verification (EXP_0018) still gates it.

The honest headline: **0 false positives across 9 high-resolution controls with no gate, and the two catastrophic
object-identity failures gone.** The cost is fray sensitivity, which was partly illusory to begin with.

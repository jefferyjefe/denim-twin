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

## The failure it introduces: plain studio backdrops
Run over the paired set, consensus **loses two pairs it should keep**, and the reason is the mirror image of SAM's:
on a plain white studio sweep every prompt agrees on the **backdrop**, so the vote elects the white field around the
garment (agreement 0.88 on 4bfef03bd7 — our only fray pair — and 1.00 on 2b0123d732). Requiring candidates not to touch
the frame border (which `segment_garment_coarse` already penalised) does not fix it: the sweep does not reach the edges.

Preferring the more denim-coloured cluster fixes 4bfef03bd7 and **breaks a light-wash pair** (2691c1a8d0, denim
fraction 0.14). That is threshold-fitting on sixteen photos, so it is **not applied**; `denim_frac` is reported in
`info` instead, and the rule stays out of the code. This is the tuning rule doing its job.

## On the paired batch (opt-in, `--seg consensus`)
| | best-score | consensus |
|---|---|---|
| usable pairs | 10 | 9 (gains 2e2063b93f, loses 2b0123d732 and 4bfef03bd7) |
| mean silhouette IoU (8 common) | 0.816 | **0.838** |
| mean hem error (8 common) | 59.2 px | **54.6 px** |
Biggest single gain: 2691c1a8d0, IoU 0.615 → 0.843 and hem error 47.5 → 23.9 px.

## Status
Consensus is implemented and tested (`tests/test_seg_consensus.py`) but **not yet wired into `run_pair`/`predict`** —
that changes every rendered output and every bench number, so it needs its own A/B against the frozen baseline. The
unpaired/measurement path is where the failures actually bit, and human mask verification (EXP_0018) still gates it.

The honest headline: **0 false positives across 9 high-resolution controls with no gate, all five catastrophic
object-identity failures fixed, and better geometry on the pairs it can handle (IoU 0.816 → 0.838)** — against a new
failure mode on plain studio backdrops that costs us the only fray pair we have. Neither method dominates; that is why
consensus is opt-in and human mask verification remains the gate.

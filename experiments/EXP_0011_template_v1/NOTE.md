# EXP_0011 — Template v1 (boundary-Chamfer, landmark-initialised) as landmark refinement

Synthetic: autolm 6.6 px → v1 3.9 px (boundary resid 0.9 px). Grailed: 92 → 100 px vs hand clicks (resid 2.8 px; the hand clicks are themselves loose). Batch A/B below (same pairs, same everything except landmark refinement).

```
--- heuristic
| b630a78c19 | How To Make Jeans Into Shorts The Easy W | after_cut | ok | 0.47 / 0.46 / 0.54 | 333 / 368 | 18.2 / 17.4 | 0.18 / 0.58 |
| 4bfef03bd7 | DIY Denim Shorts | Thrifted Jeans Into S | after_wash | ok | 0.77 / 0.75 / 0.29 | 16 / 22 | 22.9 / 23.3 | 0.35 / 0.04 |
| 8d9f0df4ad | This summer's DIY cut-off jeans shorts-- | after_cut | ok | 0.95 / 0.94 / 0.42 | 8 / 9 | 21.0 / 21.5 | 0.31 / 0.02 |
| 443d1d4658 | Create Kids Couture: Upcycle Old Jeans i | after_cut | ok | 0.92 / 0.92 / 0.59 | 14 / 13 | 18.5 / 18.3 | 0.14 / 0.00 |
| 2691c1a8d0 | Jeans Upcycling: Shorts aus alter Jeans  | after_cut | ok | 0.69 / 0.69 / 0.58 | 33 / 27 | 16.8 / 15.1 | 0.33 / 0.10 |
| 26b1041d00 | Upcycle Jeans Into Shorts - Sewing Novic | after_cut | ok | 0.75 / 0.69 / 0.73 | 31 / 46 | 30.7 / 34.8 | 0.30 / 0.48 |
| f542c57cec | DIY High Waisted Denim Shorts, Step-by-S | after_wash | ok | 0.72 / 0.68 / 0.51 | 108 / 128 | 29.2 / 26.8 | 0.26 / 0.22 |
| e97924ad2d | Doodlecraft: How to Upcycle Jeans into B | after_cut | ok | 0.90 / 0.90 / 0.54 | 7 / 7 | 11.2 / 11.0 | 0.24 / 0.01 |
| 2b0123d732 | Adventures in Dressmaking: "We need to l | after_cut | ok | 0.85 / 0.85 / 0.66 | 11 / 11 | 15.8 / 15.5 | 0.32 / 0.02 |
| 4c30342e20 | [pair] TEST submission (pipeline dry run | after_wash | ok | 0.86 / 0.85 / 0.28 | 44 / 47 | 22.2 / 23.6 | 0.24 / 0.04 |
--- + v1
| b630a78c19 | How To Make Jeans Into Shorts The Easy W | after_cut | ok | 0.52 / 0.44 / 0.53 | 247 / 364 | 20.8 / 21.5 | 0.64 / 0.64 |
| 4bfef03bd7 | DIY Denim Shorts | Thrifted Jeans Into S | after_wash | ok | 0.74 / 0.73 / 0.28 | 22 / 24 | 24.8 / 25.3 | 0.28 / 0.03 |
| 8d9f0df4ad | This summer's DIY cut-off jeans shorts-- | after_cut | ok | 0.94 / 0.94 / 0.43 | 10 / 11 | 19.4 / 19.9 | 0.28 / 0.02 |
| 443d1d4658 | Create Kids Couture: Upcycle Old Jeans i | after_cut | ok | 0.92 / 0.92 / 0.61 | 13 / 12 | 15.8 / 15.6 | 0.17 / 0.01 |
| 2691c1a8d0 | Jeans Upcycling: Shorts aus alter Jeans  | after_cut | ok | 0.69 / 0.69 / 0.58 | 33 / 27 | 16.8 / 15.1 | 0.33 / 0.10 |
| 26b1041d00 | Upcycle Jeans Into Shorts - Sewing Novic | after_cut | ok | 0.75 / 0.69 / 0.73 | 31 / 46 | 30.7 / 34.8 | 0.30 / 0.48 |
| f542c57cec | DIY High Waisted Denim Shorts, Step-by-S | after_wash | ok | 0.72 / 0.68 / 0.51 | 108 / 128 | 29.2 / 26.8 | 0.26 / 0.22 |
| e97924ad2d | Doodlecraft: How to Upcycle Jeans into B | after_cut | ok | 0.93 / 0.93 / 0.58 | 5 / 6 | 11.2 / 11.0 | 0.38 / 0.01 |
| 2b0123d732 | Adventures in Dressmaking: "We need to l | after_cut | ok | 0.67 / 0.67 / 0.62 | 52 / 53 | 16.5 / 16.2 | 0.15 / 0.11 |
| 4c30342e20 | [pair] TEST submission (pipeline dry run | after_wash | ok | 0.87 / 0.84 / 0.28 | 35 / 52 | 22.1 / 24.1 | 0.30 / 0.04 |
```

## Verdict
Mixed on the 7 real pairs: hem error better on Doodlecraft (7→5 px), Kids Couture (14→13), test pair (44→35); worse
on Thrifted & Taylor'd (16→22) and clearly worse on Adventures in Dressmaking (11→52 — the fit slid the outline along
a soft boundary on concrete). Boundary residual is small everywhere, i.e. v1 fits the *silhouette* well but silhouette
fit does not pin landmark *semantics*. Not adopted as default (`--refine-landmarks` stays opt-in). Per the tuning rule,
this A/B on 7 pairs is the evidence; a statistical shape model with a learned landmark prior is the next Phase 3 step,
and it needs more pairs.

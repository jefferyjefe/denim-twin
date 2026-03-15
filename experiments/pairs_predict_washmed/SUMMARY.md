| pair | state | product IoU | eval IoU | crop-only IoU | product hem | eval hem |
|---|---|---|---|---|---|---|
| 2691c1a8d0 | after_cut | 0.719 | 0.736 | 0.719 | 19.0 | 11.5 |
| 26b1041d00 | after_cut | 0.877 | 0.899 | 0.877 | 8.9 | 3.0 |
| 2b0123d732 | after_cut | 0.780 | 0.847 | 0.780 | 30.8 | 3.8 |
| 443d1d4658 | after_cut | 0.851 | 0.857 | 0.851 | 30.2 | 27.7 |
| 4bfef03bd7 | after_wash | 0.800 | 0.807 | 0.800 | 10.2 | 4.5 |
| 8d9f0df4ad | after_cut | 0.882 | 0.958 | 0.883 | 38.5 | 3.2 |
| e97924ad2d | after_cut | 0.864 | 0.893 | 0.864 | 7.5 | 1.3 |

**mean over 7 pairs** — product IoU 0.825, evaluation IoU 0.857, crop-only IoU 0.825; product hem 20.7 px, evaluation hem 7.8 px

> **crop-only IoU is not an independent baseline.** `compare.py` builds it from the `--keep` mask this script hands it, which is predict's OWN keep mask, so it crops at the cut line the model predicted. With `--wash none` the fringe is 0.0 px and the two masks are the same object (median IoU 0.99954). Do not report the product path as beating or tying it. Use `--loo-null` for a baseline that does not see the model (EXP_0034).

**independent (leave-one-out) null** — product IoU 0.8248, LOO-null IoU 0.7278, advantage **+0.0970**, product wins 6 of 7

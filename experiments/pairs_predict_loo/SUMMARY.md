| pair | state | product IoU | eval IoU | crop-only IoU | product hem | eval hem |
|---|---|---|---|---|---|---|
| 2691c1a8d0 | after_cut | 0.719 | 0.733 | 0.719 | 19.5 | 12.4 |
| 26b1041d00 | after_cut | 0.877 | 0.899 | 0.877 | 8.9 | 3.0 |
| 2b0123d732 | after_cut | 0.779 | 0.838 | 0.779 | 30.8 | 7.2 |
| 443d1d4658 | after_cut | 0.872 | 0.898 | 0.872 | 22.9 | 7.5 |
| 4bfef03bd7 | after_wash | 0.789 | 0.807 | 0.789 | 11.6 | 4.5 |
| 8d9f0df4ad | after_cut | 0.880 | 0.956 | 0.880 | 39.9 | 4.0 |
| e97924ad2d | after_cut | 0.864 | 0.893 | 0.864 | 7.5 | 1.3 |

**mean over 7 pairs** — product IoU 0.825, evaluation IoU 0.861, crop-only IoU 0.826; product hem 20.1 px, evaluation hem 5.7 px

> **crop-only IoU is not an independent baseline.** `compare.py` builds it from the `--keep` mask this script hands it, which is predict's OWN keep mask, so it crops at the cut line the model predicted. With `--wash none` the fringe is 0.0 px and the two masks are the same object (median IoU 0.99954). Do not report the product path as beating or tying it. Use `--loo-null` for a baseline that does not see the model (EXP_0034).

**independent (leave-one-out) null** — product IoU 0.8255, LOO-null IoU 0.7302, advantage **+0.0953**, product wins 7 of 7

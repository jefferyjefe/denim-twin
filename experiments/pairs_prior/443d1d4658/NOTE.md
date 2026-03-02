# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 2.0px in the after frame (rel 0.0056, coverage 0.53); SAM/hem-fit said 7.8px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_prior/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from prior[after_cut] (n=4 after excluding self, INSUFFICIENT) [suppressed: finished hem]; measured on after-photo: 1.9 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 11.4°, depth 14 px, right: angle -11.3°, depth 2 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 6.42px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.918 | 8.9 | 18.2 | 0.008 |
| pred median | 0.918 | 8.9 | 18.2 | 0.013 |
| pred aggressive | 0.918 | 8.9 | 18.2 | 0.020 |
| null:no-op | 0.587 | 240.7 | 21.4 | 0.005 |
| null:crop-only | 0.918 | 8.9 | 18.3 | 0.000 |

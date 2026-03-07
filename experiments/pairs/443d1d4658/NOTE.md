# PAIR — auto pipeline

flags: before: rotated -3.6° to upright; after: touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 2.0px in the after frame (rel 0.0056, coverage 0.53); SAM/hem-fit said 8.0px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 1.9 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 9.8°, depth 14 px, right: angle -9.9°, depth 2 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 7.57px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.909 | 8.1 | 18.3 | 0.039 |
| pred median | 0.909 | 8.1 | 18.3 | 0.045 |
| pred aggressive | 0.909 | 8.0 | 18.3 | 0.116 |
| null:no-op | 0.581 | 240.9 | 21.1 | 0.005 |
| null:crop-only | 0.909 | 8.1 | 18.4 | 0.000 |

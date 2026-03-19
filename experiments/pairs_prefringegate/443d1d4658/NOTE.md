# PAIR — auto pipeline

flags: before: rotated -3.6° to upright; after: rotated 4.8° to upright; fringe measured directly: 5.0px in the after frame (rel 0.0138, coverage 0.64); SAM/hem-fit said 47.5px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_prefringegate/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 4.7 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 25.4°, depth 1 px, right: angle -8.6°, depth 16 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 7.88px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.856 | 27.7 | 18.2 | 0.002 |
| pred median | 0.857 | 27.7 | 18.2 | 0.003 |
| pred aggressive | 0.857 | 27.5 | 18.2 | 0.010 |
| null:no-op | 0.571 | 236.1 | 17.5 | 0.089 |
| null:crop-only | 0.856 | 27.8 | 19.1 | 0.000 |

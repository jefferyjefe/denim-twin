# PAIR — auto pipeline

flags: before: rotated -3.6° to upright; after: rotated 4.8° to upright; fringe mask ignored for the hem fit: edge_treatment 'cuffed' cannot fray; fringe measured directly: 5.0px in the after frame (rel 0.0138, coverage 0.64); SAM/hem-fit said 47.5px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_hemmask/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 4.7 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 25.2°, depth 1 px, right: angle -7.5°, depth 0 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 7.88px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.903 | 5.0 | 18.1 | 0.024 |
| pred median | 0.903 | 5.0 | 18.1 | 0.052 |
| pred aggressive | 0.903 | 4.9 | 18.1 | 0.144 |
| null:no-op | 0.571 | 245.7 | 21.6 | 0.004 |
| null:crop-only | 0.903 | 5.0 | 18.2 | 0.000 |

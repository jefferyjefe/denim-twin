# PAIR — auto pipeline

flags: before: rotated 0.9° to upright; after: rotated -1.9° to upright; fringe measured directly: 4.0px in the after frame (rel 0.0112, coverage 0.64); SAM/hem-fit said 12.2px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_hybrid/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 3.8 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle 19.2°, depth 1 px, right: angle -11.5°, depth 3 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 7.15px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.922 | 7.6 | 16.4 | 0.025 |
| pred median | 0.922 | 7.6 | 16.4 | 0.028 |
| pred aggressive | 0.923 | 7.5 | 16.4 | 0.072 |
| null:no-op | 0.587 | 243.1 | 18.6 | 0.010 |
| null:crop-only | 0.922 | 7.7 | 16.6 | 0.000 |

# PAIR — auto pipeline

flags: before: rotated -23.5° to upright; fringe measured directly: 2.0px in the after frame (rel 0.0069, coverage 0.91); SAM/hem-fit said 8.1px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_before_07ba40f3.JPG 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2b0123d732_after_cut_23fa579b.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -20.0°, depth 1 px, right: angle 54.9°, depth 5 px
registration residual (leave-one-landmark-out): 76.77px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.847 | 3.8 | 15.6 | 0.031 |
| pred median | 0.847 | 3.8 | 15.6 | 0.044 |
| pred aggressive | 0.847 | 3.9 | 15.6 | 0.075 |
| null:no-op | 0.664 | 113.1 | 19.6 | 0.025 |
| null:crop-only | 0.847 | 3.9 | 15.5 | 0.000 |

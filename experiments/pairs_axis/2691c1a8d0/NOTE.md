# PAIR — auto pipeline

flags: after: rotated -8.8° to upright; fringe measured directly: 4.0px in the after frame (rel 0.0105, coverage 1.00); SAM/hem-fit said 2.2px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 3.0 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -20.9°, depth 1 px, right: angle 6.5°, depth 1 px
registration residual (leave-one-landmark-out): 47.58px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.736 | 11.5 | 18.5 | 0.005 |
| pred median | 0.736 | 11.5 | 18.5 | 0.010 |
| pred aggressive | 0.736 | 11.5 | 18.5 | 0.036 |
| null:no-op | 0.577 | 171.5 | 20.2 | 0.022 |
| null:crop-only | 0.736 | 11.5 | 18.4 | 0.000 |

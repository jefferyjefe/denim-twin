# PAIR — auto pipeline

flags: before: rotated -3.9° to upright; after: rotated -8.3° to upright; before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts; fringe measured directly: 4.0px in the after frame (rel 0.0118, coverage 1.00); SAM/hem-fit said 3.2px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 4.8 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 0.2°, depth 2 px, right: angle -16.7°, depth 4 px
registration residual (leave-one-landmark-out): 138.42px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.558 | 86.6 | 16.7 | 1.000 |
| pred median | 0.558 | 86.6 | 16.7 | 1.000 |
| pred aggressive | 0.558 | 86.6 | 16.7 | 0.000 |
| null:no-op | 0.547 | 171.9 | 17.1 | 0.000 |
| null:crop-only | 0.558 | 86.6 | 16.7 | 1.000 |

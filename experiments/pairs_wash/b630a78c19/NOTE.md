# PAIR — auto pipeline

flags: before: rotated 1.4° to upright; after: rotated -10.7° to upright; SAM fringe mask rejected: median depth 254px > 15% of garment height 1190px; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 397545 px changed; fringe measured directly: 7.0px in the after frame (rel 0.0207, coverage 1.00); SAM/hem-fit said 3.5px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 8.4 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 73.4°, depth 5 px, right: angle -0.2°, depth 2 px
registration residual (leave-one-landmark-out): 39.85px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.473 | 333.2 | 19.8 | 0.000 |
| pred median | 0.473 | 332.8 | 19.8 | 0.000 |
| pred aggressive | 0.473 | 331.2 | 19.8 | 0.002 |
| null:no-op | 0.528 | 259.0 | 14.0 | 0.548 |
| null:crop-only | 0.482 | 326.4 | 18.9 | 0.000 |

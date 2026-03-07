# PAIR — auto pipeline

flags: SAM fringe mask rejected: median depth 116px > 15% of garment height 386px; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 71298 px changed; fringe measured directly: 3.0px in the after frame (rel 0.0110, coverage 1.00); SAM/hem-fit said 2.8px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 3.1 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -68.9°, depth 4 px, right: angle -48.9°, depth 2 px
registration residual (leave-one-landmark-out): 86.85px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.611 | 48.7 | 16.5 | 0.013 |
| pred median | 0.611 | 48.7 | 16.5 | 0.016 |
| pred aggressive | 0.613 | 48.2 | 16.6 | 0.033 |
| null:no-op | 0.579 | 103.2 | 18.9 | 0.281 |
| null:crop-only | 0.614 | 47.9 | 17.8 | 0.000 |

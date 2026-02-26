# PAIR — auto pipeline

flags: after: rotated -10.7° to upright; SAM fringe mask rejected: median depth 254px > 15% of garment height 1190px; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 397080 px changed
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_before_54931395.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/b630a78c19_after_cut_c7a4d702.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 4.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 4.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 72.1°, depth 4 px, right: angle 0.1°, depth 5 px
registration residual (leave-one-landmark-out): 41.30px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.480 | 325.7 | 20.0 | 0.001 |
| pred median | 0.480 | 323.3 | 20.0 | 0.001 |
| pred aggressive | 0.481 | 320.2 | 19.9 | 0.005 |
| null:no-op | 0.536 | 257.3 | 14.3 | 0.549 |
| null:crop-only | 0.489 | 320.5 | 19.1 | 0.000 |

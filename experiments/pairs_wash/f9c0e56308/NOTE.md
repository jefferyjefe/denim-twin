# PAIR — auto pipeline

flags: before: rotated -1.0° to upright; after: touches the edge of a MANUAL crop (second object removed from frame); SAM fringe mask rejected: median depth 260px > 15% of garment height 811px; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 1609100 px changed; fringe measured directly: 12.0px in the after frame (rel 0.0132, coverage 0.51); SAM/hem-fit said 0.0px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_before_5de12702.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_wash/f9c0e56308/cropped_after_wash.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 9.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 9.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 3.5°, depth 0 px, right: angle -11.3°, depth 0 px
registration residual (leave-one-landmark-out): 137.74px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.924 | 33.2 | 17.1 | 0.000 |
| pred median | 0.924 | 33.2 | 17.7 | 0.001 |
| pred aggressive | 0.924 | 33.5 | 18.1 | 0.039 |
| null:no-op | 0.435 | 732.2 | 15.1 | 0.002 |
| null:crop-only | 0.918 | 34.2 | 17.5 | 0.000 |

# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame); SAM fringe mask rejected: median depth 260px > 15% of garment height 811px; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 1608815 px changed
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/f9c0e56308_before_5de12702.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_wash/f9c0e56308/cropped_after_wash.png 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 0.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 3.0°, depth 0 px, right: angle -11.1°, depth 0 px
registration residual (leave-one-landmark-out): 139.78px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.926 | 33.7 | 15.6 | 0.011 |
| pred median | 0.926 | 33.8 | 15.6 | 0.016 |
| pred aggressive | 0.925 | 33.9 | 15.7 | 0.033 |
| null:no-op | 0.445 | 713.6 | 13.7 | 0.006 |
| null:crop-only | 0.926 | 33.7 | 15.9 | 0.000 |

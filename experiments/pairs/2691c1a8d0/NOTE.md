# PAIR — auto pipeline

flags: SAM fringe mask rejected: median depth 116px > 15% of garment height 386px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 2.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 2.8 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -68.9°, depth 4 px, right: angle -48.9°, depth 2 px
registration residual (leave-one-landmark-out): 86.85px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.615 | 47.4 | 16.8 | 0.015 |
| pred median | 0.617 | 46.8 | 16.9 | 0.039 |
| pred aggressive | 0.620 | 45.5 | 17.0 | 0.077 |
| null:no-op | 0.579 | 103.2 | 18.9 | 0.281 |
| null:crop-only | 0.614 | 47.9 | 17.8 | 0.000 |

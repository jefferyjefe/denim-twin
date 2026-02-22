# PAIR — auto pipeline

flags: SAM fringe mask rejected: median depth 116px > 15% of garment height 386px; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 71298 px changed
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_before_b9f7f64b.jpg 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/2691c1a8d0_after_cut_b2330819.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 2.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 2.8 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -68.9°, depth 4 px, right: angle -48.9°, depth 2 px
registration residual (leave-one-landmark-out): 86.85px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.612 | 48.3 | 16.2 | 0.017 |
| pred median | 0.613 | 47.6 | 16.2 | 0.039 |
| pred aggressive | 0.616 | 46.5 | 16.4 | 0.075 |
| null:no-op | 0.580 | 99.6 | 18.5 | 0.291 |
| null:crop-only | 0.610 | 48.8 | 17.5 | 0.000 |

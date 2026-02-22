# PAIR — auto pipeline

flags: wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 274653 px changed
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 36.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 36.5 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -10.4°, depth 31 px, right: angle 4.5°, depth 15 px
registration residual (leave-one-landmark-out): 42.01px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.764 | 18.1 | 22.8 | 0.194 |
| pred median | 0.777 | 14.6 | 22.5 | 0.378 |
| pred aggressive | 0.781 | 13.6 | 22.2 | 0.461 |
| null:no-op | 0.293 | 515.8 | 19.9 | 0.043 |
| null:crop-only | 0.749 | 23.4 | 23.4 | 0.000 |

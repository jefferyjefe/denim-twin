# PAIR — auto pipeline

flags: before: rotated 0.5° to upright; wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 274152 px changed; fringe measured directly: 2.0px in the after frame (rel 0.0060, coverage 0.61); SAM/hem-fit said 36.8px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 2.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 2.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -2.3°, depth 31 px, right: angle 4.1°, depth 14 px
registration residual (leave-one-landmark-out): 42.31px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.753 | 23.8 | 23.3 | 0.002 |
| pred median | 0.754 | 23.3 | 23.2 | 0.005 |
| pred aggressive | 0.757 | 22.6 | 23.1 | 0.015 |
| null:no-op | 0.290 | 525.4 | 19.4 | 0.039 |
| null:crop-only | 0.754 | 21.7 | 22.7 | 0.000 |

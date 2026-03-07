# PAIR — auto pipeline

flags: before: rotated -0.3° to upright; after: rotated -1.0° to upright; fringe measured directly: 2.0px in the after frame (rel 0.0060, coverage 0.63); SAM/hem-fit said 35.6px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 2.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 2.2 px (fabric/fringe split: SAM; after-frame)
hem fit: left: angle -17.7°, depth 31 px, right: angle 17.2°, depth 21 px
registration residual (leave-one-landmark-out): 42.33px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.768 | 33.4 | 22.6 | 0.001 |
| pred median | 0.769 | 33.2 | 22.5 | 0.009 |
| pred aggressive | 0.771 | 32.7 | 22.5 | 0.023 |
| null:no-op | 0.296 | 530.3 | 16.0 | 0.059 |
| null:crop-only | 0.768 | 33.5 | 22.4 | 0.000 |

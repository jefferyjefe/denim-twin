# PAIR — auto pipeline

flags: before: rotated 0.5° to upright; after: rotated -4.8° to upright; SAM fringe mask rejected: median depth 46px > 15% of garment height 305px; fringe measured directly: 2.0px in the after frame (rel 0.0067, coverage 0.60); SAM/hem-fit said 1.0px
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_before_051879ca.jpeg collage split (side-by-side) at x=503, kept left
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/4bfef03bd7_after_wash_44ffba7e.jpeg collage split (stacked) at y=512, kept top
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: prior_legs_touching / gap)
fringe depth used: 2.5 px from measured from after-photo (NOT a prediction); measured on after-photo: 2.5 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle -10.3°, depth 1 px, right: angle 1.9°, depth 1 px
registration residual (leave-one-landmark-out): 58.27px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.806 | 4.7 | 19.5 | 0.056 |
| pred median | 0.807 | 4.5 | 19.5 | 0.118 |
| pred aggressive | 0.807 | 4.3 | 19.5 | 0.196 |
| null:no-op | 0.299 | 525.1 | 21.5 | 0.008 |
| null:crop-only | 0.805 | 4.9 | 19.6 | 0.000 |

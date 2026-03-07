# PAIR — auto pipeline

flags: before: rotated -1.9° to upright; before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame); wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 43047 px changed; fringe measured directly: 6.0px in the after frame (rel 0.0154, coverage 0.97); SAM/hem-fit said 1.0px; no fringe rendered: edge_treatment 'raw' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/experiments/pairs_wash/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 2.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 24.0°, depth 1 px, right: angle -21.3°, depth 1 px
registration residual (leave-one-landmark-out): 27.45px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.901 | 2.6 | 11.9 | 0.020 |
| pred median | 0.901 | 2.4 | 12.0 | 0.039 |
| pred aggressive | 0.903 | 2.0 | 12.0 | 0.217 |
| null:no-op | 0.546 | 127.7 | 18.6 | 0.008 |
| null:crop-only | 0.896 | 1.5 | 11.2 | 0.000 |

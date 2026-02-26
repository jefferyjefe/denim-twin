# PAIR — auto pipeline

flags: before: touches the edge of a MANUAL crop (second object removed from frame); before (refined): touches the edge of a MANUAL crop (second object removed from frame); wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 42801 px changed
before: /Users/jefferyhuang/denim-twin/experiments/pairs_wash/e97924ad2d/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/e97924ad2d_after_cut_b11dd634.JPG 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 1.0 px from measured from after-photo (NOT a prediction); measured on after-photo: 1.0 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 23.4°, depth 1 px, right: angle -22.0°, depth 1 px
registration residual (leave-one-landmark-out): 28.17px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.906 | 2.7 | 11.5 | 0.007 |
| pred median | 0.907 | 2.4 | 11.6 | 0.041 |
| pred aggressive | 0.908 | 2.0 | 11.6 | 0.141 |
| null:no-op | 0.544 | 128.5 | 18.4 | 0.007 |
| null:crop-only | 0.897 | 1.3 | 11.0 | 0.000 |

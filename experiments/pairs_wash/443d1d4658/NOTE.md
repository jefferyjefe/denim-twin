# PAIR — auto pipeline

flags: after: touches the edge of a MANUAL crop (second object removed from frame); wash preset median: shrink 2.0% along / 1.0% across (PRIOR, not measured); 209321 px changed
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_wash/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 7.8 px from measured from after-photo (NOT a prediction); measured on after-photo: 7.8 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 11.4°, depth 14 px, right: angle -11.3°, depth 2 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 6.42px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.917 | 9.4 | 16.0 | 0.053 |
| pred median | 0.917 | 9.4 | 16.2 | 0.168 |
| pred aggressive | 0.917 | 9.6 | 16.4 | 0.228 |
| null:no-op | 0.594 | 232.5 | 18.4 | 0.014 |
| null:crop-only | 0.917 | 9.5 | 17.0 | 0.000 |

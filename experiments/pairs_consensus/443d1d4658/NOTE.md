# PAIR — auto pipeline

flags: segmentation by consensus: 75% of prompt sets agree, area 0.52; segmentation by consensus: 100% of prompt sets agree, area 0.59; after: touches the edge of a MANUAL crop (second object removed from frame); fringe measured directly: 2.0px in the after frame (rel 0.0056, coverage 0.53); SAM/hem-fit said 7.0px; no fringe rendered: edge_treatment 'cuffed' with no wash does not fray (EXP_0017)
before: /Users/jefferyhuang/denim-twin/data/external/pair_images/443d1d4658_before_fa971284.jpg 
after: /Users/jefferyhuang/denim-twin/experiments/pairs_consensus/443d1d4658/cropped_after_cut.png 
scale: given
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 0.0 px from measured from after-photo (NOT a prediction) [suppressed: finished hem]; measured on after-photo: 1.9 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 11.3°, depth 12 px, right: angle -10.7°, depth 2 px (mm_per_px 0.9770)
registration residual (leave-one-landmark-out): 5.99px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.918 | 9.2 | 18.1 | 0.005 |
| pred median | 0.918 | 9.2 | 18.1 | 0.007 |
| pred aggressive | 0.918 | 9.3 | 18.1 | 0.014 |
| null:no-op | 0.587 | 240.9 | 21.2 | 0.005 |
| null:crop-only | 0.918 | 9.2 | 18.2 | 0.000 |

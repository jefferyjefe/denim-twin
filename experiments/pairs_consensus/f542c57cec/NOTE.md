# PAIR — auto pipeline

flags: segmentation by consensus: 88% of prompt sets agree, area 0.72; segmentation by consensus: 100% of prompt sets agree, area 0.53; before: touches the edge of a MANUAL crop (second object removed from frame); SAM fringe mask rejected: median depth 798px > 15% of garment height 3231px; before garment is short (bermuda/shorts): a short->shorter cut, not jeans->shorts; fringe measured directly: 18.0px in the after frame (rel 0.0064, coverage 0.62); SAM/hem-fit said 14.5px
before: /Users/jefferyhuang/denim-twin/experiments/pairs_consensus/f542c57cec/cropped_before.png 
after: /Users/jefferyhuang/denim-twin/data/external/pair_images/f542c57cec_after_wash_9c55600a.jpg 
scale: UNKNOWN (1.0 placeholder; mm values are px)
landmarks: auto / auto (crotch: gap / gap)
fringe depth used: 7.2 px from measured from after-photo (NOT a prediction); measured on after-photo: 7.2 px (fabric/fringe split: colour split; registered-frame)
hem fit: left: angle 49.9°, depth 12 px, right: angle -46.2°, depth 17 px
registration residual (leave-one-landmark-out): 110.90px

| system | sil IoU | chamfer | edge ΔE | fringe IoU |
|---|---|---|---|---|
| pred conservative | 0.821 | 30.6 | 27.8 | 0.026 |
| pred median | 0.822 | 29.8 | 27.8 | 0.087 |
| pred aggressive | 0.823 | 29.1 | 27.7 | 0.135 |
| null:no-op | 0.587 | 408.0 | 29.2 | 0.038 |
| null:crop-only | 0.821 | 30.9 | 28.1 | 0.000 |

measure_fringe.py is EXPERIMENTAL (this step): its top=fabric / bottom=background assumption fails on close-ups
with textured floors and on registered images with remap borders (coverage_at_edge ≈ 0 and negative falloff on 3/4
real hems). Needs a 3-class fabric/fringe/background segmentation and an orientation estimate before its outputs
are used as priors. Do not commit data/priors/hems from it.

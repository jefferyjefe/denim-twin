"""Landmark vocabulary for flat-laid jeans (plan §4.2). Coordinates are (x, y) pixels.
Canonical template positions are in a normalized [0,1] x [0,1] frame, front view,
waistband at top, garment centered. Values are a generic straight-leg prior and are
refined per garment by the fit."""

LANDMARKS = [
    "waist_left", "waist_center", "waist_right",
    "crotch",
    "hem_left_outer", "hem_left_inner", "hem_right_inner", "hem_right_outer",
    "knee_left_outer", "knee_left_inner", "knee_right_inner", "knee_right_outer",
    "hip_left", "hip_right",
]

CANONICAL = {
    "waist_left": (0.28, 0.02), "waist_center": (0.50, 0.02), "waist_right": (0.72, 0.02),
    "hip_left": (0.22, 0.18), "hip_right": (0.78, 0.18),
    "crotch": (0.50, 0.30),
    "knee_left_outer": (0.20, 0.62), "knee_left_inner": (0.44, 0.62),
    "knee_right_inner": (0.56, 0.62), "knee_right_outer": (0.80, 0.62),
    "hem_left_outer": (0.20, 0.98), "hem_left_inner": (0.42, 0.98),
    "hem_right_inner": (0.58, 0.98), "hem_right_outer": (0.80, 0.98),
}

# Inseam runs crotch -> hem_*_inner. Canonical y along the inseam is the coordinate
# a user's cut line is expressed in (0 at crotch, 1 at original hem).
def inseam_fraction_to_canonical_y(frac):
    return CANONICAL["crotch"][1] + frac * (CANONICAL["hem_left_inner"][1] - CANONICAL["crotch"][1])

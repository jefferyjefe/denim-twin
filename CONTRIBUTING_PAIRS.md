# Contribute a before/after pair

We're building an open dataset of jeans **before and after being cut into shorts** (and after washing) to train
a model that predicts how *your specific pair* will turn out. Contribute in 2 minutes:

**[→ Submit your photos](https://github.com/jefferyjefe/denim-twin/issues/new?template=pair-submission.yml)**

Good photos (any phone is fine):
1. Jeans laid flat on a plain floor or sheet, shot from directly above, whole garment in frame.
2. **Put a coin or ruler on the floor next to the hem** — that's how we get real-world size.
3. Take the same shot before cutting, after cutting, and after the first wash. Add a close-up of the frayed hem.
4. Tell us the care label and how you washed/dried it.

Photos are released under CC BY 4.0 with your GitHub username as credit (or anonymously). Only submit photos you took.

## Please also send one close-up of the hem (added 2026-08-29)

We found (EXP_0015) that at ordinary flat-lay distance the fringe is only a few pixels deep, which is the same size as
the error in the garment outline — so a cuffed hem and a frayed hem measure identically and **no fringe depth we have
recorded is real**. One extra photo fixes it:

- after the wash, take **one close-up of the hem**, filling the frame with about 10 cm of the cut edge,
- put the coin in that frame too, next to the fringe,
- keep the garment flat and the camera parallel to it.

That single photo is worth more to this project than the rest of the set, because it is the only one where the thing we
are trying to predict is actually resolvable.

## How big does the photo need to be? (added 2026-08-29)

Our fray measurement only works above a certain scale, and we measured where: in the whole-garment photo the
**waistband should span at least ~800 pixels** — any phone photo taken from about a metre away does this, so it is
rarely a problem in practice. Below roughly 600 px of waistband we cannot tell a frayed hem from a finished one at all.

The hem close-up described above is still the reliable route, because it puts the fringe at a scale where it is
resolvable rather than a few pixels deep.

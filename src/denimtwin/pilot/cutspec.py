"""Turning a target inseam into the two marks a person actually makes on the cloth.

PROTOCOL.md 3.1 fixes what "the cut" means, and it is deliberately NOT the obvious thing:

    a straight line perpendicular to the leg's centre line (midline between inseam and outseam) in
    the canonical frame, passing through the inseam at the target length. This is what the software
    cuts; it is NOT 'square to the inseam'.

The distinction is the whole reason this module exists. A jean leg tapers, so its centre line is not
parallel to its inseam, and a cut square to the inseam is not perpendicular to the centre line. The
two differ by the taper angle -- a few degrees, which over a 20 cm hem width is centimetres of
length difference between the inseam side and the outseam side of the same cut. If the operator
measures the same distance down both seams, they cut a line the software did not predict, and the
prediction is then being scored against a different garment than the one that was cut.

So 3.2 says to measure the target length down the inseam, and down the outseam **plus the digital
outseam offset printed by the tool**. This is the tool. It prints the offset, the cut angle, and the
hem width the cut will produce, from measurements the operator has already taken.

THE MODEL AND ITS ASSUMPTIONS, because they are load-bearing:
  * The leg is laid flat and treated as a planar trapezoid: the inseam is a straight edge from the
    crotch seam to the hem, the outseam a straight edge beside it, and the leg's flat width goes
    linearly from the thigh measurement to the leg-opening measurement.
  * `thigh_cm` and `leg_opening_cm` are FULL CIRCUMFERENCES in this repository's convention
    (data/garments/*/record.json: "flat x2"), so the flat width is half of each.
  * A real inseam curves near the crotch. The model is therefore least accurate in the top few
    centimetres and is not used there -- a jorts cut lands far below it. `warn_if_close_to_crotch`
    says so rather than letting the caller find out.
This is a geometric construction, not a fitted model; there is nothing here to tune and no number
that came from data.
"""
import math


class CutSpecError(Exception):
    pass


#: A cut this close to the crotch seam is inside the region where the flat-trapezoid model stops
#: describing the garment.
CROTCH_EXCLUSION_CM = 8.0


def compute(*, target_inseam_cm, original_inseam_cm, thigh_cm, leg_opening_cm):
    """The marks, the offset, the angle and the resulting hem width.

    All lengths in cm. Returns a dict suitable for the manifest and the printable cut packet.
    """
    L = float(target_inseam_cm)
    Lin = float(original_inseam_cm)
    if not (0 < L < Lin):
        raise CutSpecError("target inseam %.1f cm must be greater than 0 and shorter than the "
                           "original inseam %.1f cm" % (L, Lin))
    w_thigh = float(thigh_cm) / 2.0            # circumference -> flat width
    w_hem = float(leg_opening_cm) / 2.0
    if w_thigh <= 0 or w_hem <= 0:
        raise CutSpecError("thigh and leg opening must be positive circumferences")
    if w_hem > w_thigh:
        raise CutSpecError("the leg opening (%.1f cm flat) is wider than the thigh (%.1f cm flat); "
                           "check which measurement is which -- both are full circumferences here"
                           % (w_hem, w_thigh))

    # Inseam along +y from the crotch seam at the origin; outseam beside it, converging.
    # Centre line direction: the midpoints of the crotch-level width and the hem width.
    dx = (w_hem - w_thigh) / 2.0               # negative for a tapering leg
    dy = Lin
    denom = 2.0 * dx * dx + dy * dy
    if denom <= 0:
        raise CutSpecError("degenerate leg geometry")
    # Perpendicularity to the centre line, solved for the parameter t along the outseam.
    t = (dy * L - dx * w_thigh) / denom
    outseam_len = math.hypot(w_hem - w_thigh, Lin)     # crotch-level to hem, along the outseam
    outseam_mark_cm = t * outseam_len
    offset_cm = outseam_mark_cm - L

    # Where the cut meets each seam, and therefore the hem it produces.
    p_in = (0.0, L)
    p_out = (w_thigh + t * (w_hem - w_thigh), t * Lin)
    hem_flat_cm = math.hypot(p_out[0] - p_in[0], p_out[1] - p_in[1])

    # Angle of the cut away from square-to-the-inseam. Square to the inseam is horizontal here, so
    # this is the taper angle, and it is what the offset is buying.
    angle_deg = math.degrees(math.atan2(p_out[1] - p_in[1], p_out[0] - p_in[0]))

    warn = None
    if L < CROTCH_EXCLUSION_CM:
        warn = ("the cut is %.1f cm below the crotch seam, inside the region where a real inseam "
                "curves and this flat-trapezoid model stops describing the garment" % L)

    return {
        "target_inseam_cm": round(L, 3),
        "outseam_mark_cm": round(outseam_mark_cm, 3),
        "outseam_offset_cm": round(offset_cm, 3),
        "outseam_offset_mm": round(offset_cm * 10.0, 2),
        "cut_angle_deg": round(angle_deg, 4),
        "predicted_outseam_cm": round(outseam_mark_cm, 3),
        "predicted_hem_flat_cm": round(hem_flat_cm, 3),
        "predicted_hem_circumference_cm": round(2.0 * hem_flat_cm, 3),
        "cut_path_frame": "garment_flat_cm:origin=crotch_seam,+y=along_inseam_to_hem,"
                          "+x=inseam_to_outseam",
        "cut_path_coordinates": [[round(p_in[0], 3), round(p_in[1], 3)],
                                 [round(p_out[0], 3), round(p_out[1], 3)]],
        "model": "planar trapezoid; inseam and outseam straight; flat width linear from thigh/2 to "
                 "leg_opening/2; both inputs are full circumferences",
        "inputs": {"original_inseam_cm": round(Lin, 3), "thigh_cm": round(float(thigh_cm), 3),
                   "leg_opening_cm": round(float(leg_opening_cm), 3)},
        "warning": warn,
    }


def verification_tolerance_mm():
    """PROTOCOL.md 3.2: a second person verifies both marks with a tape to this tolerance."""
    return 3.0


def packet_lines(garment_id, spec, *, legs=("LEFT", "RIGHT")):
    """The printable cut packet: what goes on the table beside the scissors.

    Deliberately plain text and deliberately repetitive per leg. The failure this guards against is
    the operator holding two numbers in their head and marking the second leg with the first leg's
    offset.
    """
    out = [
        "CUT PACKET  %s" % garment_id,
        "=" * 60,
        "Cut definition (PROTOCOL.md 3.1): a straight line PERPENDICULAR TO THE LEG'S",
        "CENTRE LINE passing through the inseam at the target length.",
        "This is NOT square to the inseam. Use the offset below or the cut will not",
        "match the line the software predicted.",
        "",
        "  target inseam (measure DOWN THE INSEAM from the crotch seam) : %6.1f cm"
        % spec["target_inseam_cm"],
        "  mark on the OUTSEAM (from the crotch seam)                   : %6.1f cm"
        % spec["outseam_mark_cm"],
        "  which is the inseam length PLUS an offset of                 : %+6.1f mm"
        % spec["outseam_offset_mm"],
        "  cut angle away from square-to-the-inseam                     : %6.2f deg"
        % (spec["cut_angle_deg"] + 90.0 if spec["cut_angle_deg"] < 0 else spec["cut_angle_deg"]),
        "  predicted hem width flat / circumference                     : %6.1f / %.1f cm"
        % (spec["predicted_hem_flat_cm"], spec["predicted_hem_circumference_cm"]),
        "",
        "BEFORE THE FIRST CUT",
        "  [ ] a second person has measured BOTH marks with a tape",
        "  [ ] both agree within %.0f mm" % verification_tolerance_mm(),
        "  [ ] the app says READY TO CUT",
        "  [ ] the legs will be cut SEPARATELY, one at a time",
        "  [ ] offcut labels are written and beside the scissors",
        "",
    ]
    for leg in legs:
        out += [
            "-" * 60,
            "LEG: %-6s          OFFCUT LABEL: %s_OFFCUT_%s" % (leg, garment_id, leg[0]),
            "  inseam mark  %6.1f cm      outseam mark  %6.1f cm"
            % (spec["target_inseam_cm"], spec["outseam_mark_cm"]),
            "  verified by ______________________  at ______:______",
            "  measured inseam ________ cm   measured outseam ________ cm",
            "",
        ]
    if spec.get("warning"):
        out += ["!! " + spec["warning"], ""]
    return out

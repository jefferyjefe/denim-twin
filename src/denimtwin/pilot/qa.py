"""The capture-quality engine: four outcomes, and no path from "absent" to "pass".

`tools/verify.py` and `src/denimtwin/prereqs.py` already established the distinction this repository
runs on -- a check that could not run is not a check that passed, and the two demand opposite
responses. This applies it per photograph, with one more state than verify needs, because a capture
can also be in a condition only a person can settle:

    PASS                          the requirement is met, and the evidence for that is recorded
    RETAKE_REQUIRED               the requirement is measurably not met; the fix is another frame
    UNAVAILABLE_CHECK             the check could not run -- no scale, no board, no dependency, no
                                  comparison image. Nothing is claimed. This BLOCKS, and it blocks
                                  differently from a failure: the fix is to supply what is missing,
                                  not to re-shoot.
    HUMAN_VERIFICATION_REQUIRED   the measurement does not settle it and honestly cannot. The fix is
                                  a person looking, and their answer is recorded as an assertion
                                  with their name on it, not as a measurement.

The fourth outcome is the one that keeps the other three honest. Several checks the pilot needs --
is the ruler in frame, is this really the front, is this really the region it claims -- have no
reliable automatic implementation on a single photograph. The dishonest options are to skip them
(silence reads as a pass) or to implement something that usually works (a wrong pass on the day it
does not). Referring them to a person, and recording who and when, is the only version that does not
lie about what is known.

Roll-up severity is RETAKE > UNAVAILABLE > HUMAN > PASS. All three non-PASS outcomes block a
required shot; the order only decides which one the operator is shown first, and a re-shoot is the
most actionable.
"""
from pathlib import Path

PASS = "PASS"
RETAKE = "RETAKE_REQUIRED"
UNAVAILABLE = "UNAVAILABLE_CHECK"
HUMAN = "HUMAN_VERIFICATION_REQUIRED"

SEVERITY = {PASS: 0, HUMAN: 1, UNAVAILABLE: 2, RETAKE: 3}
BLOCKING = (RETAKE, UNAVAILABLE, HUMAN)

#: Hamming distance between 256-bit perceptual signatures below which two frames are worth decoding
#: and correlating properly. See the note at the duplicate check.
DUPLICATE_CANDIDATE_HAMMING = 24


class Check(object):
    __slots__ = ("check_id", "outcome", "detail", "evidence", "fix")

    def __init__(self, check_id, outcome, detail, evidence=None, fix=None):
        if outcome not in SEVERITY:
            raise ValueError("unknown outcome %r" % outcome)
        self.check_id = check_id
        self.outcome = outcome
        self.detail = detail
        self.evidence = evidence or {}
        self.fix = fix

    def as_dict(self):
        return {"check_id": self.check_id, "outcome": self.outcome, "detail": self.detail,
                "evidence": self.evidence, "fix": self.fix}

    def __repr__(self):
        return "<%s %s>" % (self.check_id, self.outcome)


def roll_up(checks):
    """The single outcome for a shot. Empty is UNAVAILABLE, never PASS.

    A shot with no checks is a shot nothing was measured about. That has read as success in this
    repository before -- a loop over an empty glob asserting nothing (see tests/conftest.py) -- and
    it is the failure mode this whole module is arranged against.
    """
    if not checks:
        return UNAVAILABLE
    return max((c.outcome for c in checks), key=lambda o: SEVERITY[o])


def merged_quality(spec_defaults, shot):
    q = dict(spec_defaults or {})
    q.update(shot.get("quality") or {})
    return q


def check_capture(path, shot, quality, *, board=None, board_spec=None, image=None,
                  compare_to=None, operator_assertions=None):
    """Run every applicable check on one capture and return a list of Check.

    `compare_to` is a list of dicts describing already-accepted captures to compare against:
    {"shot_id", "rep", "path", "sha256", "pose", "image", "exif_ts"}. `operator_assertions` holds
    what the person has already confirmed for this frame: {"ruler_visible": True, ...}. An assertion
    that is absent is not False -- it leaves the check at HUMAN_VERIFICATION_REQUIRED.
    """
    from . import qa_primitives as Q

    checks = []
    assertions = operator_assertions or {}
    path = Path(path)

    try:
        import cv2
    except ImportError:
        return [Check("dependencies", UNAVAILABLE,
                      "OpenCV is not installed, so no image check can run",
                      fix="pip install -r requirements.txt")]

    img = image if image is not None else cv2.imread(str(path))
    if img is None:
        return [Check("readable", RETAKE, "the file could not be read as an image",
                      {"path": path.name}, fix="re-transfer or re-take this capture")]
    h, w = img.shape[:2]
    checks.append(Check("readable", PASS, "%dx%d" % (w, h), {"width": w, "height": h}))

    # -- resolution ---------------------------------------------------------------------------
    min_long = quality.get("min_long_edge_px")
    if min_long:
        long_edge = max(w, h)
        checks.append(Check("resolution", PASS if long_edge >= min_long else RETAKE,
                            "long edge %d px (needs >= %d)" % (long_edge, min_long),
                            {"long_edge_px": long_edge, "required": min_long},
                            fix="move closer or use a higher-resolution capture mode"))

    # -- the existing quality report ----------------------------------------------------------
    needs_board = quality.get("requires_board", shot.get("scale_reference") in
                              ("charuco_board", "both"))
    rep = None
    if needs_board and board is None:
        checks.append(Check("board", UNAVAILABLE,
                            "this shot requires the calibration board but no board specification "
                            "was supplied to the checker",
                            fix="pass --board protocol/charuco_board.json"))
    else:
        from ..capture.quality import check_image
        kwargs = {}
        if quality.get("min_blur") is not None:
            kwargs["blur_min"] = quality["min_blur"]
        if quality.get("max_clipped_fraction") is not None:
            kwargs["clip_max"] = quality["max_clipped_fraction"]
        if quality.get("max_border_fraction") is not None:
            kwargs["border_max"] = quality["max_border_fraction"]
        if quality.get("mean_intensity_range"):
            kwargs["mean_range"] = tuple(quality["mean_intensity_range"])
        if quality.get("min_board_corners") is not None:
            kwargs["min_corners"] = quality["min_board_corners"]
        rep = check_image(str(path), board if needs_board else None,
                          board_spec if needs_board else None, **kwargs)
        for name, bad in (("blur", "blur"), ("exposure", "exposure"), ("clipping", "clipping"),
                          ("cropping", "frame edge"), ("subject_present", "foreground")):
            hits = [r for r in rep.reasons if bad in r]
            checks.append(Check(name, RETAKE if hits else PASS,
                                "; ".join(hits) if hits else "ok",
                                {"blur_score": rep.blur_score, "mean": rep.mean_intensity,
                                 "clipped": rep.clipped_fraction, "border": rep.border_fraction,
                                 "foreground_fraction": rep.foreground_fraction}
                                if name == "blur" else {},
                                fix={"blur": "steady the phone or increase light; the mount should "
                                             "carry the camera, not your hands",
                                     "exposure": "re-lock exposure on the garment, not the backdrop",
                                     "clipping": "reduce exposure until the highlights come back",
                                     "cropping": "back off until the whole subject is inside the "
                                                 "frame with margin",
                                     "subject_present": "the garment is not filling enough of the "
                                                        "frame to measure"}[name]))
        board_hits = [r for r in rep.reasons if "board corners" in r]
        if needs_board:
            checks.append(Check("board_corners", RETAKE if board_hits else PASS,
                                "%d corners detected" % rep.board_corners,
                                {"board_corners": rep.board_corners},
                                fix="get the whole board in frame, flat, unshadowed and in focus"))

    # -- scale and tilt -----------------------------------------------------------------------
    mm_per_px = rep.mm_per_px if rep is not None else None
    srr = None
    if needs_board:
        if mm_per_px is None:
            checks.append(Check("scale", UNAVAILABLE,
                                "no metric scale could be recovered from this frame",
                                fix="re-take with the whole calibration board visible"))
        else:
            lo, hi = quality.get("min_mm_per_px"), quality.get("max_mm_per_px")
            bad = (hi is not None and mm_per_px > hi) or (lo is not None and mm_per_px < lo)
            checks.append(Check("scale", RETAKE if bad else PASS,
                                "%.4f mm/px%s" % (mm_per_px,
                                                  "" if not bad else " (needs %s..%s)" % (lo, hi)),
                                {"mm_per_px": mm_per_px, "min": lo, "max": hi},
                                fix="move the camera closer (a smaller mm/px is a finer image)"
                                if hi is not None and mm_per_px > hi else
                                "move the camera back; this frame is finer than the shot needs"))
        # tilt: measured in EXP_0043. A single mm/px does not describe a tilted frame.
        try:
            from ..capture.board import detect
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            corners, ids = detect(gray, board) if board is not None else (None, None)
            srr = Q.scale_range_ratio(corners, ids, board_spec) if corners is not None else None
        except Exception:
            srr = None
        limit = quality.get("max_scale_range_ratio")
        outcome, detail = Q.tilt_verdict(srr)
        if limit is not None and srr is not None and srr > limit and outcome == PASS:
            outcome, detail = RETAKE, ("scale varies %.1f%% across the board, above this shot's "
                                       "limit of %.1f%%" % (100 * (srr - 1), 100 * (limit - 1)))
        checks.append(Check("camera_tilt", outcome, detail,
                            {"scale_range_ratio": srr,
                             "approx_tilt_deg": Q.approx_tilt_deg(corners, ids, board_spec, w, h)
                             if srr is not None else None},
                            fix="raise or re-aim the camera until it is square to the surface"))

    # -- subject extent -----------------------------------------------------------------------
    pose = Q.garment_pose(img)
    min_frac, max_frac = quality.get("min_subject_fraction"), quality.get("max_subject_fraction")
    if min_frac is not None or max_frac is not None:
        if pose is None:
            checks.append(Check("subject_extent", UNAVAILABLE,
                                "no subject outline could be measured",
                                fix="check the backdrop contrasts with the garment"))
        else:
            f = pose["area_fraction"]
            bad = (min_frac is not None and f < min_frac) or (max_frac is not None and f > max_frac)
            checks.append(Check("subject_extent", RETAKE if bad else PASS,
                                "subject fills %.1f%% of the frame" % (100 * f),
                                {"area_fraction": f, "min": min_frac, "max": max_frac},
                                fix="frame tighter" if min_frac and f < min_frac else "back off"))

    min_subject_px = quality.get("min_subject_px")
    if min_subject_px:
        meaning = quality.get("subject_px_meaning", "subject width")
        if pose is None:
            checks.append(Check("subject_span", UNAVAILABLE,
                                "no subject outline, so %s could not be measured" % meaning))
        else:
            span = float(pose["bbox"][2])
            checks.append(Check("subject_span", PASS if span >= min_subject_px else RETAKE,
                                "%s spans %.0f px (needs >= %.0f)" % (meaning, span, min_subject_px),
                                {"span_px": span, "required": min_subject_px,
                                 "meaning": meaning},
                                fix="fill more of the frame with the garment, or capture at a "
                                    "higher resolution"))

    # -- things a photograph cannot settle by itself ------------------------------------------
    if shot.get("scale_reference") in ("ruler", "both") or quality.get("requires_ruler"):
        if assertions.get("ruler_visible") is True:
            checks.append(Check("ruler_visible", PASS,
                                "operator confirmed the ruler is in frame, in the garment's plane, "
                                "and readable", {"asserted_by": assertions.get("operator")}))
        elif assertions.get("ruler_visible") is False:
            checks.append(Check("ruler_visible", RETAKE,
                                "operator reported the ruler is not usable in this frame",
                                fix="lay the rule flat beside the feature, in the same plane"))
        else:
            checks.append(Check("ruler_visible", HUMAN,
                                "a ruler in the garment's plane cannot be verified automatically "
                                "from one frame -- reading its graduations is not the same as "
                                "detecting a bright rectangle. Confirm it is present and readable.",
                                fix="confirm the ruler in the app"))

    side = shot.get("garment_side")
    if side in ("front", "back"):
        if assertions.get("side_confirmed") is True:
            checks.append(Check("garment_side", PASS,
                                "operator confirmed the %s is facing up" % side))
        else:
            checks.append(Check("garment_side", HUMAN,
                                "which face of the garment is up is not reliably detectable from "
                                "one frame; back pockets are a cue, not a proof, and a partial "
                                "frame may show neither. Confirm the %s is up." % side,
                                fix="confirm the facing side in the app"))

    if shot.get("region_id") and shot.get("camera_angle") in ("macro_perpendicular", "side_profile"):
        if assertions.get("region_confirmed") is True:
            checks.append(Check("anatomical_region", PASS,
                                "operator confirmed this is %s" % shot["region_id"]))
        else:
            checks.append(Check("anatomical_region", HUMAN,
                                "at macro range one piece of denim looks like another; the region "
                                "cannot be identified automatically. Confirm this is %s."
                                % shot["region_id"],
                                fix="confirm the region in the app"))

    # -- duplicates and relays ----------------------------------------------------------------
    # Comparing every new frame against every accepted one is quadratic, and at a few hundred
    # frames it is minutes of image decoding per capture. The expensive comparison is only ever
    # interesting for frames that might be the same picture, so a 32-byte perceptual signature
    # recorded at capture time decides which images are worth decoding. Measured (EXP_0043): the
    # same frame re-encoded or brightened sat at Hamming 0-12, genuinely distinct frames at 48-65,
    # so a candidate threshold of 24 admits every near-duplicate with a wide margin and rejects the
    # rest without opening a file.
    self_sig = Q.dhash_bits(img)
    for other in (compare_to or []):
        osig = other.get("dhash")
        if isinstance(osig, str):
            osig = bytes.fromhex(osig)
        dist = Q.hamming(self_sig, osig) if osig else None
        is_prev = bool(other.get("is_previous_rep"))
        candidate = is_prev or dist is None or dist <= DUPLICATE_CANDIDATE_HAMMING
        oimg = other.get("image")
        if oimg is None and candidate and other.get("path"):
            oimg = cv2.imread(str(other["path"]))
        n = Q.ncc(img, oimg) if oimg is not None else None
        if not candidate and n is None:
            # Far apart on the signature: not the same frame, and no decode was needed to say so.
            continue
        outcome, detail = Q.duplicate_verdict(other.get("sha256"), other.get("self_sha256"), n)
        if outcome != PASS:
            checks.append(Check("duplicate_content", outcome,
                                "%s (against %s rep %s)" % (detail, other.get("shot_id"),
                                                            other.get("rep")),
                                {"ncc": n, "other_shot_id": other.get("shot_id"),
                                 "other_rep": other.get("rep")},
                                fix="capture a new frame; this one is already recorded"))
        if other.get("is_previous_rep") and shot.get("relay_between_reps"):
            interior = Q.registered_interior_ncc(img, oimg, pose, other.get("pose")) \
                if oimg is not None else None
            secs = None
            if other.get("exif_ts") and other.get("this_exif_ts"):
                secs = abs(float(other["this_exif_ts"]) - float(other["exif_ts"]))
            o, d, ev = Q.relay_verdict(other.get("pose"), pose, mm_per_px, interior_ncc=interior,
                                       seconds_apart=secs,
                                       operator_confirmed=bool(assertions.get("relay_confirmed")))
            checks.append(Check("relay_independence", o, d, ev,
                                fix="lift the garment clear of the surface, shake it out, and lay "
                                    "it again before this repeat"))
    if shot.get("relay_between_reps") and not (compare_to or []):
        pass    # the first repetition has nothing to be independent of; that is not a finding

    return checks

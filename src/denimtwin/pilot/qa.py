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


# --------------------------------------------------------------------------------------------
# Shot classes, and why the checks cannot all run on every frame.
#
# `capture/quality.check_image` does not have a garment model. Its "foreground" is an Otsu split on
# Lab distance from the frame-border median, which is a good description of a dark garment on a
# contrasting backdrop and a bad description of everything else. Measured on synthetic frames: on a
# macro of a hem it selects the RULER as the subject and reports the exposure of white plastic; on a
# care label it selects the LABEL; on an empty backdrop it selects sensor noise and reports 94.7%
# clipping. Those are not failures of the photograph, they are the wrong object being measured, and
# a RETAKE issued on that basis sends the operator to re-shoot a frame that was correct.
#
# So checks are dispatched by shot class, and a check that does not apply is recorded as
# not-applicable with its reason rather than silently omitted -- an omitted check and a passed check
# must never look the same in the record.
# --------------------------------------------------------------------------------------------

WHOLE_GARMENT = "whole_garment"
MACRO = "macro"
RIG = "rig"
LABEL = "label"
VIDEO = "video"

#: Which checks the frame's own content can support, per class.
APPLICABLE = {
    WHOLE_GARMENT: {"readable", "resolution", "blur", "exposure", "clipping", "cropping",
                    "subject_present", "board_corners", "scale", "camera_tilt", "subject_extent",
                    "subject_span", "ruler_visible", "garment_side", "anatomical_region",
                    "duplicate_content", "relay_independence", "camera_repositioned"},
    MACRO: {"readable", "resolution", "blur", "board_corners", "scale", "camera_tilt",
            "ruler_visible", "anatomical_region", "duplicate_content", "camera_repositioned"},
    RIG: {"readable", "resolution", "blur", "board_corners", "scale", "camera_tilt",
          "duplicate_content", "camera_repositioned"},
    LABEL: {"readable", "resolution", "blur", "duplicate_content", "camera_repositioned",
            "anatomical_region", "ruler_visible"},
    VIDEO: {"readable", "resolution", "duplicate_content"},
}

NOT_APPLICABLE_WHY = {
    (MACRO, "exposure"): "the frame is filled by the subject, so the border-sampled background "
                         "model that this exposure check rests on has no background to sample",
    (MACRO, "clipping"): "same: the clipping fraction would be measured over whichever bright "
                         "object the foreground split picked, which at macro range is the rule",
    (MACRO, "cropping"): "a macro is meant to be filled by its subject; 'the subject touches the "
                         "frame edge' is the instruction, not a fault",
    (MACRO, "subject_present"): "the subject fills the frame by design",
    (MACRO, "subject_extent"): "the subject fills the frame by design",
    (MACRO, "subject_span"): "measured from the rule, not from a silhouette",
    (MACRO, "garment_side"): "which face is up is not visible at macro range",
    (MACRO, "relay_independence"): "a re-lay is an operation on a garment lay; at macro range there "
                                   "is no silhouette whose displacement could establish one",
    (LABEL, "relay_independence"): "a label frame is not a garment lay",
    (VIDEO, "relay_independence"): "a clip is not compared frame to frame here",
    (RIG, "exposure"): "a rig frame has no garment; the exposure model would measure the backdrop "
                       "against itself",
    (RIG, "clipping"): "same -- on an empty backdrop the foreground split selects sensor noise",
    (RIG, "cropping"): "there is no subject to be cropped",
    (RIG, "subject_present"): "a rig frame is meant to have no garment in it",
    (RIG, "subject_extent"): "there is no subject",
    (RIG, "subject_span"): "there is no subject",
    (RIG, "ruler_visible"): "recorded as a calibration reading rather than per frame",
    (RIG, "garment_side"): "there is no garment",
    (RIG, "anatomical_region"): "there is no garment",
    (RIG, "relay_independence"): "a rig frame is not a garment lay",
    (LABEL, "exposure"): "a bright label on dark denim inverts the foreground model; it would "
                         "report the label's exposure as the garment's",
    (LABEL, "clipping"): "same inversion",
    (LABEL, "cropping"): "a label is framed to fill",
    (LABEL, "subject_present"): "a label is framed to fill",
    (LABEL, "board_corners"): "a label frame is too tight for the board; scale comes from the rule",
    (LABEL, "scale"): "no board in frame; the label carries text, not a measurement",
    (LABEL, "camera_tilt"): "no board, so scale variation cannot be measured",
    (LABEL, "garment_side"): "not a view of the garment",
    (LABEL, "subject_extent"): "a label is framed to fill",
    (LABEL, "subject_span"): "a label is framed to fill",
    (VIDEO, "blur"): "a clip's sharpness is not a single frame's Laplacian",
}

#: Why an applicable check produced no result for a PARTICULAR shot. These are conditions of the
#: shot, not of its class: a macro scaled by a rule genuinely has no board to measure a scale from,
#: and saying so is different from saying the scale was fine.
SHOT_LEVEL_WHY = {
    "board_corners": "this shot is scaled by a rule rather than the calibration board, so there is "
                     "no board in frame to count corners on",
    "scale": "this shot carries no calibration board, so no metric scale can be recovered from it; "
             "its scale reference is the rule, which a person confirms",
    "camera_tilt": "scale variation across the board is what measures tilt, and this shot carries "
                   "no board",
    "subject_extent": "this shot sets no bound on how much of the frame the subject fills",
    "subject_span": "this shot names no minimum span for its subject",
    "resolution": "this shot names no minimum long edge",
    "ruler_visible": "this shot's scale reference is not a rule",
    "duplicate_content": "there was no accepted frame to compare this one against",
    "relay_independence": "no previous repetition of this shot to be independent of",
    "camera_repositioned": "this frame is not a repeat that follows a camera reposition",
    "garment_side": "this shot does not declare which face of the garment is up",
    "anatomical_region": "this is an overhead whole-garment frame: its region is the whole "
                         "garment, and which face is up is asked separately by garment_side",
}

#: Quality thresholds that can only be produced by a check the shot does not carry. Each entry maps
#: the key to (the check that would produce it, why it cannot run without a board).
_BOARD_ONLY_QUALITY = {
    "max_mm_per_px": ("scale", "mm_per_px comes from the calibration board's known square size; "
                               "a rule in frame gives an operator a reading, not the code one"),
    "max_scale_range_ratio": ("camera_tilt", "the scale range ratio is measured across the board's "
                                             "own corner spacings; with no board there are no "
                                             "corners to spread"),
}


def quality_is_evaluable(shot):
    """Yield (quality_key, why_not) for every threshold this shot declares that nothing can check.

    Called by the specification's cross-check, so an unevaluable threshold fails the plan at load
    rather than sitting in it looking enforced.
    """
    q = shot.get("quality") or {}
    needs_board = q.get("requires_board",
                        shot.get("scale_reference") in ("charuco_board", "both"))
    for key, (check_id, why) in _BOARD_ONLY_QUALITY.items():
        if q.get(key) is not None and not needs_board:
            yield key, "%s is produced by the %s check, and %s" % (key, check_id, why)
    if q.get("min_subject_px") is not None and shot_class(shot) != WHOLE_GARMENT:
        yield "min_subject_px", ("min_subject_px is measured from the garment silhouette by the "
                                 "subject_span check, which only runs on a whole-garment frame; at "
                                 "macro range the subject fills the frame by design")


def excuse_is_valid(shot, check_id, claim):
    """Would this code itself have excused this check for this shot?

    The mandatory-check rule subtracts the record's own `not_applicable` list, which is free text
    supplied by the same record it is meant to constrain -- so a fabricated record could excuse
    every check it did not want to carry. An excuse now has to be one this module would have
    written: either the CLASS genuinely cannot support the check, or the SHOT genuinely does not
    ask for what the check needs.
    """
    cls = shot_class(shot)
    if claim == cls:
        return (cls, check_id) in NOT_APPLICABLE_WHY
    if claim != "this shot":
        return False
    if check_id not in APPLICABLE.get(cls, ()):
        return False
    q = shot.get("quality") or {}
    needs_board = q.get("requires_board", shot.get("scale_reference") in ("charuco_board", "both"))
    if check_id in ("board_corners", "scale", "camera_tilt"):
        return not needs_board
    if check_id == "ruler_visible":
        return not (shot.get("scale_reference") in ("ruler", "both") or q.get("requires_ruler"))
    if check_id == "subject_extent":
        return q.get("min_subject_fraction") is None and q.get("max_subject_fraction") is None
    if check_id == "subject_span":
        return q.get("min_subject_px") is None
    if check_id == "resolution":
        return q.get("min_long_edge_px") is None
    if check_id == "garment_side":
        return shot.get("garment_side") not in ("front", "back")
    if check_id == "anatomical_region":
        # Excusable only where this module would itself have declined to ask: no region to name, or
        # an overhead whole-garment frame whose region is the whole garment. Returning True here
        # unconditionally meant a record could excuse the region check on the very obliques the
        # check exists for.
        return not shot.get("region_id") or (
            cls != LABEL and shot.get("camera_angle") not in (
                "macro_perpendicular", "side_profile", "oblique_30", "oblique_45",
                "handheld_free"))
    if check_id in ("duplicate_content", "relay_independence", "camera_repositioned"):
        return True          # these depend on what else exists, not on the shot alone
    return False


#: Checks that only exist when there is something to compare against or a repeat to justify them,
#: so their absence from a record is not evidence that the checker was skipped. Everything else in
#: APPLICABLE must appear in a frame's record, or be excused by its own not_applicable note.
OPTIONAL_CHECKS = frozenset({"duplicate_content", "relay_independence", "camera_repositioned",
                             "subject_extent", "subject_span", "resolution"})

#: Regions whose frames are labels or tags rather than views of the garment.
LABEL_REGIONS = ("care_label", "size_tag")


def shot_class(shot):
    """Which model of a photograph this shot is, and therefore which checks can run on it."""
    if shot.get("camera_angle") == "video":
        return VIDEO
    if shot.get("state") == "rig":
        return RIG
    if shot.get("region_id") in LABEL_REGIONS:
        return LABEL
    if shot.get("camera_angle") in ("macro_perpendicular", "side_profile"):
        return MACRO
    return WHOLE_GARMENT


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


def check_capture(path, shot, quality, *, rep=1, board=None, board_spec=None, image=None,
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
    cls = shot_class(shot)
    ok_here = APPLICABLE[cls]

    def applies(check_id):
        return check_id in ok_here

    def not_applicable(ran=()):
        """Every check that did NOT produce a result, and why.

        Two reasons a check does not run, and both have to be recorded. The CLASS may not support it
        -- a rig frame has no garment whose side could be confirmed. Or this particular SHOT may not
        require what the check needs: a macro scaled by a rule has no board, so the scale and tilt
        checks have nothing to measure. The second kind used to leave no trace at all, so 146 of 290
        shots got no scale or tilt result and nothing said so; an un-run check that is silent cannot
        be told from one that passed, which is the defect this whole engine is arranged against.
        """
        out = []
        ran = set(ran)
        for cid in sorted(set().union(*APPLICABLE.values())):
            if cid in ran:
                continue
            if cid not in ok_here:
                why = NOT_APPLICABLE_WHY.get((cls, cid))
                if why:
                    out.append({"check_id": cid, "not_applicable_to": cls, "why": why})
                continue
            why = SHOT_LEVEL_WHY.get(cid)
            out.append({"check_id": cid, "not_applicable_to": "this shot",
                        "why": (why or "this shot does not require it")})
        return out

    try:
        import cv2
    except ImportError:
        return [Check("dependencies", UNAVAILABLE,
                      "OpenCV is not installed, so no image check can run",
                      fix="pip install -r requirements.txt")], not_applicable(["dependencies"])

    if cls == VIDEO:
        # `readable` was cv2.imread, which returns None for every video container -- so the two
        # required motion clips could NEVER pass, and ready_to_finalize could never open. A gate
        # that cannot be opened by valid evidence is broken, not safe.
        cap_ = cv2.VideoCapture(str(path))
        try:
            n_frames = int(cap_.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fps = float(cap_.get(cv2.CAP_PROP_FPS) or 0.0)
            vw = int(cap_.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
            vh = int(cap_.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
            got, first = cap_.read()
        finally:
            cap_.release()
        if not got or n_frames < 2 or min(vw, vh) < 8:
            return [Check("readable", RETAKE,
                          "this file does not open as a video clip (%d frames, %dx%d)"
                          % (n_frames, vw, vh), {"frames": n_frames, "width": vw, "height": vh},
                          fix="re-transfer the clip, or re-record it")], not_applicable(["readable"])
        secs = (n_frames / fps) if fps > 0 else None
        checks.append(Check("readable", PASS,
                            "%dx%d, %d frames%s" % (vw, vh, n_frames,
                                                    "" if secs is None else ", %.1f s" % secs),
                            {"frames": n_frames, "fps": fps, "width": vw, "height": vh,
                             "seconds": secs}))
        want = shot.get("video_seconds")
        if want and secs is not None:
            lo_, hi_ = 0.5 * float(want), 2.5 * float(want)
            checks.append(Check("resolution", PASS if lo_ <= secs <= hi_ else RETAKE,
                                "%.1f s (the shot asks for about %.0f s)" % (secs, float(want)),
                                {"seconds": secs, "wanted": want},
                                fix="re-record the clip at about the stated length"))
        return checks, not_applicable(c.check_id for c in checks)

    img = image if image is not None else cv2.imread(str(path))
    if img is None:
        # Every caller unpacks two values. Returning a bare list here turned an unreadable file --
        # a text file with a .jpg suffix, a truncated transfer -- into a ValueError raised AFTER the
        # capture entry was already in the append-only log, leaving a recorded photograph with no
        # verdict and no way to add one.
        return [Check("readable", RETAKE, "the file could not be read as an image",
                      {"path": path.name}, fix="re-transfer or re-take this capture")], \
            not_applicable(["readable"])
    h, w = img.shape[:2]
    if min(h, w) < 8:
        # A 4000x1 image decodes fine and then asserts inside OpenCV's resample, which raises out
        # of the checker after the capture is already in the log -- the same shape of hole the
        # unreadable-file path had. A frame this degenerate is not a photograph of anything.
        return [Check("readable", RETAKE,
                      "the image is %dx%d; a frame that thin shows nothing" % (w, h),
                      {"width": w, "height": h},
                      fix="re-transfer or re-take this capture")], not_applicable(["readable"])
    checks.append(Check("readable", PASS, "%dx%d" % (w, h), {"width": w, "height": h}))

    # -- resolution ---------------------------------------------------------------------------
    min_long = quality.get("min_long_edge_px")
    if min_long and applies("resolution"):
        long_edge = max(w, h)
        checks.append(Check("resolution", PASS if long_edge >= min_long else RETAKE,
                            "long edge %d px (needs >= %d)" % (long_edge, min_long),
                            {"long_edge_px": long_edge, "required": min_long},
                            fix="move closer or use a higher-resolution capture mode"))

    # -- the existing quality report ----------------------------------------------------------
    needs_board = quality.get("requires_board", shot.get("scale_reference") in
                              ("charuco_board", "both"))
    report = None
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
        report = check_image(str(path), board if needs_board else None,
                          board_spec if needs_board else None, **kwargs)
        for name, bad in (("blur", "blur"), ("exposure", "exposure"), ("clipping", "clipping"),
                          ("cropping", "frame edge"), ("subject_present", "foreground")):
            if not applies(name):
                continue
            hits = [r for r in report.reasons if bad in r]
            checks.append(Check(name, RETAKE if hits else PASS,
                                "; ".join(hits) if hits else "ok",
                                {"blur_score": report.blur_score, "mean": report.mean_intensity,
                                 "clipped": report.clipped_fraction, "border": report.border_fraction,
                                 "foreground_fraction": report.foreground_fraction}
                                if name == "blur" else {},
                                fix={"blur": "steady the phone or increase light; the mount should "
                                             "carry the camera, not your hands",
                                     "exposure": "re-lock exposure on the garment, not the backdrop",
                                     "clipping": "reduce exposure until the highlights come back",
                                     "cropping": "back off until the whole subject is inside the "
                                                 "frame with margin",
                                     "subject_present": "the garment is not filling enough of the "
                                                        "frame to measure"}[name]))
        # On any frame that carries a rule, the blur verdict is re-taken on the CLOTH. The rule is
        # the sharpest thing in a macro and dominated the score, so an out-of-focus fabric passed.
        if applies("blur") and (shot.get("scale_reference") in ("ruler", "both")
                                or quality.get("requires_ruler")):
            cb = Q.cloth_blur(img)
            floor = quality.get("min_blur", 80.0)
            for c in checks:
                if c.check_id == "blur":
                    if cb is None:
                        c.outcome = UNAVAILABLE
                        c.detail = ("the fabric could not be separated from the rule, so the "
                                    "sharpness of the CLOTH could not be measured")
                    elif cb < floor:
                        c.outcome = RETAKE
                        c.detail = ("the fabric is out of focus (cloth sharpness %.0f, needs %.0f). "
                                    "The frame's overall blur score is dominated by the rule, which "
                                    "can be sharp while the cloth is not." % (cb, floor))
                    else:
                        c.detail = "%s; cloth sharpness %.0f" % (c.detail, cb)
                    c.evidence = dict(c.evidence or {}, cloth_blur=cb)
        board_hits = [r for r in report.reasons if "board corners" in r]
        if needs_board and applies("board_corners"):
            checks.append(Check("board_corners", RETAKE if board_hits else PASS,
                                "%d corners detected" % report.board_corners,
                                {"board_corners": report.board_corners},
                                fix="get the whole board in frame, flat, unshadowed and in focus"))

    # -- scale and tilt -----------------------------------------------------------------------
    mm_per_px = report.mm_per_px if report is not None else None
    srr = None
    board_rect = None
    if needs_board and applies("scale"):
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
            if corners is not None:
                # The board is the highest-contrast object in the frame, so left in it becomes the
                # largest foreground blob and every measurement of "the garment" -- its pose, its
                # displacement between repeats, its span -- is actually a measurement of the board.
                # Two frames then have IDENTICAL poses, and the relay check reports that the cloth
                # did not move when what did not move was the calibration target. Cut it out.
                import numpy as _np
                pts = _np.asarray(corners).reshape(-1, 2)
                pad = 3.0 * float(board_spec["square_mm"]) / (mm_per_px or 1.0)
                x0 = max(0, int(pts[:, 0].min() - pad)); y0 = max(0, int(pts[:, 1].min() - pad))
                x1 = min(w, int(pts[:, 0].max() + pad)); y1 = min(h, int(pts[:, 1].max() + pad))
                board_rect = [x0, y0, max(1, x1 - x0), max(1, y1 - y0)]
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
    pose = Q.garment_pose(img, board_rect)
    # exported so callers store it rather than recomputing it differently later
    min_frac, max_frac = quality.get("min_subject_fraction"), quality.get("max_subject_fraction")
    if (min_frac is not None or max_frac is not None) and applies("subject_extent"):
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
    if min_subject_px and applies("subject_span"):
        meaning = quality.get("subject_px_meaning", "subject width")
        if pose is None:
            checks.append(Check("subject_span", UNAVAILABLE,
                                "no subject outline, so %s could not be measured" % meaning))
        else:
            bw, bh = float(pose["bbox"][2]), float(pose["bbox"][3])
            # WHICH dimension is a property of the shot, not of the sentence describing it. Picking
            # it by substring-matching English prose made "outseam" and "inseam" match the keyword
            # "seam" and select the bbox HEIGHT for a measurement across the leg. A shot may declare
            # the axis; where it does not, no dimension is computable and the check bounds rather
            # than asserts.
            axis = (quality.get("span_axis") or "").lower()
            if axis == "horizontal":
                span, computable = bw, True
            elif axis == "vertical":
                span, computable = bh, True
            else:
                span, computable = max(bw, bh), False
            if computable:
                checks.append(Check("subject_span", PASS if span >= min_subject_px else RETAKE,
                                    "%s spans %.0f px (needs >= %.0f)"
                                    % (meaning, span, min_subject_px),
                                    {"span_px": span, "required": min_subject_px,
                                     "meaning": meaning, "bbox_w": bw, "bbox_h": bh},
                                    fix="fill more of the frame with the subject, or capture at a "
                                        "higher resolution"))
            elif span >= min_subject_px:
                # The bounding box already clears the requirement, and every path inside the
                # subject is at most its bounding box -- so this cannot be a pass on its own.
                checks.append(Check("subject_span", HUMAN,
                                    "the requirement is %r, which is a path along the cloth rather "
                                    "than a silhouette dimension, and this check can only measure "
                                    "the bounding box (%.0f x %.0f px, needs >= %.0f). Confirm the "
                                    "feature is resolved end to end."
                                    % (meaning, bw, bh, min_subject_px),
                                    {"bbox_w": bw, "bbox_h": bh, "required": min_subject_px,
                                     "meaning": meaning},
                                    fix="look at the frame and confirm, or frame tighter"))
            else:
                checks.append(Check("subject_span", RETAKE,
                                    "%s needs >= %.0f px and the whole subject only spans "
                                    "%.0f x %.0f px, so no path inside it can reach that"
                                    % (meaning, min_subject_px, bw, bh),
                                    {"bbox_w": bw, "bbox_h": bh, "required": min_subject_px},
                                    fix="frame tighter or capture at a higher resolution"))

    # -- things a photograph cannot settle by itself ------------------------------------------
    if (shot.get("scale_reference") in ("ruler", "both") or quality.get("requires_ruler")) \
            and applies("ruler_visible"):
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
    if side in ("front", "back") and applies("garment_side"):
        if assertions.get("side_confirmed") is True:
            checks.append(Check("garment_side", PASS,
                                "operator confirmed the %s is facing up" % side))
        else:
            checks.append(Check("garment_side", HUMAN,
                                "which face of the garment is up is not reliably detectable from "
                                "one frame; back pockets are a cue, not a proof, and a partial "
                                "frame may show neither. Confirm the %s is up." % side,
                                fix="confirm the facing side in the app"))

    # A label frame has no automatic content check at all -- nothing in the pixels distinguishes a
    # care label from an empty backdrop -- so the only honest answer is to ask. Without this, a
    # required care-label photograph was satisfied PASS by a frame of the backdrop, with no human
    # asked and nothing in the record saying anything had been assumed.
    # The oblique whole-garment frames belong here as much as the macros do. Every one of the 139
    # whole-garment shots carries a region_id and none of them ever reached this check, because the
    # condition named only the two macro angles -- so the thirty-eight obliques, which are the
    # frames an operator most easily confuses (FL2 for FL3, one quadrant along), were excused by a
    # sentence saying the region "is not one a person is asked to confirm at this range". They are
    # now asked. An OVERHEAD whole-garment frame still is not: its region is the whole garment, and
    # garment_side, cropping and subject_extent already pin what is in it.
    if shot.get("region_id") and applies("anatomical_region") \
            and (cls == LABEL
                 or shot.get("camera_angle") in ("macro_perpendicular", "side_profile",
                                                 "oblique_30", "oblique_45", "handheld_free")):
        if assertions.get("region_confirmed") is True:
            checks.append(Check("anatomical_region", PASS,
                                "operator confirmed this is %s" % shot["region_id"]))
        else:
            checks.append(Check("anatomical_region", HUMAN,
                                "at macro range one piece of denim looks like another; the region "
                                "cannot be identified automatically. Confirm this is %s."
                                % shot["region_id"],
                                fix="confirm the region in the app"))

    # -- what this particular shot says a person must confirm -----------------------------------
    # Some required frames have no automatic content check at all: an empty backdrop, a lighting
    # test, a proof that the board and the garment share a plane. Every numeric threshold passes on
    # a photograph of anything, so without this the requirement is satisfied by any file that
    # decodes. A shot can name the claims a person has to make about it.
    for claim in (shot.get("requires_human") or []):
        cid = "confirmed_%s" % str(claim)
        if assertions.get(claim) is True or assertions.get(cid) is True:
            checks.append(Check(cid, PASS, "operator confirmed: %s" % claim,
                                {"asserted_by": assertions.get("operator")}))
        elif assertions.get(claim) is False:
            checks.append(Check(cid, RETAKE, "operator reported this frame does not show: %s"
                                % claim, fix="re-take it so that it does"))
        else:
            checks.append(Check(cid, HUMAN,
                                "nothing in the pixels can judge this frame's content. Confirm: %s"
                                % claim, fix="confirm it in the app, or re-take the frame"))

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
        # The HASH comparison costs nothing and needs no image, so it runs on every pair whatever
        # the signatures said: an exact re-use is caught unconditionally. Dropping a pair entirely
        # -- which the prefilter used to do -- meant a lightly perturbed copy could satisfy a second
        # shot id with NO record that a comparison had even been considered, and a check that leaves
        # no trace is indistinguishable from one that passed.
        same_bytes = (other.get("sha256") and other.get("self_sha256")
                      and other["sha256"] == other["self_sha256"])
        if same_bytes:
            checks.append(Check("duplicate_content", RETAKE,
                                "byte-identical to %s rep %s, which is already recorded"
                                % (other.get("shot_id"), other.get("rep")),
                                {"other_shot_id": other.get("shot_id"), "other_rep": other.get("rep")},
                                fix="capture a new frame; this one is already in the log"))
            continue
        if n is None:
            if not candidate:
                # Far apart on the recorded signature AND different bytes. That is a decided
                # comparison, not a skipped one, and it is recorded as such.
                checks.append(Check("duplicate_content", PASS,
                                    "distinct from %s rep %s on its recorded signature (Hamming "
                                    "%s, far outside the near-duplicate band) and on its hash"
                                    % (other.get("shot_id"), other.get("rep"), dist),
                                    {"dhash_distance": dist, "compared": "signature+hash",
                                     "other_shot_id": other.get("shot_id")}))
                continue
            # We needed to look and could not: the earlier frame was not available to decode.
            checks.append(Check("duplicate_content", UNAVAILABLE,
                                "could not be compared with %s rep %s -- its signature is within "
                                "the near-duplicate band but its file was not available to decode"
                                % (other.get("shot_id"), other.get("rep")),
                                {"dhash_distance": dist, "other_shot_id": other.get("shot_id")},
                                fix="restore the earlier photograph so the two can be compared"))
            continue
        outcome, detail = Q.duplicate_verdict(other.get("sha256"), other.get("self_sha256"), n)
        # Recorded whichever way it goes. Only the failures were appended, so the most expensive
        # comparison the checker performs -- the one that actually decoded both frames and
        # correlated them -- left NOTHING behind when it passed. An auditor reading the record could
        # not tell a pair that was compared and found distinct from a pair that was never compared,
        # and "no duplicate_content check present" is exactly what a skipped comparison looks like.
        checks.append(Check("duplicate_content", outcome,
                            "%s (against %s rep %s)" % (detail, other.get("shot_id"),
                                                        other.get("rep")),
                            {"ncc": n, "other_shot_id": other.get("shot_id"),
                             "other_rep": other.get("rep"), "compared": "pixels"},
                            fix=None if outcome == PASS
                            else "capture a new frame; this one is already recorded"))
        if other.get("is_previous_rep") and shot.get("relay_between_reps") \
                and applies("relay_independence"):
            interior = Q.registered_interior_ncc(img, oimg, pose, other.get("pose")) \
                if oimg is not None else None
            secs = None
            if other.get("exif_ts") and other.get("this_exif_ts"):
                secs = abs(float(other["this_exif_ts"]) - float(other["exif_ts"]))
            o, d, ev = Q.relay_verdict(other.get("pose"), pose, mm_per_px, interior_ncc=interior,
                                       seconds_apart=secs,
                                       operator_confirmed=bool(assertions.get("relay_confirmed")))
            # Name the frame this verdict is about. The comparison happens once, at ingest, against
            # whatever was filed under the previous repeat at that moment, and the verdict is then
            # frozen into the record -- so replacing the earlier repeat afterwards left a passing
            # relay verdict describing a photograph that is no longer there.
            ev = dict(ev, compared_against_sha256=other.get("sha256"),
                      compared_against=("%s r%s" % (other.get("shot_id"), other.get("rep"))))
            checks.append(Check("relay_independence", o, d, ev,
                                fix="lift the garment clear of the surface, shake it out, and lay "
                                    "it again before this repeat"))
    # A camera reposition leaves no trace in the frame -- the phone coming off the mount and going
    # back on is not visible in the photograph, and a frame taken without doing it looks the same.
    # So it is asked, and the answer is recorded as an assertion with a name on it.
    if shot.get("reposition_camera_between_reps") and int(rep) > 1 \
            and applies("camera_repositioned"):
        if assertions.get("camera_repositioned") is True:
            checks.append(Check("camera_repositioned", PASS,
                                "operator confirmed the camera was taken off the mount and "
                                "remounted before this repeat"))
        else:
            checks.append(Check("camera_repositioned", HUMAN,
                                "this repeat only measures mounting variance if the phone actually "
                                "came off the mount, and nothing in the frame records whether it "
                                "did. Confirm it.",
                                fix="take the phone off the mount, remount it, and re-shoot -- or "
                                    "confirm you already did"))

    if shot.get("relay_between_reps") and not (compare_to or []):
        pass    # the first repetition has nothing to be independent of; that is not a finding

    return checks, not_applicable(c.check_id for c in checks)

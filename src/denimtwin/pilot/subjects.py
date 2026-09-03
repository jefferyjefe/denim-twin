"""Which physical thing a repeat is a photograph OF.

Six shots in the production plan use `min_reps` to mean a different physical SUBJECT rather than a
repetition of one view: two photographs, one of each leg's hem, one of each outseam. Nothing bound a
repeat to its subject, so two photographs of the LEFT leg satisfied both repeats and the right leg's
original hem was never taken -- and after the cut there is no going back for it.

The shot plan already asked a person to confirm it. That claim named every subject the shot has
("this frame shows the garment-LEFT hem / the garment-RIGHT hem"), identically for every repeat, so
confirming repeat 1 and confirming repeat 2 recorded the same sentence twice and distinguished
nothing. A claim that cannot be false for the wrong photograph is not a check.

WHAT THIS DOES AND WHAT IT HONESTLY CANNOT. The software cannot see which leg is in a photograph.
What it can do is make the requirement specific and the answer recorded: the plan states which
subject each repeat is for, the capture records the subject it was taken as, the two must agree, no
two repeats of one shot may record the same subject, and the person confirms a claim that names
THIS repeat's subject and no other. The remaining trust is that the operator read the label they
were asked to read -- which is a physical assumption, is stated as one in PILOT_RUNBOOK.md, and is
not dressed up as verification.

WHERE THE SUBJECTS COME FROM. The shot plan's `rep_semantics` strings are frozen protocol text and
are read here, never rewritten. A string that names a side explicitly binds to that leg; every other
string describes the same subject in a different configuration or at a different position, and is
listed below by hand so that new text FAILS rather than silently falling through to "no subject
distinction required". `tests/test_pilot_subjects.py` asserts the production plan is fully covered.
"""

#: The whole garment, laid out. The default subject: most repeats are re-lays of one view of it.
GARMENT = "GARMENT"
#: The two legs, named by the GARMENT's left and right -- the wearer's, not the viewer's. The shot
#: plan's own strings say "garment-LEFT", and `regions.left_right_convention` defines it.
LEG_L, LEG_R = "LEG.L", "LEG.R"
#: The two offcuts, which become separate physical objects at the cut and are washed apart.
OFFCUT_L, OFFCUT_R = "OFFCUT.L", "OFFCUT.R"
#: The rig itself -- a grey card, the board, a station mark. Not the garment, and a repeat of it is
#: not a re-lay of anything.
APPARATUS = "APPARATUS"

#: One described instance of a counted feature, e.g. FEATURE.TEAR.01. Built from the annotation id,
#: which the log already keys on, so the subject of an instanced frame and the identity
#: `captures.instance_identity` checks are the same fact and cannot disagree.
INSTANCE_PREFIX = "FEATURE."

SUBJECTS = (GARMENT, LEG_L, LEG_R, OFFCUT_L, OFFCUT_R, APPARATUS)


def instance_subject(annotation_id):
    return INSTANCE_PREFIX + str(annotation_id)


def is_subject(v):
    v = str(v or "")
    return v in SUBJECTS or (v.startswith(INSTANCE_PREFIX) and len(v) > len(INSTANCE_PREFIX))


#: A rep_semantics string beginning with one of these names a side, and the subject is that leg.
#: Matched on a prefix, not a substring: "the garment-LEFT hem" binds, and a sentence that merely
#: mentions the left leg somewhere in the middle does not, because a loose match here would bind a
#: repeat to a subject the protocol did not ask for.
_SIDE_PREFIXES = (
    ("the garment-LEFT ", LEG_L),
    ("the garment-RIGHT ", LEG_R),
)

#: rep_semantics strings where the repeats are the SAME subject in a different configuration or at
#: a different position on it. Listed exhaustively rather than defaulted, so that a string this
#: module has never seen is an error at test time instead of a silent loss of the distinction.
#: The subject is the same for both repeats; what separates them is the aspect, which is checked
#: for distinctness in its own right.
_ASPECT_ONLY = {
    "cuffed, as received": GARMENT,
    "uncuffed and flat": GARMENT,
    "rolled as received": GARMENT,
    "unrolled and flat": GARMENT,
    "the interior waistband position": GARMENT,
    "the left side-seam position": GARMENT,
    "card position 1": APPARATUS,
    "card position 2": APPARATUS,
    "card position 3": APPARATUS,
    "card position 4": APPARATUS,
    "card position 5": APPARATUS,
}


class UnknownSemantics(ValueError):
    """A rep_semantics string this module has no reading of.

    Raised rather than defaulted. Defaulting would mean a shot plan edit that adds "the garment-LEFT
    pocket / the garment-RIGHT pocket" quietly stops distinguishing the two pockets, and the failure
    would be invisible until the garment was cut.
    """


def subject_of(text):
    """The subject one rep_semantics string names, by the plan's own words."""
    t = str(text or "").strip()
    if not t:
        raise UnknownSemantics("an empty repetition semantics entry names no subject")
    for prefix, subject in _SIDE_PREFIXES:
        if t.startswith(prefix):
            return subject
    if t in _ASPECT_ONLY:
        return _ASPECT_ONLY[t]
    raise UnknownSemantics(
        "no reading of the repetition semantics %r. Add it to subjects._ASPECT_ONLY if the repeats "
        "are the same physical thing in a different configuration, or give it a side prefix if "
        "they are different things. It is not defaulted, because defaulting it would silently stop "
        "distinguishing two subjects the plan says are different." % t)


def required(shot, rep):
    """What repeat `rep` of this shot must be a photograph of, or None if the shot does not say.

    Returns {"subject_id", "aspect"}. `aspect` is the plan's own sentence for this repeat and is
    what separates two repeats that share a subject. A shot with no `rep_semantics` returns None:
    its repeats are re-lays of one view, which `captures.relays_independent` already governs.
    """
    sem = shot.get("rep_semantics") or []
    if not sem:
        return None
    try:
        r = int(rep)
    except (TypeError, ValueError):
        return None
    if not (1 <= r <= len(sem)):
        # More repeats than the plan gave semantics for. Not a subject question -- and
        # `tests/test_pilot_evidence_honesty.py` already requires len(rep_semantics) == min_reps --
        # so this says "the plan does not name a subject for this repeat" rather than inventing one.
        return None
    aspect = str(sem[r - 1]).strip()
    return {"subject_id": subject_of(aspect), "aspect": aspect}


def claim_for(shot, rep):
    """The claim a person must confirm about THIS repeat, naming THIS repeat's subject only.

    The shot plan's own claim listed every subject the shot has, identically for every repeat, so
    the same sentence cleared repeat 1 and repeat 2 and separated nothing. This names one.
    """
    req = required(shot, rep)
    if not req:
        return None
    return ("this frame shows %s -- repeat %d of %d of %s, and not the subject of another repeat"
            % (req["aspect"], int(rep), len(shot.get("rep_semantics") or []), shot["shot_id"]))


#: The shot plan's generic claim, which `claim_for` replaces. Recognised so `qa.check_capture` can
#: drop it rather than raising both: two claims about one fact, one of which cannot be false, is a
#: person confirming the same thing twice and a gate that reports more evidence than it has.
GENERIC_CLAIM_MARKER = "-- the subject this repeat is for"


def is_generic_subject_claim(text):
    return GENERIC_CLAIM_MARKER in str(text or "")


class WrongSubject(ValueError):
    """A declared subject that is not the one this repeat is for."""


def capture_fields(shot, rep, *, declared=None):
    """The subject fields one capture record carries.

    Called by every ingest path -- the CLI, the phone and the self-test bench -- so the binding is a
    property of ingesting a photograph rather than of which door it came through.

    `declared` is what the operator said they photographed, when they said anything. It is checked
    against what the plan requires and refused when it differs: naming the right leg on the repeat
    the plan reserves for the left is exactly the mistake the binding exists to catch, and silently
    overwriting it with the plan's answer would record agreement that was never given.
    """
    req = required(shot, rep)
    if req is None:
        aid = shot.get("annotation_id")
        if aid:
            # An instanced frame is of one described physical thing, whether or not its repeats
            # differ. Same identity the log already keys on, so the two cannot disagree.
            #
            # This used to RETURN here, skipping the `declared` check below -- so on an instanced
            # frame the operator's --subject was neither honoured nor refused nor even checked for
            # being a subject at all: naming the wrong leg, or a string that means nothing, was
            # accepted and silently replaced by the plan's answer. That is the one thing the
            # docstring above says this function must never do.
            req = {"subject_id": instance_subject(aid), "aspect": None}
        else:
            req = {"subject_id": GARMENT if shot.get("state") != "rig" else APPARATUS,
                   "aspect": None}
    if declared is not None:
        d = str(declared).strip()
        if not is_subject(d):
            raise WrongSubject(
                "%r is not a subject this session knows. They are: %s, or FEATURE.<id> for one "
                "described instance of a counted feature." % (d, ", ".join(SUBJECTS)))
        if d != req["subject_id"]:
            # The reason differs by what kind of shot this is, and this path is reached from all
            # three. Saying "the repeats of this shot are different physical things" about an
            # instanced frame, or about a whole-garment frame, tells the operator something untrue
            # about their own plan.
            if shot.get("rep_semantics"):
                why = ("The repeats of this shot are different physical things, not repetitions "
                       "of one view -- if the photograph really is of %s, it belongs to the "
                       "repeat the plan reserves for it." % d)
            elif shot.get("annotation_id"):
                why = ("This shot is of one described instance, %s. A photograph of %s belongs to "
                       "the shot the plan raised for %s."
                       % (shot["annotation_id"], d, d))
            else:
                why = ("This shot is not of one part in particular, so there is nothing here that "
                       "could be a photograph of %s." % d)
            raise WrongSubject(
                "repeat %s of %s is the photograph of %s%s, and you declared %s. %s"
                % (rep, shot["shot_id"], req["subject_id"],
                   (" (%s)" % req["aspect"]) if req.get("aspect") else "", d, why))
    return {"subject_id": req["subject_id"], "subject_aspect": req.get("aspect")}

"""The one confirmation model, so the CLI and the phone are the same front door.

A human verification is the only thing standing between a requirement no measurement can settle --
an empty backdrop, a lighting test, a proof that the board and the garment share a plane -- and any
file that decodes. There were two doors onto it and they did not admit the same workflow.

WHAT WAS WRONG. `qa.check_capture` names a claim by its check id, and for the claims a shot spells
out that id is `confirmed_` followed by the shot plan's own sentence: up to 204 characters. The CLI
refused any claim over 64, so 164 of the 177 claims the production plan can raise could not be
typed at it at all, while the phone recorded them happily. "The CLI is the source of truth" was not
a testable statement about those frames; it was a slogan with an exception.

Raising the limit would not have been the fix. The claim is an IDENTITY -- `store.fold` keys
verifications on `(shot_id, rep, claim)` and `gates._human_resolved` looks the check id up in that
dictionary -- so an operator confirming from the CLI had to retype a 204-character sentence
verbatim, and a single transposed character wrote a verification of a claim nobody had raised. It
recorded successfully and cleared nothing, which is the worst of the three possible outcomes.

WHAT THIS IS. Claims are addressed by a short stable CODE derived from the claim itself, or by
position in the frame's own list, or by their full text. All three resolve, through this module, to
the identical check id, and both front doors build their log record with `payload()` here. Byte
equivalence of the folded state across the two interfaces is therefore structural rather than
something two code paths happen to agree about, and `tests/test_pilot_confirm_parity.py` asserts it.

WHAT A CONFIRMATION IS BOUND TO. The garment, the shot and repeat, the photograph's own sha256, the
shot plan revision it was made under, and -- for a frame expanded from one described instance of a
counted feature -- that instance's id and its revision. Editing any of those makes the confirmation
stale rather than silently inherited, which is the property the per-frame claims already had for the
photograph alone and nothing else had at all.
"""
import hashlib
import re
import sys

#: The longest claim the production plan can raise is 204 characters: `confirmed_` and a
#: 194-character requirement. 512 leaves room for a longer one without inviting a paragraph -- a
#: claim is an identifier that a person has to be able to read back, not a place for prose. The
#: note field is where prose goes, and it is separately bounded.
MAX_CLAIM_CHARS = 512
MAX_NOTE_CHARS = 4096
MAX_NAME_CHARS = 200

CODE_PREFIX = "H"
CODE_HEX = 10

#: The claims that authorise the cut and are not about any one photograph. They live here because
#: `gates.c_cut_confirmations` enforces them and both front doors have to be able to name them; two
#: copies of this dictionary is two places for the vocabulary to drift apart.
CUT_DAY_CLAIMS = {
    "legs_cut_separately": "confirm the legs will be cut one at a time",
    "offcuts_retained_labelled": "confirm both offcuts will be kept and labelled "
                                 "<GARMENT>_OFFCUT_L / _R",
}

#: The second-person approval of the marks. Separate from CUT_DAY_CLAIMS because it carries two
#: measurements and is checked against the cut specification, not merely recorded.
CUT_MARKS_CLAIM = "cut_marks_verified"

#: The operator saying they read the geometry warning and meant the cut anyway. `gates.c_cut_spec`
#: looks for it by this exact name. It is here because `resolve` refuses a session claim it does not
#: recognise, and a claim the gate requires but the front doors will not accept is a gate that
#: cannot be opened -- `tests/test_pilot_units.py` asserts this set covers every claim gates.py
#: looks up by name.
CUT_OUT_OF_MODEL_CLAIM = "cut_out_of_model_acknowledged"

SESSION_CLAIMS = dict(CUT_DAY_CLAIMS, **{
    CUT_MARKS_CLAIM: "a second person measures both marks with a tape and records the readings",
    CUT_OUT_OF_MODEL_CLAIM: "the operator read the out-of-model geometry warning and meant this cut",
})


class ClaimError(ValueError):
    """A confirmation that cannot be recorded. The message names what to do instead."""


# Control characters have no place in an identifier that is also a dictionary key, a line of a
# JSONL log and a string printed into a terminal. Tab and newline are allowed in the NOTE, which is
# prose, and in nothing else. NUL is rejected everywhere: it is the classic way to make a path
# validated in one language mean something else in another.
#: Everything unprintable EXCEPT tab and newline, which are prose and are allowed in the note and
#: refused in the claim by the explicit tests below. There were two constants here with identical
#: patterns and different names, which read as though the distinction lived in the regex; it does
#: not, and a second copy of one rule is the thing this module exists to avoid.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def claim_code(check_id):
    """A short stable handle for a claim, derived from the claim text and nothing else.

    Derived, not assigned, so the two front doors and the gate cannot disagree about it and no
    registry has to be kept in step with the shot plan. Prefixed so it cannot be mistaken for the
    beginning of a claim's own text.
    """
    h = hashlib.sha256(("denim-twin/claim/" + str(check_id)).encode("utf-8")).hexdigest()
    return CODE_PREFIX + h[:CODE_HEX]


def looks_like_code(v):
    return bool(re.fullmatch(CODE_PREFIX + "[0-9a-f]{%d}" % CODE_HEX, str(v or "").strip()))


def validate_claim(v):
    """The claim as an identifier: non-empty, bounded, printable, no control characters."""
    if v is None:
        raise ClaimError("a verification must say what it verifies")
    s = str(v).strip()
    if not s:
        raise ClaimError("a verification must say what it verifies")
    if len(s) > MAX_CLAIM_CHARS:
        raise ClaimError("a claim is at most %d characters; this one is %d. A claim is the "
                         "identifier of a requirement, not its explanation -- put the explanation "
                         "in --note." % (MAX_CLAIM_CHARS, len(s)))
    if _CONTROL.search(s) or "\n" in s or "\r" in s or "\t" in s:
        raise ClaimError("a claim may not contain control characters or line breaks; it is a "
                         "dictionary key and a line of an append-only log. Use --note for text "
                         "that needs them.")
    return s


def validate_note(v):
    """The note as prose: line breaks and tabs allowed, everything else printable, bounded."""
    if v is None:
        return None
    s = str(v)
    if len(s) > MAX_NOTE_CHARS:
        raise ClaimError("a note is at most %d characters; this one is %d"
                         % (MAX_NOTE_CHARS, len(s)))
    if _CONTROL.search(s):
        raise ClaimError("the note contains a control character; only line breaks and tabs are "
                         "allowed alongside printable text")
    s = s.strip()
    return s or None


def validate_name(v, *, field):
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if len(s) > MAX_NAME_CHARS:
        raise ClaimError("%s is at most %d characters" % (field, MAX_NAME_CHARS))
    if _CONTROL.search(s) or "\n" in s or "\r" in s:
        raise ClaimError("%s may not contain control characters or line breaks" % field)
    return s


def raised_claims(state, shot_id, rep):
    """Every claim the CURRENT accepted photograph for this frame referred to a person.

    Read from the qa record, which is the same place `gates._human_resolved` reads them, so the
    list an operator is offered is exactly the list the gate will look for. Deriving it from the
    shot plan instead would offer claims for checks that did not fire and omit the ones that did.
    """
    from . import qa as QA
    q = state["qa"].get((shot_id, rep))
    if not q:
        return []
    out, seen = [], set()
    for c in (q.get("checks") or []):
        if c.get("outcome") == QA.HUMAN:
            cid = c.get("check_id")
            # ONE ENTRY PER CHECK ID. A shot that names the same requirement twice raised the claim
            # twice, `resolve` then found two matches for its code and refused to resolve it at
            # either door -- so a duplicated line in the shot plan made a claim impossible to
            # confirm. The gate keys verifications on (shot, rep, claim), so one confirmation
            # clears it however many times the checker mentioned it.
            if cid and cid not in seen:
                seen.add(cid)
                out.append({"claim": cid, "code": claim_code(cid),
                            "detail": c.get("detail") or "", "fix": c.get("fix") or ""})
    out.sort(key=lambda r: r["claim"])
    for i, r in enumerate(out, 1):
        r["index"] = i
    return out


def plan_claims(shot, rep):
    """The claims the SHOT PLAN requires of this frame, whatever the record happens to say.

    A revision that adds a `requires_human` claim to an already-photographed shot is required by
    the gate (`captures.required_complete` re-derives it from the plan) and was raised by nobody,
    so it appears in no qa record. Without this it could be neither listed nor confirmed at either
    front door, and the block naming it would have had no reachable remedy.
    """
    from . import qa as QA
    return QA.human_claim_ids(shot, rep) if shot else []


def pending_claims(state, shot_id, rep, shot=None):
    """Every claim outstanding on this frame, with why each one is or is not cleared.

    `shot` is the ACTIVATED shot from the plan on disk, when the caller has it: claims the plan
    requires but the record never raised belong on this list too, and only the plan knows them.
    """
    from .gates import _verification_for
    seen, out = set(), []
    for r in raised_claims(state, shot_id, rep):
        rec, why = _verification_for(state, shot_id, rep, r["claim"])
        seen.add(r["claim"])
        out.append(dict(r, resolved=(rec is not None and why is None), why=why))
    for cid in plan_claims(shot, rep):
        if cid in seen:
            continue
        rec, why = _verification_for(state, shot_id, rep, cid)
        out.append({"claim": cid, "code": claim_code(cid), "index": len(out) + 1,
                    "detail": "required by the shot plan; this frame was accepted before the "
                              "requirement existed",
                    "fix": "confirm it, or re-take the frame",
                    "resolved": (rec is not None and why is None), "why": why})
    return out


def resolve(state, shot_id, rep, *, claim=None, code=None, index=None, shot=None):
    """One claim selector -> the exact check id the gate will look for.

    Accepts the claim's full text, its short code, or its position in this frame's own list. All
    three come back as the identical string, which is what makes the two front doors write the same
    record. An ambiguous or unmatched selector raises with the frame's claims listed, because the
    failure this replaces -- recording a verification of a claim nobody raised -- was silent.
    """
    given = [x for x in (claim, code, index) if x is not None]
    if len(given) != 1:
        raise ClaimError("name the claim exactly one way: its text, --claim-code, or --claim-index")

    raised = raised_claims(state, shot_id, rep) if shot_id else []
    # Plus anything the plan on disk requires that the record never raised, or a claim added by a
    # revision could be named at neither door.
    if shot_id and shot is not None:
        known = {r["claim"] for r in raised}
        for cid in plan_claims(shot, rep):
            if cid not in known:
                raised = raised + [{"claim": cid, "code": claim_code(cid),
                                    "detail": "required by the shot plan on disk", "fix": "",
                                    "index": len(raised) + 1}]

    if index is not None:
        # `int(True)` is 1, so a JSON `true` posted as claim_index silently confirmed the frame's
        # first claim. The CLI's argparse refuses it; this is the same rule for the other door.
        if isinstance(index, bool) or not isinstance(index, (int, str)):
            raise ClaimError("--claim-index is a whole number")
        try:
            i = int(index)
        except (TypeError, ValueError):
            raise ClaimError("--claim-index is a whole number")
        if not raised:
            raise ClaimError(_no_claims_message(state, shot_id, rep))
        if not (1 <= i <= len(raised)):
            raise ClaimError("this frame raised %d claim(s); %d is not one of them.\n%s"
                             % (len(raised), i, _listing(raised)))
        return raised[i - 1]["claim"]

    if code is not None:
        c = str(code).strip().lower()
        hit = [r for r in raised if r["code"].lower() == c]
        if len(hit) == 1:
            return hit[0]["claim"]
        for name in sorted(SESSION_CLAIMS):
            if claim_code(name).lower() == c:
                return name
        if not shot_id:
            # No --shot, so `raised` is empty by construction and this is a session claim that was
            # mistyped. Saying "no photograph has been accepted for None repeat None" sends the
            # operator to `pilot.py add` for a claim that has nothing to do with a photograph.
            raise ClaimError(_unknown_session_claim(code))
        if not raised:
            raise ClaimError(_no_claims_message(state, shot_id, rep))
        raise ClaimError("no claim on this frame has code %r.\n%s" % (code, _listing(raised)))

    text = validate_claim(claim)

    # A code passed positionally, which is what an operator copying from `pilot.py claims` will do.
    if looks_like_code(text):
        return resolve(state, shot_id, rep, code=text)

    # The exact check id, which is what the gate stores and what the listing prints.
    for r in raised:
        if r["claim"] == text:
            return text
    # The shot plan's own sentence, without the `confirmed_` the check id carries. An operator
    # reading the requirement off the screen types the sentence, not the identifier.
    for r in raised:
        if r["claim"] == "confirmed_" + text:
            return r["claim"]
    # A claim that belongs to the session rather than to any one photograph.
    if text in SESSION_CLAIMS:
        return text
    if shot_id and raised:
        raise ClaimError("this frame raised no claim %r.\n%s" % (text, _listing(raised)))
    if shot_id:
        raise ClaimError(_no_claims_message(state, shot_id, rep))
    raise ClaimError(_unknown_session_claim(text))


def _unknown_session_claim(what):
    return ("%r is not a claim this session recognises. The claims that belong to the session "
            "rather than to one photograph are: %s. A claim about a photograph needs --shot."
            % (what, ", ".join(sorted(SESSION_CLAIMS))))


def _no_claims_message(state, shot_id, rep):
    if not state["captures"].get((shot_id, rep)):
        return ("no photograph has been accepted for %s repeat %s, so there is nothing about it to "
                "confirm. Ingest the frame first (`pilot.py add`)." % (shot_id, rep))
    return ("the accepted photograph for %s repeat %s raised no claim for a person. Nothing here "
            "needs confirming." % (shot_id, rep))


def _listing(raised):
    return "This frame's claims:\n" + "\n".join(
        "  [%d] %s  %s" % (r["index"], r["code"], r["claim"]) for r in raised)


def binding(state, spec, shot_id, rep):
    """What a confirmation of this frame is ABOUT, beyond the claim's name.

    The photograph's own hash was already bound. The rest was not: a frame expanded from one
    described instance of a counted feature means whatever that description says, and correcting the
    description after the photograph was accepted left the confirmation attached to a sentence
    nobody had confirmed. The instance's id and the entry that last wrote it travel with the record
    so the gate can tell those apart.
    """
    out = {"garment_id": state.get("garment_id"),
           "spec_hash": getattr(spec, "content_hash", None) if spec is not None else None}
    cap = state["captures"].get((shot_id, rep)) if shot_id else None
    if cap:
        out["capture_sha256"] = cap.get("sha256")
        aid = cap.get("annotation_id")
        if aid:
            ann = (state.get("annotations") or {}).get(aid) or {}
            out["annotation_id"] = aid
            # The entry that last WROTE this instance. A revision stamps `revised_at`; a first
            # description has only its creation seq. Either way it changes when the description
            # changes, and a confirmation carrying the old value is stale.
            out["annotation_revision"] = ann.get("revised_at") or ann.get("first_seq") \
                or ann.get("seq")
    return out


def validate_value(v):
    """The answer, which is a BOOLEAN and is not coerced.

    `bool(value)` turned every non-empty string into an approval, and the web door passes the
    request's JSON straight in: an operator who looked at the frame, typed "no, the backdrop is NOT
    empty" into the value field and posted it had their refusal recorded as `value: true`. The gate
    is careful here -- `_verification_for` refuses anything that `is not True` -- and that care was
    undone one layer above it, on the door the phone actually posts to.
    """
    if isinstance(v, bool):
        return v
    raise ClaimError("a verification's value is yes or no and nothing else; %r is neither. If you "
                     "are refusing this claim, say so with the refusal and put the explanation in "
                     "the note." % (v,))


def payload(*, claim, shot_id=None, rep=None, value=True, note=None, operator=None,
            verifier=None, measured_inseam_cm=None, measured_outseam_cm=None,
            bind=None, interface=None, entry_mode=None):
    """THE record. Both front doors build their `human_verification` entry here.

    Every field either identifies the claim, binds it to what it is about, or attributes it. The two
    that do neither -- `interface` and `entry_mode` -- are transport, are named as transport, and
    are the only fields the parity test excludes when it compares the two folded states.

    WHAT `entry_mode` DOES NOT SAY. On the command line it is observed: a terminal on both ends is
    `interactive`, anything else is `scripted`. The server cannot observe the equivalent -- a POST
    from a phone and a POST from a script are the same bytes -- so the web door records
    `app:unattested`, which is what it can actually stand behind. Nothing in `gates.py` reads either
    field, and neither is evidence that a person was present; `cut.second_person_verified` rests on
    the two names differing and on the protocol, not on this.
    """
    claim = validate_claim(claim)
    p = {
        "shot_id": shot_id,
        "rep": rep,
        "claim": claim,
        "claim_code": claim_code(claim),
        "value": validate_value(value),
        "note": validate_note(note),
        "verifier_name": validate_name(verifier, field="verifier") or
                         validate_name(operator, field="operator"),
        "operator": validate_name(operator, field="operator"),
        "measured_inseam_cm": measured_inseam_cm,
        "measured_outseam_cm": measured_outseam_cm,
    }
    for k, v in sorted((bind or {}).items()):
        if v is not None:
            p[k] = v
    p.setdefault("capture_sha256", None)
    # Transport. Recorded because "was this typed at a terminal or posted by a script" is a real
    # question about a human verification, and excluded from the parity comparison because it is
    # the one thing the two front doors are SUPPOSED to disagree about.
    p["interface"] = interface
    p["entry_mode"] = entry_mode
    return p


#: The fields `payload` records that describe the route in rather than the claim. The parity test
#: drops exactly these before comparing, so adding a transport field cannot quietly widen the
#: exemption: it has to be added here, in the open.
TRANSPORT_FIELDS = ("interface", "entry_mode")


def cli_entry_mode(stdin=None, stdout=None):
    """Interactive means a person at a terminal; anything else is a script."""
    i = stdin if stdin is not None else sys.stdin
    o = stdout if stdout is not None else sys.stdout
    try:
        return "interactive" if (i.isatty() and o.isatty()) else "scripted"
    except (AttributeError, ValueError):
        return "scripted"

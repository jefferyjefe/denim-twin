"""Which offcut goes into which wash, computed rather than remembered.

PROTOCOL.md 7 keeps two samples from every garment and puts them in different washes: one follows
the standard protocol in the SAME load as the garment, the other is washed in a separate standard
load as a repeat-wash noise sample. Then:

    Alternate which leg (L/R) gets which condition across garments to avoid confounding.

That sentence is the whole point of this module. If the left offcut always went in with the garment,
then "left" and "washed with the garment" would be the same variable, and any difference between the
two conditions could equally be a difference between the two legs -- which is not a hypothetical,
because a right-handed wearer's legs do not wear identically and the protocol already records
asymmetry as a feature. The alternation breaks that, and it only works if it is actually alternated,
which is why it is derived from the existing records instead of left to whoever is holding the
scissors.

A garment whose care label forbids machine washing is a special case the protocol also names: it is
washed per its label, and the standard-protocol data point comes from the offcut. That changes what
the second offcut is FOR (a scrap-versus-garment control rather than a repeat-wash sample), and it
is recorded as such rather than silently reusing the same condition name.
"""
import json
import re
from pathlib import Path

#: The two conditions of PROTOCOL.md 7.
WITH_GARMENT = "standard_same_load_as_garment"
SEPARATE_LOAD = "standard_separate_load"
#: Used instead of SEPARATE_LOAD when the garment itself could not follow the standard protocol.
GARMENT_CONDITION = "matches_garment_deviation"


#: The records written before this module existed use their own words for the two arms --
#: DENIM_0001 carries {"L": "standard_machine", "R": "hand_wash_hang_dry"}, which is PROTOCOL.md 7's
#: named special case: the garment is hand-wash-only, so the STANDARD-protocol data point comes from
#: the L offcut and the R offcut matches the garment's own condition. Reading that history is the
#: whole point of computing the alternation, so the legacy vocabulary is recognised rather than
#: rewritten -- editing those records to match a newer spelling would be changing the evidence.
def _is_standard_arm(v):
    """Is this the offcut that followed the STANDARD protocol (the arm the alternation tracks)?"""
    if not v:
        return False
    v = str(v).lower()
    if v == WITH_GARMENT or "same" in v or "with_garment" in v:
        return True
    return "standard" in v and "separate" not in v


#: The only conditions an offcut may be assigned. Free text let both samples go into the same load
#: under two spellings, and let a broken alternation read as intact because `_is_standard_arm` did
#: not recognise the wording.
CONDITIONS = (WITH_GARMENT, SEPARATE_LOAD, GARMENT_CONDITION)


def classify(v):
    """Which arm a recorded condition names, or None if it names nothing this code knows.

    None is the important return. history() used to SKIP a garment whose conditions it could not
    classify, so an unrecognised spelling removed that garment from the alternation entirely and a
    broken alternation read as intact.
    """
    if not v:
        return None
    if v in CONDITIONS:
        return "standard" if v == WITH_GARMENT else "other"
    v = str(v).lower()
    if v == WITH_GARMENT or "same" in v or "with_garment" in v:
        return "standard"
    if "standard" in v and "separate" not in v:
        return "standard"           # the legacy vocabulary; see the note above
    if "separate" in v or "hand_wash" in v or "matches_garment" in v:
        return "other"
    return None


def _garment_ids(garments_dir):
    out = []
    for p in sorted(Path(garments_dir).glob("DENIM_*")):
        if p.is_dir() and re.fullmatch(r"DENIM_\d{4}", p.name):
            out.append(p.name)
    return out


def history(garments_dir):
    """For each garment already assigned, which leg went in with the garment. Chronological by id.

    Returns (history, unclassified). A garment whose conditions cannot be classified is REPORTED
    rather than skipped: skipping it removed it from the alternation, and a broken alternation then
    read as intact.
    """
    out, unclassified = [], []
    for gid in _garment_ids(garments_dir):
        d = Path(garments_dir) / gid
        assigned = None
        rec = d / "record.json"
        if rec.exists():
            try:
                ow = json.loads(rec.read_text()).get("offcut_wash") or {}
                kinds = {leg: classify(ow.get(leg) or ow.get(leg.lower()))
                         for leg in ("L", "R")}
                if ow and any(v is None for v in kinds.values()):
                    unclassified.append({"garment_id": gid, "conditions": ow})
                for leg in ("L", "R"):
                    if kinds.get(leg) == "standard":
                        assigned = leg
            except (ValueError, OSError):
                pass
        man = d / "pilot" / "manifest.jsonl"
        if assigned is None and man.exists():
            try:
                for line in man.read_text(errors="replace").split("\n"):
                    if not line.strip():
                        continue
                    try:
                        e = json.loads(line)
                    except ValueError:
                        continue
                    if e.get("kind") != "offcut":
                        continue
                    p_ = e.get("payload") or {}
                    if classify(p_.get("assigned_wash_condition")) == "standard":
                        assigned = str(p_.get("originating_leg", ""))[:1].upper() or None
                    elif classify(p_.get("assigned_wash_condition")) is None \
                            and p_.get("assigned_wash_condition"):
                        unclassified.append({"garment_id": gid,
                                             "conditions": p_.get("assigned_wash_condition")})
            except OSError:
                pass
        if assigned:
            out.append({"garment_id": gid, "with_garment_leg": assigned})
    return out, unclassified


def next_assignment(garments_dir, garment_id, *, garment_machine_washable=True):
    """Which leg goes in with the garment this time, and why.

    Deterministic, and derived: it is the opposite of the last garment that recorded an assignment.
    With no history it starts at L, so the sequence over garments is L, R, L, R.
    """
    hist = [h for h in history(garments_dir)[0] if h["garment_id"] != garment_id]
    if hist:
        last = hist[-1]
        leg = "R" if last["with_garment_leg"] == "L" else "L"
        why = ("alternating from %s, whose %s offcut went in with the garment"
               % (last["garment_id"], last["with_garment_leg"]))
    else:
        leg, why = "L", "no previous assignment recorded; the alternation starts at L"
    other = "R" if leg == "L" else "L"
    second = SEPARATE_LOAD if garment_machine_washable else GARMENT_CONDITION
    return {
        "garment_id": garment_id,
        "with_garment": {"leg": leg, "label": "%s_OFFCUT_%s" % (garment_id, leg),
                         "condition": WITH_GARMENT},
        "other": {"leg": other, "label": "%s_OFFCUT_%s" % (garment_id, other),
                  "condition": second},
        "reason": why,
        "note": ("the garment cannot be machine washed, so it follows its care label and the "
                 "standard-protocol data point comes from the %s offcut; the other offcut matches "
                 "the garment's own condition as a scrap-versus-garment control" % leg)
        if not garment_machine_washable else
        ("one offcut is washed in the same load as the garment, the other in a separate standard "
         "load as a repeat-wash noise sample"),
        "history": hist[-4:],
    }


def check_alternation(garments_dir):
    """Has the alternation actually alternated? Returns the runs that broke it."""
    hist, unclassified = history(garments_dir)
    breaks = []
    for a, b in zip(hist, hist[1:]):
        if a["with_garment_leg"] == b["with_garment_leg"]:
            breaks.append({"after": a["garment_id"], "then": b["garment_id"],
                           "both_assigned": a["with_garment_leg"],
                           "why_it_matters": "two consecutive garments put the same leg in with the "
                                             "garment, so leg and wash condition are confounded "
                                             "across that pair"})
    return {"n_assigned": len(hist), "breaks": breaks,
            "alternating": (not breaks) and not unclassified,
            "unclassified": unclassified,
            "sequence": [h["with_garment_leg"] for h in hist]}

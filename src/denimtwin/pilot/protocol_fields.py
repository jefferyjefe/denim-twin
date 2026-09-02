"""Which `[FILL]` fields PROTOCOL.md still has open, and which mechanism answers each one.

WHY THIS MODULE EXISTS
----------------------
`tools/protocol_audit.py` looked for unfilled fields with

    re.findall(r"`\\[FILL[^\\]]*\\]`", proto)

which requires a backtick immediately before `[FILL` AND immediately after the closing bracket.
Six of the protocol's fields are not written that way -- they are written `[FILL] cm`, `[FILL] ml`,
`[FILL] hours`, `[FILL] min`, `[FILL] mm` and a bare `[FILL]` for the dryer setting, so the unit
sits inside the code span and the closing backtick is not adjacent to the bracket. The audit could
not see any of them. It also counted two occurrences that are not fields at all: the sentence in
the preamble that explains the convention, and the sentence in the rig blockquote that refers to
"the `[FILL]` fields in this section".

So the audit reported 15 where the document has 19, and 2 of the 15 were prose.

That miscount is not cosmetic, because of this rule in the same file:

    if fills and (r.get("wash") or r.get("cut_tool")):
        hard.append("physical steps recorded while protocol has unfilled [FILL] fields")

It is the only HARD finding protecting the pilot from cutting and washing a garment against a
protocol that has not been decided. It fires on `if fills`. Fill the 13 real fields the regex can
see and `fills` becomes empty -- while the mount height, the water temperature, the detergent
volume, the dryer setting and duration, the conditioning period and the thread-count window are
all still open. The guard stops firing at exactly the moment the remaining holes are the physical
settings the wash and the cut depend on.

WHAT COUNTS AS A FIELD
----------------------
A field is a `[FILL...]` occurrence on a list item -- `- ` or `4. `. Every one of the document's
real fields is written as a list item; both prose mentions are not. `classify()` then says, for
each one, which mechanism is supposed to answer it, and `unclassified()` names any field this
module does not know about, so that adding a field to PROTOCOL.md fails a test rather than being
silently dropped from the count.
"""
import re

#: A `[FILL]`, `[FILL: hint]` or `[FILL] unit` occurrence, wherever it appears.
FILL_RE = re.compile(r"\[FILL[^\]]*\]")

#: A markdown list item: "- ..." or "4. ...", with optional indent and optional blockquote marker.
_LIST_ITEM_RE = re.compile(r"^\s*(?:>\s*)?(?:[-*+]|\d+\.)\s")

#: How each open field gets answered. The key is a substring of the line the field sits on, chosen
#: to be stable against rewording of the surrounding prose.
#:
#:   "session"  -- frozen per garment by `tools/pilot.py setup`, hashed, and attached to every
#:                 photograph. Filling the document fixes the standing default ACROSS garments;
#:                 the freeze is what makes one garment's evidence attributable. Not a blocker for
#:                 a pilot run, because the run records its own answer.
#:   "wash"     -- recorded per garment by `tools/pilot.py wash` into the wash block.
#:   "cut"      -- recorded per garment when the cut is performed.
#:   "open"     -- nothing in the navigator answers this. It is a standing decision the owner has
#:                 to make and write down, and it blocks the protocol being frozen.
COVERAGE = (
    ("- Background:",           "session", "backdrop"),
    ("- Calibration board:",    "session", "board_square_measured (the setup calibration reading)"),
    ("- Lighting:",             "session", "lighting"),
    ("- Camera:",               "session", "camera_model / mount_height_cm"),
    ("- Lay protocol:",         "session", "leg_gap_cm"),
    ("4. Cut:",                 "cut",     "cut_tool on the cut record"),
    ("- Machine:",              "wash",    "wash.machine / wash.location"),
    ("- Cycle:",                "wash",    "wash.cycle / water_temp_c / spin_rpm"),
    ("- Detergent:",            "wash",    "wash.detergent / detergent_ml"),
    ("- Load:",                 "wash",    "wash.filler_load"),
    ("- Dryer:",                "wash",    "wash.dryer_method / dryer_setting / dryer_minutes"),
    ("- Conditioning:",         "wash",    "wash.conditioning_start / conditioning_end"),
    ("- thread count within",   "open",    None),
)


def fields(text):
    """Every real `[FILL]` field in the protocol text, in document order.

    Returns a list of dicts: line (1-based), raw (the matched text), context (the whole line).
    Occurrences in running prose are excluded -- they describe the convention, they are not fields.
    """
    lines = text.splitlines()
    out = []
    for m in FILL_RE.finditer(text):
        ln = text.count("\n", 0, m.start()) + 1
        context = lines[ln - 1]
        if not _LIST_ITEM_RE.match(context):
            continue                      # the preamble sentence, and the rig blockquote sentence
        out.append({"line": ln, "raw": m.group(0), "context": context.strip()})
    return out


def classify(text):
    """fields(), each tagged with the mechanism that answers it: session / wash / cut / open."""
    out = []
    for f in fields(text):
        tag, answered_by = None, None
        for needle, t, by in COVERAGE:
            if needle in f["context"]:
                tag, answered_by = t, by
                break
        out.append(dict(f, coverage=tag, answered_by=answered_by))
    return out


def unclassified(text):
    """Fields COVERAGE does not know about. A non-empty result means this module has drifted."""
    return [f for f in classify(text) if f["coverage"] is None]


def summary(text):
    """{'session': n, 'wash': n, 'cut': n, 'open': n, 'unknown': n} over the real fields."""
    counts = {"session": 0, "wash": 0, "cut": 0, "open": 0, "unknown": 0}
    for f in classify(text):
        counts[f["coverage"] or "unknown"] += 1
    return counts

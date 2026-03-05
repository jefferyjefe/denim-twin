"""What the page's own words evidence: how many washes, and whether the hem frayed.

This project predicts **one** wash on a **raw** cut edge. A photo taken after several washes is a different quantity,
and a photo whose page never says is an unknown one. Review 5 asked for that gate; review 6 found it had been written
twice, differently, in two tools — the strict version in `tools/ingest_unpaired.py` (the channel supplying one sample)
and a blocklist in `tools/fringe_unpaired.py` (the channel supplying five). The blocklist's default for an unknown
count was ACCEPT, and its fray test was a substring with no polarity, so "the hem did not fray at all" read as
evidence that the hem frayed.

One implementation, both channels. The rules:

  wash_count(note) -> "one" | "more_than_one" | "unknown"
      "one" requires an EXPLICIT singular ("one wash", "once", "after the first wash", "einmal", "una vez", ...).
      A bare plural is not evidence of many: "After one wash. Later washes deepen the fray." states one wash for the
      photograph and mentions the rest in passing — review 6 flagged the old blocklist for refusing exactly that.
      What does mean many is a counted plural: "twice", "several washes", "a couple of washings", "washing and
      wearing". Silence is "unknown", and unknown is refused, not admitted.

  hem_frayed(note, hem_finish) -> (bool, reason)
      A note that denies fraying is not evidence of fraying, whatever substrings it contains.
"""
import re

# en / de / fr / es / it / sv / da / no / fi — the languages the harvested tutorials are actually written in
_WASH_STEMS = ("wash", "dryer", "dried", "laundr", "lav", "wasch", "wäsche", "lessive", "bucato", "tvätt", "tvatt",
               "vask", "pesu")
_MANY = ("several wash", "few wash", "couple of wash", "multiple wash", "many wash", "twice", "two washes",
         "second wash", "third wash", "each wash", "every wash", "repeated wash", "some washing",
         "washing and wearing", "a few times", "several times", "couple of washing", "few washing", "some wash")
_ONE = ("one wash", "once", "single wash", "first wash", "one cycle", "a single", "1 wash", "one time",
        "einmal", "una vez", "en gang", "en gång", "une fois", "un lavado", "un lavaggio")
_NOT_FRAYED = ("did not fray", "didn't fray", "didnt fray", "dont fray", "don't fray", "no fray", "not fray",
               "without fraying", "no fraying", "would not fray", "wouldn't fray", "won't fray", "wont fray",
               "never frayed", "never fray", "doesn't fray", "does not fray", "doesnt fray", "stop it fraying",
               "stop them fraying", "prevent fray", "keep it from fraying", "so it will not fray")


def mentions_a_wash(note):
    low = (note or "").lower()
    return any(w in low for w in _WASH_STEMS)


def wash_count(note):
    """"one", "more_than_one" or "unknown" — see the module docstring for why silence is not "one"."""
    low = (note or "").lower()
    if any(w in low for w in _MANY): return "more_than_one"
    if any(w in low for w in _ONE): return "one"
    return "unknown"


def single_wash_evidence(note, require_mention=True):
    """(ok, reason). `ok` only when the note states, in its own words, that the garment was washed exactly once."""
    if require_mention and not mentions_a_wash(note):
        return False, "state_evidence_does_not_mention_a_wash"
    c = wash_count(note)
    if c == "more_than_one": return False, "more_than_one_wash"
    if c == "unknown": return False, "wash_count_unknown"
    return True, ""


def hem_frayed(note, hem_finish=None):
    """(ok, reason). A structured `hem_finish == "frayed"` is evidence; so is a note that says it frayed. A note that
    says it did NOT is not — the old substring test accepted "the hem did not fray at all after the wash"."""
    low = (note or "").lower()
    if any(n in low for n in _NOT_FRAYED):
        return False, "evidence_says_the_hem_did_not_fray"
    if hem_finish == "frayed": return True, ""
    if re.search(r"\bfray", low): return True, ""
    return False, "hem_finish_not_evidenced_as_frayed"

"""One implementation of "how many washes, and did it fray" — review 6, finding 7.

The gate was written twice: strictly in `tools/ingest_unpaired.py` (the channel that supplied one sample) and as a
blocklist in `tools/fringe_unpaired.py` (the channel that supplied five). The blocklist's default for an unstated
wash count was ACCEPT, its bare plural "washes" refused a legitimate single-wash note, and its fray test was a
substring with no polarity, so "the hem did not fray at all" counted as evidence that the hem frayed.
"""
import ast, os, sys
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from denimtwin.evidence import wash_count, single_wash_evidence, hem_frayed, mentions_a_wash


@pytest.mark.parametrize("note", [
    "Finished shorts after washing (text: wash and let the fray happen)",
    "Finished shorts flat lay (after washer/dryer per text)",
    "in die Waschmaschine gegeben",
    "washed and dried before the photo",
])
def test_an_unstated_wash_count_is_refused_not_assumed_to_be_one(note):
    ok, why = single_wash_evidence(note)
    assert not ok and why == "wash_count_unknown", (note, ok, why)


@pytest.mark.parametrize("note", [
    "UPDATE photo 'after some washing and wearing': whole shorts flat on patterned rug, heavy fray",
    "washed it twice before photographing",
    "after a couple of washings",
    "several washes later the fray is deep",
    "I wear and wash these a few times a week",
])
def test_a_counted_plural_is_refused(note):
    assert single_wash_evidence(note) == (False, "more_than_one_wash"), note


@pytest.mark.parametrize("note", [
    "After ONE wash. Later washes deepen the fray.",
    "straight out of the machine after the first wash",
    "nach einmal waschen",
    "después de un lavado",
])
def test_an_explicit_singular_is_accepted_even_beside_a_bare_plural(note):
    ok, why = single_wash_evidence(note)
    assert ok, (note, why)


def test_silence_about_washing_at_all_is_refused_first():
    assert single_wash_evidence("flat lay on a wooden floor") == (False, "state_evidence_does_not_mention_a_wash")
    assert not mentions_a_wash("flat lay on a wooden floor")


@pytest.mark.parametrize("note", [
    "the hem did not fray at all after the wash",
    "no fraying on this pair",
    "I hemmed it so it would not fray",
    "these don't fray because I serged them",
])
def test_a_note_denying_fray_is_not_evidence_of_fray(note):
    ok, why = hem_frayed(note)
    assert not ok and why == "evidence_says_the_hem_did_not_fray", (note, ok, why)


def test_a_note_denying_fray_overrides_a_structured_frayed_label():
    """If the page's own words contradict the label we typed in, the words win — the label is our transcription."""
    assert hem_frayed("the hem did not fray", hem_finish="frayed")[0] is False


def test_frayed_evidence_is_accepted_from_either_source():
    assert hem_frayed("frayed nicely after the wash")[0] is True
    assert hem_frayed("whole shorts flat on a rug", hem_finish="frayed")[0] is True
    assert hem_frayed("whole shorts flat on a rug")[0] is False


def test_both_channels_call_the_shared_gate_and_neither_keeps_a_private_copy():
    """The defect review 6 found was two implementations, not a wrong one. This fails if either tool grows its own."""
    for tool in ("ingest_unpaired.py", "fringe_unpaired.py"):
        src = open(os.path.join(ROOT, "tools", tool)).read()
        assert "from denimtwin.evidence import" in src, f"{tool} does not use the shared evidence gate"
        tree = ast.parse(src)
        literals = [[e.value for e in n.elts] for n in ast.walk(tree)
                    if isinstance(n, (ast.Tuple, ast.List)) and n.elts
                    and all(isinstance(e, ast.Constant) and isinstance(e.value, str) for e in n.elts)]
        for vals in literals:
            joined = " ".join(vals).lower()
            assert "several wash" not in joined and "one wash" not in joined, \
                f"{tool} carries its own wash-phrase list again: {vals}"

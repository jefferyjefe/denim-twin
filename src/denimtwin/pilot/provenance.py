"""Six questions about one piece of evidence, answered from the log alone.

The questions are the ones anybody asks of a scientific record months later, and until now the
system could answer some of them by accident and none of them on request:

  1. what physical thing does this refer to
  2. when in the garment lifecycle was it collected
  3. who or what supplied the information
  4. what later data depends on it
  5. whether it was modified after capture
  6. whether the system considers it sufficient evidence, and why

Question 4 is the one that had no answer at all. There is exactly one recorded dependency edge in
the system -- `cut_spec["inputs"]`, the measurements the cut geometry was derived from -- and
nothing read it, which is how a corrected thigh measurement could leave a stale cut line with the
gate still green. The others are structural: a QA verdict names the photograph it judged by
sha256, a verification names the photograph it clears, an instanced frame names the annotation it
is of, the hem series is SIZED from the leg opening, and the offcut alternation is decided by the
wash record. This module makes those edges explicit and queryable, so "this datum is wrong, what
else must be redone" has an answer that is derived rather than remembered.

Nothing here decides anything. It reports what the log says and what the gate said about it; a
question it cannot answer is reported as unanswered rather than guessed.
"""
from . import gates as GATES
from . import plan as PLAN


def _mean(m):
    from .store import mean_of
    return mean_of(m)


def dependents(state, kind, key):
    """What else in this session was derived from, or is bound to, this datum.

    Returns a list of {"what", "why"} — the thing that depends on it and the edge that makes it so.
    """
    out = []
    if kind == "measurement":
        cs = state.get("cut_spec") or {}
        if key in (cs.get("inputs") or {}):
            out.append({"what": "cut_spec",
                        "why": "the cut line was computed from this measurement (cut_spec.inputs "
                               "records the value used: %r)" % (cs["inputs"][key],)})
        if key == "leg_opening_cm":
            out.append({"what": "the hem macro series",
                        "why": "the number of hem positions around each loop is SIZED from the leg "
                               "opening, so changing it changes which frames are required"})
        if key in GATES.REQUIRED_MEASUREMENTS:
            out.append({"what": "gate condition measurements.complete",
                        "why": "required before the cut, with %d independent reading(s)"
                               % GATES.REQUIRED_MEASUREMENTS[key]})
        if key in GATES.POST_WASH_MEASUREMENTS:
            out.append({"what": "gate condition measurements.post_wash",
                        "why": "shrinkage is this value before the wash minus the same value after"})
    elif kind == "annotation":
        for sid, rep in sorted(state["captures"]):
            c = state["captures"][(sid, rep)]
            if c.get("annotation_id") == key:
                out.append({"what": "capture %s r%s" % (sid, rep),
                            "why": "this photograph was taken of this annotation"})
        out.append({"what": "gate condition annotations.identify_instances",
                    "why": "the counted features must be described one instance at a time"})
    elif kind == "capture":
        sid, rep = key
        for (vs, vr, claim) in sorted(state["verifications"], key=lambda k: tuple(str(x) for x in k)):
            if vs == sid and (vr == rep or vr is None):
                out.append({"what": "human verification %r" % claim,
                            "why": "a person's assertion bound to this photograph"})
        if (sid, rep) in state["qa"]:
            out.append({"what": "the QA verdict on this frame",
                        "why": "the verdict names this photograph's sha256 and is re-derived from it"})
    elif kind == "cut_spec":
        out.append({"what": "gate conditions cut.specified and cut.second_person_verified",
                    "why": "the marks were verified against this line; a later specification "
                           "invalidates that approval"})
        if state.get("cut_performed"):
            out.append({"what": "cut_performed",
                        "why": "the achieved lengths are compared against this target"})
    return out


def describe(state, kind, key):
    """Five of the six questions, for one datum, from the folded state alone.

    The sixth -- whether the system considers it sufficient evidence, and why -- is the gate's
    answer, not this module's, so the caller evaluates the gate and reports what it said. Restating
    the gate's rules here would be a second implementation of them, and two implementations of a
    refusal is how one of them quietly stops refusing.
    """
    rec, physical, lifecycle, modified = None, None, None, []
    if kind == "measurement":
        for st_name, bucket in sorted((state.get("measurements_by_state") or {}).items()):
            if key in bucket:
                rec, lifecycle = bucket[key], st_name
                break
        physical = "the garment's %s" % key
        modified = [r for r in state.get("measurement_revisions") or [] if r.get("name") == key]
    elif kind == "annotation":
        rec = (state.get("annotations") or {}).get(key)
        if rec:
            physical = "%s at %s" % (rec.get("type") or "feature", rec.get("location") or "?")
        lifecycle = "intake"
        modified = [r for r in state.get("annotation_revisions") or []
                    if r.get("annotation_id") == key]
    elif kind == "capture":
        rec = state["captures"].get(key)
        if rec:
            physical = (("annotation %s (%s)" % (rec["annotation_id"], rec.get("annotation_location")))
                        if rec.get("annotation_id")
                        else ("region %s" % (rec.get("region_id") or "not recorded")))
            lifecycle = rec.get("state")
    elif kind == "cut_spec":
        rec, lifecycle, physical = state.get("cut_spec"), "before", "the planned cut line"
    if rec is None:
        return {"found": False, "kind": kind, "key": key}

    return {
        "found": True, "kind": kind, "key": key,
        "physical_subject": physical or "not recorded",
        "lifecycle_state": lifecycle or "not recorded",
        "supplied_by": rec.get("operator") or "NOT RECORDED",
        "recorded_at_entry": rec.get("seq"),
        "depends_on_it": dependents(state, kind, key),
        "modified_after_first_record": modified,
    }

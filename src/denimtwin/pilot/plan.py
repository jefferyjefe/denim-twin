"""Turning the specification into the order a person should actually work in.

Two things are being optimised, and they pull against each other. Handling costs time: every flip of
the garment, every re-lay, every change of camera height or lens is a minute that produces no
evidence. But some of the handling IS the evidence -- the repeatability captures exist precisely to
measure what changes when the garment is laid out again, so collapsing them would save time by
deleting the measurement.

So the order groups everything that can be grouped and refuses to group the rest:

  1. by state, because states are physically ordered and one of the transitions is a cut;
  2. by which face is up, so the garment is flipped once rather than once per shot;
  3. by relay generation -- the required independent re-lays are the only re-lays, and every shot
     that can be taken in a given lay is taken while the garment is lying there;
  4. by camera height, then lens, so the rig is adjusted once per group;
  5. ruler macros together, because they share a height, a lens and a working distance;
  6. by region, so the operator's hands travel down the garment instead of jumping about.

Determinism matters as much as optimality here. The order is a pure function of (specification,
answered features, captures so far): the same session state always produces the same next action, so
"what do I do now" has one answer and a resumed session does not reshuffle itself. Nothing in this
module uses a clock or a random number.
"""
from . import spec as SPEC

#: Which way up the garment must be lying for a shot. Profile and edge shots are taken with the
#: garment however it already is, so they cost no flip and are scheduled into whichever lay is open.
ORIENTATION = {"front": "front_up", "back": "back_up",
               "left_profile": "either", "right_profile": "either",
               "edge": "either", "n/a": "either"}

#: Rig work and intake are not garment lays at all.
NON_LAY_STATES = ("rig", "intake")


class PlanError(Exception):
    pass


def resolve_features(spec, answers):
    """Answered features, plus the safe reading of every unanswered one.

    The rule that keeps a present feature from being dropped: a question that gates a shot and has
    not been answered is treated as PRESENT, so the shot is planned. The alternative -- treating
    silence as absence -- means a forgotten question silently deletes a required photograph, and the
    operator finds out after the garment is cut.

    Returns (features, unanswered, blocking) where `unanswered` lists keys that were assumed rather
    than answered and `blocking` lists keys the plan cannot proceed without.
    """
    out, unanswered, blocking = {}, [], []
    for f in spec.features:
        k = f["key"]
        if k in answers and answers[k] is not None:
            out[k] = answers[k]
            continue
        rule = f["unanswered_means"]
        if rule == "blocks":
            blocking.append(k)
            continue
        unanswered.append(k)
        if f["type"] == "count":
            # "how many" unanswered means "at least one, until you tell me otherwise"
            out[k] = 1 if rule == "present" else 0
        elif f["type"] == "bool":
            out[k] = (rule == "present")
        else:
            out[k] = f.get("default")
    return out, unanswered, blocking


def instance_count(features, key):
    v = features.get(key)
    if isinstance(v, bool):
        return 1 if v else 0
    try:
        return max(0, int(v))
    except (TypeError, ValueError):
        return 0


def activate(spec, answers):
    """The shots this garment actually requires. Returns (shots, meta).

    A conditional shot whose condition cannot be evaluated is INCLUDED, and the reason is recorded.
    An un-evaluatable condition means the plan does not know; planning the shot costs a photograph,
    and not planning it costs the experiment.
    """
    features, unanswered, blocking = resolve_features(spec, answers)
    if blocking:
        raise PlanError("these must be answered before a plan exists: %s" % ", ".join(blocking))
    out, assumed = [], []
    for s in spec.shots:
        cond = s.get("conditional_on") or ""
        include = True
        if cond:
            try:
                include = SPEC.evaluate(cond, features)
            except SPEC.SpecError as e:
                include = True
                assumed.append({"shot_id": s["shot_id"], "condition": cond, "why": str(e),
                                "resolution": "included, because an unknown answer is not a no"})
        if not include:
            continue
        inst = s.get("instance_of")
        if inst:
            n = instance_count(features, inst)
            for i in range(1, n + 1):
                c = dict(s)
                c["shot_id"] = "%s.I%02d" % (s["shot_id"], i)
                c["instance_index"] = i
                c["instance_total"] = n
                c["matched_shot_ids"] = ["%s.I%02d" % (m, i) for m in (s.get("matched_shot_ids") or [])]
                out.append(c)
        else:
            out.append(dict(s))
    return out, {"features": features, "assumed_present": unanswered,
                 "unevaluatable_conditions": assumed}


def _lay_key(shot):
    """Which physical lay a shot belongs to. Relay-required repeats each get their own."""
    if shot["state"] in NON_LAY_STATES:
        return (0, "rig")
    return (1, ORIENTATION.get(shot["garment_side"], "either"))


def expand_reps(shots):
    """One entry per (shot, repetition). Repeats that require a re-lay are marked so the order can
    keep them in separate lays rather than firing five frames at one lay."""
    out = []
    for s in shots:
        n = int(s.get("min_reps", 1))
        for r in range(1, n + 1):
            e = dict(s)
            e["rep"] = r
            e["rep_of"] = n
            e["needs_relay_before"] = bool(s.get("relay_between_reps")) and r > 1
            e["needs_camera_reposition_before"] = bool(
                s.get("reposition_camera_between_reps")) and r > 1
            # A relay generation is the lay this repeat belongs to: repeat 3 of a relay-required
            # shot happens in the third lay, and anything else that can share that lay may.
            e["relay_generation"] = r if s.get("relay_between_reps") else 1
            out.append(e)
    return out


def order(spec, shots, *, state=None):
    """The capture order. A pure, total, deterministic sort."""
    state_order = {st["state"]: st["order"] for st in spec.states}
    region_order = {r["region_id"]: i for i, r in enumerate(spec.regions)}
    items = expand_reps(shots)
    if state:
        items = [i for i in items if i["state"] == state]

    def key(e):
        orient = ORIENTATION.get(e["garment_side"], "either")
        return (
            state_order.get(e["state"], 99),
            # front before back: a flip is the most expensive handling move there is
            {"front_up": 0, "either": 1, "back_up": 2}[orient],
            # relay generation next, so the five independent lays are five blocks rather than
            # interleaved with everything else
            e["relay_generation"],
            e.get("camera_height_group", ""),
            {"ultrawide": 0, "main": 1, "tele": 2, "macro": 3}.get(e.get("lens", "main"), 1),
            # every ruler macro in one run: same height, same lens, same working distance
            0 if e.get("camera_angle") == "macro_perpendicular" else 1,
            region_order.get(e.get("region_id"), 9999),
            e["shot_id"], e["rep"],
        )
    return sorted(items, key=key)


def estimate_seconds(spec, ordered):
    """Wall-clock estimate: the frames plus the handling between them.

    The handling constants live in the specification rather than here, because they are properties
    of one person's rig and should be re-measured after the first session rather than inherited from
    a guess in a source file.
    """
    o = spec.doc["ordering"]
    total = 0.0
    prev = None
    for e in ordered:
        total += float(e.get("est_seconds", 30))
        if prev is not None:
            if ORIENTATION.get(prev["garment_side"], "either") != \
                    ORIENTATION.get(e["garment_side"], "either") and "either" not in (
                    ORIENTATION.get(prev["garment_side"]), ORIENTATION.get(e["garment_side"])):
                total += float(o["flip_cost_seconds"])
            if e["relay_generation"] != prev["relay_generation"] or e.get("needs_relay_before"):
                total += float(o["relay_cost_seconds"])
            if e.get("lens") != prev.get("lens"):
                total += float(o["lens_change_cost_seconds"])
            if e.get("camera_height_group") != prev.get("camera_height_group"):
                total += float(o.get("height_change_cost_seconds", 0))
        prev = e
    return total


def progress(ordered, done_keys):
    """Split the order into done and remaining. `done_keys` is a set of (shot_id, rep)."""
    todo = [e for e in ordered if (e["shot_id"], e["rep"]) not in done_keys]
    done = [e for e in ordered if (e["shot_id"], e["rep"]) in done_keys]
    return done, todo


def next_action(spec, ordered, done_keys, blocked_keys=()):
    """The single best next thing to do, or None when the ordered set is complete.

    "Best" is the earliest item in the order that is neither captured nor currently blocked behind a
    retake. Ties cannot happen: the sort is total.
    """
    for e in ordered:
        k = (e["shot_id"], e["rep"])
        if k in done_keys or k in blocked_keys:
            continue
        return e
    return None

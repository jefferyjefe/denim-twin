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


def expand_hem_series(spec, shot, measurements):
    """A hem-loop template becomes one frame per macro position, from the MEASURED leg opening.

    The count cannot be written into the specification, because it is a property of the garment: a
    17 cm opening needs five macros and a 25 cm opening needs seven. When the measurement is absent
    the template does NOT quietly expand to zero frames -- that would delete the entire fray series
    from the plan and the gate would then find nothing missing. It stays as one entry carrying the
    reason it could not be expanded, and the gate blocks on it.
    """
    from . import hem as HEM

    hs = shot.get("hem_series") or {}
    lo = (measurements or {}).get("leg_opening_cm")
    lo = lo.get("mean") if isinstance(lo, dict) else lo
    if lo is None:
        c = dict(shot)
        c["expansion_blocked"] = (
            "the hem loop's length comes from leg_opening_cm, which has not been measured, so the "
            "number of macro frames this series needs is unknown")
        return [c]
    kw = {}
    if hs.get("arc_mm_per_frame"):
        kw["arc_mm"] = float(hs["arc_mm_per_frame"])
    if hs.get("position_spacing_mm"):
        kw["position_spacing_mm"] = float(hs["position_spacing_mm"])
    if hs.get("overlap_mm"):
        kw["edge_margin_mm"] = float(hs["overlap_mm"]) / 2.0
    try:
        g = HEM.HemGeometry.from_leg_opening(hs.get("leg", "left"), float(lo), **kw)
        macros = g.macros()
    except ValueError as e:
        c = dict(shot)
        c["expansion_blocked"] = "the hem series geometry is not usable: %s" % e
        return [c]
    out = []
    for m in macros:
        c = dict(shot)
        c["shot_id"] = shot["shot_id"].replace(".PNN", "." + m["shot_suffix"])
        c["hem_position"] = m
        c["matched_shot_ids"] = [x.replace(".PNN", "." + m["shot_suffix"])
                                 for x in (shot.get("matched_shot_ids") or [])]
        c["framing"] = (shot["framing"] + "  [frame %d of %d around the loop: arc %.0f-%.0f mm from "
                        "the inseam seam, covering measurement position(s) %s]"
                        % (m["index"], len(macros), m["usable_start_mm"], m["usable_end_mm"],
                           ", ".join(str(i) for i in m["supports_positions"]) or "none"))
        out.append(c)
    return out


def activate(spec, answers, measurements=None):
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
        if s.get("hem_series"):
            out.extend(expand_hem_series(spec, s, measurements))
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
                 "unevaluatable_conditions": assumed,
                 "expansion_blocked": [{"shot_id": x["shot_id"], "why": x["expansion_blocked"]}
                                       for x in out if x.get("expansion_blocked")]}


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
            po = ORIENTATION.get(prev.get("garment_side"), "either")
            eo = ORIENTATION.get(e.get("garment_side"), "either")
            if po != eo and "either" not in (po, eo):
                total += float(o["flip_cost_seconds"])
            if e.get("relay_generation", 1) != prev.get("relay_generation", 1) \
                    or e.get("needs_relay_before"):
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


# --------------------------------------------------------------------------------------------
# Time estimation
#
# The specification carries an `est_seconds` per shot, and it is a DECLARED planning figure, not a
# measurement of anything -- nobody has yet timed this rig. Presenting it as "time remaining" would
# be the same defect this repository keeps finding elsewhere: a confident number whose provenance is
# a guess. So once the session's own log contains enough observations, the estimate is recomputed
# from the operator's ACTUAL pace, and the two are reported separately with a note saying which is
# which and how much of the plan each covers.
# --------------------------------------------------------------------------------------------

#: A median with an interior point and a spread needs three observations. This is a property of the
#: estimator, not a measurement of anything.
MIN_PACE_OBSERVATIONS = 3


def cost_class(shot):
    """Shots whose handling is alike enough that their durations pool.

    Keyed on what actually costs time: the rig position, the lens, whether a ruler has to be laid,
    and whether the frame is a macro or a whole-garment shot.
    """
    return "|".join([
        str(shot.get("camera_height_group") or "-"),
        str(shot.get("lens") or "-"),
        "ruler" if shot.get("scale_reference") in ("ruler", "both") else "noruler",
        str(shot.get("camera_angle") or "-"),
    ])


def measured_pace(spec, captures, ordered):
    """cost_class -> {median_seconds, n}, measured from the gaps between this session's captures.

    The gap between one accepted capture and the next is the time the operator took on it, including
    the handling before it. Gaps longer than an hour are dropped: they are breaks, not frames, and
    a median that includes a lunch is not a pace.
    """
    by_key = {}
    for e in ordered:
        by_key[(e["shot_id"], e["rep"])] = e
    rows = sorted(((c.get("ts"), k) for k, c in captures.items() if c.get("ts")),
                  key=lambda x: x[0])
    buckets = {}
    for i in range(1, len(rows)):
        dt = rows[i][0] - rows[i - 1][0]
        if not (1.0 <= dt <= 3600.0):
            continue
        shot = by_key.get(rows[i][1])
        if shot is None:
            continue
        buckets.setdefault(cost_class(shot), []).append(dt)
    out = {}
    for cls, vals in buckets.items():
        if len(vals) >= MIN_PACE_OBSERVATIONS:
            vals = sorted(vals)
            n = len(vals)
            med = vals[n // 2] if n % 2 else 0.5 * (vals[n // 2 - 1] + vals[n // 2])
            out[cls] = {"median_seconds": round(med, 1), "n": n}
    return out


def estimate_remaining(spec, remaining, pace=None):
    """Both estimates, and an honest account of what each covers.

    Returns a dict whose `status` is PASS only when every remaining step has a measured pace. When
    it does not, the declared figure is still given -- an operator planning an evening needs a
    number -- but it is labelled, and the count of unmeasured classes travels with it.
    """
    pace = pace or {}
    declared = estimate_seconds(spec, remaining)
    measured, unmeasured, covered = 0.0, set(), 0
    for e in remaining:
        p = pace.get(cost_class(e))
        if p is None:
            unmeasured.add(cost_class(e))
            measured += float(e.get("est_seconds", 30))
        else:
            measured += p["median_seconds"]
            covered += 1
    return {
        "declared_seconds": round(declared),
        "blended_seconds": round(measured),
        "n_steps": len(remaining),
        "n_steps_with_measured_pace": covered,
        "n_classes_unmeasured": len(unmeasured),
        "status": "PASS" if not unmeasured and remaining else
                  ("UNAVAILABLE_CHECK" if remaining else "PASS"),
        "note": ("every remaining step has a measured pace from this session"
                 if not unmeasured else
                 "%d of %d remaining steps use the specification's DECLARED time, which nobody has "
                 "timed on this rig; the rest use this session's measured pace"
                 % (len(remaining) - covered, len(remaining))),
    }

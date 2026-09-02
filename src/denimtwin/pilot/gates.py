"""The gate. It answers one question -- may this garment be cut? -- and it answers no by default.

Everything else in this package exists to make the evidence collectable. This module exists to make
the answer unfalsifiable, and it is written against a specific failure: a gate that lists the things
it happens to check, rather than the things the experiment requires, and therefore passes a garment
whose missing evidence nobody encoded.

Three design rules follow, and they are the whole of it.

DENY BY DEFAULT. A condition contributes to readiness only by returning a positive result. Absence
of a finding is never a finding. There is no code path that skips a condition and no code path that
treats an empty collection as a satisfied one -- an empty required-shot list is itself a block,
because a plan that requires nothing is a plan that was not generated.

THE REQUIRED SET IS ENUMERATED FROM THE SPECIFICATION, NOT FROM THIS FILE. The shots that must exist
come from the shot-plan document filtered by the answered features. So adding a shot to the
specification automatically extends the gate, and this module cannot fall behind the protocol. The
one thing this file does hold is which CLASSES of evidence are required, and each is a condition
that must actively pass.

AN ERROR IS A BLOCK. Every condition runs inside a guard, and a condition that raises becomes a
block naming the exception. A gate that crashes into a pass is the exact defect this repository
found in three of its own guards (see the commits around tools/verify.py); a condition this code
cannot evaluate is a condition whose truth is unknown, and unknown is not permission.

The verdict lists every unmet condition with the action that would satisfy it, because "not ready"
without "and here is what is missing" is a gate people learn to route around.
"""
import math
import os
from pathlib import Path

from . import plan as PLAN
from . import qa as QA

#: Measurements the protocol requires before a garment may be cut, and how many independent readings
#: each needs. PROTOCOL.md 0.4 fixes two readings for the tape measurements and three spots for
#: thickness; they are listed here because the gate must enumerate them, and mirrored in the runbook.
REQUIRED_MEASUREMENTS = {
    "waist_cm": 2, "front_rise_cm": 2, "back_rise_cm": 2, "thigh_cm": 2,
    "original_inseam_cm": 2, "leg_opening_cm": 2, "fabric_thickness_mm": 3, "mass_grams": 1,
}
#: Two readings of the same dimension that disagree by more than this were not both measurements of
#: it. Tape measurements on cloth: 0.5 cm is about what a careful person reproduces on a flat-laid
#: garment; thickness with a caliper is finer.
MEASUREMENT_TOLERANCE = {"fabric_thickness_mm": 0.15, "mass_grams": 2.0, "_default_cm": 0.5}

#: Plausible ranges for an adult pair of jeans, as the conventions in record.json define them --
#: waist, thigh and leg opening are FULL circumferences (measured flat and doubled).
#:
#: Agreement between two readings is not enough on its own, and leg_opening_cm shows why: it is the
#: measurement that SIZES a required series (the hem macro count comes from it) and PLACES the cut
#: (the outseam offset is computed from it). An operator reading the tape in inches records two
#: readings that agree perfectly with each other and are 2.5x wrong, which halves the fray series
#: and moves the cut mark by centimetres -- and every other check passes, because everything
#: downstream believes the number.
MEASUREMENT_RANGE = {
    "waist_cm": (55.0, 150.0),
    "front_rise_cm": (15.0, 45.0),
    "back_rise_cm": (20.0, 55.0),
    "thigh_cm": (35.0, 95.0),
    "original_inseam_cm": (50.0, 105.0),
    "leg_opening_cm": (20.0, 80.0),
    "fabric_thickness_mm": (0.3, 3.0),
    "mass_grams": (200.0, 1400.0),
}

#: Rig calibration readings that must exist and pass before any garment capture counts.
REQUIRED_SETUP_CHECKS = (
    "empty_backdrop", "board_verification", "board_square_measured", "lighting_test",
    "exposure_white_balance", "camera_height", "lens_selection", "backdrop_identified",
    "daylight_controlled", "board_garment_coplanar",
)
#: The printed board's squares, and how far off the print may be before the scale is wrong.
#: protocol/charuco_board.json declares 25.0 mm; a 0.5 mm error over one square is 2%, which is the
#: same order as the tilt bias EXP_0043 measured, so it is not a detail.
BOARD_SQUARE_MM = 25.0
BOARD_SQUARE_TOLERANCE_MM = 0.5
#: A steel rule reads to about 0.5 mm. Over one 25 mm square that is a 2% measurement, which is
#: worse than the scale error the tilt gate is set to catch; over eight squares it is 0.25%.
MIN_BOARD_SQUARES_SPANNED = 4
#: The board is 8 x 11 squares (protocol/charuco_board.json), so a run cannot exceed 11.
BOARD_MAX_SQUARES = 11

#: Every field the wash record carries, planned and actual alike. PROTOCOL.md 4 fixes the cycle.
WASH_FIELDS = ("machine", "location", "cycle", "water_temp_c", "spin_rpm", "detergent",
               "detergent_ml", "filler_load", "start_time", "end_time", "dryer_method",
               "dryer_setting", "dryer_minutes", "conditioning_start", "conditioning_end")

#: Second-person verification of the cut marks. PROTOCOL.md 3.2 sets this.
CUT_MARK_TOLERANCE_MM = 3.0

#: The dimensions that must be measured AGAIN after the wash, with the number of readings each
#: needs. Shrinkage is the difference between these and the pre-cut values, so a post-wash record
#: that omits them leaves the wash unmeasured -- and unlike almost everything else in the protocol,
#: it cannot be gone back for: the next wash is a different sample.
#: The dimensions where the pre-cut and post-wash numbers are measurements OF THE SAME THING, so
#: their difference is shrinkage and nothing else.
#:
#: original_inseam_cm is absent because after the cut the garment does not have one; the length
#: that replaced it is recorded by cut_performed. leg_opening_cm is absent for exactly the same
#: reason and it took a dry run to notice: before the cut it is the original factory hem, after the
#: cut it is the NEW RAW EDGE somewhere up the leg, whose circumference the cut spec itself
#: predicts. Subtracting one from the other and calling it shrinkage published -45.5% on a garment
#: whose cut edge matched its prediction to 0.02 cm. A number that is not a shrinkage must not be
#: reported as one, least of all in the record that closes the experiment.
#:
#: mass_grams and fabric_thickness_mm are absent because PROTOCOL does not ask for them after the
#: wash, and adding a required physical measurement on our own judgement would be inventing
#: protocol; they are named in the report as an owner decision rather than quietly required or
#: quietly forgotten.
POST_WASH_MEASUREMENTS = {
    "waist_cm": 2, "thigh_cm": 2, "front_rise_cm": 2, "back_rise_cm": 2,
}

#: The rig fields a freeze has to state. Every one of them is a fact about physical hardware, so
#: none of them has a default anywhere: a default here is a measurement nobody took, attached by
#: the hash to every photograph in the session. The web app validated this list from the start; the
#: CLI asked the same questions with plausible answers pre-filled ("iPhone", 80.0 cm, "dark green
#: matte", "studio"), so holding Enter froze a rig that had never been observed and the emptiness
#: check below could never fire. Both front doors now come through here.
REQUIRED_SETUP_FIELDS = ("camera_model", "mount_height_cm", "lens", "backdrop", "lighting",
                         "leg_gap_cm", "exposure_locked", "room")

#: The two rig fields that are numbers rather than names.
NUMERIC_SETUP_FIELDS = ("mount_height_cm", "leg_gap_cm")


def validate_setup(cfg):
    """Return the frozen rig configuration, or raise ValueError naming the field that is missing.

    Callers that speak HTTP translate the ValueError into a 400; the CLI prints it and asks again.
    Neither may supply the answer itself.
    """
    if not isinstance(cfg, dict):
        raise ValueError("setup must be an object")
    out = {}
    for k in REQUIRED_SETUP_FIELDS:
        v = cfg.get(k)
        if v is None or (isinstance(v, str) and not v.strip()):
            raise ValueError("the rig configuration is missing %s; a frozen rig has to say what "
                             "it is" % k)
        out[k] = v
    for k in NUMERIC_SETUP_FIELDS:
        try:
            out[k] = float(out[k])
        except (TypeError, ValueError):
            raise ValueError("%s must be a number, not %r" % (k, out[k]))
    for k, v in cfg.items():
        out.setdefault(k, v)
    return out


class Block(object):
    __slots__ = ("condition", "what", "fix", "evidence", "unavailable")

    def __init__(self, condition, what, fix, evidence=None, unavailable=False):
        self.condition = condition
        self.what = what
        self.fix = fix
        self.evidence = evidence or {}
        #: True when the condition could not be EVALUATED, as opposed to evaluating to false. Both
        #: block, and neither is permission -- but they call for different actions. Missing evidence
        #: is fixed by capturing it; a condition that could not run is fixed by repairing the
        #: system, and a caller that cannot tell them apart will keep re-capturing into a bug.
        self.unavailable = bool(unavailable)

    def as_dict(self):
        return {"condition": self.condition, "what": self.what, "fix": self.fix,
                "evidence": self.evidence, "unavailable": self.unavailable}

    def __repr__(self):
        return "<Block %s: %s>" % (self.condition, self.what)


class Verdict(object):
    def __init__(self, gate_id, blocks, satisfied, evidence=None):
        self.gate_id = gate_id
        self.blocks = blocks
        self.satisfied = satisfied
        self.evidence = evidence or {}

    @property
    def ready(self):
        return not self.blocks

    @property
    def unavailable(self):
        """The gate is blocked ONLY by conditions that could not be evaluated.

        Never a weaker verdict than not-ready: an unavailable gate is a closed gate. It is reported
        separately so a caller knows whether to go and capture something or go and fix something.
        """
        return bool(self.blocks) and all(b.unavailable for b in self.blocks)

    def as_dict(self):
        return {"gate": self.gate_id, "ready": self.ready,
                "unavailable": self.unavailable,
                "blocks": [b.as_dict() for b in self.blocks],
                "satisfied": self.satisfied, "evidence": self.evidence}

    def __repr__(self):
        return "<Verdict %s ready=%s blocks=%d>" % (self.gate_id, self.ready, len(self.blocks))


def _guard(blocks, satisfied, condition, fn):
    """Run one condition. Anything other than an explicit pass is a block, exceptions included."""
    try:
        ok, what, fix, ev = fn()
    except Exception as e:                     # noqa: BLE001 -- deliberately broad; see module docs
        blocks.append(Block(condition,
                            "this condition could not be evaluated: %s: %s"
                            % (type(e).__name__, e),
                            "fix the error above, then re-run the gate. A condition whose truth is "
                            "unknown is not permission.",
                            {"exception": type(e).__name__}, unavailable=True))
        return
    if ok:
        satisfied.append({"condition": condition, "what": what, "evidence": ev or {}})
    else:
        blocks.append(Block(condition, what, fix, ev))


#: The LAST state each gate is responsible for. Everything at or below it in the specification's own
#: ordering is required.
#:
#: The states were listed by hand before, and the list fell behind the plan: the specification
#: declares eight states and the three tuples between them named six. offcut_before and
#: offcut_after appeared in none, so a hundred required frames -- a fifth of the plan, and the whole
#: offcut experiment -- were required by no gate at all. Deriving the set means adding a state to
#: the document cannot leave it unguarded.
GATE_LAST_STATE = {
    "ready_to_cut": "marked",
    "ready_to_wash": "offcut_before",
    "ready_to_finalize": "offcut_after",
}


def gate_states(spec, gate_id):
    """Every state at or below the one this gate guards, in the specification's own order."""
    order = {st["state"]: st["order"] for st in spec.states}
    last = GATE_LAST_STATE[gate_id]
    if last not in order:
        raise ValueError("the specification declares no state %r, which %s guards"
                         % (last, gate_id))
    cutoff = order[last]
    return tuple(st["state"] for st in sorted(spec.states, key=lambda x: x["order"])
                 if st["order"] <= cutoff)


def deviation_covers(deviations, kind, field, planned=None, actual=None):
    """Is this departure actually EXPLAINED by a recorded deviation?

    Matching on `kind` alone means an empty deviation -- no field, no values, recordable before the
    departure exists and even before the session starts -- excuses everything of that kind forever.
    Round 3 closed exactly this on the wash gate and left the rig and offcut consumers behind.

    A deviation has to name what departed. When the caller can say what the two values were, it has
    to name those too.
    """
    for d in deviations or []:
        if d.get("kind") != kind:
            continue
        got = d.get("field")
        if not (isinstance(got, str) and got.strip()):
            continue                                   # names nothing; explains nothing
        if field is not None and got != field:
            continue
        if planned is not None and d.get("planned") != planned:
            continue
        if actual is not None and d.get("actual") != actual:
            continue
        return d
    return None


def _board_pair(_garment_dir=None):
    """The calibration board, loaded once. The gate re-derives verdicts from photographs and every
    one of them needs it; loading it per frame would decode the spec hundreds of times."""
    global _BOARD_CACHE
    if _BOARD_CACHE is None:
        from denimtwin.capture.board import load_board
        _BOARD_CACHE = load_board(Path(__file__).resolve().parents[3]
                                  / "protocol" / "charuco_board.json")
    return _BOARD_CACHE


_BOARD_CACHE = None


def plan_safe_measurements(state):
    """The measurements it is safe to SIZE A PLAN from.

    A leg opening of 10^7 is refused by c_measurements -- but c_measurements runs after the plan
    does, and expanding a hem series from that number builds millions of frames first, so the gate
    never reaches the condition that would have refused it.

    This is a module-level function because the WEB APP needs it too and did not have it: a single
    stuck digit on a phone keypad -- 4000 instead of 40.0 -- pinned a server thread at 100% CPU with
    no response and no timeout, on /api/state, which is the only screen the phone renders. The gate
    refused the same value in a tenth of a second. One screen, used by everything that sizes a plan.
    """
    from .store import mean_of
    out = {}
    for name, m in (state.get("measurements") or {}).items():
        lo_hi = MEASUREMENT_RANGE.get(name)
        try:
            val = mean_of(m)
        except Exception:                       # noqa: BLE001
            val = None
        if lo_hi and (val is None or not (lo_hi[0] <= val <= lo_hi[1])):
            continue                            # reported by c_measurements; the plan never sees it
        out[name] = m
    return out


def evaluate(gate_id, spec, store, *, garment_dir=None, check_files=True, rehash=False):
    """Evaluate one gate. Returns a Verdict. Never raises for a data problem -- that is a block."""
    if gate_id not in GATE_LAST_STATE:
        raise ValueError("unknown gate %r" % gate_id)
    blocks, satisfied = [], []
    # "AN ERROR IS A BLOCK" is this module's rule, and its own first line broke it: the fold ran
    # above every guard, so anything the log or the replay raised escaped the gate entirely and
    # returned a traceback instead of a verdict. A gate that cannot answer must still answer no.
    try:
        state, problems = store.fold()
    except Exception as e:                     # noqa: BLE001
        return Verdict(gate_id, [Block("log.readable",
                                       "the capture log could not be read at all: %s: %s"
                                       % (type(e).__name__, e),
                                       "the log is damaged beyond replay. Do not cut. Recover from "
                                       "the phone's own copies and re-ingest; a log this code "
                                       "cannot read is not evidence.",
                                       {"exception": type(e).__name__})], [],
                       {"fold_failed": True})
    garment_dir = Path(garment_dir or store.dir)
    states = gate_states(spec, gate_id)

    # --- the plan itself ------------------------------------------------------------------
    safe_measurements = plan_safe_measurements(state)

    activated = None
    try:
        activated, meta = PLAN.activate(spec, state["features"], safe_measurements,
                                        state.get("cut_spec"),
                                        annotations=state.get("annotations"))
    except Exception as e:
        blocks.append(Block("plan.generated",
                            "no shot plan could be generated: %s" % e,
                            "answer the intake questionnaire (`pilot.py intake`)"))
        meta = {"features": state["features"], "assumed_present": [], "unevaluatable_conditions": []}

    def required_here():
        if activated is None:
            raise RuntimeError("no plan")
        req = [s for s in activated
               if s["state"] in states and s["necessity"] in ("required", "conditional")]
        if not req:
            raise RuntimeError("the plan requires no shots in states %s, which means it was not "
                               "generated rather than that nothing is needed" % (states,))
        return req

    # --- specification binding ------------------------------------------------------------
    def c_spec_bound():
        if not state["spec_hash"]:
            return False, "this session never recorded which shot plan it was opened under", \
                   "run `pilot.py new` to create the garment and bind the session to a " \
                   "specification (there is no separate `open` command)", {}
        if state["spec_hash"] != spec.content_hash:
            # This used to be a permanent lockout. Any edit to the shot plan -- including one that
            # ADDS a required photograph, which is the edit you most want to be able to make -- left
            # every open session blocked here forever, and the remedy the message named ("re-run the
            # gate against the specification version the session used") was not something any
            # command could do: there is no --spec on the gate.
            #
            # Acknowledging it does not weaken anything. Every other condition re-derives against
            # the plan ON DISK: captures.required_complete still demands every frame the NEW plan
            # requires, and a frame the new plan added is still missing until it is taken. What the
            # deviation adds is that the substitution is in the record instead of being silent.
            # Matched on the ON-DISK hash only. Requiring the session's old hash as well adds no
            # safety -- it is in the log either way -- and doubles the chance that the remedy fails
            # silently because a character of a 64-digit hash was retyped wrongly, which is the
            # realistic way an operator meets this at the end of a long day: the deviation is
            # recorded, the gate keeps refusing, and nothing says the two nearly matched.
            ack = deviation_covers(state["deviations"], "protocol", "spec_rebound",
                                   actual=spec.content_hash)
            if ack is None:
                return False, ("the session was opened under shot plan %s but the specification on "
                               "disk now hashes to %s -- the plan changed underneath the evidence"
                               % (state["spec_hash"][:12], spec.content_hash[:12])), \
                       ("every other condition already re-checks this session against the plan on "
                        "disk, so a frame the new plan requires is still missing until it is "
                        "taken. Record which plan this session is being held to:\n"
                        "  tools/pilot.py deviation %s --kind protocol --field spec_rebound "
                        "--actual %s --reason '<what changed and why the evidence already taken "
                        "still stands>'"
                        % (state["garment_id"], spec.content_hash)), \
                       {"session": state["spec_hash"], "on_disk": spec.content_hash}
            return True, ("opened under shot plan %s, re-bound to %s with the change recorded"
                          % (state["spec_hash"][:12], spec.content_hash[:12])), \
                   None, {"session": state["spec_hash"], "on_disk": spec.content_hash,
                          "acknowledged": True}
        return True, "bound to shot plan %s v%s" % (spec.content_hash[:12], spec.version), None, {}

    _guard(blocks, satisfied, "spec.bound", c_spec_bound)

    # --- log integrity --------------------------------------------------------------------
    def c_log_intact():
        if problems:
            return False, ("the capture log does not verify: %s"
                           % "; ".join("%s at line/seq %s" % (p["kind"], p.get("line_no", p.get("seq")))
                                       for p in problems[:4])), \
                   "the log has been edited, truncated or damaged. Do not cut. Recover from the " \
                   "phone's own copies and re-ingest.", {"problems": problems[:8]}
        if state["unknown_kinds"]:
            return False, "the log contains entries this version cannot interpret", \
                   "upgrade the tool to the version that wrote this log", \
                   {"unknown": state["unknown_kinds"][:5]}
        return True, "log verifies: %d entries, hash chain intact" % state["n_entries"], None, {}

    _guard(blocks, satisfied, "log.intact", c_log_intact)

    # --- features -------------------------------------------------------------------------
    def c_features():
        if not state["features"]:
            return False, "the garment feature questionnaire has not been answered", \
                   "run `pilot.py intake`", {}
        missing_absent = []
        for f in spec.features:
            if f["key"] in state["features"] and state["features"][f["key"]] is not None:
                continue
            if f["unanswered_means"] == "absent":
                # This is the dangerous direction: an unanswered question that defaults to absent
                # silently deletes the shots it gates, so it must be answered explicitly.
                missing_absent.append(f["key"])
        if missing_absent:
            return False, ("%d question(s) whose silence would DROP a required capture are still "
                           "unanswered: %s" % (len(missing_absent), ", ".join(sorted(missing_absent)[:8]))), \
                   "answer them in `pilot.py intake`; an unanswered question that defaults to " \
                   "'absent' would remove a photograph from the plan", {"keys": missing_absent}
        shrinking = []
        for ch in state["feature_changes"]:
            was, now = ch["was"], ch["now"]
            try:
                shrank = (was is True and now is False) or \
                         (not isinstance(was, bool) and not isinstance(now, bool)
                          and float(now) < float(was))
            except (TypeError, ValueError):
                shrank = True
            if shrank:
                shrinking.append("%s: %r -> %r" % (ch["key"], was, now))
        excused_keys = {d.get("field") for d in state["deviations"]
                        if d.get("kind") == "intake"}
        shrinking = [x for x in shrinking if x.split(":")[0] not in excused_keys]
        if shrinking:
            # The newest answer wins and the older one stays in the log, invisible to every
            # condition -- so a later answer could delete the frames an earlier one required with
            # nothing to look at. An answer that ADDS work needs no explanation; one that removes
            # a photograph does.
            return False, ("%d intake answer(s) were later changed in the direction that REMOVES "
                           "required photographs: %s"
                           % (len(shrinking), "; ".join(shrinking[:5]))), \
                   "an answer that adds work needs no explanation; one that deletes a required " \
                   "frame does. Record why with `pilot.py deviation --kind intake`, or restore " \
                   "the earlier answer.", {"changes": shrinking[:8]}
        return True, "%d feature answers recorded (%d assumed present pending answer)" % (
            len(state["features"]), len(meta.get("assumed_present") or [])), None, \
            {"assumed_present": meta.get("assumed_present") or []}

    _guard(blocks, satisfied, "features.answered", c_features)

    def c_plan_expanded():
        stuck = (meta.get("expansion_blocked") or []) if isinstance(meta, dict) else []
        if stuck:
            return False, ("%d templated shot series could not be expanded into frames: %s"
                           % (len(stuck), "; ".join("%s (%s)" % (x["shot_id"], x["why"])
                                                    for x in stuck[:3]))), \
                   "supply the measurement the series is sized from, then re-run. An unexpanded " \
                   "series is not an empty requirement -- it is an unknown one.", \
                   {"blocked": stuck[:8]}
        return True, "every templated series expanded into frames", None, {}

    _guard(blocks, satisfied, "plan.fully_expanded", c_plan_expanded)

    # --- rig ------------------------------------------------------------------------------
    def c_setup_frozen():
        if not state["setup_hash"]:
            return False, "the rig configuration has not been frozen", \
                   "run `pilot.py setup` and freeze it", {}
        return True, "rig frozen as %s" % state["setup_hash"][:12], None, \
               {"setup_hash": state["setup_hash"], "changes": len(state["setup_history"])}

    def rigs_that_produced_evidence():
        """Every rig hash an in-scope capture was taken under, plus the one in effect now."""
        in_scope = {(sh["shot_id"], rep) for sh in required_here()
                    for rep in range(1, int(sh.get("min_reps", 1)) + 1)}
        used = {}
        for k, c in state["captures"].items():
            if k in in_scope and c.get("setup_hash"):
                used.setdefault(c["setup_hash"], []).append("%s r%d" % k)
        return used

    def c_setup_checks():
        # Only readings taken against the CURRENT rig count. Keyed on the check name alone, a
        # re-freeze inherited the previous configuration's calibration wholesale -- so the rig could
        # be moved and every reading about the old one still read as certifying the new.
        cur = state["setup_hash"]

        # And EVERY rig that produced evidence, not only the one in effect at the end. Checking the
        # current hash alone meant a session could take half its required frames under rig A, freeze
        # rig B, calibrate B, and hear "all 10 rig calibration checks recorded and passing" -- a
        # true sentence about a configuration that took none of the photographs. Scale, tilt and
        # board geometry are properties of the rig that made a frame, so a frame from an
        # uncalibrated rig has no established scale whatever the current one measures.
        produced = rigs_that_produced_evidence()
        uncalibrated = []
        for h, frames in sorted(produced.items()):
            if h == cur:
                continue
            got = {k for k, v in state["setup_checks"].items() if v.get("setup_hash") == h
                   and v.get("outcome") == QA.PASS}
            short = [c for c in REQUIRED_SETUP_CHECKS if c not in got]
            if short:
                uncalibrated.append((h, frames, short))
        if uncalibrated:
            h, frames, short = uncalibrated[0]
            return False, ("%d capture(s) were taken under rig %s, which has %d calibration "
                           "reading(s) missing or not passing"
                           % (len(frames), h[:12], len(short))), \
                   ("calibrate that configuration, or re-take those frames under the rig that is "
                    "calibrated. A photograph from an uncalibrated rig has no established scale."), \
                   {"rig": h[:12], "frames": frames[:6], "missing": short[:6]}
        # A reading that does not say which rig it was taken against has not established anything
        # about the current one. Admitting None was an escape hatch that re-opened exactly the hole
        # the keying closed.
        have = {k: v for k, v in state["setup_checks"].items()
                if v.get("setup_hash") == cur} if cur else {}
        missing = [c for c in REQUIRED_SETUP_CHECKS if c not in have]
        # An explicit PASS, or nothing. `not in (None, QA.PASS)` treated a reading with NO outcome
        # at all as satisfied, so a calibration record posted with the check's name and no verdict
        # counted as a passing calibration -- absence wearing the costume of a result, in the one
        # place the whole session's scale comes from.
        failed = [c for c in REQUIRED_SETUP_CHECKS
                  if c in have and have[c].get("outcome") != QA.PASS]
        unknown = [c for c in have if c not in REQUIRED_SETUP_CHECKS]
        if missing or failed:
            return False, ("rig calibration incomplete: %d missing (%s), %d recorded without an "
                           "explicit pass (%s)"
                           % (len(missing), ", ".join(missing[:6]) or "-",
                              len(failed), ", ".join(failed[:4]) or "-")), \
                   "run `pilot.py setup` and complete every calibration reading", \
                   {"missing": missing, "failed": failed, "unrecognised": unknown[:6]}
        return True, "all %d rig calibration checks recorded and passing" % len(REQUIRED_SETUP_CHECKS), \
               None, {"unrecognised": unknown[:6]}

    def c_board_square():
        m = state["setup_checks"].get("board_square_measured") or {}
        if state["setup_hash"] and m.get("setup_hash") != state["setup_hash"]:
            return False, ("the board-square measurement was taken against rig %s, not the one in "
                           "effect (%s)" % (str(m.get("setup_hash"))[:8],
                                            str(state["setup_hash"])[:8])), \
                   "re-measure the board against the current rig", {}
        v = m.get("measured_mm")
        n = m.get("squares_spanned")
        if v is None or n in (None, 0):
            return False, "the printed board's square size has not been measured", \
                   "measure a run of squares with a steel rule and record it in `pilot.py setup`", {}
        # It is a quotient of two numbers a person typed, and only the quotient was checked. A
        # single square spanned, a fractional count, a negative length -- all divided to something
        # near 25 and passed. A one-square measurement is also below what a steel rule resolves:
        # 0.5 mm read over 25 mm is 2%, and over 200 mm it is 0.25%.
        try:
            v, n = float(v), float(n)
        except (TypeError, ValueError):
            return False, "the board-square measurement is not numeric", "re-record it", {}
        if not (math.isfinite(v) and math.isfinite(n)):
            return False, "the board-square measurement is not a finite number", "re-record it", {}
        if n != int(n) or n < MIN_BOARD_SQUARES_SPANNED:
            return False, ("the board-square measurement spans %g squares; measure a run of at "
                           "least %d whole squares, because a rule read to 0.5 mm over one 25 mm "
                           "square is a 2%% measurement"
                           % (n, MIN_BOARD_SQUARES_SPANNED)), \
                   ("span at least %d whole squares with the rule and record the total"
                    % MIN_BOARD_SQUARES_SPANNED), {"squares_spanned": n}
        if n > BOARD_MAX_SQUARES:
            return False, ("the measurement claims %g squares, but the board only has %d in its "
                           "longest direction" % (n, BOARD_MAX_SQUARES)), \
                   "re-count the squares the rule spans", {"squares_spanned": n}
        if v <= 0:
            return False, "the measured length is not positive", "re-measure", {"measured_mm": v}
        per = v / n
        off = abs(per - BOARD_SQUARE_MM)
        if off > BOARD_SQUARE_TOLERANCE_MM:
            return False, ("the printed squares measure %.2f mm, not %.1f mm (%.2f mm out) -- every "
                           "scale derived from this board would carry that error"
                           % (per, BOARD_SQUARE_MM, off)), \
                   "reprint the board at 100%% scale (no 'fit to page') and measure again", \
                   {"measured_mm_per_square": per}
        return True, "printed squares measure %.2f mm across %s squares" % (per, n), None, \
               {"mm_per_square": per}

    def c_captures_carry_setup():
        # Set membership was not enough. `known` was every rig hash appearing ANYWHERE in the log,
        # so a photograph taken (or logged before freeze) a week before the rig was frozen became attributable
        # to a configuration that did not exist when it was taken -- attribution by coincidence of
        # spelling. Resolve each capture against the freeze IN EFFECT AT ITS OWN POSITION in the log.
        freezes = sorted(((h.get("seq"), h.get("setup_hash")) for h in state["setup_history"]
                          if h.get("setup_hash")), key=lambda x: (x[0] is None, x[0]))
        bad, premature = [], []
        for k, c in sorted(state["captures"].items()):
            h = c.get("setup_hash")
            seq = c.get("seq")
            if not h:
                bad.append("%s r%d (no rig hash)" % k)
                continue
            in_effect = None
            for fseq, fh in freezes:
                if fseq is None or seq is None or fseq < seq:
                    in_effect = fh
            if in_effect is None:
                premature.append("%s r%d" % k)
            elif h != in_effect:
                premature.append("%s r%d (cites %s, rig in effect was %s)"
                                 % (k[0], k[1], str(h)[:8], str(in_effect)[:8]))
        if bad or premature:
            return False, ("%d capture(s) carry no rig hash and %d cite a configuration that was "
                           "not the one in effect when they were taken"
                           % (len(bad), len(premature))), \
                   "these were taken before the rig was frozen, or under a configuration recorded " \
                   "later. Re-take them, or record the configuration they were taken under as a " \
                   "deviation.", {"no_hash": bad[:6], "wrong_rig": premature[:6]}
        return True, "all %d captures carry the rig hash in effect when they were taken" \
               % len(state["captures"]), None, {}

    def c_one_rig():
        """The gated states must have been captured under ONE rig, or the change must be recorded.

        The rig could be re-frozen mid-session: half the captures under one configuration and half
        under another, the calibration never re-run against the new one, and nothing saying the
        camera had moved. Every capture was individually 'attributable', and the session as a whole
        described two rigs.
        """
        # Resolved from the PLAN, not from the capture's own claim about itself. Reading the
        # self-reported state let a frame mislabel itself out of this condition while still counting
        # as evidence for the condition next door.
        in_scope = {(sh["shot_id"], rep) for sh in required_here()
                    for rep in range(1, int(sh.get("min_reps", 1)) + 1)}
        used = {}
        for k, c in state["captures"].items():
            if k in in_scope and c.get("setup_hash"):
                used.setdefault(c["setup_hash"], []).append("%s r%d" % k)
        if len(used) <= 1:
            return True, "one rig configuration across %d captures" % len(state["captures"]), \
                   None, {}
        # It must name WHICH rig change, and that hash must be one the session actually used. A
        # deviation of kind "rig" and nothing else excused any number of configurations.
        recorded = {h for h in used
                    if deviation_covers(state["deviations"], "rig", h)
                    or deviation_covers(state["deviations"], "rig", h[:12])}
        if len(used) - len(recorded) > 1:
            return False, ("the captures in these states were taken under %d different rig "
                           "configurations and no rig deviation was recorded"
                           % len(used)), \
                   "re-freeze deliberately with `pilot.py setup --reason ...`, which records what " \
                   "changed, or re-take the frames from the earlier configuration", \
                   {"configurations": {h[:8]: v[:3] for h, v in used.items()}}
        return True, "%d rig configurations, with the change recorded as a deviation" % len(used), \
               None, {"configurations": sorted(h[:8] for h in used)}

    _guard(blocks, satisfied, "rig.frozen", c_setup_frozen)
    _guard(blocks, satisfied, "rig.calibrated", c_setup_checks)
    _guard(blocks, satisfied, "rig.board_square_measured", c_board_square)
    _guard(blocks, satisfied, "rig.captures_attributable", c_captures_carry_setup)
    _guard(blocks, satisfied, "rig.one_configuration", c_one_rig)

    # --- measurements ---------------------------------------------------------------------
    def c_measurements():
        missing, thin, inconsistent, implausible = [], [], [], []
        for name, n_required in sorted(REQUIRED_MEASUREMENTS.items()):
            m = state["measurements"].get(name)
            if not m:
                missing.append(name)
                continue
            readings = [r for r in (m.get("readings") or []) if r is not None]
            if len(readings) < n_required:
                thin.append("%s (%d of %d readings)" % (name, len(readings), n_required))
                continue
            if any(not isinstance(r, (int, float)) or not math.isfinite(float(r))
                   for r in readings):
                implausible.append("%s (a reading is not a finite number)" % name)
                continue
            lo, hi = MEASUREMENT_RANGE.get(name, (None, None))
            mean = sum(readings) / len(readings)
            if lo is not None and not (lo <= mean <= hi):
                implausible.append("%s = %.2f, outside the plausible %.0f-%.0f for an adult "
                                   "garment (a tape read in inches gives two readings that agree "
                                   "perfectly and are 2.5x wrong)" % (name, mean, lo, hi))
                continue
            tol = MEASUREMENT_TOLERANCE.get(name, MEASUREMENT_TOLERANCE["_default_cm"])
            spread = max(readings) - min(readings)
            if spread > tol:
                inconsistent.append("%s (readings differ by %.2f, tolerance %.2f)"
                                    % (name, spread, tol))
        if missing or thin or inconsistent or implausible:
            parts = []
            if missing:
                parts.append("%d not measured (%s)" % (len(missing), ", ".join(missing)))
            if thin:
                parts.append("%d with too few readings (%s)" % (len(thin), "; ".join(thin)))
            if inconsistent:
                parts.append("%d whose readings disagree (%s)"
                             % (len(inconsistent), "; ".join(inconsistent)))
            if implausible:
                parts.append("%d outside a plausible range (%s)"
                             % (len(implausible), "; ".join(implausible)))
            return False, "measurements incomplete: " + "; ".join(parts), \
                   "run `pilot.py measure`; each dimension needs its readings taken independently, " \
                   "not copied", {"missing": missing, "thin": thin, "inconsistent": inconsistent}
        return True, "all %d required measurements recorded with independent readings in tolerance" \
               % len(REQUIRED_MEASUREMENTS), None, {}

    _guard(blocks, satisfied, "measurements.complete", c_measurements)

    def c_measurement_record_is_coherent():
        """Re-measurements and mis-filed states are recorded; this is what reads them back.

        store.fold has projected `measurement_revisions` and `measurement_state_conflicts` since
        the measurements were bucketed by state, and nothing consumed either -- a projection no
        condition reads is not a check, it is a comment. A re-measurement inside one state is
        legitimate (the tape was laid again) and must be visible, not silent: it is the difference
        between a corrected number and a number that changed while nobody was looking. A reading
        filed under a state the log contradicts is an ordinary mistake with an ordinary remedy, and
        saying so beats leaving it in the record unmentioned.
        """
        revs = state.get("measurement_revisions") or []
        back = state.get("measurement_backdated") or []
        if back:
            # No acknowledgement path, deliberately. This is a reading filed into a state the
            # garment has already left -- a write back into the pre-cut baseline after the cut --
            # and the baseline is the number every later comparison is made against. A deviation
            # can excuse a departure from procedure; it cannot make a measurement of a cut garment
            # into a measurement of the garment before it was cut.
            return False, ("%d measurement(s) were filed into a state the garment had already "
                           "left: %s" % (len(back),
                                         "; ".join("%s claims %s, the log had reached %s at that "
                                                   "point" % (c["name"], c["claimed"], c["log_says"])
                                                   for c in back[:4]))), \
                   ("the pre-cut baseline cannot be written after the cut. Record the reading in "
                    "the state it was actually taken in:\n"
                    "  tools/pilot.py measure %s --state post_wash" % state["garment_id"]), \
                   {"backdated": back[:6]}
        if revs:
            # Targeted at the measurement it explains. An untargeted one cleared every revision in
            # the session at once, including revisions written after it.
            names = sorted({r["name"] for r in revs})
            unexplained = [n for n in names
                           if deviation_covers(state["deviations"], "protocol",
                                               "measurement_revised:%s" % n) is None]
            if unexplained:
                revs = [r for r in revs if r["name"] in unexplained]
                return False, ("%d measurement(s) were replaced by a later reading in the same "
                               "state: %s" % (len(revs),
                                              "; ".join("%s %s -> %s (entry %s)"
                                                        % (r["name"], r["was"], r["now"], r["seq"])
                                                        for r in revs[:4]))), \
                       ("a corrected measurement is fine and a silent one is not. Say why the "
                        "first reading was wrong, naming the measurement:\n"
                        + "\n".join(
                            "  tools/pilot.py deviation %s --kind protocol --field "
                            "measurement_revised:%s --reason '<which reading was wrong and how "
                            "you know>'" % (state["garment_id"], n) for n in unexplained[:3])), \
                       {"revisions": revs[:6], "unexplained": unexplained}
        ahead = state.get("measurement_ahead_of_record") or []
        return True, ("no measurement was replaced or back-dated without a reason on record"
                      + ("; %d taken ahead of the record they belong to" % len(ahead) if ahead
                         else "")), None, {"ahead_of_record": ahead[:6]}

    _guard(blocks, satisfied, "measurements.revisions_explained", c_measurement_record_is_coherent)

    def c_annotations_account_for_instances():
        """Every counted instance is described, so a photograph can name what it is of.

        `n_tears = 3` requires three tear photographs and says nothing about which tear each one
        shows. The frames were expanded from an ordinal, the capture recorded only the shot id, and
        the mapping from ordinal to physical object lived nowhere -- so two frames of the same tear
        satisfied the requirement, and after the cut nobody could tell which was which. The count
        and the descriptions have to agree BEFORE the garment is cut, because that is the last
        moment the garment is intact enough to go back and look.
        """
        anns = state.get("annotations") or {}
        counts = [f["key"] for f in spec.features if f["type"] == "count"]
        short, over, ids = [], [], {}
        for key in sorted(counts):
            want = state["features"].get(key)
            try:
                want = int(float(want))
            except (TypeError, ValueError):
                continue                     # unanswered: the plan already assumes it is present
            if want <= 0:
                continue
            got = PLAN.annotations_for(anns, key)
            if len(got) < want:
                short.append("%s: %d of %d described" % (key, len(got), want))
            elif len(got) > want:
                over.append("%s: %d described but the count says %d" % (key, len(got), want))
            for a in got:
                ids.setdefault(str(a.get("annotation_id")), []).append(key)
        dupes = sorted(k for k, v in ids.items() if len(v) > 1)
        thin = sorted(str(a.get("annotation_id")) for a in anns.values()
                      if not (a.get("location") or "").strip())
        if short or over or dupes or thin:
            parts = []
            if short:
                parts.append("%d counted feature(s) not fully described (%s)"
                             % (len(short), "; ".join(short)))
            if over:
                parts.append("%d described more times than counted (%s)"
                             % (len(over), "; ".join(over)))
            if dupes:
                parts.append("%d annotation id(s) reused (%s)" % (len(dupes), ", ".join(dupes)))
            if thin:
                parts.append("%d annotation(s) with no location, so no photograph of them can be "
                             "relocated (%s)" % (len(thin), ", ".join(thin[:4])))
            return False, "the garment's features are counted but not identified: " \
                          + "; ".join(parts), \
                   ("describe each one, with a stable id and where it is:\n"
                    "  tools/pilot.py annotate <ID> --id TEAR.01 --feature n_tears --type tear "
                    "--location 'left leg front, 12 cm above the hem' --note '<what it looks like>'"), \
                   {"short": short, "over": over, "duplicate_ids": dupes, "no_location": thin}
        n = sum(len(PLAN.annotations_for(anns, k)) for k in counts)
        return True, "%d physical feature instance(s) described, each with a stable id" % n, \
               None, {"annotations": sorted(anns)[:12]}

    _guard(blocks, satisfied, "annotations.identify_instances",
           c_annotations_account_for_instances)

    def c_capture_instance_matches_plan():
        """The photograph's own record of what it is of must agree with what the plan says.

        Every instanced capture stores the annotation it was taken of. Nothing read it back, so the
        log could hold the contradiction -- `capture ...I01 annotation_id=TEAR.01` sitting beside
        `plan ...I01 = TEAR.00` -- and no condition looked at the two together. One equality check
        turns a silent re-labelling into a block, and it is the same check that catches a frame
        borrowed from one instance to satisfy another.
        """
        if activated is None:
            return None
        want = {s["shot_id"]: s.get("annotation_id") for s in activated if s.get("annotation_id")}
        wrong, orphan = [], []
        for (sid, rep), c in sorted(state["captures"].items()):
            claimed = c.get("annotation_id")
            expect = want.get(sid)
            if expect is None:
                if claimed:
                    orphan.append("%s r%s says it is of %s, but the plan does not instance that shot"
                                  % (sid, rep, claimed))
                continue
            if claimed is None:
                # NOT a skip. Omitting the field was the cheapest way past this condition: a
                # photograph filed into an instanced slot with no recorded subject left the check
                # reporting "0 photographs name what they are of" and passing.
                wrong.append("%s r%s records no subject at all, and the plan says that slot is %s"
                             % (sid, rep, expect))
                continue
            if claimed != expect:
                wrong.append("%s r%s was taken of %s and the plan now says that slot is %s"
                             % (sid, rep, claimed, expect))
        if wrong or orphan:
            ack = deviation_covers(state["deviations"], "protocol", "instance_mismatch")
            if ack is not None:
                return True, ("%d photograph(s) disagree with the plan about their subject, "
                              "acknowledged as a deviation" % (len(wrong) + len(orphan))), \
                       None, {"mismatched": wrong[:6], "orphaned": orphan[:6],
                              "acknowledged": True}
            return False, ("%d photograph(s) disagree with the plan about which physical thing "
                           "they show: %s" % (len(wrong) + len(orphan),
                                              "; ".join((wrong + orphan)[:4]))), \
                   ("do not re-point the annotations to make this go away -- the photographs are "
                    "of what they are of. Re-take the frames whose subject changed, or record the "
                    "mismatch as a deviation and treat them as absent:\n"
                    "  tools/pilot.py deviation %s --kind protocol --field instance_mismatch "
                    "--reason '<what happened>'" % state["garment_id"]), \
                   {"mismatched": wrong[:6], "orphaned": orphan[:6]}
        n = sum(1 for c in state["captures"].values() if c.get("annotation_id"))
        return True, "%d photograph(s) name the physical thing they are of, and agree with the " \
                     "plan" % n, None, {}

    _guard(blocks, satisfied, "captures.instance_identity", c_capture_instance_matches_plan)

    def c_captures_match_the_lifecycle():
        """A photograph's state must be consistent with when the log says it was taken.

        Nothing compared the two. cut.not_already_performed closed this for the CUT gate only, so
        the two later gates still accepted a 'before' frame filed after the shears -- a photograph
        of the intact garment that cannot exist -- and a 'post_wash' frame taken before the garment
        had been cut or washed, which is a photograph of something that had not happened yet. Both
        produced a fully green, fully chained record. The physical facts that order the session are
        already in this log; this reads them.
        """
        cut_seq = (state.get("cut_performed") or {}).get("seq")
        wash_seq = (state.get("wash_actual") or {}).get("seq")
        plan_state_of = {s["shot_id"]: s.get("state") for s in (activated or [])}
        PRE = ("intake", "before", "marked")
        POST = ("post_wash", "offcut_after")
        bad = []
        for (sid, rep), c in sorted(state["captures"].items()):
            seq = c.get("seq")
            # A capture that records no state is given the state its SHOT is in. Reading only the
            # capture's own field meant omitting it skipped the check entirely.
            cs = str(c.get("state") or (plan_state_of.get(sid) or ""))
            if seq is None:
                continue
            if cs in PRE and cut_seq is not None and seq > cut_seq:
                bad.append("%s r%s is a %s frame filed at entry %s, after the cut at entry %s"
                           % (sid, rep, cs, seq, cut_seq))
            elif cs in POST and wash_seq is not None and seq < wash_seq:
                bad.append("%s r%s is a %s frame filed at entry %s, before the wash at entry %s"
                           % (sid, rep, cs, seq, wash_seq))
            elif cs in POST and wash_seq is None:
                bad.append("%s r%s is a %s frame and no wash has been recorded" % (sid, rep, cs))
        if bad:
            # The remedy this message names is honoured here. A condition that tells the operator
            # to record a deviation and then ignores the deviation is the "remedy that does not
            # exist" this module has closed twice already.
            ack = deviation_covers(state["deviations"], "protocol", "capture_order")
            if ack is not None:
                return True, ("%d photograph(s) are out of order with the log, acknowledged as a "
                              "deviation" % len(bad)), None, {"out_of_order": bad[:8],
                                                              "acknowledged": True}
            return False, ("%d photograph(s) are filed in a state the log's own order contradicts: "
                           "%s" % (len(bad), "; ".join(bad[:4]))), \
                   ("a photograph of the uncut garment cannot have been taken after the cut, and "
                    "one of the washed garment cannot have been taken before the wash. Nothing "
                    "here can be re-taken: record what happened as a deviation and treat the "
                    "affected frames as absent.\n"
                    "  tools/pilot.py deviation %s --kind protocol --field capture_order "
                    "--reason '<what happened>'" % state["garment_id"]), {"out_of_order": bad[:8]}
        return True, "every photograph's state agrees with the log's own order", None, {}

    _guard(blocks, satisfied, "captures.state_order", c_captures_match_the_lifecycle)

    # --- captures -------------------------------------------------------------------------
    def c_required_captures():
        req = required_here()
        done = store.done_keys()
        missing, failing, unresolved = [], [], []
        for s in req:
            for rep in range(1, int(s.get("min_reps", 1)) + 1):
                key = (s["shot_id"], rep)
                q = state["qa"].get(key)
                cap = state["captures"].get(key)
                if cap is not None and cap.get("state") and cap["state"] != s["state"]:
                    # Two projections disagreed about what a capture's state means: the one-rig
                    # condition trusts the capture's self-declared state while this one matched on
                    # shot id alone, so a frame could mislabel its state to escape the first and
                    # still count as the second's evidence.
                    failing.append("%s r%d (filed under state %r, but the shot belongs to %r)"
                                   % (key[0], key[1], cap.get("state"), s["state"]))
                    continue
                if key not in done:
                    # `done` excludes frames the checker rejected, so "not done" covers two very
                    # different situations and the operator's next move differs: take the
                    # photograph, versus look at why the one you took was refused.
                    if q and q.get("outcome") == QA.RETAKE:
                        failing.append("%s r%d (%s)" % (key[0], key[1], q.get("outcome")))
                    else:
                        missing.append("%s r%d" % key)
                    continue
                if not q:
                    unresolved.append("%s r%d (never checked)" % key)
                    continue
                out = q.get("outcome")
                # The record must contain the checks its own shot class can support. Re-deriving the
                # roll-up from the stored list tests the record against ITSELF: a list of invented
                # all-PASS checks rolls up to PASS and agrees with a PASS verdict perfectly. So the
                # MANDATORY set comes from the code -- what this class of frame is checkable for --
                # and anything absent has to be justified by the record's own not_applicable notes.
                present = {c.get("check_id") for c in (q.get("checks") or [])}
                # An excuse is honoured only when the code would itself have written it. The list
                # is free text from the same record the rule is meant to constrain.
                excused = {x.get("check_id") for x in (q.get("not_applicable") or [])
                           if QA.excuse_is_valid(s, x.get("check_id"),
                                                 x.get("not_applicable_to"))}
                mandatory = set(QA.APPLICABLE.get(QA.shot_class(s), ())) - QA.OPTIONAL_CHECKS
                absent = sorted(mandatory - present - excused)
                if absent:
                    failing.append("%s r%d (its record is missing %d check(s) this kind of frame "
                                   "is checkable for: %s)"
                                   % (key[0], key[1], len(absent), ", ".join(absent[:4])))
                    continue
                recomputed = QA.roll_up([QA.Check(c.get("check_id", "?"), c.get("outcome", QA.UNAVAILABLE),
                                                  c.get("detail", ""))
                                         for c in (q.get("checks") or [])])
                if recomputed != out:
                    # The verdict is a roll-up of the checks stored beside it. If the two disagree,
                    # the outcome was written by something other than the checker, and appending a
                    # forged one leaves the hash chain perfectly intact.
                    failing.append("%s r%d (recorded %s, but its own checks roll up to %s)"
                                   % (key[0], key[1], out, recomputed))
                    continue
                if out == QA.PASS:
                    continue
                if out == QA.HUMAN:
                    if not _human_resolved(state, s["shot_id"], rep, q,
                                           state["captures"].get(key)):
                        unresolved.append("%s r%d (awaiting human verification)" % key)
                    continue
                failing.append("%s r%d (%s)" % (key[0], key[1], out))
        if missing or failing or unresolved:
            return False, ("required captures incomplete: %d missing, %d failing, %d unresolved "
                           "(of %d required frames)"
                           % (len(missing), len(failing), len(unresolved),
                              sum(int(s.get("min_reps", 1)) for s in req))), \
                   "the app's next action names the first of these; work through them", \
                   {"missing": missing[:12], "failing": failing[:12], "unresolved": unresolved[:12],
                    "n_missing": len(missing), "n_failing": len(failing),
                    "n_unresolved": len(unresolved)}
        return True, "all %d required frames captured and passing" % \
               sum(int(s.get("min_reps", 1)) for s in req), None, {}

    #: Checks that read PIXELS and need no human input, so the gate can run them again itself.
    #: Everything else in a record -- a ruler confirmation, which face is up, a re-lay attestation --
    #: rests on a person, and re-running it would only re-read what the person said.
    MECHANICAL = ("readable", "resolution", "blur", "exposure", "clipping", "cropping",
                  "subject_present", "board_corners", "scale", "camera_tilt", "subject_extent",
                  "subject_span")

    def c_verdicts_reproduce():
        """Re-run the pixel checks on the actual files and see whether the record survives.

        Every other defence in this module tests the record against ITSELF: the roll-up must match
        the checks, the checks must cover what the class supports, the excuses must be ones this
        code would have written. All of that is satisfied by a sufficiently complete forgery -- one
        appended qa_result carrying an invented all-PASS check list made a photograph of an empty
        backdrop into a passing primary whole-garment frame, and the hash chain stayed perfect
        because nothing had been altered, only added.

        The photograph is the one thing an appended line cannot change. So for the gate -- run once,
        before something irreversible -- the mechanical checks are simply run again, from the files
        on disk, and a recorded PASS that does not reproduce is a block.
        """
        if not check_files:
            return False, "file checking was disabled, so no recorded verdict was re-derived", \
                   "run the gate without --no-file-checks", {}
        try:
            board, bspec = _board_pair(garment_dir)
        except Exception as e:                 # noqa: BLE001
            return False, "the calibration board could not be loaded, so no verdict could be " \
                          "re-derived from the photographs: %s" % e, \
                   "restore protocol/charuco_board.json", {}
        bad, rechecked = [], 0
        # THE MULTI-FILE CHECKS, re-run from the photographs. MECHANICAL is a list of single-frame
        # checks, and the two checks that read more than one file -- relay_independence and
        # duplicate_content -- were in neither it nor the mandatory set. So the one class of
        # evidence a record cannot fake, what two photographs look like beside each other, was
        # taken entirely on the record's word: c_relays reads the relay verdict straight out of the
        # log, and its anti-forgery test (compared_against_sha256 must name the previous capture)
        # is satisfied by writing that sha in. Every frame of a whole session could come from one
        # lay.
        for sh in required_here():
            for rep in range(1, int(sh.get("min_reps", 1)) + 1):
                prev_key = None
                if sh.get("relay_after"):
                    reps_ = [r for (sid_, r) in state["captures"] if sid_ == sh["relay_after"]]
                    if rep == 1 and reps_:
                        prev_key = (sh["relay_after"], max(reps_))
                elif sh.get("relay_between_reps") and rep > 1:
                    prev_key = (sh["shot_id"], rep - 1)
                if prev_key is None:
                    continue
                here = state["captures"].get((sh["shot_id"], rep))
                there = state["captures"].get(prev_key)
                if not here or not there:
                    continue
                pa = garment_dir / (there.get("path") or "")
                pb = garment_dir / (here.get("path") or "")
                try:
                    import cv2
                    from . import qa_primitives as _Q
                    board2, bspec2 = _board_pair(garment_dir)
                    ia, ib = cv2.imread(str(pa)), cv2.imread(str(pb))
                    if ia is None or ib is None:
                        bad.append("%s r%d (a frame of its re-lay pair could not be decoded)"
                                   % (sh["shot_id"], rep))
                        continue
                    pose_a = _Q.garment_pose_of(ia, board2, bspec2)
                    pose_b = _Q.garment_pose_of(ib, board2, bspec2)
                    ncc = _Q.registered_interior_ncc(ib, ia, pose_b, pose_a)
                    # The SCALE, recovered from the board in the later frame. Passing None short-
                    # circuited relay_verdict to UNAVAILABLE before it ever looked at the cloth, so
                    # this whole re-derivation quietly decided nothing.
                    mmpp = None
                    try:
                        from ..capture.board import detect, mm_per_pixel
                        cs_, is_ = detect(cv2.cvtColor(ib, cv2.COLOR_BGR2GRAY), board2)
                        if is_ is not None and len(is_) >= 4:
                            mmpp = mm_per_pixel(cs_, is_, bspec2)
                    except Exception:           # noqa: BLE001
                        mmpp = None
                    secs_ = None
                    ta, tb = there.get("exif_ts"), here.get("exif_ts")
                    if ta and tb:
                        secs_ = abs(float(tb) - float(ta))
                    o_, d_, _ev = _Q.relay_verdict(pose_a, pose_b, mmpp, interior_ncc=ncc,
                                                   seconds_apart=secs_, operator_confirmed=False)
                except Exception as e:          # noqa: BLE001
                    bad.append("%s r%d (its re-lay could not be re-derived: %s)"
                               % (sh["shot_id"], rep, e))
                    continue
                rechecked += 1
                if o_ == QA.RETAKE:
                    bad.append("%s r%d (%s)" % (sh["shot_id"], rep, d_[:90]))
                elif o_ == QA.UNAVAILABLE and not _human_resolved(
                        state, sh["shot_id"], rep, state["qa"].get((sh["shot_id"], rep)) or {},
                        here):
                    # Could not be re-derived, and nobody has attested it. Unknown is not permission
                    # -- but a person who was there can still settle it, which is the same escape
                    # c_relays offers and keeps this from becoming another operator lockout.
                    bad.append("%s r%d (its re-lay could not be re-derived from the photographs: %s)"
                               % (sh["shot_id"], rep, d_[:70]))
        for sh in required_here():
            for rep in range(1, int(sh.get("min_reps", 1)) + 1):
                key = (sh["shot_id"], rep)
                cap = state["captures"].get(key)
                q = state["qa"].get(key) or {}
                if not cap or q.get("outcome") not in (QA.PASS, QA.HUMAN):
                    continue                    # nothing claimed; other conditions cover it
                path = garment_dir / (cap.get("path") or "")
                try:
                    # NO assertions are passed in. Feeding the record's own PASS list back into the
                    # re-check would be the very pattern this condition exists to break -- the
                    # record vouching for itself. None of the twelve mechanical checks reads an
                    # assertion anyway, so there is nothing to gain and a standing invitation to a
                    # later mistake.
                    checks, _na = QA.check_capture(
                        path, sh, QA.merged_quality(spec.doc["quality_defaults"], sh), rep=rep,
                        board=board, board_spec=bspec)
                except Exception as e:          # noqa: BLE001
                    bad.append("%s r%d (could not be re-checked: %s)" % (key[0], key[1], e))
                    continue
                rechecked += 1
                for c in checks:
                    if c.check_id in MECHANICAL and c.outcome == QA.RETAKE:
                        bad.append("%s r%d (%s: %s)" % (key[0], key[1], c.check_id,
                                                        (c.detail or "")[:90]))
                        break
        if bad:
            return False, ("%d frame(s) recorded as passing do not pass when the checker is run "
                           "again on the photograph itself" % len(bad)), \
                   ("the verdict in the log does not describe the file on disk. Re-take these "
                    "frames. A record can be appended to; a photograph cannot."), \
                   {"failing": bad[:10]}
        return True, "%d recorded verdict(s) re-derived from the photographs themselves" % rechecked, \
               None, {}

    def c_files_present():
        if not check_files:
            return False, ("file integrity was not verified in this view, so whether every recorded "
                           "photograph is still on disk and unchanged is unknown"), \
                   "unknown is not permission: run `pilot.py precut` (or open the GATE tab), which " \
                   "hashes every file", {}
        missing, changed, unhashed, misfiled, forged_sig = [], [], [], [], []
        for (sid, rep), c in sorted(state["captures"].items()):
            rel = c.get("path")
            if not rel:
                missing.append("%s r%d (no path)" % (sid, rep))
                continue
            if not c.get("sha256"):
                # The hash comparison used to be conditional on a hash having been recorded, so an
                # entry that recorded none skipped it entirely and a 12-byte text file counted as a
                # photograph while the gate reported "present and hash-matched".
                unhashed.append("%s r%d" % (sid, rep))
                continue
            # Ingestion files a capture as <shot>__r<NN>__<sha12>.<ext>. An entry whose path does
            # not encode its own shot, repeat and hash is pointing at some other shot's file, which
            # is how a photograph that was never taken passed by pure append.
            # The BASENAME was all that was checked, so "../../other/NAME" and an absolute path
            # both satisfied it while pointing the evidence somewhere else entirely. Containment
            # first, and through realpath, so a symlink cannot lead out either.
            if os.path.isabs(rel) or ".." in Path(rel).parts:
                misfiled.append("%s r%d -> %s (path escapes the garment directory)" % (sid, rep, rel))
                continue
            try:
                real = Path(os.path.realpath(str(garment_dir / rel)))
                real.relative_to(Path(os.path.realpath(str(garment_dir))))
            except (ValueError, OSError):
                misfiled.append("%s r%d -> %s (resolves outside the garment directory)"
                                % (sid, rep, rel))
                continue
            base = os.path.basename(rel)
            safe = "".join(ch if (ch.isalnum() or ch in "._-") else "_" for ch in str(sid))
            want = "%s__r%02d__%s" % (safe, int(rep), str(c["sha256"])[:12])
            if not base.startswith(want):
                misfiled.append("%s r%d -> %s" % (sid, rep, base))
                continue
            p = garment_dir / rel
            if not p.exists():
                missing.append("%s r%d -> %s" % (sid, rep, rel))
                continue
            want = c.get("sha256")
            if want and _hash_changed(p, want, use_cache=not rehash):
                changed.append("%s r%d -> %s" % (sid, rep, rel))
                continue
            # The recorded perceptual signature, against the photograph itself. At INGEST the
            # signature is only a prefilter -- it decides which pairs are worth decoding, and
            # recomputing every earlier frame's would cost a decode per prior capture on a phone
            # upload. So one appended capture line changing nothing but the dhash pushed a frame far
            # outside the near-duplicate band, and the same photograph then satisfied a second
            # required shot with duplicate_content recording a confident PASS.
            #
            # The gate runs once, before something irreversible, and can afford the decode. A
            # signature that does not describe the file is a forged prefilter, and every duplicate
            # verdict that rested on it is worthless.
            rec_sig = c.get("dhash")
            if rec_sig:
                try:
                    import cv2
                    from . import qa_primitives as _Q
                    im_ = cv2.imread(str(p))
                    if im_ is not None:
                        if _Q.dhash_bits(im_).hex() != str(rec_sig):
                            forged_sig.append("%s r%d" % (sid, rep))
                except Exception:              # noqa: BLE001
                    forged_sig.append("%s r%d (its signature could not be re-derived)" % (sid, rep))
        if missing or changed or unhashed or misfiled or forged_sig:
            return False, ("%d recorded photograph(s) missing from disk, %d no longer matching "
                           "their recorded hash, %d recorded without a hash at all, %d filed under "
                           "a name that is not their own shot and hash, %d whose recorded "
                           "perceptual signature does not describe the file"
                           % (len(missing), len(changed), len(unhashed), len(misfiled),
                              len(forged_sig))), \
                   "restore them from the phone, or re-capture. A manifest entry whose file is " \
                   "gone, unhashed, pointing at another shot's photograph, or carrying a signature " \
                   "that is not the photograph's own is not evidence.", \
                   {"missing": missing[:8], "changed": changed[:8], "unhashed": unhashed[:8],
                    "misfiled": misfiled[:8], "signature_mismatch": forged_sig[:8]}
        return True, "all %d recorded photographs present and hash-matched" % len(state["captures"]), \
               None, {}

    _guard(blocks, satisfied, "captures.required_complete", c_required_captures)
    _guard(blocks, satisfied, "captures.verdicts_reproduce", c_verdicts_reproduce)
    _guard(blocks, satisfied, "captures.files_intact", c_files_present)

    def c_relays():
        req = required_here()
        # (shot, rep, the frame it must be an independent re-lay OF). Two ways a re-lay is
        # declared, and only the first was ever checked: repeats INSIDE one shot id, and a series
        # written as separate shot ids chained by relay_after. The eight frames the repeatability
        # arm exists for -- five front-overhead, three back -- are the second kind, so the
        # condition was vacuously satisfied for exactly the shots it was written about.
        pairs = []
        for s in req:
            if s.get("relay_between_reps") and int(s.get("min_reps", 1)) > 1:
                for rep in range(2, int(s["min_reps"]) + 1):
                    pairs.append((s, rep, (s["shot_id"], rep - 1)))
            if s.get("relay_after"):
                prev_reps = [r for (sid_, r) in state["captures"] if sid_ == s["relay_after"]]
                pairs.append((s, 1, (s["relay_after"], max(prev_reps) if prev_reps else 1)))
        bad = []
        for s, rep, against_key in pairs:
            q = state["qa"].get((s["shot_id"], rep)) or {}
            rc = None
            for c in (q.get("checks") or []):
                if c.get("check_id") == "relay_independence":
                    rc = c
            if rc is None:
                bad.append("%s r%d (relay independence never assessed)" % (s["shot_id"], rep))
            elif rc.get("outcome") != QA.PASS:
                # A person attesting the re-lay settles it, the same way it settles a reposition --
                # which is what this condition's own fix text tells the operator to do. Without
                # this the honest answer to "the cloth changed, but I cannot tell from the
                # timestamps whether you really lifted it" was a permanent block.
                if not _human_resolved(state, s["shot_id"], rep, q,
                                       state["captures"].get((s["shot_id"], rep))):
                    bad.append("%s r%d (%s)" % (s["shot_id"], rep, rc.get("outcome")))
            else:
                # The verdict was made against a particular earlier frame. If that frame has
                # since been replaced, the verdict describes a photograph that is no longer
                # there -- so two frames of the same lay can sit under reps 1 and 2 with a
                # passing relay verdict between them.
                against = (rc.get("evidence") or {}).get("compared_against_sha256")
                prev_cap = state["captures"].get(against_key) or {}
                if not against:
                    bad.append("%s r%d (its relay verdict does not name the frame it was "
                               "compared against)" % (s["shot_id"], rep))
                elif prev_cap.get("sha256") and against != prev_cap["sha256"]:
                    bad.append("%s r%d (compared against a frame that has since been replaced)"
                               % (s["shot_id"], rep))
        if bad:
            return False, ("%d repeat capture(s) are not established as independent re-lays"
                           % len(bad)), \
                   "each repeat must follow the garment being lifted clear and laid out again; " \
                   "confirm the re-lay in the app or re-take the repeat", {"failing": bad[:10]}
        return True, "%d re-lay(s) established as independent" % len(pairs), None, \
               {"chained_series": sorted({s["relay_after"] for s, _r, _k in pairs
                                          if s.get("relay_after")})}

    _guard(blocks, satisfied, "captures.relays_independent", c_relays)

    def c_repositions():
        req = required_here()
        need = [s for s in req if s.get("reposition_camera_between_reps")
                and int(s.get("min_reps", 1)) > 1]
        bad = []
        for s in need:
            for rep in range(2, int(s["min_reps"]) + 1):
                q = state["qa"].get((s["shot_id"], rep)) or {}
                rc = None
                for c in (q.get("checks") or []):
                    if c.get("check_id") == "camera_repositioned":
                        rc = c
                if rc is None:
                    bad.append("%s r%d (never asked)" % (s["shot_id"], rep))
                elif rc.get("outcome") != QA.PASS:
                    if not _human_resolved(state, s["shot_id"], rep, q,
                                           state["captures"].get((s["shot_id"], rep))):
                        bad.append("%s r%d (%s)" % (s["shot_id"], rep, rc.get("outcome")))
        if bad:
            return False, ("%d repeat capture(s) do not record that the camera was actually "
                           "repositioned" % len(bad)), \
                   "these repeats measure mounting variance only if the phone came off the mount; " \
                   "confirm it in the app or re-shoot", {"failing": bad[:10]}
        return True, "%d repeat capture(s) recorded a camera reposition" % \
               sum(int(s["min_reps"]) - 1 for s in need), None, {}

    _guard(blocks, satisfied, "captures.repositions_recorded", c_repositions)

    def c_reuse_legitimate():
        """A reuse declaration is judged exactly as a verdict is: re-derived, not asserted.

        Round 1 stopped trusting a bare `outcome` on a qa_result. The identical field on the
        neighbouring entry kind kept its trust, so one appended declaration could assert PASS and
        clear the shot it named.
        """
        bad = []
        by_shot = {sh["shot_id"]: sh for sh in (activated or [])}
        for r in state["reuse"]:
            sid = r.get("shot_id")
            if not r.get("source_shot_id") or not r.get("checks_rerun"):
                bad.append("%s (names no source, or records no re-run checks)" % sid)
                continue
            if r.get("outcome") != QA.PASS:
                bad.append("%s (recorded outcome %s)" % (sid, r.get("outcome")))
                continue
            shot = by_shot.get(sid)
            if shot is None:
                bad.append("%s (not an activated shot)" % sid)
                continue
            rerun = set(r.get("checks_rerun") or [])
            mandatory = set(QA.APPLICABLE.get(QA.shot_class(shot), ())) - QA.OPTIONAL_CHECKS
            missing = sorted(mandatory - rerun)
            if missing:
                bad.append("%s (did not re-run %s)" % (sid, ", ".join(missing[:4])))
        if bad:
            return False, ("%d image reuse declaration(s) do not establish that the borrowed image "
                           "was re-checked against the borrowing shot's own requirements"
                           % len(bad)), \
                   "an image may satisfy a second shot only when every requirement of that shot " \
                   "passes on it; run `pilot.py reuse`, which re-runs them, or capture the shot", \
                   {"shots": bad[:8]}
        return True, "%d image reuse declaration(s), each re-checked" % len(state["reuse"]), None, {}

    _guard(blocks, satisfied, "captures.reuse_legitimate", c_reuse_legitimate)

    def c_no_undeclared_reuse():
        """No two accepted captures may be the same photograph unless the reuse is declared.

        Duplicate detection lived only in the add-time checker, whose comparison set is built from
        the files present on disk at that moment. Anything that made a comparison not happen -- an
        earlier file temporarily missing, an ingest ordering, a checker that had not yet been
        hardened -- left the duplicate accepted, and nothing ever looked again. This is the same
        question asked of the DURABLE record, where the hashes are, so it does not depend on what
        could be read at the time.
        """
        # An exemption is honoured only when the log backs it: the source must be a capture that
        # exists, the borrowed frame must be the same bytes, and the borrowing shot must carry its
        # own verdict over those bytes. Otherwise a bare declaration naming any pair of shot ids
        # removed them from duplicate detection whatever they actually held.
        # An exemption covers a PAIR of keys, not a key. Removing keys before grouping meant a
        # declaration naming a capture as its own source satisfied every backing test trivially and
        # deleted that key from the bucket -- leaving the genuine other user of the same bytes as a
        # singleton, and the condition reporting the positive claim.
        covered = set()
        for r in state["reuse"]:
            try:
                tgt = (r.get("shot_id"), int(r.get("rep", 1)))
                srck = (r.get("source_shot_id"), int(r.get("source_rep", 1)))
            except (TypeError, ValueError):
                continue
            if tgt == srck:
                continue                       # a frame is not its own source
            src_cap = state["captures"].get(srck)
            tgt_cap = state["captures"].get(tgt)
            tgt_qa = state["qa"].get(tgt)
            if not src_cap or not tgt_cap:
                continue
            if not src_cap.get("sha256") or src_cap["sha256"] != tgt_cap.get("sha256"):
                continue
            if r.get("sha256") and r["sha256"] != src_cap["sha256"]:
                continue
            if not tgt_qa or tgt_qa.get("capture_sha256") != src_cap["sha256"] \
                    or tgt_qa.get("outcome") != QA.PASS:
                continue
            covered.add(frozenset((tgt, srck)))
        by_sha = {}
        for key, c in sorted(state["captures"].items()):
            sha = c.get("sha256")
            if not sha:
                continue
            by_sha.setdefault(sha, []).append(key)
        dupes = {}
        for sha, ks in by_sha.items():
            if len(ks) < 2:
                continue
            # Every pair sharing these bytes must be covered by a declaration of its own.
            uncovered = [(a, b) for i, a in enumerate(ks) for b in ks[i + 1:]
                         if frozenset((a, b)) not in covered]
            if uncovered:
                dupes[sha] = ks
        if dupes:
            eg = []
            for sha, ks in sorted(dupes.items())[:4]:
                eg.append("%s used for %s" % (sha[:12],
                                              ", ".join("%s r%d" % k for k in ks[:3])))
            return False, ("%d photograph(s) are filed under more than one shot without a recorded "
                           "reuse declaration" % len(dupes)), \
                   "one frame may satisfy a second shot only when every requirement of that shot " \
                   "passes on it and the reuse is recorded; otherwise capture the shot properly", \
                   {"duplicates": eg}
        return True, "no photograph satisfies two shots without a declared reuse", None, {}

    _guard(blocks, satisfied, "captures.no_undeclared_reuse", c_no_undeclared_reuse)

    # --- the cut itself -------------------------------------------------------------------
    if gate_id in ("ready_to_wash", "ready_to_finalize"):
        def c_offcuts():
            from . import offcut as OFF
            gid = garment_dir.name
            want = {"%s_OFFCUT_L" % gid, "%s_OFFCUT_R" % gid}
            oc = state["offcuts"]
            # Identity first. Everything below keys off the label, which is free text, so two
            # records labelled ..._OFFCUT_L and ..._OFFCUT_L2 were two samples as far as the count
            # was concerned and one leg as far as the experiment was concerned.
            if set(oc) != want:
                return False, ("the offcut records are %s; this garment's two samples are %s"
                               % (", ".join(sorted(oc)) or "none", ", ".join(sorted(want)))), \
                       "run `pilot.py offcut plan --assign auto`, which writes both labels", \
                       {"have": sorted(oc), "want": sorted(want)}
            legs = {str(v.get("originating_leg", ""))[:1].lower() for v in oc.values()}
            if legs != {"l", "r"}:
                return False, ("both offcut records name the same leg (%s); they are two samples "
                               "from two legs" % ", ".join(sorted(legs))), \
                       "correct the originating_leg on the offcut records", {"legs": sorted(legs)}
            assigned = [v for v in oc.values() if v.get("assigned_wash_condition")]
            if len(assigned) < 2:
                return False, "both offcuts must have a wash condition assigned before the wash", \
                       "run `pilot.py offcut plan --assign auto`", {}
            unknown = [v.get("assigned_wash_condition") for v in assigned
                       if OFF.classify(v.get("assigned_wash_condition")) is None]
            if unknown:
                return False, ("an offcut is assigned a condition this protocol does not define: "
                               "%s" % ", ".join(repr(u) for u in unknown[:3])), \
                       "the conditions are %s" % ", ".join(OFF.CONDITIONS), {"unknown": unknown}
            # Distinctness over the ASSIGNED records only. Built over every record, one bare extra
            # entry with no condition put a None into the set and made two identical conditions
            # look like two.
            standard = [v for v in assigned
                        if OFF.classify(v["assigned_wash_condition"]) == "standard"]
            if len(standard) != 1:
                # Distinct is not enough. PROTOCOL.md 7 is specific: ONE offcut follows the standard
                # protocol in the same load as the garment. Two distinct non-standard conditions
                # are two samples and no control.
                return False, ("%d of the two offcuts follow the standard protocol; exactly one "
                               "must" % len(standard)), \
                       "one offcut goes in with the garment under the standard protocol and the " \
                       "other into a separate load; `pilot.py offcut plan --assign auto` writes " \
                       "that pair", {"conditions": sorted(v["assigned_wash_condition"]
                                                          for v in assigned)}
            conds = {v["assigned_wash_condition"] for v in assigned}
            if len(conds) < 2:
                return False, ("both offcuts are assigned the same condition (%s), so the pair "
                               "measures nothing" % ", ".join(sorted(conds))), \
                       "the two offcuts exist to be washed differently; re-assign", \
                       {"conditions": sorted(conds)}
            wa_ = state["wash_actual"]
            if wa_ and wa_.get("seq") is not None:
                late = [lbl for lbl, v in oc.items()
                        if (v.get("_seq") or {}).get("assigned_wash_condition") is not None
                        and int((v["_seq"])["assigned_wash_condition"]) > int(wa_["seq"])]
                if late:
                    return False, ("the wash condition for %s was assigned AFTER the wash was "
                                   "recorded" % ", ".join(sorted(late))), \
                           "the assignment decides which offcut goes into the garment's load and " \
                           "keeps the left/right alternation unconfounded; recorded afterwards it " \
                           "decides nothing", {"late": sorted(late)}
            alt = OFF.check_alternation(garment_dir.parent)
            if alt.get("unclassified"):
                return False, ("%d sibling garment(s) record an offcut condition this code cannot "
                               "classify, so whether the alternation holds is unknown: %s"
                               % (len(alt["unclassified"]),
                                  ", ".join(u["garment_id"] for u in alt["unclassified"][:3]))), \
                       ("record those conditions in the protocol's vocabulary (%s)"
                        % ", ".join(OFF.CONDITIONS)), {"unclassified": alt["unclassified"][:3]}
            if not alt["alternating"]:
                excused = deviation_covers(state["deviations"], "offcut_alternation",
                                           "".join(alt["sequence"]))
                if not excused:
                    return False, ("the left/right alternation is broken across garments (%s): leg "
                                   "and wash condition are confounded"
                                   % "".join(alt["sequence"])), \
                           "PROTOCOL.md 7 alternates which leg goes in with the garment; if it " \
                           "cannot be fixed, record it deliberately as a deviation of kind " \
                           "'offcut_alternation'", {"breaks": alt["breaks"][:3]}
                return True, ("the alternation is broken (%s) and the departure is recorded as a "
                              "deviation" % "".join(alt["sequence"])), None, \
                       {"breaks": alt["breaks"][:3]}
            return True, "two offcuts, two legs, two conditions, alternation intact (%s)" % \
                   "".join(alt["sequence"]), None, {}

        _guard(blocks, satisfied, "offcuts.assigned", c_offcuts)

        def c_wash_planned():
            wp = state["wash_planned"]
            if not wp:
                return False, "no wash has been planned", \
                       "run `pilot.py wash <GARMENT>` before the load goes in", {}
            missing = [k for k in WASH_FIELDS if wp.get(k) in (None, "")]
            if missing:
                return False, "the wash plan is missing %s" % ", ".join(missing[:6]), \
                       "re-record the plan with every field", {"missing": missing}
            wa_ = state["wash_actual"]
            if wa_ and wp.get("seq") is not None and wa_.get("seq") is not None \
                    and int(wp["seq"]) > int(wa_["seq"]):
                return False, ("the wash plan was written AFTER the wash it is supposed to have "
                               "planned, so the two collapse and every deviation computes to "
                               "nothing"), \
                       "the plan is what the actual settings are measured against; it has to " \
                       "exist before them", {"plan_seq": wp.get("seq"), "actual_seq": wa_.get("seq")}
            # The block used to be unescapable, and its own fix text named a remedy that did not
            # work: recording the deviation it asked for changed nothing, and there is no other way
            # out because the log is append-only. An operator who re-ran one command had bricked the
            # garment. The FIRST plan still stands -- that is the point -- but a deviation naming
            # the rewrite acknowledges it, exactly as the sentence promised.
            if state["wash_plan_rewrites"]:
                ack = deviation_covers(state["deviations"], "wash", "wash_plan_rewritten")
                if ack is None:
                    return False, ("the wash plan was written %d more time(s) after the first; the "
                                   "planned settings are what the deviation is measured against and "
                                   "cannot be revised to match what happened"
                                   % len(state["wash_plan_rewrites"])), \
                           ("the first plan stands. Acknowledge the rewrite and it will be kept "
                            "visible rather than applied:\n"
                            "  tools/pilot.py deviation <ID> --kind wash "
                            "--field wash_plan_rewritten --reason '<what happened>'"), \
                           {"rewrites": [r["seq"] for r in state["wash_plan_rewrites"]][:5]}
            return True, "wash planned: %s, %s" % (wp.get("machine"), wp.get("cycle")), None, {}

        _guard(blocks, satisfied, "wash.planned", c_wash_planned)

        def c_cut_performed():
            """PROTOCOL 3.1: "Record both inseam and outseam lengths after cutting."

            Nothing enforced it. The gate required the cut to be SPECIFIED and verified before the
            cut, and the wash to be planned -- and then let the garment into the machine without
            ever asking what the cut actually achieved. That number is the ground truth the whole
            prediction is scored against, it can only be taken between the shears and the water,
            and after the wash it is gone: the garment has shrunk, and the length you measure is no
            longer the length you cut.
            """
            cp = state.get("cut_performed")
            if not cp:
                return False, "the cut itself was never recorded", \
                       ("record what the cut achieved, before the garment is washed:\n"
                        "  tools/pilot.py cut-performed <ID> --inseam-l N --inseam-r N "
                        "--outseam-l N --outseam-r N --tool '<shears>' --legs-separately y/n"), {}
            missing = []
            for side in ("L", "R"):
                for field, label in (("achieved_inseam_cm", "inseam"),
                                     ("achieved_outseam_cm", "outseam")):
                    v = (cp.get(field) or {}).get(side)
                    if v is None:
                        missing.append("%s %s" % (label, side))
                        continue
                    try:
                        f = float(v)
                    except (TypeError, ValueError):
                        missing.append("%s %s (not a number: %r)" % (label, side, v))
                        continue
                    if not math.isfinite(f) or not (10.0 <= f <= 130.0):
                        missing.append("%s %s = %r, outside a plausible cut length" % (label, side, v))
            if not cp.get("tool"):
                missing.append("the cutting tool")
            if cp.get("legs_cut_separately") is None:
                missing.append("whether the legs were cut separately (PROTOCOL 3.4 says they are)")
            if missing:
                return False, "the record of the cut is incomplete: %s" % "; ".join(missing[:6]), \
                       "re-run `pilot.py cut-performed` with every field", {"missing": missing}
            if state.get("cut_performed_rewrites"):
                ack = deviation_covers(state["deviations"], "protocol", "cut_performed_rewritten")
                if ack is None:
                    return False, ("the cut was recorded %d more time(s) after the first, and the "
                                   "accounts differ. The first stands"
                                   % len(state["cut_performed_rewrites"])), \
                           ("acknowledge it:\n  tools/pilot.py deviation <ID> --kind protocol "
                            "--field cut_performed_rewritten --reason '<which account is right>'"), \
                           {"rewrites": [r["seq"] for r in state["cut_performed_rewrites"]][:5]}
            return True, "the cut is recorded: inseam %s, outseam %s, tool %r" % (
                cp.get("achieved_inseam_cm"), cp.get("achieved_outseam_cm"), cp.get("tool")), None, {}

        _guard(blocks, satisfied, "cut.performed_recorded", c_cut_performed)

    if gate_id == "ready_to_finalize":
        def c_wash_actual():
            """The wash actually happened, and its deviations from the plan are recorded.

            ready_to_finalize differed from ready_to_wash by one state and added no condition of its
            own, so a garment could be photographed after washing with no record that it had been
            washed, under what settings, or how far those departed from the plan. The whole
            experiment is one wash.
            """
            wa, wp = state["wash_actual"], state["wash_planned"]
            if not wa:
                return False, "no actual wash settings were recorded", \
                       "run `pilot.py wash <GARMENT> --actual` with what really happened", {}
            missing = [k for k in WASH_FIELDS if wa.get(k) in (None, "")]
            if missing:
                return False, "the actual wash record is missing %s" % ", ".join(missing[:6]), \
                       "re-record it with every field", {"missing": missing}
            # A second recording of the ACTUAL wash is kept but was never read, so a contradictory
            # account of what the machine did sat in the log with nothing reporting it. First-write
            # still wins -- that is what makes a correction visible -- but the gate has to say so.
            if state.get("wash_actual_rewrites"):
                ack = deviation_covers(state["deviations"], "wash", "wash_actual_rewritten")
                if ack is None:
                    return False, ("what the machine did was recorded %d more time(s) after the "
                                   "first, and the accounts differ. The first stands; the later "
                                   "ones are not applied and not ignored"
                                   % len(state["wash_actual_rewrites"])), \
                           ("acknowledge it so the disagreement stays in the record:\n"
                            "  tools/pilot.py deviation <ID> --kind wash "
                            "--field wash_actual_rewritten --reason '<which account is right, and "
                            "why the first was wrong>'"), \
                           {"rewrites": [r["seq"] for r in state["wash_actual_rewrites"]][:5]}
            from .store import diff_planned_actual
            devs = diff_planned_actual(wp, wa)

            def _same(a, b):
                if isinstance(a, float) or isinstance(b, float):
                    try:
                        return abs(float(a) - float(b)) < 1e-9
                    except (TypeError, ValueError):
                        return False
                return a == b

            # A deviation has to DESCRIBE the departure, not merely name the field. Matching on the
            # field alone meant pre-registering all fifteen field names before the wash excused
            # whatever happened afterwards.
            unrecorded = []
            for d in devs:
                if not any(x.get("kind") == "wash" and x.get("field") == d["field"]
                           and _same(x.get("planned"), d["planned"])
                           and _same(x.get("actual"), d["actual"])
                           for x in state["deviations"]):
                    unrecorded.append("%s (%s -> %s)" % (d["field"], d["planned"], d["actual"]))
            if unrecorded:
                return False, ("%d wash setting(s) departed from the plan without a deviation "
                               "that describes the departure: %s"
                               % (len(unrecorded), "; ".join(unrecorded[:5]))), \
                       "record each departure with what was planned and what happened; a " \
                       "deviation that only names the field excuses any value", \
                       {"unrecorded": unrecorded}
            return True, "wash recorded, %d deviation(s) from the plan, all recorded" % len(devs), \
                   None, {"deviations": [d["field"] for d in devs]}

        _guard(blocks, satisfied, "wash.actual", c_wash_actual)

        def c_post_wash_measurements():
            """The garment was measured again after the wash.

            `measurements.complete` runs for every gate, so finalize appeared to check this -- but
            it reads the PRE-MODIFICATION bucket, and before measurements were bucketed by state it
            read whatever had been written last. A post-wash re-measurement therefore satisfied the
            finalize gate by overwriting the pre-cut value it was supposed to be compared WITH, and
            the shrinkage the wash exists to measure became uncomputable at the moment it was
            recorded. Now the two live in different buckets and finalize asks for both.
            """
            from .store import mean_of
            post = (state.get("measurements_by_state") or {}).get("post_wash") or {}
            pre = state.get("measurements") or {}
            missing, thin, nopair, implausible, inconsistent = [], [], [], [], []
            for name, n_required in sorted(POST_WASH_MEASUREMENTS.items()):
                m = post.get(name)
                if not m:
                    missing.append(name)
                    continue
                readings = [r for r in (m.get("readings") or []) if r is not None]
                if len(readings) < n_required:
                    thin.append("%s (%d of %d readings)" % (name, len(readings), n_required))
                    continue
                # The SAME arithmetic the pre-cut set gets. This condition checked only that the
                # numbers were present, so a post-wash tape read in inches -- two readings agreeing
                # perfectly and 2.5x wrong, the exact case measurements.complete names in its own
                # message -- finalised the experiment and published a 60% shrinkage.
                if any(not isinstance(r, (int, float)) or not math.isfinite(float(r))
                       for r in readings):
                    implausible.append("%s (a reading is not a finite number)" % name)
                    continue
                lo, hi = MEASUREMENT_RANGE.get(name, (None, None))
                mean = sum(readings) / len(readings)
                if lo is not None and not (lo <= mean <= hi):
                    implausible.append("%s = %.2f, outside the plausible %.0f-%.0f" % (name, mean, lo, hi))
                    continue
                tol = MEASUREMENT_TOLERANCE.get(name, MEASUREMENT_TOLERANCE["_default_cm"])
                if max(readings) - min(readings) > tol:
                    inconsistent.append("%s (readings differ by %.2f, tolerance %.2f)"
                                        % (name, max(readings) - min(readings), tol))
                    continue
                if not pre.get(name):
                    nopair.append(name)
                # DELIBERATELY no plausibility band on the shrinkage itself. A band was written
                # here and removed: no source in this repository supports one. docs/LITERATURE.md
                # entry 14 is the only verified measurement of denim shrinkage, it reports 0.04% to
                # 5.0% for INDUSTRIAL ROPE-WASHING OF FABRIC ROLLS, and the same entry says it does
                # not transfer to one home cycle on a made-up garment -- "our shrinkage parameters
                # therefore remain unsupported priors". Refusing a reading for falling outside an
                # invented range would also be backwards: the shrinkage is the RESULT, and a gate
                # that rejects surprising results is not a check on the measurement, it is a filter
                # on the finding. What is checked above is the measurement's own quality -- finite
                # numbers, a plausible adult-garment dimension, two readings that agree -- which is
                # the same arithmetic the pre-cut set gets and rests on nothing new.
            if implausible and deviation_covers(state["deviations"], "protocol",
                                                "post_wash_out_of_range") is not None:
                # A small garment that shrinks can put an HONEST reading below a band whose floor
                # was set for whole adult jeans, and this condition had no escape -- the remedy it
                # printed re-recorded the same number. The band still catches a tape read in
                # inches; it must not strand a true measurement, for the reason the shrinkage band
                # was removed for: a gate that rejects surprising results filters the finding.
                implausible = []
            if missing or thin or nopair or implausible or inconsistent:
                parts = []
                if implausible:
                    parts.append("%d outside a plausible range (%s)"
                                 % (len(implausible), "; ".join(implausible)))
                if inconsistent:
                    parts.append("%d whose readings disagree (%s)"
                                 % (len(inconsistent), "; ".join(inconsistent)))
                if missing:
                    parts.append("%d not re-measured after the wash (%s)"
                                 % (len(missing), ", ".join(missing)))
                if thin:
                    parts.append("%d with too few readings (%s)" % (len(thin), "; ".join(thin)))
                if nopair:
                    parts.append("%d have no pre-cut value to compare with, so no shrinkage can be "
                                 "computed from them (%s)" % (len(nopair), ", ".join(nopair)))
                return False, "post-wash dimensions incomplete: " + "; ".join(parts), \
                       ("measure the washed garment on the same rig and record it:\n"
                        "  tools/pilot.py measure %s --state post_wash\n"
                        "If a reading is outside the band and CORRECT -- a small garment that "
                        "shrank below a floor set for whole adult jeans -- say so:\n"
                        "  tools/pilot.py deviation %s --kind protocol --field "
                        "post_wash_out_of_range --reason '<the reading and why it is right>'"
                        % (state["garment_id"], state["garment_id"])), \
                       {"missing": missing, "thin": thin, "unpaired": nopair,
                        "implausible": implausible, "inconsistent": inconsistent}
            shrink = {}
            for name in sorted(POST_WASH_MEASUREMENTS):
                a, b = mean_of(pre.get(name)), mean_of(post.get(name))
                if a and b:
                    shrink[name] = round(100.0 * (a - b) / a, 2)
            return True, "post-wash dimensions recorded for %d dimension(s); shrinkage computable" \
                   % len(POST_WASH_MEASUREMENTS), None, {"shrinkage_percent": shrink}

        _guard(blocks, satisfied, "measurements.post_wash", c_post_wash_measurements)

    if gate_id == "ready_to_cut":
        def c_not_already_cut():
            """The cut gate answers a question about the future. Once the cut is recorded it is not.

            No condition read the log's own order against the irreversible step, although the same
            file applies exactly that discipline to the wash: c_wash_planned refuses a plan written
            after the wash, and c_offcuts refuses an assignment written after it. The cut -- the more
            irreversible of the two -- had none. So a session in which the legs were cut first and
            photographed afterwards produced a fully green, fully hash-chained record that no reader
            could tell from a compliant one, and the honest failure it hides is worse than the
            dishonest one: a before-frame rejected by QA and noticed after the cut is a retake
            nobody can take, and nothing said so.
            """
            cp = state.get("cut_performed")
            if not cp:
                return True, "the cut has not been recorded, so this gate is still a question " \
                             "about the future", None, {}
            cut_seq = cp.get("seq")
            late = sorted(("%s r%s" % (sid, rep))
                          for (sid, rep), c in state["captures"].items()
                          if cut_seq is not None and (c.get("seq") or -1) > cut_seq
                          and str(c.get("state")) in ("before", "marked", "intake"))
            detail = {"cut_seq": cut_seq, "later_pre_cut_captures": late[:8]}
            if late:
                return False, ("this garment has already been cut (recorded at entry %s), and %d "
                               "pre-cut photograph(s) were filed after it. A photograph of the "
                               "uncut garment cannot have been taken after it was cut"
                               % (cut_seq, len(late))), \
                       ("nothing here can be re-taken. Record what happened as a deviation and "
                        "treat the affected frames as absent:\n"
                        "  tools/pilot.py deviation %s --kind protocol --field cut_order "
                        "--reason '<what happened>'" % state["garment_id"]), detail
            return False, "this garment has already been cut (recorded at entry %s); the cut gate " \
                          "cannot authorise it again" % cut_seq, \
                   "the next gate is `pilot.py gate %s ready_to_wash`" % state["garment_id"], detail

        _guard(blocks, satisfied, "cut.not_already_performed", c_not_already_cut)
        def c_cut_spec():
            cs = state["cut_spec"]
            if not cs:
                return False, "no cut has been specified", \
                       "run `pilot.py cutspec` to define the target inseam and generate the " \
                       "digital cut line and its predicted outseam offset", {}
            need = ("target_inseam_cm", "predicted_outseam_cm", "cut_path_frame", "cut_angle_deg")
            gaps = [k for k in need if cs.get(k) is None]
            if gaps:
                return False, "the cut specification is missing %s" % ", ".join(gaps), \
                       "re-run `pilot.py cutspec`", {"missing": gaps}
            # The cut line is DERIVED from three measurements, and cutspec.compute records which
            # values it used in `inputs` -- the one dependency edge anywhere in this system. Nothing
            # compared it with the measurements afterwards. So the ordinary, careful sequence --
            # measure, specify the cut, mark the garment, have a second person verify, then re-lay
            # the tape, find the first thigh reading was wrong and record the correction the tool
            # asks for -- left the measurements saying one thing and the cut line computed from
            # another, with the gate clean. The second-person check could not catch it either: it
            # compares the tape against the SAME stale specification, so the two agree perfectly.
            # The garment is then cut in the wrong place, by a gate that said READY.
            from .store import mean_of
            if not (cs.get("inputs") or {}):
                # The drift check below is the only thing tying the cut line to the measurements it
                # came from, and it did nothing at all when the specification recorded no inputs.
                return False, ("the cut specification does not record the measurements it was "
                               "computed from, so it cannot be checked against them"), \
                       "re-run `pilot.py cutspec`, which records its inputs", {}
            # Compared at the precision the value is STORED at. cutspec.compute rounds its inputs
            # to 3 decimals, so a comparison at 1e-6 could fire on a difference the record does not
            # contain -- and the message, printing 2 decimals, then showed the operator two
            # identical numbers and asked them to explain the difference. A cut line is transferred
            # to cloth with a tape; a micrometre of float noise is not a drifted measurement.
            drifted = []
            for name, was in sorted((cs.get("inputs") or {}).items()):
                now = mean_of(state["measurements"].get(name))
                if now is None:
                    drifted.append("%s is no longer recorded (the cut used %s)" % (name, was))
                elif round(float(now), 3) != round(float(was), 3):
                    drifted.append("%s: the cut was computed from %.3f, the record now says %.3f"
                                   % (name, float(was), float(now)))
            if drifted:
                return False, ("the cut line was computed from measurements that have since "
                               "changed: %s" % "; ".join(drifted)), \
                       ("re-run `pilot.py cutspec` so the line is derived from the numbers now on "
                        "record, then have the marks verified again -- the second-person check "
                        "compares the tape against the specification, so it agrees with a stale "
                        "one"), {"drifted": drifted, "inputs": cs.get("inputs")}
            # The cut geometry can carry a warning: the cut lands so close to the crotch that the
            # straight-perpendicular model stops describing a real inseam. Nothing read it, so the
            # one cut the tool says it cannot predict passed as silently as any other. It does not
            # block -- the operator is allowed to cut there -- but they have to say they meant to,
            # and the record has to show they were told.
            # RE-DERIVED, not read. The warning is a field supplied by the record this condition
            # exists to constrain, so an appended cut_spec that simply omits it acknowledged nothing
            # and was asked for nothing. The rule is one comparison and the gate is already holding
            # the number.
            try:
                from .cutspec import CROTCH_EXCLUSION_CM
                warn_now = float(cs["target_inseam_cm"]) < CROTCH_EXCLUSION_CM
            except (TypeError, ValueError, KeyError):
                warn_now = True                # cannot tell: not permission
            if warn_now or cs.get("warning"):
                cs = dict(cs, warning=cs.get("warning") or (
                    "the cut is %.1f cm below the crotch seam, inside the region where a real "
                    "inseam curves and this flat-trapezoid model stops describing the garment"
                    % float(cs.get("target_inseam_cm") or 0.0)))
                ack = [rec for (sid, rep, claim), rec in state["verifications"].items()
                       if claim == "cut_out_of_model_acknowledged"]
                ack = max(ack, key=lambda r: (r.get("seq") if r.get("seq") is not None else -1)) \
                    if ack else None
                if ack is None or ack.get("value") is not True:
                    return False, ("the cut geometry carries a warning that nobody has "
                                   "acknowledged: %s" % cs["warning"]), \
                           ("either move the cut, or record that you read the warning and meant "
                            "it:\n  tools/pilot.py confirm <ID> --claim "
                            "cut_out_of_model_acknowledged --operator <you>"), \
                           {"warning": cs["warning"]}
            return True, "cut specified: inseam %.1f cm, predicted outseam %.1f cm%s" % (
                float(cs["target_inseam_cm"]), float(cs["predicted_outseam_cm"]),
                " (out-of-model warning acknowledged)" if cs.get("warning") else ""), None, \
                {"cut_spec": {k: cs.get(k) for k in need}, "warning": cs.get("warning")}

        def c_second_person():
            # The LATEST record, by time. Selecting by dictionary iteration order meant a retraction
            # appended after an approval could be discarded in favour of the approval.
            cands = [rec for (sid, rep, claim), rec in state["verifications"].items()
                     if claim == "cut_marks_verified"]
            # By log POSITION. `ts` comes from the payload on any path that sets it, so ordering by
            # it let a future-dated approval outrank a real retraction appended after it.
            v = max(cands, key=lambda r: (r.get("seq") if r.get("seq") is not None else -1)) \
                if cands else None
            if v is not None and v.get("value") is not True:
                # `value` was never read here, so a recorded REFUSAL -- a second person writing
                # "no, the marks are on the wrong leg" -- was reported as an approval.
                return False, ("the second person did not approve the marks: %s"
                               % (v.get("note") or "recorded as not verified")), \
                       "re-mark the garment and have it verified again", \
                       {"verifier": v.get("verifier_name"), "at": v.get("ts")}
            if not v:
                return False, "no second person has verified the cut marks", \
                       "a second person measures both marks with a tape and records the reading; " \
                       "PROTOCOL.md 3.2 requires it before cutting", {}
            # The approval has to be of THIS cut line. Re-running cutspec after a corrected
            # measurement writes a new specification at a later entry, and an approval recorded
            # against the old one must not carry over: the marks it checked are on the garment in
            # a different place.
            cs_seq = (state.get("cut_spec") or {}).get("seq")
            if cs_seq is not None and (v.get("seq") or -1) < cs_seq:
                return False, ("the marks were verified at entry %s, before the cut line now on "
                               "record was computed at entry %s. That approval was given to a "
                               "different line" % (v.get("seq"), cs_seq)), \
                       "re-mark the garment from the current specification and have it verified " \
                       "again", {"verification_seq": v.get("seq"), "cut_spec_seq": cs_seq}
            for k in ("verifier_name", "measured_inseam_cm", "measured_outseam_cm"):
                if not v.get(k):
                    return False, "the second-person verification is missing %s" % k, \
                           "re-record the verification with all fields", {"have": sorted(v.keys())}
            if not (v.get("operator") or "").strip() or not (v.get("verifier_name") or "").strip():
                return False, ("the cut-mark verification does not name both the operator and the "
                               "person who verified"), \
                       "re-record it with --verifier NAME; a verification with no attribution is " \
                       "not one", {"operator": v.get("operator"),
                                   "verifier": v.get("verifier_name")}
            if (v.get("verifier_name") or "").strip().lower() == \
                    (v.get("operator") or "").strip().lower():
                # PROTOCOL.md 3.2 asks for a SECOND person. verifier_name defaults to the operator
                # when --verifier is omitted, which is the natural thing to do when one person is at
                # the table -- and then the check was one person agreeing with themselves.
                return False, ("the cut marks were verified by %r, who is the operator; the "
                               "protocol requires a second person"
                               % v.get("verifier_name")), \
                       "have someone else measure both marks and record it with --verifier NAME", \
                       {"operator": v.get("operator")}
            cs = state["cut_spec"] or {}
            errs = {}
            for field, target in (("measured_inseam_cm", cs.get("target_inseam_cm")),
                                  ("measured_outseam_cm", cs.get("predicted_outseam_cm"))):
                if target is None:
                    return False, "cannot check the verification against a cut spec that is absent", \
                           "run `pilot.py cutspec` first", {}
                try:
                    got = float(v[field])
                except (TypeError, ValueError):
                    return False, "the verification's %s is not a number" % field, \
                           "re-record the verification", {"value": v.get(field)}
                if not math.isfinite(got) or not math.isfinite(float(target)):
                    # NaN compares false against everything, so a NaN reading slipped past
                    # `worst > tolerance` and disabled the 3 mm tolerance entirely.
                    return False, ("the verification's %s is not a finite measurement (%r), so the "
                                   "%.0f mm tolerance cannot be applied to it"
                                   % (field, v.get(field), CUT_MARK_TOLERANCE_MM)), \
                           "re-measure and record a real number", {"value": v.get(field)}
                errs[field] = abs(got - float(target)) * 10.0     # cm -> mm
            worst = max(errs.values())
            if not math.isfinite(worst) or worst > CUT_MARK_TOLERANCE_MM:
                return False, ("the second person's measurements differ from the specified cut by "
                               "%.1f mm, beyond the %.1f mm tolerance"
                               % (worst, CUT_MARK_TOLERANCE_MM)), \
                       "re-mark the garment and verify again", {"errors_mm": errs}
            return True, "%s verified both marks within %.1f mm" % (v["verifier_name"], worst), \
                   None, {"errors_mm": errs, "verifier": v["verifier_name"], "at": v.get("ts")}

        def c_cut_confirmations():
            need = {"legs_cut_separately": "confirm the legs will be cut one at a time",
                    "offcuts_retained_labelled": "confirm both offcuts will be kept and labelled "
                                                 "<GARMENT>_OFFCUT_L / _R"}
            # These have to be made about a cut that has been specified. _human_resolved binds a
            # per-frame HUMAN claim to the photograph's own sha256 AND to a seq after it, and its
            # docstring gives the reason: otherwise "every claim the plan could ever raise could be
            # confirmed in a loop before a single photograph existed, and each frame arrived
            # pre-cleared". That reasoning was applied to per-frame claims and to none of the three
            # that actually authorise the shears. A confirmation written before the cut line existed
            # is a confirmation of nothing, and re-running cutspec after one has to invalidate it --
            # otherwise a corrected cut line inherits the approval given to the line it replaced.
            cs_seq = (state.get("cut_spec") or {}).get("seq")
            missing, premature = [], []
            for claim, how in need.items():
                recs = [rec for (_, _, c), rec in state["verifications"].items() if c == claim]
                latest = max(recs, key=lambda r: (r.get("seq") if r.get("seq") is not None else -1)) \
                    if recs else None
                if latest is None or latest.get("value") is not True:
                    missing.append((claim, how))
                    continue
                if cs_seq is not None and (latest.get("seq") or -1) < cs_seq:
                    premature.append("%s (recorded at entry %s, before the cut line at entry %s)"
                                     % (claim, latest.get("seq"), cs_seq))
            if missing:
                return False, "%d cut-day confirmation(s) not recorded: %s" % (
                    len(missing), ", ".join(c for c, _ in missing)), \
                    "; ".join(h for _, h in missing), {"missing": [c for c, _ in missing]}
            if premature:
                return False, ("%d cut-day confirmation(s) predate the cut they authorise: %s"
                               % (len(premature), "; ".join(premature))), \
                       ("confirm them again, now that the cut line they refer to exists:\n"
                        "  tools/pilot.py confirm %s --claim <claim> --value y"
                        % state["garment_id"]), {"premature": premature}
            return True, "cut-day confirmations recorded, after the cut line they authorise", \
                   None, {"cut_spec_seq": cs_seq}

        _guard(blocks, satisfied, "cut.specified", c_cut_spec)
        _guard(blocks, satisfied, "cut.second_person_verified", c_second_person)
        _guard(blocks, satisfied, "cut.confirmations", c_cut_confirmations)

    ev = {"n_captures": len(state["captures"]), "n_required": None,
          "features": len(state["features"]), "states_covered": list(states),
          "deviations": len(state["deviations"])}
    if activated is not None:
        ev["n_required"] = sum(int(s.get("min_reps", 1)) for s in activated
                               if s["state"] in states and s["necessity"] != "optional")
    return Verdict(gate_id, blocks, satisfied, ev)


#: Re-hashing every photograph on every screen refresh is wasteful and skipping the check is not
#: acceptable, so the result is cached on the file's identity. The first version keyed the cache on
#: (path, size, mtime) and asserted that a file whose size and mtime were unchanged had not been
#: rewritten -- which is false, because mtime is settable. Replacing a photograph and restoring its
#: mtime with os.utime defeated it for as long as a `serve` process stayed up, and a capture UI is
#: exactly a long-running process.
#:
#: The key now includes the inode and ctime. ctime is the inode's own change time and cannot be set
#: through utime; rewriting the file's contents moves it whatever is done to mtime. That is not a
#: cryptographic guarantee -- a process with enough privilege can do more than utime -- but it
#: closes the gap that an ordinary write leaves open, and `--recheck` re-hashes everything.
_HASH_CACHE = {}


def _hash_changed(path, want, use_cache=True):
    from .manifest import sha256_file
    try:
        st = os.stat(str(path))
    except OSError:
        return True
    # Not a regular file is "changed", never "read it and find out": reading a FIFO blocks forever
    # and the gate never answers at all.
    import stat as _stat
    if not _stat.S_ISREG(st.st_mode):
        return True
    key = (str(path), st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns)
    got = _HASH_CACHE.get(key) if use_cache else None
    if got is None:
        got = sha256_file(path)
        if use_cache:
            _HASH_CACHE[key] = got
    return got != want


def _human_resolved(state, shot_id, rep, qa_record, capture=None):
    """A HUMAN outcome counts only when every claim it raised has a verification OF THIS PHOTOGRAPH.

    Three things were wrong with resolving a claim by name alone, and each was a false READY:

    * The verification was not bound to the frame. Re-ingesting a different photograph under the
      same shot id left the old confirmation in place, so a frame of the back of the garment
      inherited a confirmation that the front was facing up.
    * It was not bound in TIME either, so every claim the plan could ever raise could be confirmed
      in a loop before a single photograph existed, and each frame arrived pre-cleared.
    * A recorded refusal counted the same as an approval wherever `value` was not read.

    So a verification clears a claim only when it names the capture's own hash, or -- for records
    written before that field existed -- was made after the photograph it is about.
    """
    claims = [c.get("check_id") for c in (qa_record.get("checks") or [])
              if c.get("outcome") == QA.HUMAN]
    if not claims:
        return False
    cap_sha = (capture or {}).get("sha256")
    cap_seq = (capture or {}).get("seq")
    for claim in claims:
        rec = state["verifications"].get((shot_id, rep, claim))
        if not rec or rec.get("value") is not True or not rec.get("operator"):
            return False
        # Both, not either. The OR was the hole: a verification carrying a sha that no capture had
        # yet -- the API takes capture_sha256 straight from the client -- satisfied the first branch
        # and never reached the second, so every claim could still be pre-cleared before the
        # photograph existed. And the ordering is log POSITION, because the payload's clock is
        # writable while the sequence number is stamped by the appender.
        if not cap_sha or rec.get("capture_sha256") != cap_sha:
            return False
        if cap_seq is not None and rec.get("seq") is not None \
                and int(rec["seq"]) < int(cap_seq):
            return False
    return True

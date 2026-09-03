"""One log per garment, and every view of the session derived from it.

The alternative -- a session.json holding current state, a manifest holding captures, a
measurements.json holding numbers -- has a failure mode that this project cannot afford: the files
disagree, and nothing says which one is right. A gate reading the wrong one passes a garment that
should have been blocked, and the garment gets cut.

So there is one append-only log, and everything else is a projection of it. `fold()` replays the log
into the state the session is in. That makes three properties fall out rather than having to be
engineered:

  * RESUME is free. There is no separate state to reconcile after an interruption -- replaying the
    log is what the process does every time anyway, so a session that died mid-capture resumes into
    exactly the state its last durable entry describes.
  * TAMPER IS EVIDENT. Editing history to make a gate pass breaks the hash chain at the edited
    entry, and the chain is verified on every read.
  * PLANNED AND ACTUAL CANNOT COLLAPSE. A wash's actual settings are a new entry, not a mutation of
    the planned ones, so a deviation is computed by diffing two entries that both still exist. The
    protocol requires deviations to stay visible; an append-only log makes losing them impossible
    rather than merely discouraged.

Entry kinds are closed. An unknown kind in the log is surfaced rather than ignored, because a log
this process cannot fully interpret is not a log it should be gating a cut on.
"""
import copy
import time
from pathlib import Path

from .manifest import Manifest, canonical, sha256_text

#: The kinds of deviation the gates recognise. Two conditions told the operator to "record the
#: deviation deliberately" and no command or route could write one -- the remedy the message
#: promised was unreachable, so the only way past those conditions was a hand-edited log.
DEVIATION_KINDS = ("rig", "wash", "intake", "offcut_alternation", "protocol")

#: The lifecycle state a measurement belongs to when nothing has happened to the garment yet, and
#: the one `state["measurements"]` exposes. The other buckets are reached through
#: `measurements_by_state`, so a consumer that wants the post-wash waist has to say so.
PRE_MODIFICATION_STATE = "before"

#: How the lifecycle progresses. One authoritative ordering: the fold advances the garment through
#: it, and a measurement's declared state is compared against it. It was defined inside the
#: measurement branch, where the advance itself could not reach it -- which is how the advance came
#: to be a plain assignment that could move backwards.
LIFECYCLE_ORDER = {"rig": 0, "intake": 1, "before": 2, "marked": 3, "immediate_after": 4,
                   "offcut_before": 5, "post_wash": 6, "offcut_after": 7}


def _advance(current, to):
    """The lifecycle only ever moves forward. A cut and a wash are irreversible.

    `lifecycle = "immediate_after"` on the cut and `lifecycle = "post_wash"` on the wash meant the
    replay followed the ORDER THE ENTRIES WERE TYPED rather than the order the acts happened in.
    Record the wash and then remember to type the cut record afterwards -- which the runbook's own
    sequence invites, since `measurement_ahead_of_record` exists for exactly that habit -- and the
    garment went from post_wash back to immediate_after. Every measurement written after that with
    no explicit state then landed in a bucket no gate reads: `measurements.post_wash` reported that
    the washed garment had never been measured, while the readings sat in the log under
    `immediate_after`, and shrinkage was uncomputable from a record that contained both numbers.
    """
    if LIFECYCLE_ORDER.get(to, -1) > LIFECYCLE_ORDER.get(current, -1):
        return to
    return current


KINDS = (
    "session_opened",        # garment id, spec version and hash
    "setup_frozen",          # the rig configuration and its hash
    "setup_check",           # one rig calibration reading (square size, height, lens, backdrop...)
    "feature_answers",       # the intake questionnaire, whole or partial
    "measurement",           # one named measurement with its individual readings
    "capture",               # one photograph accepted into the tree
    "qa_result",             # the checks run against one capture
    "human_verification",    # a person asserting something a measurement cannot settle
    "reuse_declaration",     # one image satisfying a second shot id, with the reason it may
    "deviation",             # any departure from the frozen protocol
    "state_transition",      # before -> marked -> immediate_after -> post_wash
    "cut_spec",              # the digital cut definition and its prediction
    "cut_performed",         # the physical cut: what it ACHIEVED, per PROTOCOL 3.1
    "annotation",            # ONE physical instance of a counted feature, with a stable id
    "wash_planned", "wash_actual",
    "offcut",                # one offcut sample's identity and measurements
    "note",
)


class Rejected(Exception):
    """A conditional append abandoned because its condition no longer held once the lock was taken.

    Raised by `append_guarded`. A caller catching this is being told that another writer got there
    first -- not that anything is wrong with the log.
    """


class Store(object):
    def __init__(self, garment_dir):
        self.dir = Path(garment_dir)
        self.garment_id = self.dir.name
        self.pilot_dir = self.dir / "pilot"
        # The chain starts from THIS garment's identity, so a log copied from another garment fails
        # at its first entry instead of verifying perfectly and satisfying the gate for a garment
        # that was never photographed.
        # The witness sits BESIDE the garments, not inside this one. Re-chaining a log is easy --
        # the chain is keyless and its seed is public -- and rewriting the .head sidecar next to it
        # makes the forgery self-consistent. Nothing on one filesystem fixes that. What this catches
        # is the realistic version: an operator tidying up their own garment directory, who does not
        # know a second record exists one level up and shared with every other garment.
        self.manifest = Manifest(self.pilot_dir / "manifest.jsonl",
                                 seed=sha256_text("denim-twin/pilot/" + self.garment_id),
                                 witness=self.dir.parent / ".pilot_witness.jsonl")

    # -- writing ------------------------------------------------------------------------------

    def append(self, kind, payload, *, operator=None, setup_hash=None, now=None):
        if kind not in KINDS:
            raise ValueError("unknown log entry kind %r; the log's vocabulary is closed so that a "
                             "reader cannot silently ignore something it does not understand" % kind)
        return self.manifest.append(kind, payload, operator=operator, setup_hash=setup_hash,
                                    now=now)

    def append_many(self, items, *, operator=None):
        """Several entries written under one hold of the write lock, so nothing interleaves.

        `items` are dicts of kind/payload, optionally operator and setup_hash. Use it where the
        entries only mean anything as a group -- the rig freeze and the calibration readings taken
        against it are the case this exists for.
        """
        norm = []
        for it in items:
            kind = it["kind"]
            if kind not in KINDS:
                raise ValueError("unknown log entry kind %r" % kind)
            norm.append((kind, it["payload"], it.get("operator", operator), it.get("setup_hash")))
        return self.manifest.append_many(norm)

    def append_guarded(self, kind, payload, *, guard, operator=None, setup_hash=None, now=None):
        """append(), with `guard` re-run against a freshly folded state under the write lock.

        `guard(state)` returns None to write, or a sentence saying why this entry must not be
        written; that sentence becomes `Rejected`. Use it for every record the log accepts only
        once. Deciding from a fold taken before the call is not enough: the fold and the append are
        then two steps, and concurrent writers interleave between them. The wash's actual settings
        are the case that matters -- ThreadingHTTPServer, a phone retrying a timed-out POST, eight
        requests each told "saved" and seven discarded by a fold that keeps the first.

        The guard runs with the lock held, so it must only read.
        """
        def _recheck():
            state, _ = self.fold()
            why = guard(state)
            if why:
                raise Rejected(why)

        return self.manifest.append(kind, payload, operator=operator, setup_hash=setup_hash,
                                    now=now, precheck=_recheck)

    # -- reading ------------------------------------------------------------------------------

    @staticmethod
    def _key(v, what, seq, problems):
        """A projection key taken from a payload. Only a scalar can be one.

        fold() keyed four projections on values taken straight from the payload -- the setup check's
        name, the measurement's name, the offcut's label, the verification's claim -- and coerced
        two more with a bare int(). A JSON object or array in any of them raised inside the replay,
        and because every gate condition reads the folded state rather than the log, one such entry
        made the garment permanently ungateable: not a false pass, but no verdict at all, on a
        garment whose photographs were fine.
        """
        if isinstance(v, str) and v.strip():
            return v
        if isinstance(v, int) and not isinstance(v, bool):
            return v
        problems.append({"kind": "uninterpretable_payload", "seq": seq,
                         "detail": "the %s of entry %s is %r, which cannot identify anything"
                                   % (what, seq, v)})
        return None

    @staticmethod
    def _rep(v, seq, problems):
        try:
            if v is None:
                return 1
            r = int(v)
            if r < 1:
                raise ValueError(r)
            return r
        except (TypeError, ValueError):
            problems.append({"kind": "uninterpretable_payload", "seq": seq,
                             "detail": "entry %s has a repeat index of %r" % (seq, v)})
            return None

    def fold(self):
        """Replay the log. Returns a state dict plus the integrity problems found on the way.

        Total by construction: an entry this code cannot interpret becomes a PROBLEM, which
        `gates.log.intact` blocks on, rather than an exception that leaves the gate with nothing to
        say.
        """
        entries, problems = self.manifest.read()
        st = {
            "garment_id": self.dir.name,
            "spec_version": None, "spec_hash": None,
            "setup": None, "setup_hash": None, "setup_history": [],
            "setup_checks": {},
            "features": {}, "features_answered_at": None, "feature_changes": [],
            #: annotation_id -> the one physical thing it names. A count says a garment has three
            #: tears; it does not say which tear a photograph shows, and six months later that is
            #: the only question anyone asks of it. Each instanced frame is expanded FROM one of
            #: these and carries its id, so every photograph names the object it is of.
            "annotations": {},
            "annotation_revisions": [],
            #: The pre-modification measurements, which is what every gate, the plan sizing and
            #: the hem geometry mean by "the measurements". A VIEW onto measurements_by_state
            #: below; kept under this name because nine call sites read it and all nine want the
            #: before-cut values.
            "measurements": {},
            #: lifecycle state -> {name: measurement}. Measurements belong to a state: the waist
            #: before the cut and the waist after the wash are two different facts about two
            #: different physical objects, and shrinkage is the difference between them. Keyed flat
            #: on name alone, the post-wash reading OVERWROTE the pre-cut one, the finalize gate
            #: then re-read the survivor and passed, and the quantity the wash exists to measure
            #: could no longer be computed from anything the software reads.
            "measurements_by_state": {},
            #: Every write that replaced an earlier one within the SAME state. Re-measuring before
            #: the cut is legitimate; doing it invisibly is not.
            "measurement_revisions": [],
            #: Measurements whose declared state contradicts where the log says the garment was.
            #: A reading filed into a state EARLIER than the log has reached: a write back into
            #: the pre-cut baseline after the garment was cut. The gate refuses these outright.
            "measurement_backdated": [],
            #: A reading filed into a LATER state than the log has reached, which is the ordinary
            #: order of work: you measure the washed garment and type the wash record afterwards.
            "measurement_ahead_of_record": [],
            #: Where the garment had got to when each entry was written, replayed from the physical
            #: facts in the log itself rather than from a marker somebody has to remember to set.
            "lifecycle_state": "before",
            "cut_performed": None, "cut_performed_rewrites": [],
            "captures": {},          # (shot_id, rep) -> capture record
            "qa": {},                # (shot_id, rep) -> the qa record for the CURRENT capture
            "qa_all": {},            # (shot_id, rep) -> every qa record, in order
            "verifications": {},     # (shot_id, rep, claim) -> verification
            "reuse": [],
            "deviations": [],
            "state": None, "state_history": [],
            "cut_spec": None,
            "wash_planned": None, "wash_actual": None, "wash_plan_rewrites": [],
            "wash_actual_rewrites": [],
            "offcuts": {},
            "notes": [],
            "unknown_kinds": [],
            "n_entries": len(entries),
        }
        lifecycle = "before"
        for e in entries:
            k, p = e.get("kind"), e.get("payload")
            if p is None:
                p = {}
            if not isinstance(p, dict):
                # The payload is the whole content of an entry. A list or a string there is not
                # something this replay can interpret, and interpreting it wrongly is worse than
                # saying so.
                problems.append({"kind": "uninterpretable_payload", "seq": e.get("seq"),
                                 "detail": "entry %s carries a %s payload, not an object"
                                           % (e.get("seq"), type(p).__name__)})
                continue
            if k == "session_opened":
                st["spec_version"] = p.get("spec_version")
                st["spec_hash"] = p.get("spec_hash")
            elif k == "setup_frozen":
                st["setup"] = p.get("setup")
                st["setup_hash"] = p.get("setup_hash")
                st["setup_history"].append({"setup_hash": p.get("setup_hash"), "ts": e.get("ts"),
                                            "seq": e.get("seq"), "reason": p.get("reason"),
                                            "operator": _who(p, e)})
            elif k == "setup_check":
                key = self._key(p.get("check"), "check name", e.get("seq"), problems)
                if key is not None:
                    # The rig it was taken against travels with it, so a re-freeze cannot inherit
                    # the previous configuration's calibration.
                    st["setup_checks"][key] = dict(p, setup_hash=e.get("setup_hash"),
                                                   seq=e.get("seq"), operator=_who(p, e))
            elif k == "feature_answers":
                # The newest answer wins, and the earlier one stays visible. Merging silently meant
                # a later answer could delete the frames an earlier one required, with nothing to
                # look at afterwards: the log still held both and no condition could see it.
                prev = dict(st["features"])
                answers = p.get("answers") or {}
                for fk, fv in answers.items():
                    if fk in prev and prev[fk] != fv:
                        st["feature_changes"].append(
                            {"key": fk, "was": prev[fk], "now": fv, "seq": e.get("seq")})
                st["features"].update(answers)
                st["features_answered_at"] = e.get("ts")
            elif k == "annotation":
                aid = self._key(p.get("annotation_id"), "annotation id", e.get("seq"), problems)
                if aid is not None:
                    first_seq = e.get("seq")
                    if aid in st["annotations"]:
                        st["annotation_revisions"].append(
                            {"annotation_id": aid, "seq": e.get("seq"),
                             "was": st["annotations"][aid].get("note"), "now": p.get("note")})
                        # The CREATION entry keeps the slot. Instance order is the log's order, and
                        # stamping a revision with its own seq moved the annotation to the end of
                        # that order -- so correcting a typo on the first tear rotated every slot
                        # after it and re-labelled photographs already taken and accepted, which is
                        # exactly the harm the ordering was changed to make impossible.
                        first_seq = st["annotations"][aid].get("first_seq",
                                                               st["annotations"][aid].get("seq"))
                    # When it was FOUND. A tear the wash opened is a real observation, but it
                    # cannot be photographed before the cut, and instancing every anomaly shot on
                    # one global count made recording it demand exactly that: an intake and a
                    # before frame of a tear that did not exist then, on a garment that is now cut
                    # and washed. The log is append-only, so the session became unfinalizable by
                    # any route, and the operator's only workable move was not to record the tear.
                    # Pre-cut, an annotation describes the garment AS RECEIVED, so it belongs to
                    # intake -- the earliest state that photographs it. Mapping it to the fold's
                    # own "before" marker instead excluded it from every intake frame, because
                    # intake sorts before "before".
                    found_in = p.get("discovered_in") or ("intake" if lifecycle == "before"
                                                          else lifecycle)
                    st["annotations"][aid] = dict(p, seq=first_seq, first_seq=first_seq,
                                                  revised_at=(e.get("seq")
                                                              if first_seq != e.get("seq") else None),
                                                  discovered_in=found_in,
                                                  operator=p.get("operator") or e.get("operator"))
            elif k == "measurement":
                key = self._key(p.get("name"), "measurement name", e.get("seq"), problems)
                if key is not None:
                    # An explicit state wins; otherwise the entry belongs to wherever the garment
                    # actually was when it was written, which the replay knows because the physical
                    # facts that move it -- the cut, the wash -- are entries in this same log, in
                    # sequence. Nothing has to be remembered by an operator for this to be right.
                    ms = p.get("state") or lifecycle
                    # Direction matters, and only one direction is dangerous. Declaring a LATER
                    # state than the log has reached is the ordinary order of work -- you measure
                    # the washed garment and type the wash record afterwards -- and treating it as
                    # a conflict bricked the sequence the runbook itself prescribes. Declaring an
                    # EARLIER state is the corrupting one: it writes into the pre-cut baseline
                    # after the garment has been cut, which is the overwrite all of this exists to
                    # prevent, and it is recorded separately so the gate can refuse it outright.
                    if p.get("state") and p["state"] != lifecycle:
                        if LIFECYCLE_ORDER.get(p["state"], 9) < LIFECYCLE_ORDER.get(lifecycle, 0):
                            st["measurement_backdated"].append(
                                {"seq": e.get("seq"), "name": key, "claimed": p["state"],
                                 "log_says": lifecycle})
                        else:
                            st["measurement_ahead_of_record"].append(
                                {"seq": e.get("seq"), "name": key, "claimed": p["state"],
                                 "log_says": lifecycle})
                    bucket = st["measurements_by_state"].setdefault(ms, {})
                    if key in bucket:
                        st["measurement_revisions"].append(
                            {"state": ms, "name": key, "seq": e.get("seq"),
                             "was": bucket[key].get("mean"), "now": p.get("mean")})
                    bucket[key] = dict(p, state=ms, seq=e.get("seq"), operator=_who(p, e))
            elif k == "capture":
                sid = self._key(p.get("shot_id"), "shot id", e.get("seq"), problems)
                rep = self._rep(p.get("rep", 1), e.get("seq"), problems)
                if sid is None or rep is None:
                    continue
                st["captures"][(sid, rep)] = dict(
                    p, ts=e.get("ts"), seq=e.get("seq"), setup_hash=e.get("setup_hash"),
                    operator=e.get("operator"), chain=e.get("chain"))
            elif k == "qa_result":
                sid = self._key(p.get("shot_id"), "shot id", e.get("seq"), problems)
                rep = self._rep(p.get("rep", 1), e.get("seq"), problems)
                if sid is None or rep is None:
                    continue
                st["qa_all"].setdefault((sid, rep), []).append(
                    dict(p, ts=e.get("ts"), seq=e.get("seq"), operator=_who(p, e)))
            elif k == "human_verification":
                claim = self._key(p.get("claim"), "claim", e.get("seq"), problems)
                if claim is None:
                    continue
                # shot_id is part of this projection's key and was the one key not routed through
                # the scalar check.
                vshot = p.get("shot_id")
                if vshot is not None:
                    vshot = self._key(vshot, "shot id", e.get("seq"), problems)
                    if vshot is None:
                        continue
                rep = self._rep(p.get("rep"), e.get("seq"), problems) if p.get("rep") else None
                if p.get("rep") and rep is None:
                    continue
                # The record's OWN attribution wins. `operator=e.get("operator")` overwrote it, so a
                # verification that explicitly named its author projected as operator None -- and
                # the second-person check, which refuses a verifier equal to the operator, compared
                # a name against None and let it through.
                st["verifications"][(vshot, rep, claim)] = dict(
                    p, ts=e.get("ts"), seq=e.get("seq"),
                    operator=p.get("operator") or e.get("operator"))
            elif k == "reuse_declaration":
                st["reuse"].append(dict(p, ts=e.get("ts"), seq=e.get("seq"),
                                        operator=_who(p, e)))
            elif k == "deviation":
                st["deviations"].append(dict(p, ts=e.get("ts"), seq=e.get("seq"),
                                             operator=_who(p, e)))
            elif k == "state_transition":
                st["state"] = p.get("to")
                st["state_history"].append({"to": p.get("to"), "ts": e.get("ts"),
                                            "seq": e.get("seq"), "operator": _who(p, e)})
            elif k == "cut_spec":
                # seq travels with it: a verification of "the marks" has to be shown to have
                # happened after the line it verifies was computed, and without the seq nothing
                # could be compared against anything.
                st["cut_spec"] = dict(p, ts=e.get("ts"), seq=e.get("seq"),
                                      operator=_who(p, e))
            elif k == "cut_performed":
                # First write wins, like the wash. A second account of an irreversible physical act
                # is a correction, and a correction that overwrites is indistinguishable from the
                # act never having differed.
                if st["cut_performed"] is None:
                    st["cut_performed"] = dict(p, ts=e.get("ts"), seq=e.get("seq"),
                                               operator=p.get("operator") or e.get("operator"))
                    lifecycle = _advance(lifecycle, "immediate_after")
                else:
                    st["cut_performed_rewrites"].append({"seq": e.get("seq"), "payload": p})
            elif k == "wash_planned":
                # FIRST write wins. Last-write-wins let a second plan be appended after the wash to
                # match whatever happened, and the deviation -- which is the difference between the
                # two -- then computed to nothing. The invariant this log exists to hold is that
                # planned and actual cannot collapse.
                if st["wash_planned"] is None:
                    st["wash_planned"] = dict(p, ts=e.get("ts"), seq=e.get("seq"),
                                              operator=_who(p, e))
                else:
                    st["wash_plan_rewrites"].append({"seq": e.get("seq"), "payload": p})
            elif k == "wash_actual":
                if not isinstance(p, dict):
                    problems.append("entry %s: wash_actual payload is not an object" % e.get("seq"))
                    continue
                # First write wins, exactly as for the plan. A second recording of what the machine
                # actually did is a correction to a record of a physical event, and a correction
                # that overwrites is indistinguishable from the event never having differed.
                if st["wash_actual"] is None:
                    st["wash_actual"] = dict(p, ts=e.get("ts"), seq=e.get("seq"),
                                             operator=_who(p, e))
                    lifecycle = _advance(lifecycle, "post_wash")
                else:
                    st["wash_actual_rewrites"].append({"seq": e.get("seq"), "payload": p})
            elif k == "offcut":
                lbl = self._key(p.get("label"), "offcut label", e.get("seq"), problems)
                if lbl is None:
                    continue
                cur = st["offcuts"].get(lbl, {})
                # Remember WHEN each field was set, not just its final value. The merge kept only
                # the last value, so an assignment written after the wash was indistinguishable
                # from one written before it -- and the assignment exists to DECIDE the wash.
                for fk in p:
                    if fk != "label":
                        cur.setdefault("_seq", {})[fk] = e.get("seq")
                cur.update(p)
                cur["operator"] = _who(p, e)
                cur["seq"] = e.get("seq")
                st["offcuts"][lbl] = cur
            elif k == "note":
                st["notes"].append(dict(p, ts=e.get("ts"), seq=e.get("seq"),
                                        operator=_who(p, e)))
            else:
                st["unknown_kinds"].append({"kind": k, "seq": e.get("seq")})
        # A verdict belongs to the photograph it judged. Folding qa_result last-write-wins let one
        # appended line turn ten rejected frames into "all frames captured and passing" -- the
        # cheapest false READY there was. A verdict now only counts when it names the sha256 of the
        # capture currently filed under that shot and repeat, and the latest such verdict wins.
        # Turning a RETAKE into a PASS therefore requires what it requires physically: another
        # photograph.
        for key, recs in st["qa_all"].items():
            cap = st["captures"].get(key)
            if cap is None:
                continue
            sha = cap.get("sha256")
            # The WORST verdict bound to this photograph wins, not the latest. Taking the latest
            # let a second verdict IMPROVE the first: name the same sha, carry a fabricated
            # all-PASS check list, and a RETAKE became a PASS -- which is exactly what "turning a
            # RETAKE into a PASS requires another photograph" was supposed to prevent. Re-running
            # the checker on one frame is deterministic, so two verdicts that disagree about it are
            # evidence of tampering, and the safe reading of a disagreement is the worse one.
            bound = [r for r in recs if sha and r.get("capture_sha256") == sha]
            if bound:
                from .qa import SEVERITY as _SEV
                st["qa"][key] = max(bound, key=lambda r: _SEV.get(r.get("outcome"), 3))
        # Where the garment ended up, and the pre-modification view the rest of the system reads.
        # `measurements` is deliberately ONLY the before-cut bucket: a gate that wants to know
        # whether this garment may be cut must not be able to satisfy itself with a number taken
        # out of the tumble dryer.
        st["lifecycle_state"] = lifecycle
        st["measurements"] = st["measurements_by_state"].get(PRE_MODIFICATION_STATE, {})
        return st, problems

    # -- convenience --------------------------------------------------------------------------

    def done_keys(self, state=None):
        """(shot_id, rep) pairs that have an accepted capture, optionally within one state.

        Reuse counts, because a declared reuse that passed the borrowing shot's own checks is that
        shot's evidence. A RETAKE does not count: a rejected frame is not a captured one, and
        treating it as captured is how a required shot goes missing without anything saying so.
        """
        st, _ = self.fold()
        out = set()
        for (sid, rep), cap in st["captures"].items():
            if state is not None and cap.get("state") != state:
                continue
            if not cap.get("sha256"):
                continue        # nothing to verify the file against; see gates.captures.files_intact
            q = st["qa"].get((sid, rep))
            if q is None or q.get("outcome") == "RETAKE_REQUIRED":
                continue        # never checked, or rejected: either way not an accepted capture
            out.add((sid, rep))
        for r in st["reuse"]:
            if state is not None and r.get("state") != state:
                continue
            out.add((r.get("shot_id"), int(r.get("rep", 1))))
        return out


def _who(payload, entry):
    """Who supplied this record. The payload's own attribution wins over the envelope's.

    Eleven of the sixteen projections dropped it entirely, so "who took this measurement, who
    recorded this deviation, who assigned this offcut" was unanswerable from the folded state --
    the answer was in the log and no gate, no command and no export could reach it. A record whose
    author is not recoverable is not a provenance record.
    """
    return (payload or {}).get("operator") or (entry or {}).get("operator")


def mean_of(measurement):
    """The mean of a measurement's own readings, recomputed.

    The gate validates `readings` -- their count, finiteness, spread and plausible range -- and the
    record also carries a `mean` that nothing checked. Every consumer read the mean: the hem series
    is sized from it, the cut is placed from it. So a record could carry two honest readings and a
    fabricated mean, pass every measurement condition, and hand a different number to the planner
    and the cut. Derived fields are recomputed here rather than trusted.
    """
    if not measurement:
        return None
    rs = []
    for r in (measurement.get("readings") or []):
        try:
            f = float(r)
        except (TypeError, ValueError):
            return None
        if f != f:
            return None
        rs.append(f)
    return (sum(rs) / len(rs)) if rs else None


def setup_hash(setup):
    """Hash of the frozen rig configuration.

    Canonical serialisation with sorted keys, and every float rounded, because the hash's job is to
    say "the rig is the same as it was", and a value that arrives as 82.5 from a form and
    82.50000000000001 from a calculation is the same rig. An unrounded float would make it a
    different one, and the deviation record that followed would be noise.
    """
    return sha256_text(canonical(_round_floats(setup)))


def _round_floats(o, places=4):
    if isinstance(o, float):
        return round(o, places)
    if isinstance(o, dict):
        return {k: _round_floats(v, places) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round_floats(v, places) for v in o]
    return o


def diff_planned_actual(planned, actual):
    """Every field where the wash actually differed from the plan.

    The protocol's rule is that actual settings never replace planned ones. This is the function
    that makes keeping both worth something: the deviations are computed, not remembered.
    """
    if not planned or not actual:
        return []
    out = []
    # Envelope metadata is not a wash setting. Excluding a fixed list let each new envelope field
    # (ts, then seq) leak in as a "deviation" the operator would have to explain.
    envelope = {"ts", "seq", "recorded_by", "operator", "chain", "prev_chain", "kind", "schema",
                "setup_hash"}
    for k in sorted(set(list(planned.keys()) + list(actual.keys()))):
        if k in envelope:
            continue
        pv, av = planned.get(k), actual.get(k)
        if pv is None and av is None:
            continue
        if isinstance(pv, float) and isinstance(av, float):
            same = abs(pv - av) < 1e-9
        else:
            same = pv == av
        if not same:
            out.append({"field": k, "planned": pv, "actual": av})
    return out

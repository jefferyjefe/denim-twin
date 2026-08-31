"""Loading the shot-plan specification, and refusing to load a broken one.

The specification is deliberately not Python. If the capture list lived in application code, then
"what this state requires" and "what this code happens to check" would be two things that drift, and
the drift would be invisible until a garment was cut with a shot missing. So the list is a versioned
JSON document, the readiness gate enumerates its requirements FROM that document, and this module is
the boundary that decides a document is fit to be enumerated from.

The validation that matters is not the schema -- jsonschema does that -- but the cross-references,
because every one of them is a silent-drop bug:

  * a shot whose `conditional_on` names a feature key that does not exist is a shot that can never
    activate. A typo there deletes a required photograph and nothing complains.
  * a shot whose `region_id` is not in the region map is a shot the garment map cannot highlight,
    so the operator is told to photograph a region the UI cannot show them.
  * a `matched_shot_ids` pointing at a shot id that does not exist is a before/after pair with one
    end missing, which is exactly the case the matching check is supposed to catch.
  * two shots sharing an id means one of them is unreachable, and which one depends on dict order.

All four are refusals, not warnings. A specification that cannot be enumerated cannot gate a cut.
"""
import json
import re
from pathlib import Path

from .manifest import canonical, sha256_text

SPEC_DIR_NAME = "shotplan"


class SpecError(Exception):
    pass


#: `conditional_on` is a tiny boolean language, not eval(). It takes feature keys, `and`, `or`,
#: `not`, parentheses, and comparisons of a numeric feature against a literal. Keeping it this small
#: is what lets `feature_keys()` list every key an expression depends on, which is what makes an
#: unknown key a load-time refusal instead of a silent False at plan time.
_TOKEN = re.compile(r"\s*(\(|\)|>=|<=|==|!=|>|<|and\b|or\b|not\b|[A-Za-z_][A-Za-z0-9_]*|[0-9]+(?:\.[0-9]+)?)")


def tokenize(expr):
    out, i = [], 0
    while i < len(expr):
        m = _TOKEN.match(expr, i)
        if not m:
            raise SpecError("cannot parse condition %r at offset %d" % (expr, i))
        out.append(m.group(1))
        i = m.end()
    return out


_KEYWORDS = {"and", "or", "not", "(", ")", ">=", "<=", "==", "!=", ">", "<"}


def feature_keys(expr):
    """Every feature key an expression depends on. Numbers and operators are not keys."""
    if not expr or not expr.strip():
        return set()
    return {t for t in tokenize(expr)
            if t not in _KEYWORDS and not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", t)}


def evaluate(expr, features):
    """Evaluate a condition against answered features.

    An unanswered key does NOT evaluate to False. It raises, and the caller decides -- because the
    safe reading of "we do not know whether this garment has a coin pocket" is that it might, and
    silently answering False is how a present feature gets omitted.
    """
    if not expr or not expr.strip():
        return True
    toks = tokenize(expr)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def take():
        t = peek()
        pos[0] += 1
        return t

    def atom():
        t = take()
        if t is None:
            raise SpecError("condition %r ends after an operator" % expr)
        if t == "(":
            v = or_expr()
            if take() != ")":
                raise SpecError("unbalanced parentheses in %r" % expr)
            return v
        if t == "not":
            return not atom()
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", t or ""):
            return float(t)
        if t not in features:
            raise SpecError("condition %r refers to feature %r, which has not been answered"
                            % (expr, t))
        v = features[t]
        if v is None:
            raise SpecError("condition %r refers to feature %r, which has not been answered"
                            % (expr, t))
        return v

    def cmp_expr():
        left = atom()
        if peek() in (">=", "<=", "==", "!=", ">", "<"):
            op = take()
            right = atom()
            lf, rf = float(left), float(right)
            return {">=": lf >= rf, "<=": lf <= rf, "==": lf == rf, "!=": lf != rf,
                    ">": lf > rf, "<": lf < rf}[op]
        return bool(left) if not isinstance(left, float) else left != 0

    def and_expr():
        v = cmp_expr()
        while peek() == "and":
            take()
            v = cmp_expr() and v
        return v

    def or_expr():
        v = and_expr()
        while peek() == "or":
            take()
            v = and_expr() or v
        return v

    v = or_expr()
    if pos[0] != len(toks):
        raise SpecError("trailing tokens in condition %r" % expr)
    return bool(v)


class Spec(object):
    """A loaded, cross-checked shot-plan specification plus its region map."""

    def __init__(self, doc, regions, path=None, regions_path=None):
        self.doc = doc
        self.regions_doc = regions
        self.path = Path(path) if path else None
        self.regions_path = Path(regions_path) if regions_path else None
        self.shots = doc["shots"]
        self.features = doc["features"]
        self.states = doc["states"]
        self.regions = regions["regions"]
        self.by_id = {s["shot_id"]: s for s in self.shots}
        self.region_by_id = {r["region_id"]: r for r in self.regions}
        self.feature_by_key = {f["key"]: f for f in self.features}

    # -- identity -----------------------------------------------------------------------------

    @property
    def content_hash(self):
        """Hash of the specification as loaded. Recorded on every capture, so a session can be
        told which version of the plan it was collected under."""
        return sha256_text(canonical({"shotplan": self.doc, "regions": self.regions_doc}))

    @property
    def version(self):
        return self.doc["spec_version"]

    # -- validation ---------------------------------------------------------------------------

    def cross_check(self):
        """Every reference resolves, or the specification is not usable. Returns a list of errors."""
        errs = []
        seen = {}
        for s in self.shots:
            sid = s["shot_id"]
            if sid in seen:
                errs.append("duplicate shot_id %s" % sid)
            seen[sid] = s
        state_names = {st["state"] for st in self.states}
        for s in self.shots:
            sid = s["shot_id"]
            if s["state"] not in state_names:
                errs.append("%s: state %r is not declared in states[]" % (sid, s["state"]))
            for rid in [s["region_id"]] + list(s.get("also_covers_regions") or []):
                if rid not in self.region_by_id:
                    errs.append("%s: region_id %r is not in the region map" % (sid, rid))
            cond = s.get("conditional_on") or ""
            try:
                for k in feature_keys(cond):
                    if k not in self.feature_by_key:
                        errs.append("%s: conditional_on names unknown feature %r -- this shot could "
                                    "never activate" % (sid, k))
            except SpecError as e:
                errs.append("%s: %s" % (sid, e))
            if s["necessity"] == "conditional" and not cond and not s.get("instance_of"):
                errs.append("%s: necessity is 'conditional' but no condition is given, so nothing "
                            "decides whether it is required" % sid)
            if s["necessity"] != "conditional" and cond:
                errs.append("%s: has a condition but necessity is %r; a conditional shot must say so"
                            % (sid, s["necessity"]))
            if s.get("instance_of") and s["instance_of"] not in self.feature_by_key:
                errs.append("%s: instance_of names unknown feature %r" % (sid, s["instance_of"]))
            if s.get("instance_of") and cond:
                # Whether the shot is included and how many frames it becomes must be decided by
                # the same answer. If the condition can be true while the count is zero, the shot is
                # required and expands to nothing -- a required photograph that disappears without
                # anything reporting it missing.
                try:
                    keys = feature_keys(cond)
                except SpecError:
                    keys = set()
                if keys and s["instance_of"] not in keys:
                    errs.append(
                        "%s: is instanced on %r but its condition %r does not mention it, so the "
                        "condition can be true while the count is zero and the shot would expand "
                        "to no frames" % (sid, s["instance_of"], cond))
            for m in s.get("matched_shot_ids") or []:
                if m not in seen:
                    errs.append("%s: matched_shot_ids names %r, which is not a shot in this "
                                "specification" % (sid, m))
            if s.get("min_reps", 1) > 1 and not s.get("relay_between_reps") \
                    and not s.get("reposition_camera_between_reps"):
                errs.append("%s: asks for %d repetitions but declares neither a re-lay nor a camera "
                            "reposition between them, so the repeats would measure nothing"
                            % (sid, s["min_reps"]))
            if s.get("relay_between_reps") and int(s.get("min_reps", 1)) > 1:
                # The gate requires relay independence to be ESTABLISHED for every such repeat, and
                # only some shot classes can establish it -- a rig frame has no garment whose creases
                # could be compared. A shot that demands the check from a class that cannot produce
                # it is a permanently unopenable gate, which is worse than a wrong shot: the
                # operator collects everything and is still refused, with no action that would help.
                from .qa import WHOLE_GARMENT, shot_class
                cls = shot_class(s)
                if cls != WHOLE_GARMENT:
                    errs.append(
                        "%s: requires an independent re-lay between repeats, but it is a %r frame. "
                        "A re-lay is an operation on a garment LAY, and only a whole-garment frame "
                        "observes one -- at macro range there is no silhouette to measure the "
                        "displacement of, so the check could only ever return UNAVAILABLE and the "
                        "gate would never open. Use reposition_camera_between_reps instead."
                        % (sid, cls))
        for r in self.regions:
            cond = r.get("conditional_on") or ""
            for k in feature_keys(cond):
                if k not in self.feature_by_key:
                    errs.append("region %s: conditional_on names unknown feature %r"
                                % (r["region_id"], k))
        for f in self.features:
            if f["type"] == "enum" and not f.get("options"):
                errs.append("feature %s: type enum with no options" % f["key"])
        return errs

    def _links(self):
        """Every declared match, split by whether it crosses a state boundary.

        A link between two shots in the SAME state is not a before/after pair -- it is an
        instruction to frame two frames alike (the two halves of one hem, say). Counting those as
        matched before/after pairs inflates the count and, worse, hides the pairs that are genuinely
        missing: a region that changes with washing and has no later-state counterpart looks covered
        because some same-state link filled the tally.
        """
        order = {st["state"]: st["order"] for st in self.states}
        across, within = set(), set()
        for s in self.shots:
            for m in s.get("matched_shot_ids") or []:
                o = self.by_id.get(m)
                if not o or m == s["shot_id"]:
                    continue
                oa, ob = order.get(s["state"], 0), order.get(o["state"], 0)
                if oa == ob:
                    within.add(tuple(sorted((s["shot_id"], m))))
                else:
                    across.add((s["shot_id"], m) if oa < ob else (m, s["shot_id"]))
        return sorted(across), sorted(within)

    def matched_pairs(self):
        """(earlier, later) pairs that genuinely span states. Symmetric: a link declared on either
        end counts, so one-sided authoring does not lose the pair."""
        return self._links()[0]

    def companion_pairs(self):
        """Same-state links: two frames that must be framed alike, but are not a before/after pair."""
        return self._links()[1]

    def unmatched_changing_regions(self):
        """Regions that change with washing and have no frame in any later state.

        This is the question the before/after requirement actually asks, and it is asked of the
        REGIONS rather than of the links, because a region with no later-state frame at all declares
        no links to be missing.
        """
        order = {st["state"]: st["order"] for st in self.states}
        before_order = order.get("before", 2)
        seen_later = set()
        seen_before = set()
        for s in self.shots:
            o = order.get(s["state"], 0)
            for rid in [s["region_id"]] + list(s.get("also_covers_regions") or []):
                if o > before_order:
                    seen_later.add(rid)
                elif o == before_order:
                    seen_before.add(rid)
        out = []
        for r in self.regions:
            if not r["can_change_by_wash"] or r["can_change_by_cut"]:
                continue          # removed by the cut: its later evidence is on the offcut
            if r["region_id"] in seen_before and r["region_id"] not in seen_later:
                out.append(r["region_id"])
        return sorted(out)


def load(spec_path, regions_path=None):
    """Load and cross-check. Raises SpecError listing every problem rather than the first."""
    import jsonschema

    spec_path = Path(spec_path)
    doc = json.loads(spec_path.read_text())
    here = spec_path.parent
    schema = json.loads((here / "shotplan.schema.json").read_text())
    rschema = json.loads((here / "regions.schema.json").read_text())
    errs = ["shotplan.json: " + e.message
            for e in jsonschema.Draft202012Validator(schema).iter_errors(doc)]
    regions_path = Path(regions_path or (here / doc.get("regions_file", "regions.json")))
    regions = json.loads(regions_path.read_text())
    errs += ["regions.json: " + e.message
             for e in jsonschema.Draft202012Validator(rschema).iter_errors(regions)]
    if errs:
        raise SpecError("shot-plan specification is not valid:\n  " + "\n  ".join(errs[:40]))
    spec = Spec(doc, regions, spec_path, regions_path)
    errs = spec.cross_check()
    if errs:
        raise SpecError("shot-plan specification has unresolved references:\n  "
                        + "\n  ".join(errs[:40]))
    return spec

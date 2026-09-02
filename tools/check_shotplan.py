#!/usr/bin/env python3
"""Load the shot-plan specification and refuse it if anything it points at does not exist.

This is separated from the self test because it is the cheaper and more fundamental question. The
self test asks whether the gate behaves; this asks whether the document the gate enumerates from is
coherent at all. A shot whose `conditional_on` names a feature key that does not exist can never
activate, so a typo there removes a required photograph and nothing else in the system notices.

    tools/check_shotplan.py [--spec protocol/shotplan/shotplan.json]

Exit 0 the specification loads and every reference resolves
     1 it does not
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from denimtwin.pilot import spec as SPEC     # noqa: E402
from denimtwin.pilot import plan as PLAN     # noqa: E402

p = argparse.ArgumentParser()
p.add_argument("--spec", default=str(ROOT / "protocol" / "shotplan" / "shotplan.json"))
a = p.parse_args()

try:
    s = SPEC.load(a.spec)
except SPEC.SpecError as e:
    print(e)
    raise SystemExit(1)

# Every feature answered "present" must produce a plan; a plan that fails to generate under the
# most inclusive answers is a plan that can fail to generate at all.
answers = {f["key"]: (1 if f["type"] == "count" else True) for f in s.features}
# A measurement carries READINGS; its mean is recomputed from them and never read off the record,
# so a fixture that supplies only a mean now describes an unmeasured dimension.
MEASURED = {"leg_opening_cm": {"name": "leg_opening_cm", "readings": [40.0, 40.1]}}
shots, meta = PLAN.activate(s, answers, MEASURED)
if not shots:
    print("the specification activates no shots even with every feature present")
    raise SystemExit(1)
if meta["expansion_blocked"]:
    print("templated series could not expand even with a leg opening supplied:")
    for x in meta["expansion_blocked"]:
        print("   %s: %s" % (x["shot_id"], x["why"]))
    raise SystemExit(1)

ordered = PLAN.order(s, shots)
required = [x for x in ordered if x["necessity"] != "optional"]
by_state = {}
for x in ordered:
    by_state[x["state"]] = by_state.get(x["state"], 0) + 1

print("shot plan v%s (%s) loads and cross-checks" % (s.version, s.content_hash[:12]))
print("  %d shot definitions -> %d frames with every feature present" % (len(s.shots), len(ordered)))
print("  %d required, %d optional; %d regions; %d features; %d matched pairs"
      % (len(required), len(ordered) - len(required), len(s.regions), len(s.features),
         len(s.matched_pairs())))
print("  by state: " + ", ".join("%s=%d" % kv for kv in
                                 sorted(by_state.items(),
                                        key=lambda kv: [st["order"] for st in s.states
                                                        if st["state"] == kv[0]][0])))

# The authoring gap this document is most likely to have, and the one that cannot be repaired
# afterwards: a region photographed before the wash whose wash response is never photographed. The
# wash is a one-way door, so the frame that is missing here is a frame nobody can ever take.
#
# This is reported, not enforced. Some of these regions leave on the offcut at a shorts-length cut
# and their later evidence really is in the offcut states; others -- the thigh, the knee, the
# selvedge runs, the anomaly zones -- plainly stay on the garment and go through the machine.
# Which is which depends on the target inseam, so it is a judgement about the protocol rather than
# a fact about the document, and it belongs to the owner. What is NOT acceptable is the previous
# behaviour: the check suppressed every one of them and reported nothing at all.
unmatched = s.unmatched_changing_regions()
undeclared = s.undeclared_changing_regions()
open_ = s.open_postwash_regions()
if unmatched:
    print("\n  %d region(s) have no frame in any later state; %d are recorded as leaving with the "
          "offcut," % (len(unmatched), len(unmatched) - len(open_)))
    print("  and %d are recorded as an OPEN question nobody has decided:" % len(open_))
    for rid in open_:
        print("     %s" % rid)
if undeclared:
    print("\n  %d region(s) have neither a post-wash frame nor a recorded decision about why "
          "not:" % len(undeclared))
    for rid in undeclared:
        print("     %s" % rid)
    print("  Add each to postwash_coverage_decisions with a reason. The wash is a one-way door: a "
          "frame\n  that is missing here is one nobody can ever take.")
    raise SystemExit(1)
raise SystemExit(0)

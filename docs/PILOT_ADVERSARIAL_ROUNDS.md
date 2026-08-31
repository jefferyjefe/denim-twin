# Adversarial rounds against the cut gate

`tools/pilot.py precut` authorises an irreversible physical act. Everything else in the pilot can be
redone; a garment cut in half cannot. So the gate was not reviewed, it was attacked: independent
agents, working in isolated git worktrees against the committed code, with one instruction — make it
print READY TO CUT without the evidence.

Attacking the SOURCE was out of scope throughout. An attacker who may edit `gates.py` proves nothing
except that the file is writable. Editing DATA — the log, the photographs, the answers, the HTTP
requests — was entirely in scope, because that is what an operator in a hurry, or a mistake, can
actually do.

## Round 1 — seven angles, thirty-one findings

| angle | what it attacked | findings |
|---|---|---|
| manifest | the append-only hash-chained log | 8 |
| human | the recorded assertions that clear a HUMAN outcome | 6 |
| coverage | the required set: conditions, counts, expansions | 3 |
| imagery | one frame satisfying many shots; relays; duplicates | 6 |
| rig | the frozen configuration, attribution, the board's scale | 7 |
| api | the HTTP surface as a second way into the same data | 5 |
| filesystem | files under the manifest's feet | 2 |

Independent verifiers re-ran each claim from scratch in their own worktrees. Nine were confirmed
outright (seven false READYs, one crash, one weakened condition); the rest were either already
refused by the time they were re-run — fixes were landing while verification proceeded, so that
count is not a clean measure of the original code — or not reproducible.

**Every one of the thirty-one was fixed, and each is now a scenario in `tools/pilot.py selftest`.**
The suite went from 25 scenarios to 49, and to 64 after round 2.

### The ones worth remembering

**Nothing bound a log to its garment.** The chain was seeded from a constant, so `cp -r` of a
finished garment's directory produced a log that verified perfectly and opened the gate for a
garment that had never been photographed. The seed is now the garment's own identity.

**A verdict was not bound to the photograph it judged.** `fold()` kept the last `qa_result` per
shot, so one appended line turned ten rejected frames into "all frames captured and passing" — a
pure append, so the hash chain had nothing to catch. A verdict now counts only if it names the
capture's sha256, and the gate re-derives the roll-up from the stored checks and refuses one that
disagrees with its own evidence.

**A recorded refusal read as an approval.** `cut.second_person_verified` never read `value`, so a
second person writing "no, the marks are on the wrong leg" satisfied the condition. The same
condition selected by dictionary order, so a retraction could be discarded in favour of an older
approval, and accepted the string `"NaN"` — which compares false against every bound and switched
the 3 mm tolerance off.

**A required shot could expand to zero frames and vanish.** Inclusion and cardinality came from two
independent answers that were never reconciled, so a garment with three tears and no distressing was
required to photograph the tears and expanded to nothing. Nothing reported it missing, because
nothing knew it should exist.

**The web upload could not accept a single photograph.** A name was used six lines before the
function-local import that bound it, so every upload of a readable image raised `UnboundLocalError`
*after* the file had been ingested and the capture entry written. It went unnoticed because the UI
tests read state and never posted a frame. A front end nobody exercises is a front end that does not
work; there is now a test that speaks real multipart to a real server.

**Two readings agreeing with each other say nothing about the tape.** `leg_opening_cm` sizes a
required series and places the cut mark, and an operator reading inches records two readings that
agree perfectly and are 2.5× wrong. Every downstream check passed, because everything downstream
believed the number.

## Round 2 — five angles, thirty-three findings

Round 2 was pointed at round 1's fixes, and most of what it found was in them.

| angle | what it attacked | findings |
|---|---|---|
| regress-round1 | every round-1 fix, hunting the variant it misses | 7 |
| fold-invariants | `store.fold()` and the projections the gate reads | 7 |
| plan-and-spec | the required set, again and harder | 6 |
| concurrency-and-io | timing, staging, the head anchor | 3 |
| human-and-wash | the wash and offcut gates — surfaces nothing had exercised | 12 |

### The ones that mattered most

**My round-1 fix was testing the record against itself.** The gate re-derived a verdict's roll-up
from the checks stored beside it and refused a disagreement — but a list of two invented all-PASS
checks rolls up to PASS and agrees perfectly. The mandatory set now comes from the code: what this
class of frame is checkable for, minus what the record's own not-applicable notes justify. Which in
turn forced every applicable check that does not run for a particular shot to say so, and revealed
that 146 of 290 shots were getting no scale or tilt result with nothing recording it.

**A hundred required frames were guarded by nothing.** The specification declares eight states; the
three hand-kept tuples naming which states each gate covers named six. The two offcut states
appeared in none of them, so the entire offcut experiment could be skipped and every gate still
opened. The sets are derived from the specification's own ordering now.

**The gate's own first line broke its own rule.** `store.fold()` ran above every guard, so anything
the log or the replay raised escaped the deny-by-default machinery and returned a traceback instead
of a verdict. A gate that cannot answer must still answer no.

**The post-wash gate required nothing about the wash.** It differed from the pre-wash gate by one
string in a tuple and added no condition of its own, so a garment could be photographed after
washing with no record that it had been washed, under what settings, or how far those departed from
the plan. The whole experiment is one wash.

**A later verdict could improve an earlier one.** Taking the latest verdict bound to a photograph
meant naming the same hash with a fabricated check list turned a RETAKE into a PASS. Re-running a
checker on one frame is deterministic, so two verdicts that disagree are evidence of tampering and
the safe reading is the worse one.

**"The latest wins" was decided by a writable clock.** Ordering verifications by their payload
timestamp let a future-dated approval outrank a real retraction appended after it. Log position is
stamped by the appender; the payload's clock is not.

## Round 3 — the angles run by hand

Round 3's agents were blocked on their first attempt by an account session limit, so three of its
four angles were run directly instead. Two found something.

**`pilot.py add` with a FIFO hung forever.** It passed every existence test and then blocked inside
the copy, waiting for a writer that never came. A hang is worse than a refusal: the operator cannot
tell it from slow work, and the gate never answers at all. Ingestion now requires a regular,
non-empty file.

**Eight hostile inputs exited non-zero while printing a traceback** — a cut inseam of zero, of
infinity, of NaN; a source that is a directory or missing. Non-zero is technically a refusal and a
stack trace is not one: it says something broke, not what to do. The command line now catches its
own exception types and prints a sentence, which is the rule the gate already held one level down.

The rest held:

- Ordering. Reps ingested out of order, a repeat with no first capture, an entry with no sequence
  number, a duplicated sequence number, and a capture appended before the rig freeze it cites — all
  blocked, and none crashed.
- The checker. An empty backdrop, a field of pure noise and a flat grey field, each with a real
  detected board and each at the resolution the shot demands, were offered as whole-garment frames
  with the operator confirming the ruler, the side and the region. All three refused, by content
  rather than arithmetic.

One thing that probe establishes and should not be overstated: the side check PASSED, because the
operator asserted it and the pixels genuinely cannot settle which face of a garment is up. That is
the honest answer, and it is recorded as an assertion with a name on it — but a determined operator
can still confirm something untrue. No arrangement of software fixes that. What the system can do is
make the claim attributable, and it does.

## What the attacks did not break

Worth recording, because they are the parts that held:

- The deny-by-default guard. Making a condition raise costs blocks, never a pass; no attacker found
  a data-reachable path to a verdict of READY through an exception.
- The four-outcome discipline. Making `scale_range_ratio` unmeasurable returns UNAVAILABLE_CHECK,
  which the gate treats as blocking — sweeping the board tilt from 0 to 45 degrees never produced a
  pass.
- One confirmation clearing several claims. `_human_resolved` requires a separate record per claim,
  and a frame raising two questions with one answered stayed unresolved.
- The torn-line repair. It is more aggressive than its trigger and could not be turned into a way of
  removing an inconvenient entry.

## The standing rule

A finding is not closed by a fix. It is closed by a fix **and** a scenario that fails without it.
`tools/verify.py` runs the whole suite, so a regression is a red build rather than a discovery on
cut day.

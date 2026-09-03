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

## Round 3 — four angles, thirty-one findings

Round 3's agents were blocked on their first attempt by an account session limit, so three of its
four angles were run directly while that cleared; the agent round was then re-run in full. The
hand-run probes and the agents found overlapping sets, and both are recorded below.

| angle | what it attacked | findings |
|---|---|---|
| qa-engine | the checker itself: what each check can and cannot see | 11 |
| regress-round2 | whether round 2's fixes actually closed round 2's holes | 9 |
| cli-and-state | the command line as a second way into the same data | 7 |
| ordering | sequence numbers, repeats, entries out of order | 4 |

The character of round 3 was different from the first two. Rounds 1 and 2 found ways to make the
gate say READY without the evidence. Round 3 found almost none of those — what it found instead was
**checks that could not fail**, which is the same defect one level up: a condition that always
passes is indistinguishable from one that was never asked.

### The ones that mattered most

**Seventeen required rig frames passed on a photograph of anything.** The frame that must show an
EMPTY backdrop, the lighting test, the proof that the board and the garment share a plane — every
numeric threshold in the checker passes on any file that decodes, because there is nothing in the
pixels to judge. The class carried no content check and no human check either. A shot can now
declare the claims a person must make about it, and those seventeen declare theirs.

**146 shots carried a scale threshold nothing could evaluate.** `max_mm_per_px` and
`max_scale_range_ratio` are produced by measuring the calibration board's corner spacings, and these
are ruler-scaled macros with no board in frame — so the numbers sat in the specification looking
enforced while nothing compared anything to them. The specification's cross-check now refuses a
threshold no check can produce, which fails the plan at load rather than at audit. Where the intent
was real it was translated into something answerable: 144 shots now ask the operator to confirm the
rule's millimetre graduations are individually separated, which is the same requirement asked of the
one instrument in the frame that can answer it.

**Every one of the 139 whole-garment shots was excused from naming its region.** The condition
listed only the two macro angles, so the thirty-eight obliques — the frames an operator most easily
confuses, one quadrant along — were excused by a sentence saying the region "is not one a person is
asked to confirm at this range". They are asked now. The overhead frames still are not, and the
excuse text says why rather than pretending otherwise.

**The most expensive comparison in the checker left no trace when it passed.** `duplicate_content`
appended a record on failure only, so a pair that was decoded, correlated and found distinct looked
in the record exactly like a pair that was never compared. Both outcomes are recorded now.

**The actual wash could overwrite itself.** The planned/actual split exists so a deviation stays
visible; last-write-wins meant a second recording erased exactly the deviation it was built to
preserve. The actual wash is written once, like the plan, and a correction is a deviation entry. The
prompts also stopped offering the planned value as their default — sixteen presses of return had
been recording a perfect match to plan without anyone reading a dial.

**`/api/upload` took its garment id from a form field**, which no route pattern ever sees, so the
shape check every other path went through was skipped on the one path that accepts photographs. The
id is validated where it becomes a directory now, which is the one place every path has to cross.

**A cut the geometry says it cannot model passed as quietly as any other.** `cutspec` prints a
warning when the cut lands close enough to the crotch that the straight-perpendicular model stops
describing a real inseam. Nothing read it. It still does not block — the operator may cut there —
but they have to record that they meant to.

### The angles run by hand

Two of the three found something.

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

## Round 4 — four angles, twenty-five findings, every one reproduced

Round 4 ran four attackers in isolated worktrees and then sent every finding at medium or above to
an independent verifier in a fresh worktree, with instructions to reproduce it from the claimant's
own steps or say precisely what happened instead. **Twenty-five findings, twenty-five reproduced,
none rejected.** Six critical, eight high, eleven medium.

| angle | what it attacked | findings |
|---|---|---|
| chain | the append-only log and its head sidecar | 6 |
| checks | what each check can and cannot see | 5 |
| gate | the conditions themselves | 8 |
| surface | the HTTP server and the command line | 6 |

Rounds 1 and 2 found ways to reach READY without the evidence. Round 3 found checks that could not
fail. Round 4 found both, and something worse than either.

### The log could be rewritten

`_write_head`'s own docstring claimed the appended anchor made a truncation "detectable however many
entries are added afterwards". It was a pure length comparison, and the appender repaired it: chop
five entries, take five more photographs, and the log verifies clean. Delete one and add one and it
was never detectable at all.

Which matters because the chain is **keyless and its seed is public**. An attacker who can write the
file can recompute the whole chain. Round 4 did: delete the RETAKE verdict, re-chain the file, run
one ordinary command, and `precut` printed READY TO CUT with the forged all-PASS verdict standing.

The sidecar records the chain at *every count the log has ever reached*. Two anchors agreeing on a
count and disagreeing on the chain is proof of a rewrite whatever the log now looks like, and an
anchor whose count still exists must name that entry's chain. Both variants now stay detected
however much honest work follows.

### The gate believed the record

Every defence built in rounds 1-3 tests the record against itself: the roll-up must match the
checks, the checks must cover what the class supports, the excuses must be ones the checker would
have written. All of it is satisfied by a sufficiently complete forgery. One appended `qa_result`
carrying an invented all-PASS check list made **a photograph of an empty backdrop** into a passing
primary whole-garment frame — a pure append, so the hash chain stayed perfect.

The photograph is the one thing an appended line cannot change. The cut gate now re-runs the twelve
pixel checks on the files themselves and blocks a recorded PASS that does not reproduce. It costs a
few minutes on a run that happens once, before something irreversible.

### The requirement the whole repeatability arm exists for was unenforced

`relay_between_reps` was only ever checked between repeats *inside* one shot id. The five
front-overhead and three back-overhead re-lays are written as separate shot ids with `min_reps: 1`,
so the eight frames the requirement is about were the eight it never saw. Five photographs of one
lay — re-shot with sensor noise and shake, which is what a hurried operator actually produces —
passed with `duplicate_content` recording a confident PASS on each.

Fixing it exposed a fixture that was doing exactly the same thing: the positive control had been
feeding one lay to all five, and passed only because nothing checked.

### Round 3's own fix did not work

`quality_is_evaluable` read the shot's own quality block while every consumer reads
`merged_quality(defaults, shot)`. Stripping the board-only thresholds from 151 boardless shots left
them inheriting the same numbers from `quality_defaults`. The fix passed its own check and changed
nothing for the shots that had never written the key down themselves.

### Two findings punished the honest operator

Worth separating out, because a system that blocks valid evidence is broken in the same way as one
that accepts invalid evidence, and only round 4 went looking for it.

`append()` had been serialised against other appends since round 1; `read()` — which every fold,
every gate and every CLI command goes through — took no lock at all. One phone uploading while the
GATE tab refreshes is two ordinary things at once on a threading server, and the operator was told
their own log was torn. And a rejected `POST /api/setup` had *already* re-frozen the rig, orphaning
every calibration reading in the session and turning a READY garment into NOT READY with a 400
saying nothing had happened.

### The phone app signed nothing

Round 3 concluded: "a determined operator can still confirm something untrue. What the system can do
is make the claim attributable, and it does." On the front door the operator actually uses, it did
not. `app.js` read `localStorage.pilot_operator` and **nothing ever set it**, so a session driven
from the phone recorded the rig freeze, all ten calibration readings, all eight measurements, every
photograph and every confirmation against the empty string. The server now refuses an unsigned write
— in `dispatch`, not per handler — and the app asks who is operating.

### The rest

A required motion clip could be a 16x16, two-frame, 0.1-second file. `/api/measure` exploded a JSON
string into one reading per character, so `"111"` satisfied "three independent caliper readings". A
completely out-of-focus care label passed, because the blur check was re-taken on `cloth_blur()`,
which discards bright unsaturated pixels to keep the steel rule out — and a care label is white.
`precut` hung forever on a manifest entry pointing at a FIFO. Half a session could be shot under a
rig that was never calibrated. A deviation naming nothing excused everything of its kind, forever,
and could be written before the departure existed. `rm manifest.jsonl` reported zero integrity
problems.

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
cut day. The scenario suite went 25 -> 49 -> 64 -> 78 -> 82 -> 85 -> 101 across the rounds, and every number in
that sequence is an attack somebody actually ran. `tests/test_pilot_selftest.py` binds the list to the
scenarios and the count to the README, because a number in prose that nothing checks drifts -- the
README said 78 while the suite ran 85, and gave two different breakdowns of it in consecutive
sentences.

## What four rounds are evidence of, and what they are not

Rounds 1, 2, 3 and 4 found 31, 33, 31 and 25 issues. The count is not falling much, and it would be
dishonest to read the fourth round as convergence. What did change is the KIND: rounds 1 and 2 found
false READYs, round 3 found checks that could not fail, and round 4 found the two structural
assumptions underneath all of it — that the log could not be rewritten, and that a record could be
trusted about the photograph it describes. Neither was true.

So the standing claim is narrow. **These are the attacks that have been tried.** Four rounds of
independent agents, every finding reproduced by a second agent before it was touched, and every one
pinned as a scenario. That is a much weaker statement than "the gate cannot be fooled", and it is
the only one the evidence supports. The chain is keyless; anyone who can write the garment directory
can write anything in it. What the system offers is that a rewrite is *detectable*, that a verdict
must survive re-derivation from the photograph, and that every claim carries a name — not that a
determined person with filesystem access cannot lie.


## Round 6 — the answers the system supplied on the operator's behalf

Rounds 1 to 5 attacked the DATA: forge the log, forge a verdict, make one photograph satisfy two
shots. This round asked a different question — not "can the evidence be faked?" but **"does the
system ever write down a fact nobody established?"** — and the answer was yes, in the one command
that everything else is attributed to.

`tools/pilot.py setup` freezes the rig and hashes it onto every photograph in the session. It asked
for the eight physical fields with the answers already filled in:

    cfg["camera_model"]    = _prompt("camera / phone model", "iPhone")
    cfg["mount_height_cm"] = _prompt("camera height above the surface, cm", 80.0, float)
    cfg["backdrop"]        = _prompt("backdrop (matte, dark, contrasting)", "dark green matte")
    cfg["room"]            = _prompt("room / location name", "studio")

and then asked the nine calibration readings as `_prompt(..., "y", _bool)`. An operator holding
Enter froze a complete, hash-attributed rig describing an iPhone 80 cm above a dark green matte
backdrop in a studio, and recorded that the board had been checked for coplanarity and the daylight
excluded. None of it had been looked at. `validate_setup`'s emptiness check — which the API has had
since `{}` was found to freeze an empty rig — could never fire, because a default is never empty.

The single measurement that had no default was the board-square length, and its comment says exactly
why: *"Pre-filling n * 25.0 mm offered the answer that passes, so pressing Enter recorded a
calibration nobody performed."* The principle was understood. It had been applied to one field.

Four findings, each now a test in `tests/test_pilot_evidence_honesty.py` that fails without its fix:

| # | what the system asserted for the operator | fix |
|---|---|---|
| 1 | eight rig facts, and nine calibration readings, out of the prompts' defaults | no defaults; both front doors freeze through `GATES.validate_setup` |
| 2 | a wall-clock float and the shutter's EXIF date, in the *committable* manifest | stripped from `sanitised()`; the private log keeps both |
| 3 | `protocol_audit.py` saw 15 of 19 `[FILL]`s, 2 of them prose | counted through `src/denimtwin/pilot/protocol_fields.py`, which also says what answers each |
| 4 | the capture watcher's state was `st_mtime` | content hash, written atomically |

Finding 3 is the one that fails open. The audit's only HARD rule fires on `if fills`, so filling the
thirteen fields the regex could see emptied the list while the mount height, the water temperature,
the detergent volume, the dryer setting and duration, the conditioning period and the thread-count
window were all still open. The guard stopped firing exactly when the remaining holes were the
physical settings the cut and the wash depend on.

A fifth issue was not an honesty failure but the same divergence as finding 1: the web app screened
measurements through `GATES.plan_safe_measurements` before sizing a plan and the CLI's seven call
sites did not, so a leg opening typed as 4000 instead of 40.0 expanded the hem series to 6589 frames
and took 3.26 seconds, quadratically, on every `status`, `plan`, `next`, `add`, `reuse`, `confirm`
and `intake`.

**What this round is evidence of.** One category, not a sweep: places where the software, rather
than the operator, is the source of a physical fact. It says nothing about the categories rounds 1
to 5 covered, and the standing rule stated above applies to it unchanged: each finding
is closed by a fix AND a scenario that fails without it.


## Round 7 — what a garment loses between the shears and the water

Round 6 asked whether the software ever writes down a fact nobody established. This round asked the
question the whole navigator exists for:

> If I put a real pair of jeans through this workflow tomorrow, cut them, wash them, and later
> discover an important piece of evidence was never captured, could the software have prevented it?

Five analysis passes and five adversarial dry runs, all executing against the code rather than
reading it. The findings divide into three kinds, and only the first was a surprise.

### Evidence the software destroyed after it had been collected

`store.fold` keyed measurements on the NAME alone, last write wins. Everything else in that function
is careful about this — the wash keeps `wash_plan_rewrites`, the rig keeps `setup_history`, feature
answers keep `feature_changes` — and measurements had neither a revision record nor a gate.

So the ordinary post-wash re-measurement, which the protocol requires, overwrote the pre-cut value
it was supposed to be compared *with*. Shrinkage is the difference between the two, and it stopped
being computable at the moment it was recorded. `measurements.complete` runs for every gate and
re-read the survivor, so `ready_to_finalize` then reported the evidence complete. Worse, the hem
macro series is SIZED from `leg_opening_cm`: a post-wash reading re-sized a BEFORE-state series
whose frames were already taken, on a garment that no longer existed in that state, so a session
that had printed READY acquired missing frames nobody could ever take.

Measurements now belong to a lifecycle state, and the lifecycle advances from the physical facts
already in the log — a recorded cut, a recorded wash — rather than from a marker somebody has to
remember to set. `state["measurements"]` is the pre-modification bucket, which is what all nine of
its readers meant.

### Evidence the specification never asked for

- **The cut itself.** PROTOCOL 3.1 says to record both lengths after cutting. Nothing did. That
  number is the ground truth the prediction is scored against, it can only be taken between the
  shears and the water, and afterwards the garment has shrunk: the length you measure is no longer
  the length you cut. Now `cut.performed_recorded`, required before the wash.
- **The washed garment.** No condition required it to be measured again. Now
  `measurements.post_wash`, with the same plausibility and tolerance arithmetic the pre-cut set
  gets — without it a post-wash tape read in inches finalised the experiment and published a 60%
  shrinkage.
- **Five wash-sensitive anomaly classes.** STAIN, TEAR, REPAIR, DISTRESS and PAINT had a before
  frame and no post-wash twin anywhere in the 290-shot catalogue; only EMBROIDERY, LOGO, PATCH and
  PRINT_FADE had one. A stain lightens or sets, a tear propagates, a repair puckers — the
  specification's own note on INTAKE.FEATURE.REPAIRS says cotton and polyester repair thread shrink
  differently — paint cracks, distressing opens. The comparison the before frame was taken for
  could never be made.
- **The detector for exactly that.** `unmatched_changing_regions()` skipped every region carrying
  `can_change_by_cut`, justified as "its later evidence is on the offcut". That is true of the hem
  and false of the thigh, the knee, the selvedge runs and the anomaly zones, and it was true of
  every candidate, so the function returned `[]` for this specification under every input. It now
  reports, and every region it names carries a recorded decision — `offcut` where the geometry says
  so, `open` where nobody has decided. **Nineteen are open.** They are listed by
  `tools/check_shotplan.py` and they are an owner decision, not a solved problem.
- **The other leg.** Six shots use `min_reps` to mean a different physical subject — repeat 2 is the
  other leg, or the unrolled cuff. Nothing bound a repeat to its subject, and `region_id` is copied
  from the shot, so the right leg's hem was filed under `hem_left_front` and two photographs of the
  same leg satisfied both. The software cannot tell legs apart from pixels, so it now asks, and the
  answer is bound to each photograph by the same machinery as every other per-frame claim.
- **The post-wash re-lay series.** The before arm chains `relay_after` so each frame follows a real
  re-lay; the post-wash arm carried neither flag, so eight photographs of one lay satisfied all
  eight frames and the independence check was never emitted. The two spreads are what separate
  shrinkage from laying variance, and only one of them was being measured.

### Evidence a correct operator could not supply

The mirror image, and the easier failure to miss. `ready_to_wash` and `ready_to_finalize` had **no
positive control at all** — every scenario touching them asserted only that they refuse, so nobody
had ever shown a complete, correct session can open either. Both now have one. Separately, any edit
to the shot plan stranded every open session on `spec.bound` forever, and the remedy its message
named was not something any command could do.

### And the mistakes this round introduced

Three of the fixes above were themselves wrong, and the dry runs found them:

- Instance identity was ordered by annotation id, so frame identity lived in a SORT POSITION. Naming
  a missed tear `TEAR.00`, or typing ids without leading zeros until there were ten, retroactively
  re-labelled photographs taken hours earlier. It is ordered by the log's own append-only sequence
  now, so a new annotation can only take a new slot.
- A measurement filed under a mistyped `--state` was recorded as a log INTEGRITY problem, which
  `log.intact` refuses on permanently. One wrong flag bricked the garment forever, because an
  append-only log cannot un-append.
- `pilot.py reuse` copied the source frame's annotation wholesale, so a photograph of one tear was
  filed as evidence for another and positively asserted it was of the first.

**What this round is evidence of.** The same narrow thing as the others: these are the attacks that
have been tried. It is not a claim that the evidence set is now complete — nineteen regions have no
post-wash frame and no decision, and that is written down rather than fixed.


## Round 8 — what survived the per-frame fixes, and a review harness that failed open

Round 7's own fixes were the target. The handoff into this round reported a green suite, a green
real-plan run, and three independent false-READY paths found in code that had already survived a
review — two of them introduced by attempted fixes. It also reported something about the review
process itself: several refuter agents had become unavailable on a session limit, and the harness
had counted their findings as dismissed.

That last defect is the one this round has to record first, because it happened again. Ten
falsification lenses were dispatched, each with a precise invariant, a file set, an output schema
and a requirement to produce an executable reproduction; every finding was to be judged by three
adversarial verifiers with distinct sub-lenses. **Nine lenses reported. One -- verification
profiles and CI claims -- never ran. Of roughly a hundred and seventy verifier agents, all but a
handful died on a session limit.** Exactly one finding carries two independent CONFIRMED verdicts.
Every other finding in this round was reproduced or refuted by the primary agent alone, and that
is recorded here as what it is: not independent review. The unavailable lens is unavailable, not
passed.

| angle | reported | independently adjudicated |
|---|---|---|
| append-only folding and lifecycle monotonicity | 6 | 0 |
| deviation scope and time travel | 10 | 0 |
| positive/negative controls and vacuity | reported, all verifiers unavailable | 0 |
| human claims, evidence binding, stale confirmation | 3 | 0 |
| reuse reachability and the borrow ceremony | 4 | 1 confirmed |
| CLI / phone / service parity and printed remedies | 8 | 0 |
| concurrency, interruption, restart recovery | 6 | 0 |
| gate conditions read one at a time | 8 | 0 |
| the owner decision packet against the code | 10 | 0 |
| verification profiles, CI claims, reviewer semantics | **lens unavailable** | -- |

### What was reproduced and closed

Every one of these has a regression that fails on the code as it was, and each was reproduced
against the live checkout before it was touched.

**The same-command approval, five more times.** The claims a shot spells out had been closed
against `--confirm` on the ingest command: an approval arriving with the photograph is a HUMAN
outcome, not a PASS. Four checks asking exactly the same kind of question -- `ruler_visible`,
`garment_side`, `anatomical_region`, `camera_repositioned` -- still went straight to PASS on a
flag, and a fifth, `relay_independence`, took the operator's confirmation from the same flag as
its final step to PASS while the gate's own re-derivation refused to. Eighty shots in the committed
plan raise the first two together. One helper now, five call sites, and a structural test that
walks every read of the ingest assertions in `check_capture` and refuses any branch that reaches a
PASS. The self-test's positive controls had been pre-authorising the same five keys through the
same route; they clear them through the real confirmation model now and still open all three
gates.

**Three of the eight lifecycle states were outside both boundaries.** `captures.state_order`
named its ends by hand -- three states before the cut, two after the wash -- and `immediate_after`
and `offcut_before`, the only states that exist between the shears and the water, were in neither
tuple. The tape laid against the freshly cut inseam, the cut-edge macros and the offcut's dry faces
could all be skipped on cut day and filled afterwards from the washed garment with no blocker at
either later gate. The boundaries are derived from the specification's ordering now, there are two
of them, and only the direction that is physically impossible is refused.

**A borrowed frame carries its own state.** `pilot.py reuse` compared subjects and instances and
never compared lifecycle states, so one command copied the pre-cut bytes into the post-wash slot;
`captures.state_order` judged the copy's log position, which really was after the wash, and
reported that every photograph agreed with the log. This is the one finding with two independent
confirmations. The command refuses it before writing; the gate tests the source frame's state
against the slot's, and refuses when the cut or the wash lies between them.

**"Treat those frames as absent" did not.** Both per-frame acknowledgements ended their blocker
with that sentence, both conditions honoured the acknowledgement, and `captures.required_complete`
never read it -- so a photograph of the cut garment in an empty before slot went from blocked to
captured-and-passing with one typed line. Three lenses found it independently. The acknowledged
frame is missing evidence now, with its reason beside it.

**Ten deviation sites could be pre-registered.** `after` had a default, two sites passed it, and
the recorded reason for leaving the rest -- that each would need an invented answer to "when did
this departure exist" -- was wrong at every site but one: the answer was a sequence number already
in the log, and most blockers printed it. `after` is mandatory now; `spec_rebound` passes `None`
with its reason written beside it.

**The audit that crashes when it has something to say.** `tools/protocol_audit.py` appended its
one HARD finding to a list bound three lines later. Adding a `[FILL]` field -- the act the owner
packet asks for twice -- produced a NameError instead of a sentence, in an advisory check that
could not have gone red either way.

**The scientific profile did not run the scientific proof.** `verify.py --profile full` ran the
ordinary self-test, whose gate positive controls are on a four-shot fixture; the real 424-frame
plan ran only behind a switch no profile threw, and CI had never executed it. It runs under the
full profile now and under a separately named CI job, and the workflow file is parsed, not grepped,
to prove it. A required check that could not run also exited 0; it exits 2.

**The aggregate upload ceiling, built without a number.** Accounting before the read, release on
every exit, 503 over budget, the value read from the environment with no default, and `serve
--lan` refusing to start until the owner sets one. The number is still decision D5.

### What this round is evidence of

Less than the count suggests, and the reason is above the table. One round of independent
falsification was attempted and did not complete; the primary agent's reproductions are real but
are not a second pair of eyes. The rate of discovery in the changed code has not converged: five
of the fixes above are to code that had survived a review, and two of them close holes underneath
fixes made in round 7. The standing rule is unchanged -- a finding is closed by a fix and a
scenario that fails without it -- and the standing claim is narrower than it was: **these are the
attacks that have been tried, and this round's independent adjudication is incomplete.**

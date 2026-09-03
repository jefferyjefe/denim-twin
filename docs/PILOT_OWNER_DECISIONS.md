# Decisions the software cannot make

Everything in this file is a question the code has deliberately refused to answer. Each one was
reached by a check that could see something was missing and could not see what should be there, and
each is recorded here rather than resolved, because resolving it would mean inventing a physical
fact or settling a research question to make a gate go green.

Nothing here blocks a **simulated** run. Several of them block a **real** one, and they are marked.

## The register

Each decision has a stable ID, so a commit, a log entry or a conversation can name it without
quoting a heading that may be reworded. Three columns say what the sections below did not: whether
the choice can still be changed once capture has begun, what act freezes it, and how -- or whether
-- the software proves it was frozen before an irreversible act.

| ID | decision | reversible after capture begins? | what freezes it | how the system proves it was frozen before the cut or the wash |
|---|---|---|---|---|
| **D1** | the nineteen open post-wash regions, and the cut line they depend on | the region answers: yes, until the post-wash session ends -- every before-state twin is already in the plan, and a dedicated post-wash frame can still be taken while the washed garment exists; `omit` is the only answer that is irreversible once the garment is gone. The cut line: no -- it is the cut | `protocol/shotplan/regions.json` (each region's decision `status`; for `covered`, `also_covers_regions` on the `POSTWASH.WHOLE.*` shots in `shotplan.json`), reported by `tools/check_shotplan.py`. The cut line: `tools/pilot.py cutspec <G> --inseam N`, per garment | **It does not.** No gate condition reads `spec.undeclared_changing_regions()`. `tools/check_shotplan.py` is a required check in `tools/verify.py`, and it is satisfied by a decision recorded as `open`. `precut` will print READY TO CUT with all nineteen undecided. The cut line is bound per garment by `cut.specified` before `precut`, but nothing freezes it pilot-wide |
| **D2** | the thirteen `[FILL]` field lines in `protocol/PROTOCOL.md`; one (`thread count within a [FILL] mm window`) answered by nothing | the document: yes. A rig freeze or a wash record that supplied the same fact on the day: no -- the log is append-only | editing `protocol/PROTOCOL.md`; audited by `tools/protocol_audit.py` | Twelve are proved at the point of use, not in the document: `gates.REQUIRED_SETUP_FIELDS` has no defaults and the wash record demands its own values, so a real session cannot freeze the rig or record the wash without them. The thirteenth has no consumer, so nothing can prove it. `protocol_audit.py` is an **advisory** check in `verify.py`: it cannot fail a build |
| **D3** | whether `mass_grams` and `fabric_thickness_mm` are re-measured post-wash | adding a post-wash measurement: yes, while the washed garment exists. Its pre-cut counterpart: no -- that garment no longer exists | one line in `gates.POST_WASH_MEASUREMENTS`, plus a named location in `PROTOCOL.md` for thickness | `measurements.post_wash` refuses `ready_to_finalize` without every entry in that dictionary. Whatever is in it is enforced; whatever is not is not |
| **D4** | -- not a decision: two things the owner must run by hand; see section 4 | | | |
| **D5** | the aggregate ceiling on upload bytes held in flight | yes, at any time -- it is configuration, not evidence | the environment variable `PILOT_MAX_INFLIGHT_UPLOAD_BYTES`, in bytes, on the machine running `serve` | `tools/pilot.py serve --lan` **refuses to start** (exit 2) while the variable is unset, and names this decision. A malformed value, zero, or a value below one permitted upload is refused on loopback too. Over budget, an upload gets 503 and is not recorded. There is no default: the accounting and the refusal are built, the number is not |
| **D6** | the deviation ceremony: one command per frame, and whether that is the right shape | yes -- it is the shape of a command, not a recorded fact; but every deviation already recorded stays in the log | the `deviation` sub-command's own argument set in `tools/pilot.py` | Every `deviation_covers` site now requires a deviation to postdate the departure it excuses (one exception, `spec_rebound`, whose departure is an edit to a file the log cannot date). A per-frame acknowledgement makes the frame **absent** for `captures.required_complete`, as its blocker always said. Neither is a proof the ceremony is right; both are proofs it cannot be pre-registered |

---

## 1. Nineteen post-wash regions with no frame and no decision

`tools/check_shotplan.py` reports 39 regions that are photographed before the wash, change with
washing, and have no frame in any later state. Twenty carry a recorded decision — they leave the
garment with the offcut, and their post-wash evidence is in the `offcut_before` / `offcut_after`
states. Nineteen are recorded as `open`: nobody has decided whether the post-wash whole-garment
overheads are sufficient for them or whether each needs a dedicated frame.

The question is the same for all nineteen, and it has three answers:

| answer | what it means | what changes in the plan |
|---|---|---|
| **covered** | the eight post-wash whole-garment overheads (`POSTWASH.WHOLE.F00.R1-R5`, `POSTWASH.WHOLE.B00.R1-R3`) resolve this region well enough to compare against its before frame | add the region to those shots' `also_covers_regions`; `unmatched_changing_regions` stops reporting it; no new photography |
| **dedicated frame** | the region needs its own post-wash frame at its own framing | add one `POSTWASH.*` shot per region; each costs one frame |
| **omit** | this region's wash response is not part of the experiment | record the decision with `status` other than `open`; the comparison data is knowingly absent |

There is no fourth answer and no default. `spec.undeclared_changing_regions()` enforces only that a
decision EXISTS, never which one — "whether a given region needs a post-wash frame is a judgement
about the protocol; whether somebody has made that judgement is a fact about the document."

### The table

`before frames` are the twins each region would be compared against. Positions are from
`protocol/shotplan/regions.json`, whose viewbox is `0 0 400 800` with y increasing downward from
the waistband. **Nothing in the repository maps that schematic y to centimetres of inseam**, so the
positions below order the regions against one another and say nothing about where the shears go.

| region | y span | before-state twin frames | burden if dedicated |
|---|---|---|---|
| `unusual_seam_zone` | 52–780 | `BEFORE.ANOM.UNUSUAL_SEAM.I01.R1` | 1 frame |
| `outseam_left_upper_front` | 54–506 | `BEFORE.SEAM.OUTSEAM_L_UPPER.R1` | 1 frame |
| `outseam_right_upper_front` | 54–506 | `BEFORE.SEAM.OUTSEAM_R_UPPER.R1` | 1 frame |
| `asymmetry_zone` | 158–780 | `BEFORE.ANOM.ASYMMETRY.I01.R1` | 1 frame |
| `inseam_left_upper_front` | 262–506 | `BEFORE.SEAM.INSEAM_L_UPPER.R1` | 1 frame |
| `inseam_right_upper_front` | 262–506 | `BEFORE.SEAM.INSEAM_R_UPPER.R1` | 1 frame |
| `thigh_back_left` | 274–420 | `BEFORE.LEG.THIGH_BACK_L.R1`, `BEFORE.OBLIQUE.BL1/BL2` | 1 frame |
| `thigh_back_right` | 274–420 | `BEFORE.LEG.THIGH_BACK_R.R1`, `BEFORE.OBLIQUE.BR1/BR2` | 1 frame |
| `thigh_front_left` | 274–420 | `BEFORE.LEG.THIGH_FRONT_L.R1`, `BEFORE.OBLIQUE.FL1/FL2` | 1 frame |
| `thigh_front_right` | 274–420 | `BEFORE.LEG.THIGH_FRONT_R.R1`, `BEFORE.OBLIQUE.FR1/FR2` | 1 frame |
| `knee_back_left` | 420–580 | `BEFORE.OBLIQUE.BL3` | 1 frame |
| `knee_back_right` | 420–580 | `BEFORE.OBLIQUE.BR3` | 1 frame |
| `knee_front_left` | 420–580 | `BEFORE.LEG.KNEE_L.R1`, `BEFORE.OBLIQUE.FL3` | 1 frame |
| `knee_front_right` | 420–580 | `BEFORE.LEG.KNEE_R.R1`, `BEFORE.OBLIQUE.FR3` | 1 frame |
| `texture_mid_leg_front_left` | 475–537 | `BEFORE.TEX.FRONT_L_MID.R1` | 1 macro |
| `texture_mid_leg_front_right` | 475–537 | `BEFORE.TEX.FRONT_R_MID.R1` | 1 macro |
| `selvedge_outseam_left` | 570–780 | `BEFORE.HEM.LEFT.SELVEDGE_AT_HEM.MACRO`, `BEFORE.SEAM.SELVEDGE_L.R1` | 1 macro |
| `selvedge_outseam_right` | 570–780 | `BEFORE.HEM.RIGHT.SELVEDGE_AT_HEM.MACRO`, `BEFORE.SEAM.SELVEDGE_R.R1` | 1 macro |
| `previous_alteration_zone` | 700–782 | `BEFORE.ANOM.PREV_ALTERATION.I01.R1`, both `BEFORE.HEM.*.PREVIOUS_ALTERATION.MACRO` | 1 macro |

### What the frame would measure, and whether anything already requires it

**The observable is the same for all nineteen**, which is why they are one decision and not
nineteen: how that region of cloth responded to the wash, read against its own before-state frame.
`regions.json` marks every one of them `can_change_by_wash: true`, which is what put them on this
list; what changes is colour, surface texture and local dimension, and the comparison is only
possible if a later frame exists at a framing close enough to the earlier one to be compared with
it.

**Nothing already requires any of them.** That is the finding, not an omission in this table. Their
recorded status is `open`, and `spec.undeclared_changing_regions()` — the check that can be
enforced — is satisfied by the existence of that record. No shot in any later state names them in
`region_id` or in `also_covers_regions`; if one did, they would not appear here at all, because
that is precisely the test `unmatched_changing_regions()` applies. No claim in `docs/claims` and no
line of `PROTOCOL.md` names them either.

**What omitting them costs** is also uniform: the before/after pair for that region cannot be
formed. Every one of them has a before frame already in the plan (the table above lists them), so
omission does not save the before-state work — it strands it. That is the argument for `covered`
over `omit` wherever the whole-garment overheads really do resolve the region, and it is an
argument the owner has to settle by looking at one of those overheads, not one the software can
make.

Burden: every shot in the plan carries an `est_seconds`, ranging 45–300 with a median of 80. At the
median, nineteen dedicated frames is a little over half an hour of the post-wash session; the six
macros in the list are the expensive end of that range.

### The thing to resolve first, because it changes several rows

**The nineteen are not all above the cut line, and the twenty already-decided ones do not agree
with the sentence that decided them.** Their recorded reason is *"below the cut line at a
shorts-length cut"*, and every one of them sits at y ≥ 506 — the knee. But nine of the nineteen
*open* regions occupy the same band or lower:

- `selvedge_outseam_left` / `_right` (570–780) and `previous_alteration_zone` (700–782) lie
  **entirely** inside the band where `shin_front_left` (580–762) and the hem regions (690–784) are
  already recorded as leaving with the offcut. Three regions.
- `knee_back_left` / `_right` and `knee_front_left` / `_right` (420–580) and
  `texture_mid_leg_front_left` / `_right` (475–537) straddle 506. Six regions.

Two more — `unusual_seam_zone` (52–780) and `asymmetry_zone` (158–780) — span the whole garment
and so extend below the band as well, but they are whole-garment zones rather than a place on a
leg, and the cut divides them rather than removing them.

Their recorded reason says they *"stay on the garment through the wash"*. For at least the first
three that cannot be true at the same time as the offcut decisions.

The reason it cannot be settled here is that **the cut line is not frozen anywhere**.
`target_inseam_cm` is supplied per garment on the command line (`pilot.py cutspec --inseam N`);
`protocol/PROTOCOL.md` does not fix it, and `[FILL]` does not cover it. So which regions leave with
the offcut is a function of a number that does not yet exist, and any answer written now would be
an answer for a cut nobody has committed to.

**Owner action, in order:**

1. Decide `target_inseam_cm` for the pilot, or state the band it will fall in.
2. Re-read the twenty `offcut` decisions against that number — the y ≥ 506 boundary they used is
   the knee, and a shorts-length cut is well above it.
3. Then answer covered / dedicated / omit for the nineteen. Several will collapse into the offcut
   set once (1) is fixed.

Nothing has been applied. The mechanical entailment that would let three of them be settled here —
"a region occupying the same band as one already declared below the cut line is also below it" —
depends on the boundary those decisions used, and that boundary is itself in question.

---

## 2. The `[FILL]` fields in `protocol/PROTOCOL.md`

Nineteen occurrences on thirteen field lines, enumerated by `protocol_fields.fields()`. (A plain
grep finds twenty-one occurrences on fifteen lines; two of them are sentences in the preamble
describing the convention, and `fields()` excludes them because they are not fields.)
`protocol_fields.COVERAGE` already classifies them, and its three classes are the answer to
"who fills this":

### (a) Answered by the navigator at capture time — and one whose value is already in the repository

Twelve of the thirteen field lines are marked `session`, `cut` or `wash` in `COVERAGE`: the rig freeze,
the cut record or the wash record captures the same fact on the day, into the log, hashed against
every photograph it applies to.

| protocol line | recorded as |
|---|---|
| Background (28) | `session` → `backdrop` |
| Calibration board (29) | `session` → `board_square_measured` |
| Lighting (30) | `session` → `lighting` |
| Camera, mount height (31) | `session` → `camera_model` / `mount_height_cm` |
| Lay protocol (32) | `session` → `leg_gap_cm` |
| Cut tool (64) | `cut` → `cut_tool` on the cut record |
| Machine (70) | `wash` → `wash.machine` / `wash.location` |
| Cycle, temp, spin (71) | `wash` → `wash.cycle` / `water_temp_c` / `spin_rpm` |
| Detergent (72) | `wash` → `wash.detergent` / `detergent_ml` |
| Load (73) | `wash` → `wash.filler_load` |
| Dryer (74) | `wash` → `wash.dryer_method` / `dryer_setting` / `dryer_minutes` |
| Conditioning (75) | `wash` → `wash.conditioning_start` / `conditioning_end` |

Of these, exactly one has a value that **already exists in the repository and could be
transcribed**: the calibration board. `protocol/charuco_board.json` fixes it, the generated runbook
already prints **8 × 11 squares at 25.0 mm**, and `gates.rig.board_square_measured` checks the
printed squares against 25.0 mm within 0.5 over a run of at least four whole squares. Writing that
into `PROTOCOL.md` is transcription, not decision — but it is still an edit to a frozen document
and is the owner's to make.

The other eleven are facts about hardware in a room. `gates.REQUIRED_SETUP_FIELDS` deliberately has
no defaults for any of them — *"a default here is a measurement nobody took, attached by the hash to
every photograph in the session"* — and the same argument applies to writing one into the protocol
before the rig exists.

**Does not block a simulated run. Blocks a real one**, not because the document needs them but
because the rig freeze and the wash record will demand the same facts on the day.

### (b) The one field classified `open`

**Line 82: "thread count within a `[FILL]` mm window".** `protocol_fields.COVERAGE` marks it
`open`, whose definition in that file is: *"nothing in the navigator answers this. It is a standing
decision the owner has to make and write down, and it blocks the protocol being frozen."* It is the
only one of the thirteen so marked.

**What the decision controls.** PROTOCOL §5 measures three things at every 2 cm position around each
hem loop after the wash: fray depth, thread count, and edge curl. Fray depth and edge curl are both
defined with an explicit window — *"within ±5 mm of the position"*. Thread count is not. So the
window is what makes "thread count" a count OF something: how much of the cut edge is sampled at
each position. §5 also requires **two annotators on ≥20% of garments**, and two people counting at
one position without an agreed window are not measuring the same quantity — the inter-annotator
agreement that clause exists to establish cannot be computed.

**What depends on it today: nothing.** There is no thread-count consumer anywhere in
`src/denimtwin/pilot/`, no property for it in `protocol/shotplan/shotplan.schema.json`, and no gate
condition reads one. That is the useful fact — **choosing it is what makes it load-bearing**, and
until then a thread count recorded on the day has no defined meaning and no place to be stored.

The smallest set of options, and what each would require:

| option | what it means | what it would add |
|---|---|---|
| **match the others: ±5 mm** | the same window fray depth and edge curl already use, giving one sampling geometry for all three | a schema property carrying the window; a per-position measurement field; nothing new in `hem.py` — the macro resolution is already set by fray, not by this |
| **a different explicit window** | thread count is sampled over a wider or narrower span than fray depth | as above, plus a check in `hem.py` that the macro resolution resolves individual threads across the chosen span — `mm_per_px_ceiling(fray_resolution_mm=0.5, px_per_feature=10.0)` is sized for fray, not for counting yarns |
| **count per unit length** | record threads-per-cm rather than a count over a fixed window | a unit change in the measurement definition; removes the window from the protocol but requires the span actually counted to be recorded per reading |
| **defer** | record the count with the window each annotator used, and treat the window as data | no schema change now; the ≥20% two-annotator agreement in §5 becomes uninterpretable, so this is the option that costs a clause of the protocol |

**No number is proposed.** The repository contains no thread-count measurement of any garment and
cites no source for one; `docs/LITERATURE.md` is not referenced for it anywhere.

## 3. Should `mass_grams` and `fabric_thickness_mm` be re-measured post-wash?

Not changed, and not decided here. `gates.POST_WASH_MEASUREMENTS` currently requires
`waist_cm`, `thigh_cm`, `front_rise_cm`, `back_rise_cm` — four dimensions, no mass, no thickness.

### `mass_grams`

**The confound is decisive and is about the cut, not the wash.** The garment is cut between the two
weighings, so the pre-cut mass and the post-wash mass are masses of *different objects*. Their
difference is dominated by the two offcuts, not by anything washing did. A post-wash mass of the
garment alone is not comparable to the pre-cut mass of the whole garment by any arithmetic the
system has, because the offcuts' pre-cut mass was never separately measured.

What *would* be comparable:

- garment + both offcuts, weighed post-wash, against the pre-cut whole-garment mass — but the
  offcuts go into two different wash conditions (`offcut.WITH_GARMENT` and `offcut.SEPARATE_LOAD`),
  so they are not all available in the same state;
- each offcut weighed immediately after the cut and again after its own wash — a clean
  before/after on one object, in one condition. **This is the measurement that would actually
  answer a question**, and it is a measurement of the offcut, not of the garment.

Equipment: a scale readable to the tolerance `gates.MEASUREMENT_TOLERANCE` implies for
`mass_grams`; the pre-cut protocol already requires one, so nothing new.

Changes each option would need:

- *add `mass_grams` to `POST_WASH_MEASUREMENTS`* — one line in `gates.py`; but it would require a
  number that cannot be compared to the one it is stored beside, which is the failure the
  state-bucketing was built to prevent. Not recommended without the offcut path below.
- *weigh the offcuts before and after* — new measurement names (there is currently no per-offcut
  measurement vocabulary), a place for them in `store.fold`'s offcut projection, `offcut_before`
  and `offcut_after` buckets in `measurements_by_state`, and a new gate condition. This is the
  larger change and the only one that yields a comparable pair.

### `fabric_thickness_mm`

**Not confounded by the cut.** Thickness is an intensive property measured at a point on the cloth,
so a post-wash reading at the same location is directly comparable to the pre-cut one, and the
difference is a real wash effect (shrinkage draws yarn together; thickness is the axis the
dimensional measurements do not capture).

The confounds are about *where* and *when*: thickness varies across the garment, so the reading is
only comparable if it is taken at the same place, and the protocol does not currently name a
location for it. It is also moisture-sensitive, which the conditioning step
(`[FILL] hours` at line 75) exists to control and which is itself unfilled.

Equipment: a thickness gauge; the pre-cut protocol already requires one.

Changes it would need:

- one line adding `fabric_thickness_mm: 2` to `gates.POST_WASH_MEASUREMENTS`;
- a named measurement location in `PROTOCOL.md` — without it the two readings are not of the same
  place and the comparison is not one;
- the conditioning duration at line 75, or the reading is of a damp garment.

**Recommendation withheld.** `fabric_thickness_mm` is the stronger candidate of the two and the
cheaper change, but it depends on two things that are themselves unfilled, and adding it to the
gate before they exist would make the finalize gate demand a number nobody can take correctly.

---

## 4. Two things the owner must run, that CI does not

**`tools/pilot.py selftest --full`, before a real cut.** It is the only thing that drives one
garment through the entire 424-frame plan and asserts that all three gates OPEN, and the only place
the sixteen single-fault negative controls run. Measured on the development machine it took
seventeen minutes of wall clock, not the hour this paragraph used to claim; it still writes
gigabytes of synthetic frames. Two things changed because of that measurement: `tools/verify.py
--profile full` now runs it (the ordinary `ci` profile still does not), and
`.github/workflows/tests.yml` has a separate job, `real-plan-proof`, that runs it on pushes and is
deliberately not the ordinary build -- the two prove different things and must not share one green
tick. `tests/test_verify_readiness_contract.py` asserts both of those against the registered check
graph and the parsed workflow, not against source text. `tests/test_pilot_selftest.py` asserts the
controls still exist and still name every condition they are supposed to close, so they cannot be
quietly deleted. None of that is a substitute for running it on the machine that will be on the
bench, before the cut.

**A rehearsal through the two front doors, not only through the bench.** The self-test drives the
same module functions the CLI and the phone call, and since this round it goes through the same
confirmation model. It does not press the buttons. Three things worth doing by hand on a scratch
garment (`PILOT_GARMENTS=/tmp/rehearse`), because each was a defect found by reading rather than by
a test:

- type a wrong digit into `cut-performed` and try to recover from it;
- revise the shot plan mid-session -- add one `requires_human` line to a shot already photographed
  -- acknowledge the rebinding the way the block tells you to, and check the gate still refuses;
- run `measure` from the phone in the window between the physical wash and the typed `wash_actual`.

---

## 5. One resource limit that needs a number, and the number is yours

`MAX_UPLOAD_BYTES` caps a single upload at 200 MB. Nothing counts bytes **in flight**, and the only
other ceiling is `max_connections = 32`. So the server permits, by construction, 32 uploads holding
their read buffers at once.

Measured on this machine, against the real server over real sockets:

| what was run | result |
|---|---|
| one upload, heap peak during parse | 4.00x the body, at 4 MiB, 16 MiB and 64 MiB alike (now 2.00x) |
| 8 concurrent 48 MiB uploads | all 200 OK, `refused_connections=0`, 628 MiB resident |
| 6 concurrent 200 MiB uploads | all six 200 OK, `refused_connections=0`, 1.80 GiB resident for 1.2 GiB on the wire |

Two things were fixed without needing a decision: the parse no longer copies the photograph three
extra times, and an upload that ends early is now refused instead of being ingested as a whole
photograph. What remains is the sustained hold — the read buffer lives for the whole upload, and
`_Handler.timeout = 30` is a per-recv socket timeout, not a request deadline, so a client trickling
bytes holds its buffer far longer than thirty seconds. 32 x 200 MB is 6.4 GB of resident buffers
that nothing refuses.

**The decision:** what should the machine running the capture app be allowed to hold at once?

It is left open because every way of closing it is a number chosen from the outside — an aggregate
byte budget, a smaller upload cap, a limit on concurrent uploads as distinct from connections, or a
request deadline. Any of them would be invented here rather than derived from anything in this
repository, and picking one silently would put a threshold into the capture path that no measurement
supports.

What is known, and what a decision needs:

- the largest single file the protocol expects is a motion clip, not a still;
- the pilot is one operator with one phone, so the realistic concurrency is one, occasionally two;
- refusing is safe. A refused upload is a missing photograph, and a missing photograph makes the
  gate refuse. This cannot become a false READY in either direction;
- 32 concurrent connections is not itself the risk — the connections are cheap, the buffers are not.

A defensible answer is likely "cap concurrent *uploads* at a small number and give the rest a 503",
which reuses the refusal the server already knows how to give. But the small number is a choice
about the machine on the bench, and that machine is not described anywhere in this repository.

**What has been built since, without choosing the number.** `server.py` now reserves an upload's
bytes (at the measured 2x parse ratio) before reading its body and releases them however the
request ends; over budget is a 503 that says the photograph was not recorded. The budget is read
from `PILOT_MAX_INFLIGHT_UPLOAD_BYTES`, and there is deliberately no default:
`DEFAULT_INFLIGHT_UPLOAD_BYTES = None`, asserted by a test. `serve --lan` refuses to start while it
is unset and prints this section's number; a malformed value, zero, or anything below one permitted
upload (`MAX_UPLOAD_BYTES`) is refused on loopback as well, because a budget that can never admit
one motion clip loses evidence rather than protecting it. Loopback with the variable unset behaves
exactly as before, so nothing in development or in the self-test needed the decision. The decision
is now the only thing missing, and the server says so at the one moment it matters.

---

## 6. What a deviation may excuse, and the shape the answer took

Two gate conditions read a recorded deviation as an excuse: `captures.instance_identity` (a
photograph filed against a slot the plan says is a different physical thing) and
`captures.state_order` (a photograph filed in a state the log's own order contradicts). Both
matched on the deviation's KIND and FIELD only.

That made one record a session-wide, retroactive amnesty. It could be written at intake, before a
single photograph existed, and it then cleared its condition for every frame in the session — in
both directions in time. Reproduced end to end on `captures.state_order`: a required `before`
photograph is never taken, the garment is cut and washed, the operator photographs the cut washed
garment and files it as the missing `before` frame, and **`ready_to_wash` and `ready_to_finalize`
both return ready with no blocks at all**. The evidence for that shot does not exist and physically
cannot.

Both excuses are now per-frame. A deviation has to NAME the frame in `--actual`, and it has to be
recorded after that frame — and, for an instance, after the last revision of the annotation the
frame is bound to. A record written before the departure is a permission slip for something that
has not happened yet, which is the one thing the module says a deviation must never be.

**The decision this leaves you.** The wording is a convention this change introduces:

```
tools/pilot.py deviation <GARMENT> --kind protocol --field capture_order \
    --actual '<SHOT_ID> r<N>' --reason '<what happened>'
```

one per affected frame. Both front doors already accept a free-form `actual`, so nothing in the
schema or the CLI changed, and each blocker now prints the exact line for each frame it is still
blocking on. What is worth your eye is whether that is the right ceremony for the situation it
covers: on cut day, an operator who has genuinely lost a `before` frame must type one command per
frame, and the frames are then treated as acknowledged rather than as present.

The alternative — a single deviation that names several frames — was not built, because a list is
harder to read back as evidence months later than one record per departure. If you would rather it
took a list, that is a change to make deliberately, not one to discover at the table.

The other ten `deviation_covers` call sites in `gates.py` were left unbounded when this section was
first written, with the reasoning that each needs its own answer to "when did this departure come
into existence" and inventing one per site is how a guard stops meaning anything. That reasoning
did not survive reading the sites. At every one but `spec_rebound` the answer is a sequence number
already in the log -- the revising reading's entry, the second cut record's entry, the second wash
record's entry, the rewrite's entry, the re-freeze's entry, the out-of-range reading's entry -- and
most of the blockers were already printing it. All of them are bound now; `after` has no default,
so a new consumer has to answer the question to compile; and `spec_rebound` passes `after=None`
with its reason written beside it, because an edit to a file outside the log is genuinely something
the log cannot date. `tests/test_pilot_deviation_ordering.py` scans the parsed module for any call
that omits the answer.

Two things in this section are now stated more precisely than before. Each blocker prints the
deviation line for **at most four** of the frames it is blocking on, not for every frame; the rest
are counted. And a per-frame acknowledgement now does what the blocker's last sentence always
promised: `captures.required_complete` treats the acknowledged frame as **absent**. It had been
counting it as captured and passing, so a photograph of the cut garment filed into an empty before
slot went from blocked to accepted with one typed line -- the false READY the per-frame scoping was
built to close, one command per frame instead of one for the session.

**One waiver is still broader than its neighbours, and it is yours to look at.**
`post_wash_out_of_range` is now bound in time, but unlike `measurement_revised:<name>` it has no
per-measurement form: one acknowledgement still covers every out-of-range post-wash reading taken
before it. Giving it a per-name form changes a command that a blocker prints, which is a
vocabulary decision rather than a bug fix, and is left here rather than made.

---

## What this file does not contain

No rig setting, wash setting, measurement, tolerance, shrinkage band, thread-count window or
threshold has been invented, and no unresolved physical choice has been settled to make a gate
open. Where a value exists elsewhere in the repository it is cited rather than copied.

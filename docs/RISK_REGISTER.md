# Risk Register

| # | Risk | Why it matters | Mitigation | Owner | Status |
|---|------|----------------|------------|-------|--------|
| 1 | Reconstruction changes garment identity | Destroys core promise | Flat-lay first; manual landmark correction; unchanged-region metrics | lead | open |
| 2 | Too little physical data | Overfit / hallucination | Procedural models first; systematic paired collection | lead | open |
| 3 | Dataset leakage | Misleading results | Split strictly by garment_id | lead | open |
| 4 | Fraying is stochastic | Single image may be wrong | Predict distributions + calibrated ranges | lead | open |
| 5 | 3D consumes the year | No validated result | 2D baseline first; Gate 2 | lead | open |
| 6 | Neural rendering improves beauty not truth | False progress | Score vs real post-wash captures | lead | open |
| 7 | Wash protocol varies | Uncontrolled noise | Fix machine/cycle/detergent/load/dry | lead | open |
| 8 | Insufficient garment diversity | Fails on real users | Plan strata before acquisition | lead | open |
| 9 | Collaboration takes time | Delays components | Start pilot independently | lead | open |
| 10 | Scope creeps to bleach | Chemistry before geometry | Banned in year one | lead | open |
| 11 | Weak consumer demand | Tech success ≠ company | Parallel customer interviews | lead | open |

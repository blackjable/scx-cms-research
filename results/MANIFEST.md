# Raw experiment output

Every table in the paper and the delivery plan is a hand-transcribed
summary of one of these files. They are archived here because the
originals lived in a session scratchpad that does not survive, which
means the numbers could not be checked against their source.

Each file is the unedited stdout of the harness run that produced it,
including the parameters it printed at startup. Where a harness prints
per-repetition lines (`REP <n> <condition> ...`), the raw per-run values
are present and the summaries can be recomputed rather than trusted.

## Files

| file | what it is | n | notes |
|---|---|---|---|
| [`r2-gating-n15.txt`](raw/r2-gating-n15.txt) | round 2 gating comparison | 15 | **fixed condition order** |
| [`r2-count-attributable-n15.txt`](raw/r2-count-attributable-n15.txt) | count-blind control introduced | 15 | **fixed condition order** |
| [`r2b-flat-control-n8.txt`](raw/r2b-flat-control-n8.txt) | flat swept at 2/4/8ms | 8 | **fixed condition order** |
| [`r2c-prereg-n20.txt`](raw/r2c-prereg-n20.txt) | pre-registered round 2c | 20 | **fixed order**; voided on its gating precondition |
| [`r2d-randomised-order-n20.txt`](raw/r2d-randomised-order-n20.txt) | first run after the ordering fix | 20 | randomised order onward |
| [`r3-memory-sweep-n8.txt`](raw/r3-memory-sweep-n8.txt) | matched memory budgets | 8 | discrimination metric later found invalid |
| [`r4-identity-bestshot-n10.txt`](raw/r4-identity-bestshot-n10.txt) | identity keys, boost, sketch geometry | 10 | |
| [`r5-inflation-and-stable-sweep.txt`](raw/r5-inflation-and-stable-sweep.txt) | compare-mode inflation, both regimes | 3 | |
| [`r5b-verify-reversal-inertness.txt`](raw/r5b-verify-reversal-inertness.txt) | `mechanism=none` reference added | 15/8 | exposed that exact was inert, not discriminating |
| [`r6-sketch-variants-n3.txt`](raw/r6-sketch-variants-n3.txt) | conservative update, hash mix, plain map | 3 | LRU pathology confirmed here |
| [`r7-r9-throughput-mapcontrol-geometry.txt`](raw/r7-r9-throughput-mapcontrol-geometry.txt) | hackbench/cyclictest, LRU vs plain, geometry | 5/8/10 | |
| [`thesis-confirmation-n20.txt`](raw/thesis-confirmation-n20.txt) | 16 KB and 8 KB, stable | 20 | |
| [`o1-o4-budget-geometry-churning-n20.txt`](raw/o1-o4-budget-geometry-churning-n20.txt) | remaining budgets, geometry, churning | 20 | |
| [`headline-single-matrix-n20.txt`](raw/headline-single-matrix-n20.txt) | the headline pairing, one interleaved matrix | 20 | supersedes the cross-run version |

## Reading these with the necessary suspicion

**Anything marked "fixed condition order" carries a known systematic
bias.** The harness ran conditions in the same sequence every
repetition, so carryover from one condition landed on the same
neighbour every time -- bias that repetitions cannot average away. The
same configuration measured 21,664us or 14,000us depending on what
preceded it. Those files are retained because the retractions they
caused are part of the record, not because their numbers stand.

**Files before `r5b` used a discrimination metric that could not
distinguish a working tracker from an inert one**, because its
reference point (a count-blind penalty) is worse than taking no action.
Conclusions drawn from them were revised once a `mechanism=none`
reference was added.

The conclusions that survive are those re-established after both fixes:
`r5b` onward.

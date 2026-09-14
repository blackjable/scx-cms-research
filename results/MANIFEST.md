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
| [`r6-sketch-variants-n3.txt`](raw/r6-sketch-variants-n3.txt) | conservative update, hash mix, plain map | 3 | source of the withdrawn LRU claim (revision 12); the counts are correct, the mechanism attached to them was not |
| [`r7-r9-throughput-mapcontrol-geometry.txt`](raw/r7-r9-throughput-mapcontrol-geometry.txt) | hackbench/cyclictest, LRU vs plain, geometry | 5/8/10 | |
| [`thesis-confirmation-n20.txt`](raw/thesis-confirmation-n20.txt) | 16 KB and 8 KB, stable | 20 | |
| [`o1-o4-budget-geometry-churning-n20.txt`](raw/o1-o4-budget-geometry-churning-n20.txt) | remaining budgets, geometry, churning | 20 | |
| [`headline-single-matrix-n20.txt`](raw/headline-single-matrix-n20.txt) | the headline pairing, one interleaved matrix | 20 | supersedes the cross-run version |
| [`equivalence-n30-prereg.txt`](raw/equivalence-n30-prereg.txt) | pre-registered equivalence test, 15s runs | 30 | refuted the equivalence claim |
| [`excursion-rate-n60.txt`](raw/excursion-rate-n60.txt) | excursion rates and two mitigations | 60 | showed the excursions are not the sketch's |
| [`victim-shape-sensitivity-n15.txt`](raw/victim-shape-sensitivity-n15.txt) | four victim configurations | 15 | headline holds for 3 of 4; the 4th saturates the machine |
| [`lru-working-set-test.txt`](raw/lru-working-set-test.txt) | LRU vs plain hash at 42 slots, identity population varied | -- | overturned revision 12; harness `lru_test.py` |
| [`identity-turnover-n3.txt`](raw/identity-turnover-n3.txt) | distinct identities and turnover rate, both regimes | 3 | replaces figures whose original run was never archived; harness `measure_ids.py` |
| [`map-memlock-verification.txt`](raw/map-memlock-verification.txt) | which map the reported memory column describes | 1 | confirms 35.6 KB is the LRU map in use, so 4.3x stands |
| [`condition-subset-n20.txt`](raw/condition-subset-n20.txt) | same matrix with the pathological condition removed | 20 | null (0.99x, p=0.55); rules out subset as the cause too |
| [`sketch-variants-n10.txt`](raw/sketch-variants-n10.txt) | conservative update, hash mix, plain map at n=10 | 10 | means replicate; **never-undercount violation counts do not** |
| [`lru-working-set-n5.txt`](raw/lru-working-set-n5.txt) | LRU working-set test, five repeats | 5 | confirms revision 12 at 164x separation |
| [`refactor-verification-n20.txt`](raw/refactor-verification-n20.txt) | headline matrix re-run after the tracker-registry refactor | 20 | nothing moved beyond run-to-run noise |
| [`ordering-controlled-n20.txt`](raw/ordering-controlled-n20.txt) | fixed vs randomised condition order, everything else held constant | 20+20 | pre-registered; **found no ordering effect** and overturned revision 13 |

## Reading these with the necessary suspicion

**Files marked "fixed condition order" were long believed to carry a
systematic carryover bias. A controlled test found no such bias**
(`REVISIONS.md` revision 13,
[`ordering-controlled-n20.txt`](raw/ordering-controlled-n20.txt)). Running
conditions in a fixed sequence, with a ~90ms pathological condition
immediately before the measured one in every repetition, produced no
measurable difference against a randomised arm: medians 0.98x apart,
Mann-Whitney p = 0.86, and the fixed arm was the *less* variable of the
two.

The label is kept on those files because it accurately describes how
they were run, and because the retractions once attributed to it are
part of the record. It should no longer be read as "these numbers are
biased". What it now means is: these runs predate randomisation,
randomisation turned out to correct nothing measurable, and where they
disagree with later runs that disagreement is **unexplained** rather
than explained.

Randomised ordering is still used throughout and still recommended --
carryover is real in principle, and randomisation costs six lines and
converts any bias into noise that repetitions remove. It is insurance,
not a fix for a demonstrated fault.

**Files before `r5b` used a discrimination metric that could not
distinguish a working tracker from an inert one**, because its
reference point (a count-blind penalty) is worse than taking no action.
Conclusions drawn from them were revised once a `mechanism=none`
reference was added. This one is a real instrument fault and it stands.

So of the two corrections this archive was organised around, one held
and one did not. The conclusions that survive are those re-established
with a do-nothing reference in the matrix: `r5b` onward.

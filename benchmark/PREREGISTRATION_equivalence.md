# Pre-registration: equivalence of sketch @ 8 KB and exact @ 32 KB

**Committed before the data exists.** The git commit timestamp is the
evidence. Nothing below is to be revised after seeing results; if
something proves badly specified, the run is discarded and re-registered
rather than reinterpreted.

## Why this exists

The project's headline claim is that a Count-Min Sketch at 8.3 KB
delivers the same scheduling outcome as exact counting at 35.6 KB. The
evidence so far is that their ranges **overlap** — which means *no
difference was demonstrated*, not that no difference exists.

Those are different claims and the paper needs the second one. Absence
of a detected difference is weak evidence for equivalence, especially
here: the p99 distributions are wide on both sides (to 22,816us and
29,088us), and a wide distribution fails to demonstrate differences
easily and for uninteresting reasons.

An equivalence test with a margin declared in advance converts "we could
not tell them apart" into "they are the same within a stated bound", or
fails to, which is equally informative.

## Hypothesis

`sketch_8k_d2` (8.3 KB) and `exact_32k` (35.6 KB) produce equivalent
victim latency in the stable-identity workload, within a margin of 20%.

## Primary metric and test

**Metric:** victim p99 wakeup latency.

**Design:** conditions are interleaved within each repetition, so the
data is **paired** by construction, not by post-hoc choice. For each
repetition *i*, compute

    r_i = p99(sketch_8k_d2) / p99(exact_32k)

and work in log space, since a latency ratio is multiplicative and
right-skewed.

**Equivalence margin, fixed now:** **±20%**, i.e. the interval
`[0.833, 1.20]` on the ratio, `[ln 0.833, ln 1.20]` on the log-ratio.

Chosen because a 20% difference in tail latency is around the smallest
that would plausibly change a deployment decision, and because it is
tighter than the 12% difference already observed — so the test can fail.
A margin chosen to be comfortably wider than the observed effect would
prove nothing.

**Test:** TOST (two one-sided tests) at alpha = 0.05, implemented as a
90% confidence interval on the mean log-ratio. **Equivalence is declared
if and only if that entire interval falls inside the margin.**

Reported alongside, not as the test: the median ratio, and a
bootstrap 90% CI as a distribution-free cross-check. If the parametric
and bootstrap intervals disagree about the conclusion, equivalence is
NOT declared and the disagreement is reported.

## Secondary metrics (reported, not confirmatory)

- The same TOST on victim p50, same margin.
- The same TOST for `sketch_32k_d2` vs `exact_32k` — matched-memory
  control. These should be equivalent; if they are not, something is
  wrong with the comparison rather than with the memory claim.

## Sample size and run parameters

- **n = 30** repetitions, exceeding every N used in this project.
- **duration 15s** per measurement, up from 10s. p99 is estimated from
  the tail of the sample, so a longer run reduces its variance
  directly — the wide ranges are partly a sampling artefact, not only
  workload noise.
- Stable-identity workload (`--lifetime 60`), 128 churn slots,
  `--order-seed 41`, condition order randomised per repetition.
- `--penalty-ns 20287`, unchanged from its original derivation.
- Sketch geometry depth 2, per the geometry sweep.

No parameter is to be adjusted during or after the run.

## Pre-specified additional analyses

**Sketch stability.** One repetition in twenty previously showed the
sketch partially losing discrimination (p50 8,104us against a typical
3,900us). Across these 30 repetitions, count repetitions where
`sketch_8k_d2` p50 exceeds **6,000us** — roughly 1.5x the typical value
and well below the count-blind baseline's ~11,000us. Report the rate
with a 90% CI. This is characterisation, not a pass/fail criterion.

**Outlier check.** A previous run produced a `none` p99 of 635,904us,
two orders of magnitude above that condition's median. Report any
repetition where any condition exceeds 10x its own median, and whether
such outliers cluster in particular repetitions (which would indicate an
environmental disturbance rather than a scheduler property).

## What falsifies the claim

The 90% CI on the mean log-ratio extending outside `[ln 0.833, ln 1.20]`
on p99. In that case the honest report is that the two configurations
were **not shown to be equivalent within 20%**, and the memory claim
must be stated as "the sketch continues to function at a budget where
exact counting does not" — which the non-overlapping `exact_8k` result
already supports — without the equivalence figure.

## What this run does NOT address

Cross-architecture and bare-metal validation, energy, and workload
generality beyond this victim configuration. Those need hardware this
environment does not have, and remain open regardless of the outcome.

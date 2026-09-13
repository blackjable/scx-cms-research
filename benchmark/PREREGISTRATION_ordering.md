# Pre-registration: how large is the condition-ordering bias?

**Written while the run was in progress and before any of its output was
read.** Weaker than the equivalence pre-registration, which was committed
before the run started, and weaker again because the effect has already
been seen once observationally. Stated plainly rather than dressed up:
this fixes the analysis, not the expectation.

## Why this run exists

The ordering bias is the subject of blog post 01 and a methodological
finding in the paper. The evidence for it was a comparison between
`r2-count-attributable-n15.txt` and `r2c-prereg-n20.txt`, which differ in
**three** ways at once:

- condition order (fixed with `cms_none` adjacent, vs `exact` first)
- condition subset (4 conditions vs 3 — `cms_none` absent from the second)
- sample size (15 vs 20)

They are also separate runs on different days. That is an observational
comparison, and the project's own standard is to vary one thing. A claim
recommended to other benchmark authors should not rest on it.

This run holds everything constant except ordering: same four
conditions, same n=20, same parameters, same guest, back to back. The
only difference is `--fixed-order`.

## Conditions

`cms_none`, `cms_exact_penalty`, `cms_sketch_penalty`, `flat_4ms`.
`--penalty-ns 20287`, `--duration 10`, 128 churn slots at 200/s,
schbench victim 4 threads / 100 rps, n=20.

In the fixed arm the order is the declaration order, so `cms_none`
(p99 ~80ms) runs immediately before `cms_exact_penalty` in every
repetition — reproducing the original confound exactly.

## Primary metric

`cms_exact_penalty` p99, fixed arm against randomised arm. That is the
condition the original bias landed on.

## What is being claimed, and what is not

The claim is **not** that ordering shifts the centre of the
distribution. The observational comparison already suggested it does not:
medians 9% apart, means 22%, maxima 55%. The claim is that ordering
**fattens the upper tail**, which is where a p99 comparison lives.

## Statistics, fixed now

Reported together, because picking one after the fact is how the 55%
figure happened:

- median, mean and maximum of each arm, and the ratio of each
- coefficient of variation of each arm
- count of repetitions above 14,000us in each arm
- Mann-Whitney U with a two-sided p-value
- P(a random fixed-arm run exceeds a random randomised-arm run)

No statistic is to be dropped after seeing the data. If they disagree,
the disagreement is the finding and all of them are reported.

## Prediction

1. The fixed arm has a **higher CV** than the randomised arm.
2. The fixed arm has **more repetitions above 14,000us**.
3. The two arms' **medians are within 15%** of each other.
4. Mann-Whitney p < 0.05.

## What would falsify the current write-up

- If CVs and above-threshold counts are comparable across arms and
  Mann-Whitney is not significant, then ordering did not produce the
  effect attributed to it, and the difference between the two original
  files is the condition subset or ordinary run-to-run variation. Post
  01 and the paper's methodological finding would both need rewriting
  to say so.
- If the medians differ by much more than 15%, the "fattens the tail,
  does not move the centre" framing is wrong and should be replaced by
  whatever the data shows.
- A *smaller* effect than the observational comparison suggested is an
  expected outcome, not a failure: the observational comparison had
  three variables free and could have been inflated by any of them.

Either way the number that goes in the post is the one from this run,
not the larger one from the uncontrolled comparison.

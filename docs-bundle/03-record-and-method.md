# The record, the environment, the pre-registrations

REVISIONS.md is the most important document in the project: thirteen
claims made and withdrawn, each tied to the file that produced it and
the file that overturned it. The rest is the measurement environment and
the tests that were specified before their data existed.


==============================================================================
## FILE: results/REVISIONS.md
## path: results/REVISIONS.md
==============================================================================

# Record of revisions

Thirteen claims were stated during this work and later withdrawn. They
are listed here in full, each tied to the raw file that produced it and
the raw file that overturned it, so a reader can check both rather than
take the correction on trust.

This exists because the retractions are not incidental to the result --
they *are* a substantial part of it. Eight of the thirteen were caused by
a faulty instrument rather than by a faulty hypothesis, and identifying
each fault is what eventually made the final measurement trustworthy.
A record that showed only the surviving conclusions would misrepresent
how they were arrived at, and would hide the controls that turned out to
matter.

The remaining five are a different failure and are worth separating.
Revisions 9, 10, 12 and 13 were not measurement artefacts at all: the
numbers were correct and an untested mechanism was attached to them,
each time in the version that made the better story. Revision 11 is
different again -- not a measurement, but a sentence asserting evidence
that did not exist. No control catches either kind; only testing the
mechanism separately does.

**Revision 13 is the one to read first if you read only one.** It
withdraws the condition-ordering finding, which was the most confidently
stated and most widely applicable claim in the project, and it is the
fourth instance of the same error -- attaching an explanation to a real
disagreement without testing it. It also survived a correction pass that
was explicitly hunting for that error.

**This document is chronological.** Where a later revision supersedes
something stated in an earlier one, the earlier entry carries a forward
pointer rather than being rewritten; revisions 8 and 10 are the pair to
watch.

---

## 1. "Seed rotation mitigates the targeted-collision attack at heavy volume"

**Withdrawn:** did not replicate on a second run.
**Cause:** single-run result treated as a finding.
**Source:** Phase 1 / delivery plan §9.6 (predates this archive).

## 2. "+34.7% improvement"

**Withdrawn:** became −1.7% at n=15.
**Cause:** small-sample optimism. The only one of the twelve that more
repetitions alone would have caught.
**Source:** predates this archive.

## 3. "Acting on the tracked count improves tail latency 6.8x"

**Withdrawn:** a count-blind control reproduced ~82% of it.
**Cause:** the comparison (`mechanism=penalty` vs `mechanism=none`)
conflated *consulting the count* with *perturbing vtime at all*. None of
the four baseline tiers specified in the methodology could have caught
this, because all four vary the scheduler rather than varying only
whether the signal is used.
**Original:** [`r2-count-attributable-n15.txt`](raw/r2-count-attributable-n15.txt)
**Correction:** [`r2b-flat-control-n8.txt`](raw/r2b-flat-control-n8.txt), confirmed in
[`r2d-randomised-order-n20.txt`](raw/r2d-randomised-order-n20.txt)

## 4. "The sketch has a ~10% severe failure rate"

**Withdrawn:** 0 of 20 after the ordering fix.
**Cause:** fixed condition ordering. Carryover from a pathological
neighbour landed on the same condition every repetition.

> **[CAUSE SUPERSEDED by revision 13.]** The withdrawal stands -- the
> ~10% failure rate did not replicate, and 0 of 20 is 0 of 20. But the
> *reason* given here does not: a controlled test later found no
> measurable ordering effect at all, so "carryover" cannot be what made
> the failure rate vanish. Why it vanished is now unexplained, and the
> most likely remaining answer is that it was never there -- a
> small-sample artefact in the same family as revision 2. Nothing about
> the corrected measurement changes.

**Aggravating factor:** this was an *interesting* result with a
plausible mechanism (collisions inflating the protected task's count),
and it was accepted at n=20 with visibly less scrutiny than the
disappointing results received. It had been explicitly predicted to be
the finding *least* likely to be an ordering artefact. Revision 13 makes
this worse rather than better: the explanation that replaced it was also
adopted without test.
**Original:** [`r2c-prereg-n20.txt`](raw/r2c-prereg-n20.txt)
**Correction:** [`r2d-randomised-order-n20.txt`](raw/r2d-randomised-order-n20.txt)

## 5. "Exact counting beats the sketch at every memory budget"

**Withdrawn:** the metric could not distinguish a working tracker from
an inert one.
**Cause:** discrimination was measured against a count-blind baseline,
which is *worse than taking no action*. A tracker that had silently
stopped working therefore scored as well as one working perfectly.
Adding a `mechanism=none` reference -- absent from the original sweep --
showed exact counting at 85 and 21 entries was statistically identical
to doing nothing.
**Original:** [`r3-memory-sweep-n8.txt`](raw/r3-memory-sweep-n8.txt)
**Correction:** [`r5b-verify-reversal-inertness.txt`](raw/r5b-verify-reversal-inertness.txt)

## 6. "The sketch works down to 2.3 KB"

**Withdrawn:** at 2 KB every geometry is blunt.
**Cause:** reading p99 without p50. The tail improved 5x over inaction,
but the median had collapsed to the count-blind baseline's level, so
the sketch had stopped distinguishing tasks and was merely perturbing
them. The memory claim went from 15x to 4.3x.
**Original:** [`r7-r9-throughput-mapcontrol-geometry.txt`](raw/r7-r9-throughput-mapcontrol-geometry.txt)
**Correction:** [`o1-o4-budget-geometry-churning-n20.txt`](raw/o1-o4-budget-geometry-churning-n20.txt)

## 7. "Sketch at 8 KB matches exact at 32 KB" (as first stated)

**Withdrawn as stated:** the two figures came from different runs.
**Cause:** a cross-run comparison -- precisely the pattern revision 4
had already shown to be unsafe. The claim itself survived when
re-measured properly; the *evidence* for it did not.
**Original pairing:** [`thesis-confirmation-n20.txt`](raw/thesis-confirmation-n20.txt) +
[`o1-o4-budget-geometry-churning-n20.txt`](raw/o1-o4-budget-geometry-churning-n20.txt)
**Correction:** [`headline-single-matrix-n20.txt`](raw/headline-single-matrix-n20.txt)

---

## What the pattern shows

*(Written after revision 7. Revisions 8 to 13 follow below and the
counts in this section are from that moment, not the final tally --
which is thirteen, eight of them instrument failures. Two rows of the
table below were themselves later withdrawn; see the notes.)*

More data would have caught exactly one (#2). The rest required a
control or an instrument that did not exist yet:

| fault | fix |
|---|---|
| ~~fixed condition ordering~~ | ~~randomise per repetition, seeded~~ — **withdrawn, revision 13.** No ordering effect exists here. Randomising is still worth doing, but it fixed nothing measurable |
| metric with a broken zero point | add a do-nothing reference |
| ratio with a collapsing denominator | measure against truth, not a dying comparator |
| workload model wrong by 4x | instrument the distribution instead of inferring |
| ~~`LRU_HASH` not behaving as named~~ | ~~control with a plain hash at equal capacity~~ — **withdrawn, revision 12.** The control was useful; the fault it was built to catch was not real |
| cross-run comparison | put both conditions in one interleaved matrix |

Two of the six entries in that table did not survive, which is the most
compact summary of this document available: a third of the "faults"
identified with confidence were explanations rather than faults.

Every fix was permanent and additive, and the final measurements use
all of them. That is the reason for confidence in the surviving
results -- not that they came out favourable, but that the instruments
which produced them had each been shown to be capable of producing an
unfavourable answer.

## The caveat that applies to this document too

Those instruments are young. The final numbers were taken with a
harness whose most important fixes are hours old, and "it is fixed now"
is what could have been said after each of the previous six rounds. The
defence against a seventh revision is not confidence; it is that the
final runs were structured so specific predictions could fail, and the
raw output is archived here so someone else can check whether they did.

*(That caveat earned itself twice over: six more revisions followed, and
the last of them withdrew the very fix this section credits for the
others. Read it as applying to revisions 8 through 13 as much as to the
seven above it -- and note that "the instruments are young" was itself
too optimistic, since one of the instruments turned out to be treating a
non-problem.)*

---

## 8. "Sketch at 8 KB is equivalent to exact at 32 KB"

**Withdrawn:** a pre-registered equivalence test refuted it.
**Cause:** claiming equivalence from overlapping ranges. Overlap shows a
difference was not *detected*; it is not evidence that none exists,
particularly when both distributions are wide.

A paired TOST at n=30 with a ±20% margin declared in advance
(`PREREGISTRATION_equivalence.md`, committed before the data existed)
put the 90% CI on the p99 log-ratio at **[1.114, 1.394]** — entirely
outside the margin on the upper side. Parametric and bootstrap agreed.

**What it revealed.** The matched-memory control failed too:
`sketch_32k_d2` vs `exact_32k`, at the *same* budget, is also not
equivalent on p99 (CI [0.995, 1.448]). So the tail penalty is a property
of the sketch rather than a cost of the memory saving. One repetition
shows the mechanism plainly — `sketch_32k_d2` reached 240,384us, 24x its
own median, with no other condition disturbed in that repetition.

> **[SUPERSEDED by revision 10.]** That paragraph is wrong in both of
> its steps and is left here because the correction is the content. The
> 240,384us observation is environmental (revision 9), it is what drove
> the matched-memory control's failure, and with it excluded the two
> structures at matched memory *are* equivalent. The tail premium is the
> price of the memory saving, not an intrinsic cost of approximating.

Median latency *is* equivalent (CI [0.974, 1.060]). The sketch matches
exact on the typical case and loses on the tail.

**The corrected claim:** the sketch continues to function at a budget
where exact counting does not, at the cost of roughly 17% worse tail
latency and with equivalent median latency. A trade, not a free lunch.

> **[The "17%" is also superseded by revision 10.]** It is the median
> paired ratio of one run reported as though it were a premium each run
> pays. It is not: about 40% of runs are *better* and about a third are
> more than 50% worse. See revision 10 for the honest characterisation.

**Original:** [`headline-single-matrix-n20.txt`](raw/headline-single-matrix-n20.txt) (where the ranges
overlapped)
**Correction:** [`equivalence-n30-prereg.txt`](raw/equivalence-n30-prereg.txt)

**Note on how this one was caught.** Unlike the previous seven, this
revision came from a test written specifically so that it could fail,
with its margin, metric, analysis and falsification clause committed
before any data was collected. The margin was deliberately set tighter
than the difference already observed. That is the only reason the
result changed rather than being confirmed by a test built to agree
with it.

---

## 9. "The sketch has a sporadic failure mode: rare severe tail excursions with a normal median"

**Withdrawn:** exact counting shows the same excursion rate.
**Cause:** a single outlier generalised into a failure mode, plus an
outlier check whose logic was wrong.

A dedicated run at n=60 per condition, with an excursion defined in
advance as any repetition exceeding 3x the `exact_32k` median:

| condition | excursions | rate | worst |
|---|---|---|---|
| exact_32k | 1/60 | 1.7% | 4.0x |
| sketch_32k_d2 | 1/60 | 1.7% | 3.0x |
| sketch_32k_d4 | 3/60 | 5.0% | 5.7x |
| sketch_32k_d8 | 1/60 | 1.7% | 3.6x |
| sketch_32k_d2_rot | 0/60 | 0.0% | 2.2x |
| sketch_8k_d2 | 1/60 | 1.7% | 2.3x |

All confidence intervals overlap. Exact counting was also the *noisiest*
condition in this run (CV 0.43 against the sketch's 0.35), inverting the
previous run where exact measured 0.18 and the sketch 0.40. The 24x
excursion did not reproduce across 360 further measurements; nothing
exceeded 5.7x.

**The flawed check.** The 240,384us excursion was attributed to the
sketch rather than the environment because it affected only one
condition in its repetition, and a host disturbance was assumed to
affect several. That reasoning is wrong: conditions run *sequentially*
within a repetition, so a disturbance lasting seconds hits exactly one.
The signature treated as exonerating is what an environmental
disturbance produces.

This was a pre-registered check, which did not save it. Specifying a
check in advance guarantees it is not chosen to fit the data; it does not
guarantee the check tests what it claims to.

**The corrected position:** excursions occur at roughly 2% across all
conditions including exact counting, and are a property of this
environment or workload rather than of approximation. No sketch-specific
sporadic failure mode is demonstrated.

**Not claimed, but noted:** `sketch_32k_d2_rot` recorded 0 excursions,
the lowest CV, and the lowest worst case. Seed rotation may dampen the
tail. At 0 against 1 with n=60 that is not a result, and it is recorded
here only so a future run knows where to look.

**Original:** [`equivalence-n30-prereg.txt`](raw/equivalence-n30-prereg.txt) (the single 24x outlier)
**Correction:** [`excursion-rate-n60.txt`](raw/excursion-rate-n60.txt)

---

## 10. "The tail penalty is intrinsic to approximation, not a cost of the memory saving"

**Withdrawn:** at matched memory the two structures are
indistinguishable.
**Cause:** built on a single outlier, in a control that failed for
reasons unrelated to what it was controlling for.

The matched-memory comparison (`sketch_32k_d2` vs `exact_32k`) failed
its equivalence test, and that failure was read as showing the tail
premium is what approximation costs at any size. The failure was driven
by the 240,384us observation now known to be environmental (revision 9).

With that understood, the matched-memory medians agree across two
independent runs at **1.03x and 1.04x**. Give the sketch the same memory
and it performs the same. The tail premium is the price of the memory
saving.

**Stated on the same statistic as the test it overturns.** Those two
figures are ratios of condition medians, while the test that produced
the error was a paired TOST on the mean log-ratio — comparing a median
against a mean-based interval, which is a fair thing to object to. It is
not necessary. Re-running the pre-registered analysis on run A with the
single environmental repetition excluded from *both* arms, so nothing is
being cherry-picked:

| comparison | geo-mean ratio | 90% CI | within ±20%? |
|---|---|---|---|
| matched memory (`sketch_32k_d2` / `exact_32k`) | 1.083x | [1.010, 1.160] | **yes** |
| 4x less memory (`sketch_8k_d2` / `exact_32k`) | 1.239x | [1.103, 1.390] | no |

Equivalent at matched memory, not equivalent at 4x less, on the same
test, the same margin and the same pairing that refuted equivalence in
revision 8. The conclusion does not depend on switching statistics.

The exclusion is the only judgment call, and it is one the
pre-registration did not authorise in advance — so this is reported as a
sensitivity analysis supporting revision 10, not as the pre-registered
result, which stands as recorded in revision 8.

**Also corrected here: the "predictability" framing.** The claim that
the sketch's cost is variance rather than magnitude rested on run A's
per-condition CVs (exact 0.18, sketch 0.40). Run B inverts them (exact
0.43, sketch 0.35). Per-condition variance is outlier-driven and does
not replicate.

What *does* replicate, closely, is the shape of the per-repetition
ratio:

| | run A (n=30) | run B (n=60) |
|---|---|---|
| median ratio | 1.18x | 1.14x |
| sketch better | 37% | 40% |
| sketch >50% worse | 30% | 33% |

So the honest characterisation is neither "17% worse" nor "less
predictable" but: **typically ~15% worse, with about 40% of runs better
and about a third more than 50% worse.** Reporting the median ratio
conceals that -- the same error as reporting p99 without p50, applied
one level up to a summary statistic.

**Original:** [`equivalence-n30-prereg.txt`](raw/equivalence-n30-prereg.txt)
**Correction:** [`excursion-rate-n60.txt`](raw/excursion-rate-n60.txt) plus re-analysis of both

---

## 11. "I looked for scheduler evaluations that randomise condition order and didn't find them"

**Withdrawn:** no such search was ever performed.
**Cause:** fabrication, in the course of making a weak claim sound
stronger.

This one is different in kind from the ten above. It was not a
measurement error; it was a sentence written into a draft blog post
asserting evidence that does not exist.

The original claim was "I've never seen a scheduler paper mention
condition ordering" -- unverifiable, and open to the obvious reply that
this says more about my reading than about the field. Asked to make it
defensible, I replaced it with "I looked and didn't find them", which
is worse: it asserts a literature search that never happened.

This project did run a literature search, on approximate data
structures in schedulers, and it is documented in paper Section 2.4. It
backs the novelty claim in the result post. Nothing was ever searched
about benchmarking practice.

**The corrected text** states only what is supportable: that
randomising treatment order is long-established experimental design,
that medicine calls this failure mode carryover and crossover trials
control for it by design, that my own harness had the bug -- and that I
have not surveyed how common it is and will not claim a pattern I have
not measured.

Recorded here because a record that included only measurement errors
would be a flattering one. The failure mode of reaching for evidence
that would be convenient is the same one the ten revisions above
describe, applied to prose instead of to data.

---

## 12. "BPF's LRU_HASH stops behaving like an LRU when the map is small"

**Withdrawn:** a small LRU_HASH works fine when the working set fits.
**Cause:** a mechanism asserted without being tested, fitted to data an
ordinary explanation also covers.

The claim was that BPF's per-CPU free lists make a small map smaller than
its own bookkeeping, so entries churn rather than order by recency. The
evidence was that at 42 entries the map reported a mean tracked count of
1.6 where a plain hash reported 189.8.

The competing explanation was never ruled out: **a correct LRU thrashes
when the working set exceeds capacity.** With ~330 live identities
competing for 42 slots, every insert evicts something about to be needed
again, entries are dropped between their own increments, and counts never
accumulate. A mean near 1 is what thrashing looks like, not what a bug
looks like.

Shrinking the identity population separates them. Repeated at n=5
([`lru-working-set-n5.txt`](raw/lru-working-set-n5.txt)) after the
original single run ([`lru-working-set-test.txt`](raw/lru-working-set-test.txt)):

| identities | slots | LRU median (range) | plain median (range) |
|---|---|---|---|
| 8 | 42 | **843.8** (835-848) | 820.3 (804-856) |
| 20 | 42 | **410.2** (385-476) | 535.4 (531-550) |
| 100 | 42 | 2.5 (2.3-2.6) | 209.8 (206-212) |
| 300 | 42 | 1.5 (1.5-1.7) | **0.1** (0.0-0.2) |

A 42-entry LRU_HASH retains counts perfectly well with 8 or 20
identities, and the separation between the fitting and overcommitted
groups is **164x**. Were the per-CPU free lists responsible, it would
fail at 42 entries regardless of identity count. It does not. **The
collapse tracks overcommitment, not map size** -- which is a property of
LRUs rather than of BPF.

**One cell in the original did not replicate**, and it is worth naming
because it appeared in this table and in blog post 03. At 300 identities
the plain hash read 200.4 once and 0.0-0.2 across five later runs; every
other cell agrees within spread. Five runs against one, so the 0.1 is
the better figure. It refines the plain-hash story rather than
overturning it: "locks in early arrivals and lets those accumulate to
~200" holds at 100 identities but not at 300, presumably because the 42
locked-in keys are decreasingly likely to be the ones currently waking.
Nothing in revision 12 turns on it -- the LRU column is the test.

**What survives.** The two map types fail differently under
overcommitment, and that difference was genuinely useful here. LRU
thrashes uniformly: nothing accumulates, every query reads near 1. A
plain hash locks in whichever keys arrived first and lets those
accumulate to ~200 while 83% of queries return zero. Neither is usable;
they are unusable in different shapes, and that is what allowed
separating an inert tracker from a discriminating one.

**What does not survive** is the framing as a BPF trap, a threshold to
watch for, or anything a BPF author needs warning about. Sizing a cache
below its working set degrades it. That is not news.

**Why this one differs from the eleven above.** It was not a measurement
artefact -- the measurements were correct throughout. I attached a
mechanism to them that I had not tested, in a form flattering enough to
become a headline: "a tool silently stops doing what its name says" is a
better story than "an undersized cache thrashes". Revisions 9 and 10 were
the same error, and I repeated it two days later while writing the
document that describes it.

**Original:** [`r6-sketch-variants-n3.txt`](raw/r6-sketch-variants-n3.txt),
[`r7-r9-throughput-mapcontrol-geometry.txt`](raw/r7-r9-throughput-mapcontrol-geometry.txt)
**Correction:** [`lru-working-set-test.txt`](raw/lru-working-set-test.txt)

---

## 13. "Fixed condition ordering biased the results, and the effect was large enough to reverse a conclusion"

**Withdrawn:** a controlled test finds no ordering effect at all.
**Cause:** an uncontrolled comparison between two runs that differed in
three ways, with the difference attributed to the one that had a story
attached.

This is the largest retraction in this list, because the claim is the
entire subject of blog post 01, one of two methodological findings in
the paper, and the thing most likely to be repeated by someone else.

**What the evidence actually was.** Two matrices disagreed:

| | `cms_exact_penalty` p99 |
|---|---|
| [`r2-count-attributable-n15.txt`](raw/r2-count-attributable-n15.txt) | median 12,784us, max 21,664us |
| [`r2c-prereg-n20.txt`](raw/r2c-prereg-n20.txt) | median 11,712us, max 14,000us |

The first ran `cms_none` (p99 ~88ms) immediately before
`cms_exact_penalty`; the second ran `cms_exact_penalty` first. That
looked like carryover, and carryover is real in principle, so it was
written up as carryover.

But the two files also differ in **condition subset** (four conditions
against three -- `cms_none` is absent from the second) and in **sample
size** (15 against 20), and they are separate runs on different days.
Parameters were identical; nothing else was. Three variables, one
explanation, no test. **Both files are fixed-order**, so the comparison
was never fixed-against-random in the first place.

**The controlled test** ([`ordering-controlled-n20.txt`](raw/ordering-controlled-n20.txt),
pre-registered in `benchmark/PREREGISTRATION_ordering.md`): same four
conditions, same n=20, same parameters, same guest, back to back. Only
the shuffling changes.

| statistic | fixed | randomised | ratio |
|---|---|---|---|
| median | 11,808us | 12,080us | 0.98x |
| mean | 12,219us | 12,619us | 0.97x |
| maximum | 16,016us | 19,424us | 0.82x |
| CV | 0.11 | **0.18** | |
| above 14,000us | 2/20 | 3/20 | |

Mann-Whitney p = 0.86. P(a fixed run exceeds a randomised run) = 0.48.
Three of four pre-registered predictions failed, and the fixed arm is
marginally *better* and clearly *less* variable than the randomised one.

**A second, independent angle agrees.** Within the randomised arm,
adjacency was assigned at random, which makes it a genuine experiment on
the same question. `cms_none` landed immediately before
`cms_exact_penalty` in 6 of 20 repetitions:

| | n | median | max |
|---|---|---|---|
| preceded by `cms_none` | 6 | 11,664us | 12,976us |
| not preceded by `cms_none` | 14 | 12,208us | 19,424us |

Ratio 0.96x, Mann-Whitney p = 0.458. The repetitions that followed the
pathological condition were, if anything, slightly better.

**What survives.** Randomising condition order remains the right default
and the recommendation stands, but on a priori grounds rather than
measured ones: carryover is a real phenomenon, randomisation converts any
systematic bias into noise that repetitions remove, and it costs six
lines. What does not survive is the claim that it mattered *here*, or any
figure quantifying how much.

**No measurement changes.** This revision is about an explanation, not
data. Every result re-established under randomised ordering stands
exactly as reported; randomised ordering simply turns out to have been
insurance rather than a fix.

**What explained it, once both candidates were tested.** Condition
subset was the other difference between the two matrices, and it is null
too ([`condition-subset-n20.txt`](raw/condition-subset-n20.txt)): same
parameters, randomised both times, with and without `cms_none` in the
matrix, ratio 0.99x at p = 0.55.

Six independent measurements of the same condition now exist, spanning
both orderings and both subsets:

| run | order | subset | n | median | max | CV |
|---|---|---|---|---|---|---|
| `r2-count-attributable-n15` | fixed | with none | 15 | 12,784 | 21,664 | 0.23 |
| `r2c-prereg-n20` | fixed | without none | 20 | 11,712 | 14,000 | 0.08 |
| `r2d-randomised-order-n20` | randomised | with none | 20 | 11,744 | **39,488** | 0.47 |
| `ordering-controlled` 1a | fixed | with none | 20 | 11,808 | 16,016 | 0.11 |
| `ordering-controlled` 1b | randomised | with none | 20 | 12,080 | 19,424 | 0.18 |
| `condition-subset` | randomised | without none | 20 | 12,192 | 22,048 | 0.27 |

**The median varies by 1.09x across every configuration. The maximum
varies by 2.82x with no relationship to either variable** -- and the
largest maximum of all, 39,488us, comes from a randomised run with the
pathological condition present, which is the configuration the theory
predicted would be cleanest.

The original claim compared two *maxima*: 21,664 against 14,000, a 1.55x
difference sitting comfortably inside the 2.82x range the maximum spans
anyway. **The two matrices disagreed because the maximum of a sample is
a noisy statistic and I compared two of them.** That is the whole
explanation, and it is the same error as reporting p99 without p50
(revision 6) and as generalising a single outlier (revision 9), applied
this time to the summary statistic of a distribution rather than to the
distribution itself.

**Why this one is the worst.** Revisions 9, 10 and 12 were untested
mechanisms attached to correct measurements. This is the same error a
fourth time, on the most-recommended claim in the project, and it
survived two passes that were specifically looking for that error. It
also survived my own correction of it: hours before this test, the "55%"
figure here was rewritten into a more rigorous form -- 6 of 15
repetitions above 14,000us against 0 of 20, Mann-Whitney p = 0.004 --
computed from **the same two confounded files**. Making a statistic more
careful does nothing about a confounded design, and the more careful
version read as more trustworthy.

**Original:** [`r2-count-attributable-n15.txt`](raw/r2-count-attributable-n15.txt) +
[`r2c-prereg-n20.txt`](raw/r2c-prereg-n20.txt) (compared across runs)
**Correction:** [`ordering-controlled-n20.txt`](raw/ordering-controlled-n20.txt)


==============================================================================
## FILE: results/MANIFEST.md
## path: results/MANIFEST.md
==============================================================================

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


==============================================================================
## FILE: results/ENVIRONMENT.md
## path: results/ENVIRONMENT.md
==============================================================================

# Measurement environment

Recorded because several findings are environment-specific, and because
one finding was wrongly attributed to the scheduler when it belonged
here instead (the 240,384us excursion, revision 9).

## Guest (where everything was measured)

| | |
|---|---|
| kernel | `6.19.10-300.fc44.aarch64` |
| distro | Fedora Linux 44 (Cloud Edition) |
| architecture | **aarch64** |
| CPUs | **4** |
| RAM | 3 GB |

## Host

| | |
|---|---|
| machine | Apple M4 |
| OS | macOS 26.6.1 |
| virtualisation | Lima 2.2.0, `vz` driver |

## Why these numbers matter to specific findings

**CPU count (4).** This was initially thought to determine the entry
count below which `LRU_HASH` stops behaving like an LRU. It does not --
see `REVISIONS.md` revision 12. The exact tracker's failure threshold
tracks the ratio of live identities to map capacity, so it should be
reproducible on any core count given the same workload. The CPU count
still matters for the scheduling results themselves, since runqueue
depth is the mechanism under study and four cores is a small machine.

**Architecture (aarch64) and everything else.** No x86 validation was
performed. Memory-ordering behaviour around the atomic counters, cache
effects underlying the runqueue-depth result, and the BPF LRU internals
are all plausibly architecture-sensitive. Every result should be treated
as aarch64-specific until checked elsewhere.

**Virtualisation and timer delivery.** Timer *delivery* in this guest has
a floor near 1.7ms, which is high enough to swamp the scheduling
differences under study. This invalidated `rt-app` as a victim workload
outright: churn levels of 24, 4 and 0 tasks all produced ~1700us,
indistinguishable. All results therefore rest on `schbench`'s
task-to-task wakeup path, which has no such floor. On bare metal this
constraint disappears and `rt-app` should be re-tested.

**RAM (3 GB) and what could not be measured.** No RAPL counters and no
battery gauge are exposed to the guest, so energy -- the established
motivation for tracking wakeup frequency, and the direction this work
most wants to go next -- could not be measured at all. The method for
doing so when hardware allows is written up in advance in
[`../benchmark/ENERGY_METHOD.md`](../benchmark/ENERGY_METHOD.md).

## An uncontrolled variable: the host is heterogeneous

The M4 host has **10 physical cores -- 4 performance and 6 efficiency**.
The guest's 4 vCPUs are scheduled onto those by macOS, and nothing in
the guest controls or observes which class they land on. The assignment
may also change during a run as the host rebalances.

This is an uncontrolled variable in **every measurement in this
archive**. It plausibly contributes to the wide p99 ranges seen
throughout, since a vCPU migrating from a performance core to an
efficiency core mid-run would inflate latency for reasons having nothing
to do with the scheduler being tested.

It also offers an alternative explanation for the sporadic tail
excursions once attributed to sketch collisions: a host-level scheduling
hiccup would produce the same signature from inside the guest.

**That alternative is the surviving explanation.** An earlier version of
this section claimed the opposite, and the reasoning is worth recording
because it was pre-registered and still wrong.

The pre-registration required reporting whether outliers cluster across
conditions within a repetition, on the stated assumption that a
host-level disturbance would affect whichever conditions were running
near that moment. They did not cluster: in the repetition where
`sketch_32k_d2` reached 240,384us, `exact_32k` measured a wholly
unremarkable 10,032us. That was read as ruling the host out.

**It rules nothing out.** Conditions run *sequentially* within a
repetition, so a disturbance lasting a few seconds hits exactly one of
them. The signature treated as exonerating is precisely what an
environmental cause produces. A dedicated run at n=60 per condition
settled it: exact counting shows excursions at the same rate as every
sketch geometry (1/60 against 1/60), the 24x never recurred across 360
further measurements, and nothing exceeded 5.7x. The excursions belong
to this environment, not to approximation. See `REVISIONS.md`
revision 9, and `BENCHMARK_HOST.md` for what to disable on a host to
reduce them.

Specifying a check in advance guarantees it was not chosen to fit the
data. It does not guarantee the check tests what it claims to.

The general limitation stands regardless: this environment cannot
isolate the guest from host scheduling decisions, and bare metal would
remove the question rather than answer it.

**This also rules out running experiments in parallel VMs.** Two guests
of 4 vCPUs each would need 8 of the host's 10 cores, forcing at least
four vCPUs onto efficiency cores, and `vz` offers no physical-core
pinning to prevent it. The two VMs would be measuring different
hardware, with the assignment shifting under them.

## Preparing a host for these measurements

Configuring a machine so that what is measured is the scheduler rather
than the machine -- which timers to disable, why frequency scaling is a
confound, and why nothing else should run on the host -- is documented
separately in [`BENCHMARK_HOST.md`](BENCHMARK_HOST.md).

## Workload constants

Unless a run's own header says otherwise:

- victim: `schbench`, 2 message threads, 4 worker threads, 100 rps
- churn: 128 tasks or slots, 200 wakeups/s, 200us CPU burn each
- window: 1000ms, estimates summing current and previous windows
- `--penalty-ns 20287`, derived once from a pre-flight measurement and
  never retuned
- `--flat-ns 4000000` for the count-blind control
- stable-identity runs use `--lifetime 60`; churning runs `--lifetime 0.25`


==============================================================================
## FILE: results/BENCHMARK_HOST.md
## path: results/BENCHMARK_HOST.md
==============================================================================

# Preparing a machine to measure scheduling latency

Notes on configuring a host so that what you measure is the scheduler
rather than the machine. Written after spending a day investigating a
240,384us latency excursion that turned out to be environmental
(`REVISIONS.md`, revision 9), which is a reasonably expensive way to
learn that the measurement environment is part of the experiment.

The principle throughout: **anything that wakes up on a timer is worse
than steady background load.** Constant load raises every number and
mostly cancels out of a comparison. Periodic load fires *during* some
runs and not others, producing exactly the sporadic spikes that look
like a finding.

## Install a minimal system

Fedora Server or a minimal install, not Workstation. A desktop session
brings a compositor, file indexers, and a dozen daemons, none of which
you need on a machine driven over SSH.

Anything from Fedora 42 onward carries a kernel new enough for
`sched_ext`, which landed in 6.12. Check with `uname -r` rather than
assuming.

## Disable periodic timers

The main offenders:

```bash
systemctl list-timers --all          # audit first

sudo systemctl disable --now dnf-makecache.timer
sudo systemctl disable --now fstrim.timer
sudo systemctl disable --now man-db-cache-update.timer
sudo systemctl disable --now logrotate.timer
```

`dnf-makecache` deserves singling out: it wakes periodically, hits the
network and burns CPU. On a host measuring wakeup latency that is
directly contaminating, and it fires often enough to catch some runs and
not others.

## Disable services you are not using

```bash
sudo systemctl disable --now bluetooth cups ModemManager
```

Keep `avahi-daemon` if you want `hostname.local` to resolve; it is quiet
enough to leave alone.

## Pin the CPU frequency

Frequency scaling is a confound. A core ramping up partway through a run
changes latency for reasons that have nothing to do with the scheduler.

```bash
sudo dnf install tuned
sudo tuned-adm profile latency-performance
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor   # expect: performance
```

Consider disabling turbo as well. It costs peak throughput and removes a
source of frequency variation -- and since every measurement here is
*relative* (tracker against tracker, condition against control), a slower
but stable machine is strictly better than a fast one whose clock wanders.

The same reasoning applies to thermal throttling, which is the laptop
version of this problem. Verify before trusting any results:

```bash
stress-ng --cpu $(nproc) --timeout 600s &
watch -n5 'grep MHz /proc/cpuinfo'
```

If clocks sag over ten minutes, pin a lower fixed frequency and accept it.

## Run headless

Drive the host over SSH and leave nothing running locally:

```bash
sudo systemctl enable --now sshd
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```

On a laptop, also stop the lid suspending it -- set `HandleLidSwitch=ignore`
and `HandleLidSwitchExternalPower=ignore` in `/etc/systemd/logind.conf`.

Use wired ethernet rather than wireless where possible. It removes a
driver from the equation, and on a headless box a wireless failure means
you cannot get in to fix it.

**Do not run an agent, IDE, or analysis tooling on the host itself.**
Everything that runs there competes for the resource being measured, and
it competes *while you are actively working*, which is worse than random
noise. Keep tooling on a separate machine and treat the host as an
instrument.

`tmux` is the exception worth installing, so a dropped connection does
not kill a run in progress.

## Audit before trusting anything

```bash
systemctl list-units --type=service --state=running
systemctl list-timers --all
```

On a properly minimal system this is a short list. Investigate anything
unexpected before running experiments rather than afterwards.

## Record what you ended up with

Whatever configuration you settle on, write it down alongside the kernel
version and CPU details. "What else was running on the box" is precisely
the sort of detail that turns out to matter several retractions later,
and it is unrecoverable after the fact.


==============================================================================
## FILE: benchmark/ENERGY_METHOD.md
## path: benchmark/ENERGY_METHOD.md
==============================================================================

# Measuring energy, when hardware allows it

The established reason to track wakeup frequency is not latency. It is
that every wakeup drags a core out of a deep idle state, and re-entering
costs real joules -- the "wakeup tax". That is a one-step causal chain
where this project's latency argument is three, and a sketch's
overestimation matters far less to a batching heuristic than to a
scheduling decision.

None of it was measured. The VM exposed neither RAPL counters nor a
battery gauge, so this document is the method written in advance, while
the reasoning is fresh and before any data exists to shape it.

## Measure the mechanism, not only the outcome

The obvious experiment is "does the scheduler use less energy". The
better one also asks **"does it do the thing that would cause that"**,
because a joules figure alone cannot distinguish a real effect from a
coincidence.

The causal chain is: *fewer or better-batched wakeups → fewer idle-state
exits → less energy*. The middle step is directly observable:

```
/sys/devices/system/cpu/cpu*/cpuidle/state*/usage   # times entered
/sys/devices/system/cpu/cpu*/cpuidle/state*/time    # total us resident
/sys/devices/system/cpu/cpu*/cpuidle/state*/name    # C1, C1E, C6, C10...
```

Sample before and after each condition and difference them. If a
mechanism reduces energy **without** changing deep-state residency,
something other than the wakeup tax is responsible and the explanation
is wrong. If it increases deep-state residency but energy does not move,
the effect is real but too small to matter on this hardware.

Either mismatch is more informative than the energy number alone.

## Reading package energy

Easiest, wrapping a command:

```bash
perf stat -e power/energy-pkg/,power/energy-cores/,power/energy-ram/ \
    -- ./run-condition.sh
```

Directly, for finer control:

```bash
cat /sys/class/powercap/intel-rapl:0/energy_uj          # microjoules
cat /sys/class/powercap/intel-rapl:0/max_energy_range_uj
```

**The counter wraps.** Read `max_energy_range_uj` and handle it, or a
long run silently produces a negative or absurd delta:

```python
delta = (after - before) % max_range
```

Domains vary by platform: `intel-rapl:0` is the package, `:0:0` usually
cores, `:0:1` uncore or graphics, `:0:2` DRAM where present. Read package
as the headline and cores separately if available.

AMD exposes package energy through the same `perf` PMU on Zen and later,
but with fewer domains and less maturity than Intel. The `amd_energy`
hwmon driver was removed from the kernel over a side-channel issue; the
perf PMU is the supported path.

## Whole-system draw, on a laptop

```bash
cat /sys/class/power_supply/BAT0/power_now      # microwatts, if present
# otherwise: current_now * voltage_now
```

A degraded battery still reports **instantaneous** current and voltage
accurately -- capacity loss does not corrupt a power reading. So a
battery that holds almost no charge is still usable for short spot
checks on mains-free runs.

Two independent measurements agreeing is considerably stronger than
either alone, and whole-system draw is the more honest figure if the
argument is ever framed in embedded terms.

## The metric must be energy per unit work

**Raw joules is not the measure.** A scheduler that gets less done uses
less energy, trivially and uselessly. Normalise:

    joules / requests completed

The victim's completed request count and the churn loop counts are both
already collected by the existing harnesses. Report energy, throughput,
and the ratio -- a mechanism that cuts energy 10% while cutting work 15%
has made things worse.

## Run this first: validate the instrument

Before any condition is compared against any other, establish that this
machine can detect a *large, known* energy difference at all.

```
idle,       60s   -> baseline joules, deep-state residency
heavy load, 60s   -> does RAPL move as expected?
                  -> does C6/C10 residency collapse as expected?
```

An instrument that cannot detect a sledgehammer cannot detect the
mechanism. This is the same positive-control logic that rescued round 2
of the latency work, where six candidate workloads were rejected by a
control before a full matrix was ever run -- and it is cheap, because a
null from an unvalidated instrument is uninterpretable rather than
informative.

Check the direction as well as the magnitude. Energy should rise and
deep-state residency should fall under load. If they do not move
together, something is wrong with the measurement rather than
interesting about the scheduler.

## Do not start by comparing against EEVDF

The tempting first experiment is the CMS penalty scheduler against the
stock kernel scheduler. It is the wrong one, and for a reason this
project has already paid for.

EEVDF and `scx_cms` differ in policy, dispatch path and implementation,
not merely in whether wakeups are tracked. Any energy difference between
them conflates all of it -- which is precisely the error that produced a
6.8x latency result later shown to be 82% generic vtime perturbation
(`../results/REVISIONS.md`, revision 3).

The primary comparison is `flat` against `exact + penalty`: same binary,
same policy, same overhead, one variable. EEVDF belongs in the matrix
eventually as context -- *is a custom scheduler worth it at all* -- but
not as the comparison the conclusion rests on.

Order the runs accordingly:

| order | condition | question |
|---|---|---|
| 0 | idle / heavy load | can the instrument see anything? |
| 1 | `mechanism=none` | tracking overhead only |
| 2 | `mechanism=flat` | does *any* perturbation change energy? |
| 3 | `exact + penalty` | does acting on the count change it? |
| 4 | `sketch + penalty` | does approximation preserve it? |
| 5 | EEVDF | context, not conclusion |

## Statistics: a two-stage design

The margin cannot be pre-registered yet, because nothing is known about
the scale or variance of the effect. For latency there were prior runs
to set a +/-20% margin against; here there is nothing.

So the design is explicitly two-stage, and the stages must not be
confused:

**Stage 1, pilot.** Establish scale and run-to-run variance. Exploratory
by declaration: **no conclusions are drawn from it**, and no margin is
chosen after seeing it that could have been chosen before.

**Stage 2, confirmatory.** Margin, metric, test, sample size and
falsification clause committed before the run, in the manner of
`PREREGISTRATION_equivalence.md`. Paired per-repetition ratios, since the
harness interleaves conditions within each repetition and pairing is
therefore a property of the design rather than a post-hoc choice.

**One judgment call belongs before stage 1, not after it:** what size
energy difference would actually matter? If wakeup tracking saves 0.5%
of package energy, is that a finding or a curiosity? Decide and write it
down now. Left undecided, the threshold will end up being whatever the
data happens to show.

## The control still applies

The count-blind control (`--mechanism flat`) dissolved 82% of this
project's apparent latency benefit. There is no reason to expect energy
to be different, and every reason to check.

Conditions, at minimum:

| condition | question |
|---|---|
| `mechanism=none` | baseline: tracking overhead only |
| `mechanism=flat` | does *any* vtime perturbation change energy? |
| `exact + penalty` | does acting on the count change energy? |
| `sketch + penalty` | does approximation preserve whatever the count buys? |

If `flat` captures most of the effect again, the finding is about
perturbation rather than tracking -- exactly as it was for latency.

## Pitfalls specific to energy

**RAPL is package-wide.** It reports everything on the die, including
whatever else is running. The host-cleanliness requirements in
`../results/BENCHMARK_HOST.md` matter more here than for latency, not
less.

**Establish an idle baseline.** Measure the machine doing nothing, for
the same duration, and report both absolute and idle-subtracted figures.
Absolute energy is dominated by baseline draw and will hide a real
effect.

**Frequency scaling is a confound twice over** -- it changes both
latency and energy. The governor must be pinned before any of this
means anything.

**Longer runs.** RAPL updates roughly every millisecond, but thermal
behaviour and idle-state distribution need time to settle. Prefer 30-60s
per measurement over the 10-15s used for latency.

**Permissions.** `perf` energy events need
`kernel.perf_event_paranoid <= 0` or root.

## What would falsify the energy case

Deep-state residency unchanged across conditions, or energy per unit
work statistically indistinguishable between `flat` and
`exact + penalty`. In that event the honest report is that
wakeup-frequency tracking does not reduce energy on this hardware --
which, given the latency results, would make this a negative result
about the technique generally rather than about one application of it.

That outcome must be as publishable as the alternative. Writing that
down here, before any data exists, is the point of writing it down at
all.


==============================================================================
## FILE: benchmark/PREREGISTRATION_equivalence.md
## path: benchmark/PREREGISTRATION_equivalence.md
==============================================================================

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

---

## Appended after the run: one of these checks was wrong

**Nothing above has been edited.** The specification is what it was when
committed and the run was analysed against it exactly. This note is
appended because leaving it off would mean the document quietly
misleads anyone who re-runs the analysis.

**The outlier check's inference does not follow.** The section above
says outliers clustering across conditions "would indicate an
environmental disturbance rather than a scheduler property", and the
non-clustering of the single 240,384us observation was read as ruling
the environment out. That is backwards. Conditions run **sequentially**
within a repetition, so a disturbance lasting a few seconds hits exactly
one of them. Non-clustering is what an environmental cause produces, not
what it excludes.

A dedicated run at n=60 per condition settled it: exact counting shows
excursions at the same rate as every sketch geometry, and the 24x never
recurred across 360 further measurements. See `../results/REVISIONS.md`
revision 9.

The primary and secondary tests are unaffected -- they are TOSTs on
paired log-ratios and do not depend on this check. What the error
changed was the interpretation of the matched-memory control, which is
revision 10.

**The lesson is the narrow one.** Pre-registration guarantees a check
was not chosen to fit the data. It does not guarantee the check tests
what it claims to, and this one was specified in advance and still
wrong.


==============================================================================
## FILE: benchmark/PREREGISTRATION_ordering.md
## path: benchmark/PREREGISTRATION_ordering.md
==============================================================================

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


==============================================================================
## FILE: benchmark/PREREGISTRATION_round2c.md
## path: benchmark/PREREGISTRATION_round2c.md
==============================================================================

# Pre-registration: round 2c, the collateral-damage claim

**Committed before any round 2c data is collected.** The git commit
timestamp on this file is the evidence for that. Everything below is
fixed at commit time and is not to be revised after seeing results; if
something here turns out to be badly specified, the run is discarded and
re-registered rather than reinterpreted.

## Why this exists

Round 2 produced a p99 improvement that a negative control (`flat`, a
count-blind penalty of equal strength) reproduced almost entirely. On
the pre-declared p99 metric, `cms_exact_penalty` and `flat_4ms` were
statistically indistinguishable at n=15 (ranges 10,928-21,664 vs
15,344-29,600, overlapping).

The effect was then located in p50, which had been collected all along
but was not the declared primary metric. That is metric-shopping, and
this project has already produced two false positives from exactly that
family of mistake. The p50 observation is therefore treated as a
*hypothesis generated by* round 2, testable only on data round 2 has not
seen.

## Hypothesis

A count-proportional penalty and a count-blind penalty of equal strength
achieve statistically indistinguishable tail (p99) improvement, but the
count-blind penalty pays for it with a large median (p50) regression
that the count-proportional penalty does not pay, because the latter can
distinguish the latency-sensitive victim from the churn.

Stated as a claim about cost-effectiveness, not about magnitude: **at
matched tail benefit, discrimination shows up as absence of collateral
damage.**

## Primary metric

Victim p50 wakeup latency (`schbench` `request_latency_pct50.0`).

## Primary comparison

`cms_exact_penalty` vs `flat_4ms`.

`flat_4ms` specifically because it had the *lowest* median p99 of the
three flat variants swept (2ms/4ms/8ms), making it the strongest
available count-blind control. Choosing the strongest control is
deliberate; a control that could not compete would prove nothing.

## Analysis, fixed in advance

1. **Gating precondition.** The p99 ranges of `cms_exact_penalty` and
   `flat_4ms` must overlap, confirming matched tail benefit. If they do
   NOT overlap, the "matched benefit, different cost" framing is wrong
   and the primary comparison below is void -- report that instead and
   re-register.
2. **Primary test.** Paired sign test on p50 across repetitions
   (conditions are interleaved within each repetition by the harness, so
   pairing is a property of the design, not a post-hoc choice).
   One-sided, `cms_exact_penalty` < `flat_4ms`, alpha = 0.05.
3. **Supporting criterion.** p50 ranges must not overlap.

Confirmed only if BOTH 2 and 3 hold, with 1 satisfied.

## Sample size

n = 20 repetitions per condition. Chosen because the effect died between
n=8 and n=15 last time; 20 exceeds every N used in this project so far.

## Secondary comparison (exploratory, not confirmatory)

`cms_sketch_penalty` vs `cms_exact_penalty` on p50. Reported with
ranges and the paired sign test, but explicitly labelled exploratory:
establishing equivalence needs a TOST with a margin declared before a
run designed for it, which this run is not.

## Parameters, frozen

- `--penalty-ns 20287` (derived in round 2's pre-flight, unchanged)
- `--flat-ns 4000000`
- 128 churn tasks @ 200 wakeups/s burning 200us
- schbench victim, 4 threads, 100 rps, 10s, 3s warmup
- `--identity-key pid`, `--window-ms 1000`

No parameter is to be adjusted during or after the run. If the result is
null, it is null.

## What falsifies the claim

Sign test p >= 0.05, or overlapping p50 ranges. In that case round 2
yields **no positive finding about wakeup-frequency tracking at all**,
and the honest report is that the mechanism's apparent benefit is fully
explained by vtime perturbation. That outcome is to be written up as the
result, not treated as a reason for a further run.

## What this run does NOT establish even if confirmed

- Anything about the Count-Min Sketch specifically (that is round 3).
- Anything about memory (round 3).
- Generalisation beyond this VM, this CPU count, and this workload shape.


==============================================================================
## FILE: scheduler README
## path: ../scx_cms/README.md
==============================================================================

# scx_cms

An experimental `sched_ext` scheduler that tracks per-task wakeup
frequency and acts on it, built to answer one question: **can a
Count-Min Sketch replace exact per-task counters, saving memory without
hurting scheduling quality?**

Short answer: yes, with a cost. A sketch at 8.3 KB does what exact
counting needs 35.6 KB for — identical typical latency, a worse and
noisier tail. Full results, data and a rather long list of retractions
live in the research repo (see below).

## What it is

`scx_simple`'s scheduling policy (global weighted-vtime, optional FIFO)
unmodified, plus three things made swappable at **load time** rather
than compile time, so that comparisons hold everything else constant:

| axis | flag | options |
|---|---|---|
| how counts are stored | `--tracker` | `exact` (LRU hash), `sketch` (Count-Min) |
| what a "task" is | `--identity-key` | `pid`, `tgid`, `comm` |
| what the count does | `--mechanism` | `none`, `penalty`, `boost`, `flat` |

Both trackers are compiled in and the verifier eliminates the unselected
branch, so switching `--tracker` changes the counting method and nothing
else. That property is what makes the central comparison meaningful.

`--mechanism flat` is the count-blind control: it applies the same vtime
perturbation while ignoring the tracked count entirely. It exists because
comparing `penalty` against `none` conflates *consulting the count* with
*perturbing scheduling at all* — and when that control was finally built,
it reproduced about 82% of what had looked like a 6.8x win for tracking.

## Building

**This repository is not standalone.** `Cargo.toml` depends on
`scx_utils` and `scx_cargo` by relative path, and the BPF build uses
scx's tooling. Drop it into an scx checkout:

```
git clone https://github.com/sched-ext/scx.git
git clone <this repo> scx/scheds/experimental/scx_cms
cd scx && cargo build -p scx_cms
```

Developed against scx as of September 2026, kernel 6.19, aarch64. The
`sched_ext` support it needs landed in 6.12.

## Notable flags

```
--tracker exact|sketch        counting method (the study's variable)
--sketch-width N              columns per row (depth 2 outperformed the
--sketch-depth N              default depth 4 by 1.8x at equal memory)
--max-tracked N               exact tracker's entry count
--mechanism none|penalty|boost|flat
--identity-key pid|tgid|comm
--compare                     run BOTH trackers over the same wakeups and
                              report divergence, max overshoot, and any
                              never-undercount violations
--plain-map                   back the exact tracker with a plain hash
                              instead of an LRU (see below)
--hash-mix                    extra avalanche before the modulo
--conservative                conservative update (see caveat below)
--stats N                     periodic counters, including mechanism reach
```

## Two findings about BPF, not about sketches

**Bounded maps fail in different shapes, and only one failure is
legible.** Under overcommitment an `LRU_HASH` thrashes uniformly —
nothing accumulates, every query reads near 1 — while a plain
`BPF_MAP_TYPE_HASH` of identical capacity locks in whichever keys
arrived first, letting those reach ~200 while 83% of queries return
zero. Neither is usable below its working set, but a zero from the plain
hash means *not tracked*, where a low count from the LRU could equally
mean an idle task. That difference is what `--plain-map` exists for: it
is how you tell a tracker that has stopped working from one that is
working on quiet tasks.

> **Retracted:** an earlier version of this section claimed `LRU_HASH`
> stops behaving like an LRU when the map is small, and blamed BPF's
> per-CPU free lists. The measurements were right and the mechanism was
> invented. A 42-entry LRU retains counts normally with 8 or 20
> identities (medians 843.8 and 410.2 across five runs) and collapses
> only at 100 or 300 — a 164x separation — so the failure tracks
> *overcommitment* rather than map size, which is what any LRU does
> below its working set, and not news about BPF. The
> withdrawn prediction that the threshold scales with CPU count goes
> with it. See `REVISIONS.md` revision 12 in the research repository.

**Conservative update cannot be implemented safely here.** It requires
reading all *d* cells, taking the minimum and writing back atomically;
each cell needs its own `bpf_map_lookup_elem`; and the verifier rejects
a lock held across those calls with *"function calls are not allowed
while holding a lock"*. The `--conservative` implementation is therefore
lock-free and **races observably**, producing thousands of
never-undercount violations in every run. No rate is quoted because none
replicates: the same configuration gave 1,749 and then 1,036, and a
neighbouring variant moved 197 to 1,750. One violation is enough — that
guarantee is the reason to choose this structure. Included so the
measurement can be reproduced, not because it is usable.

## Known open issues

- **Increment-then-read is not atomic as a unit.** The regression suite
  in `tests/` carries this as an expected failure. Phase 6 measurements
  deliberately used distinct churn identities to keep this bug out of the
  results, which means the same-identity concurrent path is not exercised
  by any of them.
- `--conservative` is unsound, as above.

## Results, data, and what was retracted

The research repository holds the paper draft, the benchmark harnesses,
the raw output of every run, and a record of thirteen claims that were
made and then withdrawn — each tied to the file that produced it and the
file that overturned it.

The retractions are worth reading before trusting any number here. Eight
of the thirteen were caused by a faulty instrument rather than a faulty
hypothesis, and the controls that eventually caught them (a do-nothing
reference condition, a count-blind control) are reproducible with the
flags above.

Four were a different failure: the measurements were correct and an
untested mechanism was attached to them — including the one retracted
above, in this file, and the condition-ordering bias that reached a
paper and a blog post before a controlled test found no such effect.


==============================================================================
## FILE: research README
## path: README.md
==============================================================================

# sched_ext wakeup-frequency tracking — research

Research material for the Count-Min Sketch vs. exact-counter scheduling
study. Start at
[`sched_ext_phase2_handoff/MANIFEST.md`](sched_ext_phase2_handoff/MANIFEST.md),
which explains what every file here is and the order to read them in.

## Why this is its own repository

This material previously lived at
`sched_ext/repo/.claude/sched_ext_phase2_handoff/`, inside a clone of
[sched-ext/scx](https://github.com/sched-ext/scx). That location is
covered by that repo's `.gitignore` (`**/.claude`), so none of it —
the paper draft, the delivery plan, the validated Python prototype, the
pytest suite — was under version control at all. It was one
`git clean -xdf` or one lost machine away from being gone.

It also should not simply be committed *into* that clone: that repo is a
fork of an upstream project, and this is not upstream's material.

## Relationship to the scheduler code

The BPF/Rust scheduler this research drives, `scx_cms`, has its own
repository: **https://github.com/blackjable/scx-cms**, extracted with
`git subtree split` so its commit history is preserved.

It does **not** build standalone. It depends on `scx_utils` by relative
path and uses scx's BPF tooling, so it has to sit inside a checkout of
[sched-ext/scx](https://github.com/sched-ext/scx) at
`scheds/experimental/scx_cms/` to build. That local scx clone is
upstream's, not this project's — nothing here is ever pushed to it.

The two repositories move together: the delivery plan's order of
operations tracks the scheduler's progress, and the paper's build
checklist cites it.


==============================================================================
## FILE: bare metal setup
## path: sched_ext_phase2_handoff/04_bare_metal/README.md
==============================================================================

# Setting up a bare-metal measurement host

Everything in this project was measured in a VM on 4 aarch64 cores. That
environment invalidated one workload outright (`rt-app`, defeated by a
~1.7ms timer-delivery floor), hid an uncontrolled variable in every
result (the host moving vCPUs between performance and efficiency cores),
and could not measure energy at all.

This is how to build the machine that removes those limits.

## Before you buy or commit: does the machine qualify?

Two hard requirements, and one that is easy to get wrong.

**Intel RAPL needs Sandy Bridge (2nd gen, 2011) or later.** Nehalem and
Lynnfield -- the 1st-generation i5-7xx and i7-8xx -- have no RAPL, which
rules out energy work entirely. The year on the box is not reliable;
check the model number.

**`sched_ext` needs kernel 6.12 or later.** Fedora 44 ships 6.19.

**Avoid 12th-generation Intel and newer.** Those are hybrid, P-cores plus
E-cores, which reintroduces exactly the heterogeneity confound this
exercise exists to escape. 6th through 10th generation are homogeneous
and cheap secondhand.

## Buying secondhand: one question that matters more than the rest

Most cheap qualifying hardware is ex-corporate, and ex-corporate
machines frequently ship with a **BIOS supervisor password still set**.
That can block changing boot order, booting from USB, or disabling SMT,
and on many ThinkPads and business Dells it cannot be cleared without
replacing the mainboard.

Every other defect is recoverable after delivery. This one is not, so
ask before buying:

> 1. Is the BIOS supervisor password cleared?
> 2. What is the exact CPU model (i5-10210U, i5-8265U, and so on)?
> 3. Is the drive an SSD?
> 4. Is the charger included?

All four are lookups a seller can do from the BIOS screen or the
sticker. **Do not expect a seller to run diagnostic commands** -- they
will not, and there is no need: RAPL presence follows from the CPU
generation, so the exact model number answers it. The risk being managed
here is a mis-described listing, not uncertain hardware.

Buy from a seller offering returns. If it arrives mis-described or with
a locked BIOS, that is the remedy.

Verify on the machine before installing anything, from a live USB:

```bash
lscpu | grep -E 'Model name|^CPU\(s\)|Thread'
ls /sys/class/powercap/intel-rapl/            # must not be empty
perf stat -e power/energy-pkg/ sleep 1        # must return joules
cat /sys/devices/system/cpu/cpu0/cpuidle/state*/name
```

If RAPL is absent, the machine can still close the timer and
architecture gaps -- it just cannot answer the energy question.

## Which image

**Fedora Server 44, x86_64.**

- *Server*, not Workstation: a desktop session brings a compositor,
  indexers and background daemons onto a machine whose scheduling
  latency you are trying to measure. See `../../results/BENCHMARK_HOST.md`.
- *44*, matching the VM, so that when bare-metal results are compared
  against the existing archive the operating system is held constant and
  only the hardware has changed.
- *x86_64*, **not aarch64**. The VM is aarch64; the bare-metal candidates
  are Intel. Downloading the wrong architecture is an easy 2 GB mistake.

```
https://download.fedoraproject.org/pub/fedora/linux/releases/44/Server/x86_64/iso/Fedora-Server-dvd-x86_64-44-1.7.iso
```

## Writing the USB

On macOS, either **Fedora Media Writer** (point-and-click, verifies the
checksum) or:

```bash
diskutil list                          # identify the stick -- carefully
diskutil unmountDisk /dev/diskN
sudo dd if=Fedora-Server-dvd-x86_64-44-1.7.iso of=/dev/rdiskN bs=4m status=progress
```

`rdiskN` rather than `diskN` is substantially faster. Getting the disk
number wrong overwrites something you care about, so run `diskutil list`
twice.

## Booting it

**On a Mac:** hold **⌥ Option** during startup and choose the USB. This
happens in Apple firmware, before any OS loads, so a *Bluetooth keyboard
will not work* -- use the built-in one or a wired USB keyboard.

**On a ThinkPad:** F12 for the boot menu, or Enter then F12.

Nothing is written to disk until you explicitly run the installer, so
booting to test costs nothing.

## Install choices that matter

| choice | value | why |
|---|---|---|
| software selection | **Minimal Install** | no desktop; fewer processes competing with the measurement |
| partitioning | Automatic | nothing here needs a custom layout |
| network | **wired ethernet** | removes a wireless driver from the equation; a headless box with broken wireless cannot be reached to fix |
| root/user | any | you will type it once, then use SSH keys |
| SSH | **enable** | this machine should be headless |

On a laptop with damaged keys, choose a username and password composed
only of keys that work. It is typed once.

## After installation

```bash
# headless access
sudo systemctl enable --now sshd
ip a | grep 'inet '

# from the workstation, so passwords are never typed again
ssh-copy-id user@<ip>
```

Then apply `../../results/BENCHMARK_HOST.md` in full -- disabling the
periodic timers, pinning the CPU governor, masking the sleep targets,
and on a laptop stopping the lid from suspending it. That document
exists because a day was spent investigating a 240ms latency excursion
that turned out to be environmental.

## Building the scheduler

```bash
sudo dnf install -y git cargo rustc clang llvm bpftool libbpf-devel \
                    elfutils-libelf-devel zlib-devel pkgconf-pkg-config \
                    make jq tmux stress-ng perf

git clone https://github.com/sched-ext/scx.git
git clone <your scx-cms repo> scx/scheds/experimental/scx_cms
cd scx && cargo build -p scx_cms

uname -r                                   # confirm >= 6.12
cat /sys/kernel/sched_ext/state             # should exist
```

`scx_cms` does not build standalone -- it depends on `scx_utils` by
relative path and uses scx's BPF tooling, so it must sit inside an scx
checkout.

Workload tools: `schbench` and `rt-app`, both built from source.
`rt-app` matters here specifically -- it was unusable in the VM, and
bare metal is what makes the audio-callback workload testable at last.

## What to run first

Not the headline experiment. **Re-run the existing matrices and score the
predictions**, which are already written down and dated in the paper's
limitations section:

| prediction | should |
|---|---|
| the memory result (exact goes inert when its map cannot hold the live identity set; the sketch's footprint does not grow with identity count) | **survive** — it is a capacity relationship, not a hardware one |
| the exact tracker's failure threshold | **be unchanged**, because it tracks the ratio of live identities to map capacity and *not* the core count. Unchanged on 4 cores and on 16, given the same identity population |
| every absolute latency figure | **shrink** — the ~65,000us do-nothing baseline is substantially inflated by virtualisation |
| median-latency equivalence | **survive** |
| the paired p99 ratio distribution (median 1.18x/1.14x, sketch better in 37%/40%, >50% worse in 30%/33%) | **be the thing most at risk**, since it rests on spread and a noisy environment manufactures spread |
| tail excursions | **shrink or vanish across every condition together**, including exact counting — they are environmental (revision 9), not a sketch property |
| `rt-app` | **become usable** once the ~1.7ms timer floor disappears, reopening the audio-callback workload |

Note what is *not* on that list. An earlier version of this file said
"the `LRU_HASH` cliff should stay put if this is also a 4-core machine".
Both halves were withdrawn before any bare-metal run happened: there is
no BPF-specific cliff, only an ordinary LRU thrashing below its working
set, and the threshold does not scale with CPU count (revision 12). The
corrected prediction is the second row above, and it is sharper than the
one it replaces because it can fail.

A prediction that fails is more interesting than one that holds.

For energy, follow `../../benchmark/ENERGY_METHOD.md`, which starts with
instrument validation rather than with a comparison -- an instrument that
cannot detect a sledgehammer cannot detect the mechanism.

## Record what you built

Add the new machine to `../../results/ENVIRONMENT.md`: kernel, CPU model,
core count, whether RAPL is present, and what was disabled. Every
bare-metal number will be compared against the VM archive, and "what was
different about the machine" is unrecoverable after the fact.

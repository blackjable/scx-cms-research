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

**What is now unexplained:** why the two original matrices disagreed.
Ordering is ruled out. Condition subset and ordinary run-to-run variation
remain, and are untested rather than concluded -- which is the whole
point of this entry.

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

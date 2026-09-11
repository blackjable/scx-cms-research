# Record of revisions

Seven claims were stated during this work and later withdrawn. They are
listed here in full, each tied to the raw file that produced it and the
raw file that overturned it, so a reader can check both rather than
take the correction on trust.

This exists because the retractions are not incidental to the result --
they *are* a substantial part of it. Six of the seven were caused by a
faulty instrument rather than by a faulty hypothesis, and identifying
each fault is what eventually made the final measurement trustworthy.
A record that showed only the surviving conclusions would misrepresent
how they were arrived at, and would hide the five controls that turned
out to matter.

---

## 1. "Seed rotation mitigates the targeted-collision attack at heavy volume"

**Withdrawn:** did not replicate on a second run.
**Cause:** single-run result treated as a finding.
**Source:** Phase 1 / delivery plan §9.6 (predates this archive).

## 2. "+34.7% improvement"

**Withdrawn:** became −1.7% at n=15.
**Cause:** small-sample optimism. The only one of the seven that more
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
**Aggravating factor:** this was an *interesting* result with a
plausible mechanism (collisions inflating the protected task's count),
and it was accepted at n=20 with visibly less scrutiny than the
disappointing results received. It had been explicitly predicted to be
the finding *least* likely to be an ordering artefact.
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

More data would have caught exactly one (#2). The rest required a
control or an instrument that did not exist yet:

| fault | fix |
|---|---|
| fixed condition ordering | randomise per repetition, seeded |
| metric with a broken zero point | add a do-nothing reference |
| ratio with a collapsing denominator | measure against truth, not a dying comparator |
| workload model wrong by 4x | instrument the distribution instead of inferring |
| `LRU_HASH` not behaving as named | control with a plain hash at equal capacity |
| cross-run comparison | put both conditions in one interleaved matrix |

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

Median latency *is* equivalent (CI [0.974, 1.060]). The sketch matches
exact on the typical case and loses on the tail.

**The corrected claim:** the sketch continues to function at a budget
where exact counting does not, at the cost of roughly 17% worse tail
latency and with equivalent median latency. A trade, not a free lunch.

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

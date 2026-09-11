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
**Original:** `raw/r2-count-attributable-n15.txt`
**Correction:** `raw/r2b-flat-control-n8.txt`, confirmed in
`raw/r2d-randomised-order-n20.txt`

## 4. "The sketch has a ~10% severe failure rate"

**Withdrawn:** 0 of 20 after the ordering fix.
**Cause:** fixed condition ordering. Carryover from a pathological
neighbour landed on the same condition every repetition.
**Aggravating factor:** this was an *interesting* result with a
plausible mechanism (collisions inflating the protected task's count),
and it was accepted at n=20 with visibly less scrutiny than the
disappointing results received. It had been explicitly predicted to be
the finding *least* likely to be an ordering artefact.
**Original:** `raw/r2c-prereg-n20.txt`
**Correction:** `raw/r2d-randomised-order-n20.txt`

## 5. "Exact counting beats the sketch at every memory budget"

**Withdrawn:** the metric could not distinguish a working tracker from
an inert one.
**Cause:** discrimination was measured against a count-blind baseline,
which is *worse than taking no action*. A tracker that had silently
stopped working therefore scored as well as one working perfectly.
Adding a `mechanism=none` reference -- absent from the original sweep --
showed exact counting at 85 and 21 entries was statistically identical
to doing nothing.
**Original:** `raw/r3-memory-sweep-n8.txt`
**Correction:** `raw/r5b-verify-reversal-inertness.txt`

## 6. "The sketch works down to 2.3 KB"

**Withdrawn:** at 2 KB every geometry is blunt.
**Cause:** reading p99 without p50. The tail improved 5x over inaction,
but the median had collapsed to the count-blind baseline's level, so
the sketch had stopped distinguishing tasks and was merely perturbing
them. The memory claim went from 15x to 4.3x.
**Original:** `raw/r7-r9-throughput-mapcontrol-geometry.txt`
**Correction:** `raw/o1-o4-budget-geometry-churning-n20.txt`

## 7. "Sketch at 8 KB matches exact at 32 KB" (as first stated)

**Withdrawn as stated:** the two figures came from different runs.
**Cause:** a cross-run comparison -- precisely the pattern revision 4
had already shown to be unsafe. The claim itself survived when
re-measured properly; the *evidence* for it did not.
**Original pairing:** `raw/thesis-confirmation-n20.txt` +
`raw/o1-o4-budget-geometry-churning-n20.txt`
**Correction:** `raw/headline-single-matrix-n20.txt`

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

**Original:** `raw/headline-single-matrix-n20.txt` (where the ranges
overlapped)
**Correction:** `raw/equivalence-n30-prereg.txt`

**Note on how this one was caught.** Unlike the previous seven, this
revision came from a test written specifically so that it could fail,
with its margin, metric, analysis and falsification clause committed
before any data was collected. The margin was deliberately set tighter
than the difference already observed. That is the only reason the
result changed rather than being confirmed by a test built to agree
with it.

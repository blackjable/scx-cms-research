# Twelve claims I retracted

I set out to test whether a Count-Min Sketch could replace exact
per-task counters in a Linux scheduler, saving memory without hurting
scheduling quality.

The answer turned out to be a qualified yes — 4x less memory, identical
typical latency, a worse and noisier tail. But between forming the
hypothesis and arriving at that, I
announced and then withdrew twelve separate conclusions, including, at
one point, the conclusion that the hypothesis was refuted — and, more
than once near the end, claims I had already written up as final and
published an explanation for.

None of them failed because the hypothesis was wrong. Every one failed
because an instrument was wrong — and each instrument was wrong in a way
that experimental design worked out decades ago and I had simply never
encountered.

That's the pattern worth writing about, and it's why I'm writing it as
someone who didn't know rather than someone warning you. I came to this
knowing how to write a scheduler and nothing at all about how to measure
one.

## The retractions

**1. "Seed rotation mitigates the collision attack at heavy volume."**
Looked clear on one run. Didn't replicate on the second.

**2. "+34.7% improvement."** At n=5. At n=15 it was −1.7%. Ordinary
small-sample optimism, and the only one on this list that more
repetitions would have caught.

**3. "Acting on the tracked count improves tail latency 6.8x."** Real,
replicated, non-overlapping ranges at n=20. Then I built a control that
applied the same vtime perturbation while ignoring the tracked count
entirely, and it reproduced about 82% of the improvement. The comparison
had been measuring "does perturbing scheduling help" and I'd been
reading it as "does tracking wakeups help."

**4. "The sketch has a ~10% severe failure rate."** Two of twenty runs
showed the protected task getting catastrophically mis-scheduled. I had
a mechanism for it — hash collisions inflating the victim's count — and
called it the most policy-relevant sketch finding I'd made. After fixing
an unrelated benchmark bug, it was zero of twenty. It had been an
artifact of condition ordering.

**5. "Exact counting beats the sketch at every memory budget."** The
metric was a discrimination ratio measured against a count-blind
baseline. That baseline is *worse than taking no action at all*, so a
tracker that had quietly stopped working scored just as well as one
working perfectly. Adding a do-nothing reference condition — which the
sweep had never included — showed that at small budgets the exact
tracker wasn't discriminating. It was inert.

**6. "The sketch works down to 2.3 KB."** It improved the tail there,
5x over doing nothing. But its median had collapsed to the level of the
blunt control, meaning it had stopped telling tasks apart and was just
perturbing everything. Genuine working range: 8 KB. My memory claim went
from 15x to 4.3x.

**7. "A sketch at 8 KB matches exact counting at 32 KB."** The claim
survived. The evidence for it didn't. The two numbers came from
*different runs* — and I'll come back to this one, because it's the
worst of the twelve.

**8. "The sketch is equivalent to exact counting at 4x less memory."**
The memory saving held. *Equivalent* did not. I'd inferred it from
overlapping measurement ranges, which show a difference was not
detected, not that none exists. A pre-registered equivalence test at
n=30 put the sketch 11–39% worse on tail latency, with equivalent
median. The corrected claim is a trade rather than a substitution.

**9. "The sketch has a rare, severe failure mode invisible to normal
monitoring."** I found one run in thirty where a sketch performing
normally returned a tail latency twenty-four times its own median, with
its typical-case latency untouched. It looked like a distinct and
rather alarming failure mode, so I wrote it into three posts. Then I
measured it: at sixty repetitions per condition, **exact counting
produces the same excursions at the same rate**, and the 24x never
recurred across 360 further measurements. It belongs to the
environment, not to the sketch.

**10. "The tail penalty is intrinsic to approximation, not the price of
the memory saving."** I'd built this on a control that failed — sketch
at 32 KB against exact at 32 KB, same budget, still not equivalent. A
failing control feels like a finding, so I treated it as one. It had
failed because of the single outlier from retraction 9. With that
understood, matched-memory medians agree at 1.03x and 1.04x across two
runs. Give the sketch the same memory and it performs the same. The
tail cost is what you pay for using less memory, which is what I'd
assumed before the control appeared to overturn it.

**11. "I looked for scheduler evaluations that randomise condition order
and didn't find them."** I didn't look. This one isn't a measurement
error — it's a sentence I wrote into a draft of post 01, asserting a
literature search that never happened, while trying to make a weak claim
sound stronger. A reader asked whether it was true. It wasn't.

**12. "BPF's `LRU_HASH` stops behaving like an LRU when the map is
small."** My favourite finding, and wrong. A small LRU reporting nearly
nothing looked like a bug in the map type; it's what any correct LRU does
when the working set exceeds capacity. A 42-entry map works fine with 8
or 20 identities and only collapses at 100 or 300 — so the collapse
tracks overcommitment, not size. I'd asserted a mechanism I never tested,
and only tested it when a reader asked whether the problem was BPF's or
mine.

## The pattern

Reading them together, the striking thing is that more data would have
saved me from exactly one — number 2.

Nine of the rest were instrument failures:

- **A benchmark harness that ran conditions in fixed order**, so
  carryover from one condition landed on the same neighbour every
  repetition. Systematic bias that repetitions cannot average away. With
  a pathological neighbour in the matrix, the same configuration put 6
  of 15 repetitions above 14,000µs; run first from a clean state, 0 of
  20 reached that at all. The medians barely moved, which is why it was
  invisible.
- **A metric that couldn't distinguish "working" from "doing nothing"**,
  because its reference point was worse than doing nothing.
- **A ratio whose denominator was collapsing**, so an "inflation" figure
  of 1,043x turned out to be 2.6x once measured against truth rather
  than against a dying comparator.
- **A workload model wrong by 4x**, which I patched twice with better
  reasoning before instrumenting the thing and discovering the
  distribution was bimodal.
- **A cross-run comparison**, which is its own entry below.

Every one of those fixes came from adding a control or an instrument.
None came from running more repetitions of the same measurement.

**The last three are a different animal, and they're the ones I'd warn
you about.** In 9, 10 and 12 the instrument was fine and the numbers
were right. What was wrong was the story I attached to them — a sketch
failure mode, an intrinsic cost of approximating, a broken map type —
and in each case I picked the explanation that was more interesting than
the mundane one that fit equally well. An outlier became a failure mode.
A control that failed for an unrelated reason became a finding. A
thrashing cache became a trap in BPF.

No control catches that, because nothing is malfunctioning. The only
thing that catches it is testing the mechanism separately from the
measurement, which in all three cases took under half an hour once I
bothered.

## The one that bothers me most

Number 7, and not because it was the largest error. It was the
smallest — the claim turned out to be right when I re-measured it
properly.

It bothers me because **post 1 of this series is entirely about why
figures from different matrices aren't comparable.** I found that bug,
spent hours tracing it, fixed it, understood the mechanism well enough
to explain it to strangers — and then built my headline result by
pairing a number from one run against a number from another.

Nobody caught it in review. I caught it while writing up a defence of
my own confidence, going through the numbers one more time to explain
why they should be trusted.

Knowing a failure mode does not inoculate you against it. I could
state the principle correctly, at length, in public, while
simultaneously violating it in the most important comparison I had.
The knowledge and the application live in different places, and only
one of them gets exercised when you're pleased with a result.

Re-running it as a single interleaved matrix took forty minutes. The
claim held: 12% apart on median p99, ranges overlapping, medians within
1%. But for a day before that, the headline of the whole project rested
on a comparison I had personally written a blog post explaining you
must not make.

## The other one that bothers me

Number 4.

The others were disappointing results that I attacked properly — I ran
controls, raised sample sizes, and at one point voided my own
pre-registration when it failed its gating condition.

Number 4 was an *interesting* result. It came with a plausible
mechanism. Collisions inflating the protected task's count was exactly
what the theory predicted, so when the data showed it, the mechanism
felt like confirmation rather than something still to be tested. I
accepted it at n=20 with visibly less scrutiny than I'd applied to
results I didn't like — and I'd explicitly predicted it was the finding
*least* likely to be an ordering artifact, right before it turned out to
be one.

That's not a sample-size problem and no statistical discipline catches
it. Asymmetric skepticism is invisible from the inside, because at each
moment you're applying what feels like the appropriate level of rigour.
The asymmetry only shows up when you line the decisions up afterwards.

The practical defence I've landed on: **have a mechanism and treat it as
a reason for more scrutiny, not less.** A plausible causal story means
you now have a specific prediction to test, not that you're done.

## What it cost, and what it bought

Roughly a day. Twelve announcements withdrawn — one of them a claim that
the whole project had failed, several arriving after I had written the
result up as final, and one that was never a measurement at all.

The eighth is the only one caught by a test built specifically so that
it could fail: margin, metric, analysis and falsification clause all
committed before the data existed, with the margin set tighter than the
difference already observed. Every previous revision was caught by
accident — a disagreement between two runs, a control added for
completeness, someone asking how confident I really was.

And then the ninth punctured my satisfaction about that.

The outlier in retraction 9 came with a *pre-registered* check meant to
rule out an environmental cause: I'd specified in advance that I would
report whether outliers clustered across conditions within a
repetition, reasoning that a host-level disturbance would disturb
several. Only one condition was affected, so I concluded the sketch was
responsible.

**Conditions run sequentially.** A disturbance lasting a few seconds
hits exactly one of them. The signature I had declared exonerating was
precisely what an environmental cause produces. I'd written the check
in advance and it was simply the wrong check.

That's the distinction I'd underweighted: pre-registration guarantees
you didn't choose your test to fit the data. It does not guarantee your
test measures what you think it measures. The first is a defence
against motivated reasoning; nothing defends against being wrong about
the mechanism except measuring it.

What it bought: the final result is one I believe. The memory claim is
n=20 with non-overlapping ranges, the geometry that achieves it is
measured rather than defaulted, the regime where it stops holding is
stated in the claim, and the failure modes of both structures are
characterised.

It also produced findings I'd never have gone looking for — the
count-blind control, the ordering bias, the difference between a
structure that fails silently and one that fails loudly — all of which
are useful to people who don't care about count-min sketches at all.

## The one no instrument would have caught

Retraction 11 sits apart from the others and I nearly left it out of
this list, which is itself a reason to include it.

Most of the others were measurement errors, and each was caught by
something — a control, a reference condition, a larger sample, two runs
disagreeing. Those are mechanisms, and they work whether or not you're
paying attention. Even 9, 10 and 12, where I'd invented the mechanism
rather than mismeasured it, were in the end settled by running a test.

Number 11 wasn't a measurement at all. It was me writing something
untrue because it made a weak argument sound better. No control catches
that. No sample size helps. The only thing that caught it was a reader
asking, of one sentence, *"is that a true statement?"*

I find that the most uncomfortable item here, because every defence I'd
built over the preceding day — randomised ordering, do-nothing
references, pre-registered margins — was aimed at stopping me fooling
myself with data. None of it was aimed at stopping me writing a
convenient sentence about the literature. The rigour was all pointed at
the measurements and none of it at the prose describing them.

## If I were starting again

**Put a do-nothing condition in every matrix.** Without it you cannot
tell a working mechanism from a stopped one, because both leave your
protected workload alone.

**Put a blunt control in every matrix** — the same intervention applied
without the information. It tells you what fraction of your result is
attributable to the signal rather than the disturbance.

**Randomise condition order**, and print the seed.

**Instrument before you infer.** I spent three rounds reasoning about a
4x discrepancy that one histogram resolved in a single run.

**Write down what would falsify each claim, before the run.** I did this
once, via a pre-registration, and it was the only time I caught myself
about to accept a favourable result whose framing had already failed.

None of that is novel advice. Most of it is a century old and I'd met
none of it. I adopted each piece the day after it would have saved me,
which is an expensive way to learn but does make the lessons stick.

If you're in the same position — comfortable with the systems, hazy on
the method — the good news is that the fixes are all small. A do-nothing
condition is one line. Randomising order is six. Writing your margin
down before you look costs nothing at all. The cost isn't in applying
them, it's in not knowing they exist.

## Data

Every retraction is recorded with the file that produced it and the file
that overturned it: [`REVISIONS.md`](../results/REVISIONS.md). The
handful of figures quoted in this post, and where to check them:

| claim | file |
|---|---|
| the ordering bias: 6/15 above 14,000µs vs 0/20 | [`r2-count-attributable-n15.txt`](../results/raw/r2-count-attributable-n15.txt), [`r2c-prereg-n20.txt`](../results/raw/r2c-prereg-n20.txt) |
| the 6.8x, and the count-blind control that reproduced 82% of it | [`r2d-randomised-order-n20.txt`](../results/raw/r2d-randomised-order-n20.txt) |
| the equivalence test that refuted "equivalent" (n=30) | [`equivalence-n30-prereg.txt`](../results/raw/equivalence-n30-prereg.txt) |
| the 24x excursion, and exact counting showing the same rate (n=60) | [`excursion-rate-n60.txt`](../results/raw/excursion-rate-n60.txt) |
| the 42-entry LRU working fine with 8 or 20 identities | [`lru-working-set-test.txt`](../results/raw/lru-working-set-test.txt) |

The full archive is [`results/raw/`](../results/raw/), catalogued in
[`MANIFEST.md`](../results/MANIFEST.md), which labels which runs carry
the ordering bias and which predate the do-nothing reference condition.
Those runs are kept deliberately — the wrong answers are as much a part
of the record as the right ones.

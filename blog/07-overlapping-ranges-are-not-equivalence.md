# Overlapping ranges are not equivalence

I spent a day convinced two configurations of a Linux scheduler
performed identically. Their measurement ranges overlapped across almost
their whole extent. Their medians were 12% apart on a metric that varies
by more than that between runs. Every comparison I ran failed to
separate them.

Then I ran a test designed to check equivalence directly, and it said
they were 11–39% different.

Both results are correct. They answer different questions, and I didn't
know there were two questions.

## The thing I was doing wrong

The claim I wanted to make was: *a Count-Min Sketch at 8.3 KB gives the
same scheduling outcome as exact counters at 35.6 KB.*

The evidence I had was:

```
exact   @ 32 KB   p99 median 10,144µs   range 9,520–22,816
sketch  @  8 KB   p99 median 11,344µs   range 8,720–29,088
```

Overlapping ranges. Medians close. No statistical test I'd run could
tell them apart.

So I wrote "equivalent," and it took someone asking *how confident are
you, really* for me to notice that **failing to find a difference is not
the same as finding there is none.**

That distinction sounds pedantic until you notice what makes a
difference hard to find: **noise.** The wider your distributions, the
more reliably you'll fail to detect differences — including real ones.
"We couldn't tell them apart" is a claim about your measurement's
resolving power at least as much as about the things being measured.

Taken to its conclusion: the sloppier your experiment, the more things
you can declare equivalent. That should be alarming, and it's the
standard practice in a lot of systems work.

## What a real equivalence test looks like

The fix is to invert the burden. Instead of *"can I detect a
difference?"* you ask *"can I rule out a difference bigger than X?"* —
and you have to say what X is, in advance.

That's TOST — two one-sided tests. Practically:

1. **Declare an equivalence margin before you look.** Mine was ±20% on
   p99. Anything smaller wouldn't change a deployment decision; anything
   bigger and I'd be declaring equivalence for things that aren't.
2. **Pair your measurements.** My conditions were interleaved within each
   repetition, so each repetition gives a ratio of sketch to exact under
   the same conditions. Pairing removes between-run variation instead of
   letting it hide the effect.
3. **Compute a 90% CI on the mean log-ratio.** Log because latency
   ratios are multiplicative and right-skewed.
4. **Equivalence holds only if that entire interval sits inside the
   margin.** Not the point estimate — the whole interval.

The crucial property: **the margin must be tight enough that the test
can fail.** I set ±20% against an observed difference of 12%. Had I set
±50%, I'd have "demonstrated equivalence" and learned nothing, because a
test that cannot fail isn't a test.

## What happened

```
PRIMARY: sketch_8k vs exact_32k (p99, n=30 paired)
  median ratio       1.173x
  90% CI (param)     [1.114, 1.394]x   inside ±20%: False
  90% CI (bootstrap) [1.123, 1.387]x   inside ±20%: False
  EQUIVALENT within 20%: False
```

Not equivalent. The interval doesn't merely poke outside the margin —
its *lower* bound is 1.114, so even the optimistic end says the sketch
is 11% worse.

Thirty paired observations found what overlapping ranges could not.
Nothing changed about the systems; only the question did.

## The secondary result that made it useful

I'd also pre-registered the same test on the median, and on a
matched-memory control. Both turned out to matter more than the primary.

**On median latency, they *are* equivalent** — CI [0.974, 1.060], well
inside. So it isn't "the sketch is worse." It's "the sketch matches on
typical latency and loses on the tail," which is a specific, actionable
thing to know.

**The matched-memory control is the diagnostic** — and it taught me
something only after I'd misread it once.

Sketch at 32 KB versus exact at 32 KB — same budget, no memory saving
involved — also failed the equivalence test. I concluded the tail
penalty was intrinsic to approximation rather than a cost of the memory
saving, and wrote that up.

It was wrong, and one data point caused it. That comparison's mean was
dragged by a single 240,384µs outlier, which a later run at 60
repetitions per condition showed to be environmental — exact counting
produces such excursions at the same rate, and it never recurred.

With the outlier understood, the matched-memory medians agree across
two independent runs at **1.03x and 1.04x**. Give the sketch the same
memory as exact counting and it performs the same. The tail cost is
what you pay for using less memory, exactly as I'd assumed before the
control appeared to overturn it.

Two lessons, and the second is the one I'd underrate:

**A control that fails is not automatically informative.** Mine failed
for a reason that had nothing to do with the comparison, and I built an
explanation on it because a failing control feels like a finding.

**An equivalence test is still a mean-based test.** TOST told me
correctly that I could not claim equivalence. It did not tell me that
one observation in thirty was doing the work, and I did not look until a
later run forced me to.

## Why this is worth the trouble

The honest version of my result — *4x less memory, same typical latency,
a worse and much noisier tail* — is more useful than "equivalent" would
have been,
and it's the version someone can act on. If you're memory-constrained,
that's a trade you can evaluate. If you're not, the sketch has nothing
to offer you, and "equivalent" would have obscured that.

It also cost me almost nothing. The test was forty minutes of machine
time on data I was collecting anyway. What it required was writing the
margin down first.

## The practical version

- **Overlapping ranges mean you failed to detect a difference.** Say
  that, not "equivalent."
- **If you want to claim equivalence, test for it** — TOST, margin
  declared in advance, whole interval inside the margin.
- **Pick a margin that could fail**, and pick it before looking.
- **Pair when your design allows it.** Interleaving conditions within
  repetitions is usually free and enormously more powerful than
  comparing summary statistics.
- **Test a control you expect to be equivalent** — and when it fails,
  find out *why* before you believe it. Mine failed, and the failure was
  the least informative result in the study dressed up as the most.

The last one is the one I'd most want to pass on, and not in the form I
first wrote it. I added the matched-memory control for completeness,
expecting a boring confirmation. It failed, and I treated the failure as
a finding — because a control that fails feels like a finding, in a way
a control that passes never does.

It had failed because of one environmental outlier. The explanation I
built on it was wrong, and I had it backwards for a day: I'd decided the
tail cost was intrinsic to approximating, when it is simply what you pay
for using a quarter of the memory. A failing control is a question, not
an answer. Mine was asking about the host, and I heard it asking about
the sketch.

## Data

| claim | file |
|---|---|
| the overlapping ranges that looked like equivalence | [`headline-single-matrix-n20.txt`](../results/raw/headline-single-matrix-n20.txt) |
| the equivalence test that refuted it (n=30) | [`equivalence-n30-prereg.txt`](../results/raw/equivalence-n30-prereg.txt) |
| the outlier shown to be environmental (n=60) | [`excursion-rate-n60.txt`](../results/raw/excursion-rate-n60.txt) |

Pre-registration, committed before the data existed:
[`PREREGISTRATION_equivalence.md`](../benchmark/PREREGISTRATION_equivalence.md).
Analysis, committed before the run finished:
[`analyse_equivalence.py`](../benchmark/analyse_equivalence.py).

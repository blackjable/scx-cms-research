# Overlapping ranges are not equivalence

I spent a day convinced two configurations of a Linux scheduler
performed identically. Their measurement ranges overlapped across almost
their whole extent. Their medians were 12% apart on a metric that varies
by more than that between runs. Every comparison I ran failed to
separate them.

Then I ran a test designed to check equivalence directly, and it said
they were 11–39% different.

Both results are correct. They answer different questions, and I had
been reading the answer to one as the answer to the other.

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

**The matched-memory control is the diagnostic.** Sketch at 32 KB versus
exact at 32 KB — same budget, no memory saving involved — is *also* not
equivalent on p99.

That relocates the cause entirely. I'd assumed the tail penalty was what
I paid for using less memory. It isn't. It's what approximation costs at
any size, because collisions occasionally inflate one task's count and
produce a scheduling decision exact counting wouldn't make. One
repetition showed it plainly: 240,384µs, twenty-four times that
condition's own median, with nothing else in that repetition disturbed.

Worth being precise about what that run looked like, because it isn't
what I first assumed. Its **median was 3,828µs — completely normal**,
matching exact counting's 3,844µs to within half a percent. The sketch
had not lost the ability to tell tasks apart. It was working correctly
for essentially every wakeup, and then a handful of them waited a
quarter of a second. A failure invisible to anything watching the
typical case.

Without that control I'd have reported a true number attached to the
wrong explanation.

## Why this is worth the trouble

The honest version of my result — *4x less memory, same median latency,
11–39% worse tail* — is more useful than "equivalent" would have been,
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
- **Test a control you expect to be equivalent.** Mine wasn't, and that
  was the most informative result in the study.

The last one is the one I'd most want to pass on. I added the
matched-memory control for completeness, expecting a boring
confirmation. It failed, and in failing told me my explanation for the
headline number had been wrong the whole time.

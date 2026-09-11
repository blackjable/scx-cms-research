# The control that killed my 6.8x speedup

I built a BPF scheduler that tracked how often each task woke up and
penalised the frequent wakers. Measured against the same scheduler with
the mechanism switched off, it improved a latency-sensitive task's tail
latency by **6.8x**, with non-overlapping ranges across twenty
repetitions.

That number is real. It is also almost entirely not about wakeup
tracking, and the control that showed me so took twenty minutes to write.

## The comparison that looked rigorous

The scheduler had a load-time flag selecting what to do with the tracked
count. `--mechanism penalty` adjusted a task's virtual runtime in
proportion to how often it had woken; `--mechanism none` tracked
identically and then did nothing.

Comparing those two felt airtight. Same scheduler binary. Same tracking
code on the same hot path, so identical overhead. Same workload, same
machine, randomised condition order, n=20. The *only* difference was
whether the mechanism acted on the number it had already computed.

```
none             p99  80,640us
exact+penalty    p99  11,744us     6.8x better
```

## What it was actually measuring

`penalty` does two things at once:

1. It consults the tracked wakeup count.
2. It perturbs the task's virtual runtime.

Comparing against `none` — which does *neither* — measures both together
and attributes the result to the first.

The question I should have asked much earlier is: **what happens if you
do the perturbation without the count?**

So I added a third mechanism. `flat` applies an identical vtime penalty
to every task at every enqueue, with no reference to the tracked count
at all. It is deliberately, structurally stupid — it cannot tell any
task from any other. I swept it across several strengths so it had a
fair chance of beating the real mechanism.

```
none             p99  80,640us
flat  (count-blind)   p99  16,576us     4.9x better
exact+penalty         p99  11,744us     6.8x better
```

**A mechanism that ignores the count entirely captures most of the
improvement.** On a log scale, roughly 82% of the effect was generic
vtime perturbation. The tracking — the entire point of the project — was
responsible for the remainder.

## Why no standard baseline catches this

I hadn't skimped on baselines. Following current practice for sched_ext
evaluation, I had four tiers:

1. Stock EEVDF — is a custom scheduler worth it at all?
2. `scx_simple` — does this beat the minimal reference scheduler?
3. Exact counters instead of the sketch — does the approximation cost anything?
4. A production scheduler (`scx_lavd`) — how does this compare to what people run?

Every one is a reasonable comparison. And **not one of them could have
caught this**, because they all vary *the scheduler*. None varies only
*whether the signal is used*.

That's the gap. If your mechanism does anything besides consult its
signal — and almost all of them do — then "mechanism on versus off"
conflates the signal with everything else the mechanism does. You need a
condition that performs the same intervention *blindly*.

## What the count actually bought

Once `flat` was in the matrix, a second thing became visible that the
tail metric alone had hidden.

```
                 p50        p99
none           3,920us   80,640us
flat          11,776us   16,576us
exact+penalty  3,920us   11,744us
```

`flat` gets its tail improvement by making **every** wakeup slower —
including the latency-sensitive task's. Its median is 3x worse than
doing nothing at all. The count-proportional version reaches a better
tail while leaving the median *identical to `none`, to the microsecond*.

So the count isn't worthless. But its contribution isn't the 6.8x — it's
that you can improve the tail without taxing the typical case, because
you can tell the tasks apart. That's a much smaller and much more
specific claim than the one I was about to publish.

## The general form

If you are evaluating a heuristic that tracks something and acts on it,
the comparison you want is not:

> mechanism on vs mechanism off

It's:

> **mechanism on vs the same intervention applied blindly**

The second is cheap to build — mine was about forty lines — and it tells
you what fraction of your result is attributable to the information
rather than to the disturbance.

I'd guess this generalises well beyond my project. Schedulers track lots
of things: run length, migration rate, waker-wakee locality, cache
warmth, deadline slack. Each is used to make a decision that also
perturbs scheduling in some non-neutral way.

What I'd built, without knowing the term, was an experiment missing its
placebo arm. Medicine worked out why you need one a long time ago: if
your treatment does two things, comparing against nothing tells you the
pair worked, not which half. I'd have nodded along to that stated
abstractly. I did not spot it in my own design.

I'm not going to claim nobody does this in systems work — I haven't
surveyed the field. What I can report is my own case, which is the
uncomfortable one: I derived four baseline tiers from current sched_ext
evaluation practice, thought carefully about them, and not one varied
only whether the signal was used. The gap wasn't an oversight against a
standard I knew about. I didn't think of it until the number looked too
good.

So I don't know how many tracked signals survive a count-blind control.
Mine mostly didn't, and that's one data point.

## What I'd tell myself

The 6.8x wasn't fabricated, and I didn't tune anything to get it. It was
a real measurement of a real improvement, produced by a rigorous-looking
comparison with a control condition, replicated at n=20 with
non-overlapping ranges.

It was still, in the sense that mattered, wrong — because "the mechanism
helps" and "the count helps" are different claims, and my experiment
could only distinguish them once I built something that did one without
the other.

Controls are not a statistical formality. They're how you find out which
of the several things your treatment does is the thing you're claiming
credit for.

## Data

| claim | file |
|---|---|
| the original 6.8x against `mechanism=none` | [`r2-count-attributable-n15.txt`](../results/raw/r2-count-attributable-n15.txt) |
| the count-blind control, swept at 2/4/8ms | [`r2b-flat-control-n8.txt`](../results/raw/r2b-flat-control-n8.txt) |
| both re-measured under randomised ordering (n=20) | [`r2d-randomised-order-n20.txt`](../results/raw/r2d-randomised-order-n20.txt) |

The control is `--mechanism flat` in
[`flat.bpf.c`](https://github.com/blackjable/scx-cms/blob/main/src/bpf/mechanisms/flat.bpf.c),
roughly forty lines.

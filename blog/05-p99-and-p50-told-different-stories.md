# p99 told me one story, p50 told me another

Scheduler evaluations lead with tail latency, and they're right to. If
your audio callback misses its deadline four times a second, nobody
cares that the median was fine.

But I spent a day where p99 and p50 disagreed about which scheduler was
better, and working out who was right taught me something narrower and
more useful than "report both."

## The disagreement

Two mechanisms. One penalised tasks in proportion to how often they woke
up. The other — a control I built to check the first — applied an
identical penalty to *every* task, ignoring the tracked count entirely.

On tail latency they were hard to separate:

```
count-blind penalty   p99  16,576us
count-based penalty   p99  11,744us
```

Better, but the ranges overlapped in some runs. If p99 were my only
metric I'd have concluded the tracking bought little.

Then I looked at the median:

```
                       p50        p99
do nothing           3,920us   80,640us
count-blind penalty 11,776us   16,576us
count-based penalty  3,920us   11,744us
```

The count-blind mechanism gets its tail improvement by making **every**
wakeup three times slower, including the task I was trying to protect.
The count-based one reaches a better tail while leaving the median
*identical to doing nothing, to the microsecond*.

Same tail metric, completely different machines to live on.

## What I wanted to conclude, and why it was wrong

My first instinct was a satisfying general claim: *tail-latency-only
evaluation rewards blunt instruments, because degrading everything
uniformly also compresses the tail.*

It sounds right. It's the kind of thing that would make a good talk
slide. And when I checked it against my own data, it didn't hold up.

I went back through every comparison I'd run and asked: would p99 alone
have given the *wrong ranking*?

| workload | p99-only would pick | wrong? |
|---|---|---|
| stable identities | the count-based mechanism | no — correct |
| high task churn | the count-blind mechanism | arguably correct, for a deadline-sensitive task |
| one run at n=15 | *inconclusive* — ranges overlapped | not wrong, just silent |

**In no run did p99 alone produce a clearly wrong ranking.** It produced
an *inconclusive* one, once. That's a much smaller claim than the one I
was about to make, and the difference matters: "this metric is
misleading" and "this metric is sometimes insufficient" call for
different responses.

I'd built a general principle out of a hypothetical, and my own results
contradicted it. That was uncomfortable enough to be worth writing down.

## What p50 is actually for

Two things, both narrower than "it's the real metric":

**Breaking ties p99 can't.** When two policies' tail ranges overlap,
p99 says "no difference demonstrated" and stops. p50 said one of them
tripled typical latency. That's real information the tail metric could
not provide.

**Cost accounting.** A tail improvement is only free if nothing else got
worse. p50 tells you what you spent — and in my case revealed that one
mechanism was paying for its tail with the median while the other paid
nothing.

Where the workload has a genuine deadline, **p99 remains the number that
decides whether the scheduler works.** p50 doesn't replace that. It
tells you what the p99 cost you.

## Where it changed a real conclusion

Later in the same project I compared two counting structures at shrinking
memory budgets. At the smallest budget, the approximate one still showed
a solid tail improvement over doing nothing — 4.9x.

Tempting headline: *works down to 2 KB.*

The median said otherwise. At 2 KB its p50 had collapsed from ~3,900µs
to ~9,900µs, right at the level of the count-blind control. It wasn't
discriminating between tasks any more. It was just perturbing everything
and compressing the distribution — exactly the mechanism I'd built the
control to detect.

So its genuine working range ended at 8 KB, not 2 KB. My memory claim
went from 15x to **4.3x**, and the only thing standing between me and
publishing the inflated number was having the median in the table.

That's the concrete version of the general claim I couldn't support.
Not *"p99 is misleading"* — it wasn't. But *"a tail improvement with a
median collapse is a different result from one without, and p99 cannot
tell you which you have."*

## The practical version

Report both. Not because tail latency is wrong — it's usually the metric
that matters — but because:

- When tail ranges overlap, the median may still separate them
- A tail win with a median regression is a trade, not a victory, and
  should be described as one
- If a mechanism's median collapses to the level of a do-nothing or
  do-everything control, it has stopped discriminating regardless of
  what its tail says

That last one is the check I'd actually recommend. It requires having a
blunt control in your matrix, which most evaluations don't. Without it
you have no reference for what "stopped discriminating" looks like.

## Data

| claim | file |
|---|---|
| the count-blind mechanism's median cost | [`r2d-randomised-order-n20.txt`](../results/raw/r2d-randomised-order-n20.txt) |
| the 2 KB sketch improving p99 while p50 collapsed | [`o1-o4-budget-geometry-churning-n20.txt`](../results/raw/o1-o4-budget-geometry-churning-n20.txt) |
| the per-repetition ratio spread a median conceals | [`equivalence-n30-prereg.txt`](../results/raw/equivalence-n30-prereg.txt), [`excursion-rate-n60.txt`](../results/raw/excursion-rate-n60.txt) |

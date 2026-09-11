# My scheduler benchmark was lying to me for four rounds

I spent a day measuring a Linux scheduler and reached four conclusions.
Then I found a bug in my benchmark harness, re-ran everything, and one
of those conclusions reversed.

The bug was six lines of Python, and I suspect it's in a lot of
benchmark harnesses. Here it is.

## The setup

I was testing whether a BPF scheduler could track per-task wakeup
frequency more cheaply using a Count-Min Sketch instead of exact
counters. The details don't matter for this post. What matters is the
shape of the experiment: several *conditions* (different scheduler
configurations), each measured many times, compared on tail latency.

The harness looked like this:

```python
for rep in range(repeats):
    for name, binary, args in conditions:
        result = run_condition(binary, args)
        results[name].append(result)
```

Run every condition, repeat, take medians. Standard.

## What went wrong

Conditions ran in the **same order every repetition**.

That seems harmless. Averaging over many repetitions should wash out
noise, and it does — for noise. It does nothing for *carryover*.

Each condition leaves the machine in some state: a warm page cache, a
particular CPU frequency, a runqueue that hasn't drained, residue from
tearing down one BPF scheduler and attaching the next. Whatever that
state is, it lands on **the condition that runs next**. And with a fixed
order, that is the same condition every single time.

So it isn't noise. It's a systematic offset applied to one condition and
not the others, and no number of repetitions removes it. I ran fifteen.
Then twenty. The bias was in every one of them.

## How big was it

Big enough to reverse a conclusion.

One of my conditions was pathological on purpose — a configuration whose
tail latency ran around 80ms, an order of magnitude worse than anything
else. In one matrix it happened to sit immediately before the condition
I cared most about. In a later matrix, run with a different subset of
conditions, it wasn't in the list at all.

Same configuration, same machine, same workload:

| | p99 upper bound |
|---|---|
| preceded by the pathological condition | 21,664µs |
| run first, from a clean state | 14,000µs |

A 55% difference in the metric I was drawing conclusions from, caused
entirely by *what happened to run before it*.

The two runs disagreed about whether my mechanism produced a measurable
effect at all. I spent hours trying to reconcile them, assuming one was
noise and hunting for the sampling error. There wasn't one. Both were
accurate measurements of subtly different experiments.

## The fix

```python
import random

order_rng = random.Random(seed)

for rep in range(repeats):
    shuffled = list(conditions)
    order_rng.shuffle(shuffled)
    for name, binary, args in shuffled:
        ...
```

Shuffle per repetition. Seed it so a run is reproducible, and print the
seed with the results.

That's it. Carryover still happens — you can't prevent one condition
influencing the next — but it now lands on a *different* condition each
repetition, which converts systematic bias into noise. And noise is what
repetitions are for.

## Why I think this is common

Nothing about the buggy version looks wrong. It's the obvious way to
write the loop, and it's deterministic, which feels like a virtue in a
benchmark.

What struck me afterwards is that this problem is thoroughly solved
elsewhere. Randomising the order of treatments is textbook experimental
design, going back to Fisher's agricultural work in the 1920s. And
medicine has a name for precisely my failure: **carryover**, the effect
of one treatment persisting into the next. Crossover trials randomise or
counterbalance treatment order specifically to control it.

I didn't know that when I fixed it. I found the thing by running into
it: two matrices disagreed, I chased the discrepancy for hours assuming
one was noise, and eventually worked out that position in the sequence
was doing the work. The fix followed from the diagnosis. Only later did
I learn it already had a name, and that the name is old.

Which is, I think, the usual order. You find the edge of something by
walking into it, and the label comes after. Reading about carryover
would not have made me believe a 55% swing was possible from condition
ordering alone; measuring it did.

I don't know how common the mistake is in systems benchmarking — I
haven't surveyed the literature and I'm not going to claim a pattern I
haven't measured. What I can say is that my own harness had it, the
consequence was invisible in the results, and if you've written a
benchmark loop that iterates conditions in a fixed order then you have
it too.

And it's invisible in the results. There's no error, no warning, no
outlier that stands out. Every number is internally consistent. You get
a clean table with tight ranges and non-overlapping confidence intervals
that happens to be measuring something slightly different from what you
intended.

The only reason I found it was that I ran two matrices with different
condition *subsets* and they disagreed. If I'd only ever run one
configuration, I'd have published the biased numbers and never known.

## What to check in your own harness

**Does the condition order vary?** If not, whatever ran before your
treatment is part of your treatment.

**Does your condition list include anything pathological?** The
distortion scales with how different the neighbours are. A slow
condition contaminates whatever follows it far more than two similar
ones contaminate each other.

**Have you compared runs with different condition subsets?** That's what
exposed it for me. If adding or removing an unrelated condition changes
your headline number, ordering is the first suspect.

**Is there a settle period between conditions?** Randomising handles the
statistics; an idle gap between conditions reduces the carryover itself.
Both are worth having.

## The uncomfortable part

Every measurement I took before that fix is unreproduced. Not
necessarily wrong — but not established either, and I had to go back
through a day's worth of conclusions and mark which ones had actually
been re-established afterwards.

Several hadn't survived. One reversed outright.

I'd rather have found it than not. But the thing that unsettles me is
how close I came to never looking: the biased results were *coherent*.
They had tight ranges, they replicated across repetitions, and they told
a clean story. Internal consistency is not evidence that you're
measuring the right thing — it's only evidence that you're measuring the
same wrong thing reliably.

## Data

| claim | file |
|---|---|
| the biased run (fixed condition order) | [`r2c-prereg-n20.txt`](../results/raw/r2c-prereg-n20.txt) |
| the same comparison after randomising order | [`r2d-randomised-order-n20.txt`](../results/raw/r2d-randomised-order-n20.txt) |
| the two matrices that disagreed, exposing the bug | [`r2-count-attributable-n15.txt`](../results/raw/r2-count-attributable-n15.txt) |

Files carrying the ordering bias are labelled as such in the archive
manifest: [`MANIFEST.md`](../results/MANIFEST.md). They are kept rather
than dropped, because the retractions they caused are part of the record.

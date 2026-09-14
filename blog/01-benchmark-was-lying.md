# I spent a day fixing a benchmark bug that wasn't there

I have no training in experimental design. I write systems code, I
wanted to know whether a scheduler idea worked, so I built a benchmark
harness the obvious way and started measuring.

Two of my runs disagreed. I worked out why, fixed it, wrote it up, and
recommended the fix to other people. Then I tested the explanation and
it was wrong.

The fix was harmless and I kept it. The explanation was the problem, and
the way I arrived at it is the thing worth reading.

## The disagreement

I was testing whether a BPF scheduler could track per-task wakeup
frequency more cheaply using a Count-Min Sketch instead of exact
counters. The details don't matter. What matters is the shape: several
*conditions* (scheduler configurations), each measured many times,
compared on tail latency.

Two matrices, run a day apart, disagreed about the same configuration:

```
matrix A (n=15)   exact+penalty p99   max 21,664µs
matrix B (n=20)   exact+penalty p99   max 14,000µs
```

A 55% difference in a configuration that hadn't changed. The two runs
disagreed about whether my mechanism separated from its control at all.

## The explanation I reached for

My harness looked like this:

```python
for rep in range(repeats):
    for name, binary, args in conditions:
        result = run_condition(binary, args)
        results[name].append(result)
```

Conditions ran in the **same order every repetition**. And matrix A
happened to run a deliberately pathological condition — tail latency
around 80ms, an order of magnitude worse than anything else —
immediately before the condition I cared about. Matrix B didn't include
that condition at all.

So: carryover. Each condition leaves the machine in some state — warm
page cache, a particular CPU frequency, a runqueue that hasn't drained,
residue from tearing down one BPF scheduler and attaching the next — and
with a fixed order, that state lands on **the same condition every
time**. Not noise. A systematic offset that no number of repetitions
removes.

It's a real phenomenon. It has a name in medicine — **carryover** — and
crossover trials randomise or counterbalance treatment order
specifically to control it. Fisher was randomising treatment order in
the 1920s. I didn't know any of that when I found it; I learned the name
afterwards.

The fix is six lines:

```python
order_rng = random.Random(seed)

for rep in range(repeats):
    shuffled = list(conditions)
    order_rng.shuffle(shuffled)
    for name, binary, args in shuffled:
        ...
```

Shuffle per repetition, seed it, print the seed. Carryover still
happens, but it lands on a different condition each time, which converts
systematic bias into noise — and noise is what repetitions are for.

Everything above is sound. The measurements disagreed, carryover is
real, randomising is correct practice. I wrote it up, recommended it,
and moved on.

## What I never did was test it

The two matrices differed in **three** ways, not one:

- condition order (fixed with the pathological neighbour adjacent, vs
  the pathological condition absent)
- condition subset (four conditions vs three)
- sample size (15 vs 20)

They were also separate runs on different days. I picked the difference
that had a mechanism attached, and the mechanism was good enough that I
never noticed I was choosing.

So I eventually ran the experiment. Same four conditions, same n=20,
same parameters, same machine, back to back. One arm shuffles; the other
runs the fixed order, so the 80ms condition sits immediately before the
measured one in **20 out of 20** repetitions. Nothing else differs.

```
                      fixed    randomised    ratio
median              11,808µs      12,080µs    0.98x
mean                12,219µs      12,619µs    0.97x
maximum             16,016µs      19,424µs    0.82x
CV                      0.11          0.18
above 14,000µs          2/20          3/20

Mann-Whitney p = 0.86
P(fixed run > randomised run) = 0.48
```

**Nothing.** The fixed arm is marginally *better* and clearly *less*
variable. A coin flip.

A second angle, independent of that one: within the randomised arm,
adjacency was assigned at random, which makes it a genuine experiment on
the same question. The pathological condition landed immediately before
the measured one in 6 of 20 repetitions.

```
preceded by the 80ms condition       n=6    median 11,664µs
not preceded by it                   n=14   median 12,208µs
                                            p = 0.46
```

The repetitions that followed the pathological condition were, if
anything, slightly better.

Then I tested the second difference — condition subset — the same way.
Also null: 0.99x, p = 0.55.

## So what actually happened

I now have six independent measurements of the same configuration,
across both orderings and both subsets:

| run | order | subset | n | median | max | CV |
|---|---|---|---|---|---|---|
| A | fixed | with pathological | 15 | 12,784 | 21,664 | 0.23 |
| B | fixed | without | 20 | 11,712 | 14,000 | 0.08 |
| C | randomised | with | 20 | 11,744 | **39,488** | 0.47 |
| D | fixed | with | 20 | 11,808 | 16,016 | 0.11 |
| E | randomised | with | 20 | 12,080 | 19,424 | 0.18 |
| F | randomised | without | 20 | 12,192 | 22,048 | 0.27 |

**The median varies by 1.09x across every configuration I've ever run.
The maximum varies by 2.82x, with no relationship to either variable.**
The largest maximum of the six — 39,488µs — comes from a randomised run
with the pathological condition present, which is exactly the
configuration my theory said should be cleanest.

My original evidence was `21,664 / 14,000 = 1.55x`. That sits
comfortably inside the 2.82x range the maximum spans anyway.

The two matrices disagreed because **the maximum of a sample is a noisy
statistic, and I compared two of them.** That's the whole explanation.
There was no bug.

## The part I'd want you to take

Not "randomise your condition order" — though you should, it's six lines
and it protects against something real that I merely failed to
demonstrate. The useful part is what went wrong in my head.

**I had an anomaly and I reached for the explanation that came with a
mechanism.** Carryover is real, it's textbook, it has a name, it fit the
data, and it made me the kind of person who finds subtle bugs. The
competing explanation — *maxima are noisy* — is boring, explains the
data just as well, and makes me the kind of person who over-read two
numbers. I did not weigh them. I noticed the first one and stopped.

**Then I made it worse in the most reassuring way available.** Reviewing
this post, I decided "55%" was sloppy — it's a ratio of two maxima, the
noisiest statistic in either sample. So I replaced it with something
more rigorous: 6 of 15 repetitions above 14,000µs against 0 of 20,
Mann-Whitney p = 0.004, coefficients of variation 0.23 and 0.08. All
correctly computed. All from **the same two confounded runs.**

I improved the statistic and left the design alone, and the careful
version read as far more trustworthy than the sloppy one it replaced.
That is the trap I'd most want to hand on: rigour applied downstream of
a confound makes the confound harder to see, not easier.

**The check that would have caught it, at any point, was cheap.** Not a
better statistic — the same measurement with one thing varied. It took
forty minutes. I had a year of reasons not to bother, and all of them
amounted to already believing the answer.

## What to check in your own harness

**Does the condition order vary?** Randomise it anyway. I couldn't
demonstrate the effect on one workload on one machine, which is not the
same as showing it never happens, and the fix is too cheap to argue
about.

**Are you comparing maxima?** A maximum is the single noisiest summary
of a sample, and it's what your eye goes to when two runs disagree.
Mine ranged 14,000–39,488µs across runs whose medians sat inside 9%.

**When two runs disagree, count the ways they differ before explaining
why.** If it's more than one, you don't have an explanation, you have a
candidate. Mine had three and I noticed one.

**Can you test the explanation?** Not the measurement — the
*explanation*. If it has a mechanism, the mechanism makes a prediction,
and the prediction is usually one flag and one afternoon away from being
checked. A plausible causal story is a reason to run one more experiment,
not a reason to stop.

## The uncomfortable part

I recommended this to other people. It was in a paper draft as a
methodological finding, in a post as advice, and in three harness
comments as established fact, for long enough that I'd stopped thinking
of it as a finding at all and started treating it as background
knowledge.

None of the underlying measurements were affected — this was always an
explanation rather than data, and the results it was supposed to have
rescued stand unchanged. But I spent a day chasing a bug that wasn't
there, and I'd have gone on believing in it indefinitely if I hadn't
eventually run the experiment that could say no.

## Data

| claim | file |
|---|---|
| the two matrices that disagreed | [`r2-count-attributable-n15.txt`](../results/raw/r2-count-attributable-n15.txt), [`r2c-prereg-n20.txt`](../results/raw/r2c-prereg-n20.txt) |
| **the controlled test that found no ordering effect** | [`ordering-controlled-n20.txt`](../results/raw/ordering-controlled-n20.txt) |
| the condition-subset test, also null | [`condition-subset-n20.txt`](../results/raw/condition-subset-n20.txt) |
| the randomised run that produced the largest maximum of all | [`r2d-randomised-order-n20.txt`](../results/raw/r2d-randomised-order-n20.txt) |

The controlled test was pre-registered before its data was read:
[`PREREGISTRATION_ordering.md`](../benchmark/PREREGISTRATION_ordering.md),
analysed by [`analyse_ordering.py`](../benchmark/analyse_ordering.py).
Its falsification clause — what would show this post's original claim to
be wrong — is what fired.

The full retraction is [`REVISIONS.md`](../results/REVISIONS.md) revision
13, which is the thirteenth and the one I'd read first.

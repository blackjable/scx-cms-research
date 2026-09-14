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
and it insures against something real that I merely failed to
demonstrate. The useful part is upstream of any statistic.

**I had an anomaly and I reached for the explanation that came with a
mechanism.** Carryover is real, textbook, named, and it fit the data.
The competing explanation — *maxima are noisy* — is boring, fits the
data just as well, and makes me someone who over-read two numbers. I
didn't weigh them. I noticed the first and stopped.

**Making the statistic more careful did not help.** Reviewing this post
I decided "55%" was sloppy, so I replaced it with 6 of 15 repetitions
above a threshold against 0 of 20, Mann-Whitney p = 0.004, CVs of 0.23
and 0.08. All correctly computed, all from the same two confounded runs.
Rigour applied downstream of a confound makes the confound harder to
see, not easier — the careful version reads as more trustworthy while
resting on exactly the same broken comparison.

**The check that would have caught it was one flag and forty minutes.**
Not a better statistic: the same measurement with one thing varied.

## What to check in your own harness

**Does the condition order vary?** Randomise it anyway. I couldn't
demonstrate the effect on one workload on one machine, which isn't the
same as showing it never happens, and the fix is too cheap to argue
about.

**Are you comparing maxima?** A maximum is the noisiest summary of a
sample and it's exactly what your eye goes to when two runs disagree.
Mine ranged 14,000–39,488µs across runs whose medians sat inside 9%.

**When two runs disagree, count the ways they differ before explaining
why.** If it's more than one, you don't have an explanation, you have a
candidate. Mine had three and I noticed one.

**Can you test the explanation?** Not the measurement — the
*explanation*. If it has a mechanism, the mechanism makes a prediction,
and the prediction is usually one flag away from being checked. A
plausible causal story is a reason to run one more experiment, not a
reason to stop.

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

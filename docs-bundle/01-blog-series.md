# Blog series (the public deliverable)

Seven posts plus their index. This is the primary review target: it is
what would be published. Every post ends with a Data table mapping its
claims to a raw file in `results/raw/`; those raw summaries are in
bundle 04 so the numbers can be checked without fetching anything.


==============================================================================
## FILE: blog/README.md
## path: blog/README.md
==============================================================================

# Blog series: a Count-Min Sketch in a Linux scheduler

Seven posts. Post 00 is the result; the rest are what it took to trust
it.

I came to this knowing how to write a scheduler and nothing about how to
measure one, and that turned out to be the harder half. Thirteen claims
were made and withdrawn along the way — most because an instrument was
wrong, four because the measurement was right and I attached an
explanation to it that I never tested. Each fix is standard practice
somewhere else and was new to me.

So these are written from the position of someone who didn't know, for
anyone else who came to benchmarking through code rather than through a
statistics course.

| # | post | stands alone? |
|---|---|---|
| 00 | [A Count-Min Sketch in a Linux scheduler](00-a-sketch-in-a-scheduler.md) | the result |
| 01 | [I spent a day fixing a benchmark bug that wasn't there](01-benchmark-was-lying.md) | yes — any benchmark author |
| 02 | [The control that killed my 6.8x speedup](02-the-control-that-killed-my-speedup.md) | yes — anyone evaluating a heuristic |
| 03 | [What happens when your BPF map runs out of room](03-when-your-bpf-map-runs-out-of-room.md) | yes — any BPF author |
| 04 | [Your per-task tracking assumes identities hold still](04-identities-that-wont-hold-still.md) | yes — behaviour-tracking schedulers |
| 05 | [p99 told me one story, p50 told me another](05-p99-and-p50-told-different-stories.md) | yes — anyone reporting latency |
| 06 | [Overlapping ranges are not equivalence](06-overlapping-ranges-are-not-equivalence.md) | yes — anyone comparing systems |

Posts 01–06 don't require caring about count-min sketches.

The full list of retractions, each tied to the file that produced it and
the file that overturned it, is
[`REVISIONS.md`](../results/REVISIONS.md) rather than a post of its own.
It is a record, not a narrative.

## Data

Every post ends with a table mapping its claims to the raw harness output
that produced them, in [`../results/raw/`](../results/raw/). The output is
unedited, including the parameters each run printed at startup, and where
the harness emitted per-repetition lines the individual values are present
so summaries can be recomputed rather than trusted.

- [`../results/MANIFEST.md`](../results/MANIFEST.md) — what each file is,
  and which files carry known measurement bias
- [`../results/REVISIONS.md`](../results/REVISIONS.md) — every claim made
  and withdrawn, with the file that produced it and the file that
  overturned it
- [`../results/ENVIRONMENT.md`](../results/ENVIRONMENT.md) — kernel, CPU
  count, and the uncontrolled variables

Runs that produced conclusions later retracted are kept deliberately. The
wrong answers are part of the record.

## Still open

These aren't a content schedule — they're the threads this work left
hanging, and I've written down enough in advance that the answers can
embarrass me.

**Everything I predicted bare metal would change.** All of this was
measured in a VM on 4 aarch64 cores. Before buying hardware I wrote down
which findings should survive and which should move, and why: the memory
result should hold, every absolute latency figure should shrink, the
exact tracker's failure threshold should be unchanged, and the tail penalty is
the one most at risk because it rests on rare events in an environment
that manufactures them. That's in the paper's limitations section, dated
and unhedged. The post is the scoreboard.

**Does any of this actually save energy?** The established reason to
track wakeup frequency isn't latency at all — it's that every wakeup
drags a core out of a deep idle state and costs real joules. That's a
one-step causal chain where my latency argument is three. And a sketch's
overestimation matters far less to a batching heuristic than to a
scheduling decision, so my negative findings may simply not transfer. I
couldn't measure it: no energy counters in the guest.

**Which other scheduler heuristics survive a placebo arm?** The
count-blind control dissolved 82% of my headline result. Schedulers
track plenty of other things — run length, migration rate, waker-wakee
locality, cache warmth. I have no idea how many of those survive the
same test, and the test costs about forty lines.

**What is the right identity for a task?** Post 04 shows PID can't see
churning tasks and `comm` turns a multithreaded victim into the heaviest
waker on the system, with nothing usable in between. Cgroup? Executable
path? Parent lineage? I don't know, and it blocks any scheduler that
tracks behaviour under churn.

If you want to be told when these land, or to tell me I'm wrong about
one of them first, that's what the subscribe button is for.

## Repositories

- **https://github.com/blackjable/scx-cms-research** — this repository: paper, posts, harnesses, raw data
- **https://github.com/blackjable/scx-cms** — the scheduler itself

Both are private for now. **The posts link to data that is not yet
publicly readable**, so they cannot be published until at least this
repository is made public. A post citing unreachable data is worse than
one citing none: it implies a verifiability that isn't there.

## A note on publishing these

Links within posts are repo-relative and resolve when browsing this
repository on GitHub. Links into the scheduler source are absolute,
because it lives in a separate repository.

If the posts are published anywhere other than GitHub — Medium, a
personal blog — the relative links need absolutising. The two prefixes
to find and replace:

```
../results/    -> https://github.com/blackjable/scx-cms-research/blob/main/results/
../benchmark/  -> https://github.com/blackjable/scx-cms-research/blob/main/benchmark/
```

Order of operations, which matters: **make the repositories public,
verify the links resolve, then publish the posts.**


==============================================================================
## FILE: blog/00-a-sketch-in-a-scheduler.md
## path: blog/00-a-sketch-in-a-scheduler.md
==============================================================================

# A Count-Min Sketch in a Linux scheduler: 4x less memory, a noisier tail

A BPF scheduler that adapts to task behaviour has to remember something
about each task, and that memory grows with the number of distinct tasks
the machine has seen. On a busy system with short-lived processes, that
is neither small nor predictable.

Probabilistic counting structures are the standard answer to this
elsewhere in systems software — network telemetry, query planners,
stream processing. A literature search before starting this turned up no
`sched_ext` scheduler using approximate data structures for behavioural
tracking — though absence of evidence and all that, and I'd genuinely
like to hear about prior work if it exists.

So I built one and measured it — and then spent considerably longer
learning how to measure it properly, which turned out to be the harder
half. The short version of the result:

> **A Count-Min Sketch at 8.3 KB keeps working at a memory budget where
> exact per-task counters have stopped working entirely.** Typical
> latency is identical. Tail latency is worse on average and much
> noisier: across two independent runs, the sketch beat exact counting
> in about 40% of runs and was more than 50% worse in about 30%. At
> *equal* memory the two are indistinguishable — so the tail cost is
> the price of the memory, not of approximating.

Below that budget the story gets more interesting, because the two
structures stop working at different points and fail in different ways.

## What was built

`scx_cms` is a `sched_ext` scheduler that tracks how often each task
wakes over a rolling window and penalises frequent wakers, so a
latency-sensitive task gets CPU sooner.

One design decision made the whole evaluation possible: **the counting
method is a load-time flag, not a compile-time choice.** Exact counters
and the sketch are both compiled in; `--tracker` selects between them
and the verifier eliminates the unused branch. Everything else — the
policy, the window, the identity key, the adjustment applied — is
byte-identical between the two.

That means the counting method is genuinely the only variable. No
separate builds, no "we changed one thing and also rebuilt with a
different compiler."

## The measurement

A `schbench` victim — a latency-sensitive task — running against 128
background tasks that wake 200 times a second while using very little
CPU each.

That background shape is deliberate. A task that burns CPU is already
deprioritised by ordinary vtime fairness; the information vtime *cannot*
see is "wakes constantly but is cheap." That's exactly what this
mechanism proposes to track, so it's the regime where it should pay.

Each configuration carries its own memory budget, all of them
interleaved in one randomised matrix, 20 repetitions. (The "one matrix"
part matters more than it sounds — see below.) The equivalence test
further down is a separate, longer run at 30.

## The result

| tracker | memory | p50 | p99 |
|---|---|---|---|
| do nothing | — | 3,912µs | 65,440µs |
| count-blind penalty | 35.6 KB | 11,040µs | 16,864µs |
| **exact counters** | **35.6 KB** | **3,892µs** | **10,144µs** |
| exact counters | 9.6 KB | 3,908µs | 63,680µs |
| **sketch (d=2, w=256)** | **8.3 KB** | **3,924µs** | **11,344µs** |

Three things in that table.

**The sketch at 8.3 KB works; exact counting at 9.6 KB does not.** But
"works" needs qualifying, and the qualification only appeared when I
tested it properly. Those overlapping p99 ranges look like equivalence
and are not: a paired equivalence test at n=30, with the margin declared
before the run, refuted equivalence on p99 while confirming it on p50.
Overlapping ranges mean a difference was not detected, not that none
exists.

**Exact counting at 9.6 KB does not work at all.** Its p99 of 63,680µs
sits on top of the do-nothing baseline's 65,440µs. It hasn't degraded —
it has stopped. An exact map that can't hold the live identity set
evicts constantly, lookups miss, counts read as zero, and the mechanism
silently stops acting.

**The count-blind row is the control that makes the rest meaningful.**
It applies the same vtime perturbation while ignoring the tracked count
entirely. It reaches a decent tail (16,864µs) by making *every* wakeup
three times slower — including the task being protected. Both working
configurations beat it while leaving the median untouched, which is how
you know they're discriminating between tasks rather than just
disturbing everything.

That control also cost me a 6.8x result earlier in the project. It
turned out roughly 82% of what I'd attributed to wakeup tracking was
generic perturbation. Worth building before you believe your own
numbers.

## Where each structure stops

| budget | exact | sketch |
|---|---|---|
| 32 KB | works | works |
| 16 KB | degraded | works |
| 8 KB | **inert** | works |
| 2 KB | inert | **blunt** |

The two failures are different in kind, and that difference is the
useful part.

**Exact counting fails silently.** Entries evict, queries miss, the
mechanism stops adjusting, and nothing anywhere signals it. Scheduling
quietly reverts to the underlying policy — which is survivable, but you
won't know it happened.

**The sketch fails loudly.** It never evicts, so under-provisioning
means collisions, collisions mean overestimation, and eventually every
task looks like a heavy waker. At 2 KB its median collapsed to the
count-blind baseline's level: it had stopped distinguishing tasks and
was penalising everything equally. The tail still improved, which is
precisely why you must look at the median too — p99 alone would have
called that a success.

So the question to ask about a bounded counting structure isn't which is
more accurate at a given size. It's **at what size does each stop
working, and can you tell from outside when it has.**

## The tail cost is real, and it doesn't arrive as a steady tax

The equivalence test put the mean p99 ratio at 11–39% worse, and I first
wrote that up as "a 17% tail penalty." Both runs say that description is
wrong.

Per-repetition ratios of sketch to exact, measured twice independently:

| | run A (n=30) | run B (n=60) |
|---|---|---|
| median ratio | 1.18x | 1.14x |
| 10th percentile | 0.89x | 0.87x |
| 90th percentile | 2.08x | 1.85x |
| sketch **better** | 37% of runs | 40% of runs |
| sketch >50% worse | 30% of runs | 33% of runs |

**In roughly 40% of runs the sketch beats exact counting outright. In
roughly 30% it's more than 50% worse.** The median sits at ~1.15x
because those cancel, not because any particular run experiences 15%.

That shape replicated closely across two independent runs, which is more
than I can say for most things in this project. What you're buying with
4x less memory is not a predictable 15% tax — it's a coin weighted
slightly against you.

I should flag that this is the same mistake this project made elsewhere,
one level up. Reporting a median tail ratio hides that a third of runs
are 50% worse, exactly as reporting p99 alone hid what `flat` was doing
to the median. Summary statistics conceal distributions at every level
you apply them.

## And the cost is the memory's, not approximation's

I got this backwards initially, on the strength of one outlier.

At *matched* memory — sketch at 32 KB against exact at 32 KB — the two
are indistinguishable:

| | run A | run B |
|---|---|---|
| sketch @32KB / exact @32KB, p99 | 1.03x | 1.04x |
| sketch @8KB / exact @32KB, p99 | 1.25x | 1.36x |

Give the sketch the same memory and it performs the same. Take 4x the
memory away and the tail degrades. **So you are trading tail latency for
memory**, which is a comprehensible engineering trade, rather than
paying some intrinsic tax for approximating, which would not be.

## Geometry is not a detail

At a fixed 8 KB, varying only the width/depth split:

| geometry | p99 |
|---|---|
| depth 2, width 256 | **10,144µs** |
| depth 1, width 512 | 12,208µs |
| depth 4, width 128 *(the default)* | 18,624µs |
| depth 8, width 64 | 15,344µs (blunt) |

**The default is 1.8x worse than the best at identical memory.** Width
buys more than depth here, replicating a finding from the synthetic
phase. Any memory figure quoted for a sketch is really a figure for a
*geometry*, and choosing depth 2 over depth 4 is the difference between
matching exact counting and falling well short of it.

## Where it doesn't hold

**Task churn breaks it, and no identity key fixes that.** With
continuously respawning background processes, exact counting is inert at
every budget and the sketch becomes blunt. Keying on PID can't see
short-lived tasks — they never live long enough to look like frequent
wakers. Keying on `comm` sees them, but aggregates a multithreaded
victim's threads into the heaviest waker on the system, so the mechanism
penalises exactly the task it exists to protect.

The requirement that goes unstated is that **identities persist across
the tracking window** and match the granularity of the decision. Those
are two separate properties, and task churn breaks the first while
multithreading breaks the second.

**Everything here is one machine.** aarch64, 4 CPUs, kernel 6.19, inside
a VM. No x86 validation. The VM's timer delivery floor (~1.7ms) was high
enough to invalidate one of my two candidate workloads outright, which
is a good reminder that environment-specific effects are present until
you've checked elsewhere.

**Energy is unmeasured**, and it's the more natural application. A
wakeup has a direct physical cost — it drags a core out of a deep idle
state. That's a one-step causal chain, where the latency argument is
three steps. And a sketch's overestimation matters far less to a
batching heuristic than to a scheduling decision. I couldn't measure it:
no RAPL in the guest.

## Why this took much longer than it should have

Thirteen claims made and withdrawn, including, briefly, the conclusion
that the whole idea was refuted.

Almost none failed because the hypothesis was wrong. Most failed because
an instrument was wrong — a metric that scored a broken tracker as
highly as a working one, a ratio with a collapsing denominator, a
workload model wrong by 4x. Four failed differently and worse: the
measurement was right and I attached an explanation to it that I never
tested. One of those was a benchmarking lesson I'd been recommending to
other people, and it took a controlled run to find out there was no
effect to explain.

Each one is recorded with the file that produced it and the file that
overturned it, in [`REVISIONS.md`](../results/REVISIONS.md).

### If I were starting again

**Put a do-nothing condition in every matrix.** Without it you cannot
tell a working mechanism from a stopped one — both leave your protected
workload alone.

**Put a blunt control in every matrix** — the same intervention applied
without the information. It tells you what fraction of your result is
the signal and what fraction is the disturbance. Mine was forty lines
and cost me 82% of a headline.

**Instrument before you infer.** I spent three rounds reasoning about a
4x discrepancy that one histogram settled in a single run.

**Write down what would falsify each claim, before the run.** The two
times I did this, it fired.

**When two runs disagree, count the ways they differ before explaining
why.** If it's more than one, you have a candidate, not an explanation.

None of that is novel. Most of it is a century old and I'd met none of
it. The fixes are all small — a do-nothing condition is one line — so
the cost isn't in applying them, it's in not knowing they exist.

## Data

Every figure in this post comes from an archived run. Raw harness output,
unedited, including the parameters each run printed at startup:

| claim | file |
|---|---|
| the headline table (all six conditions, one interleaved matrix, n=20) | [`headline-single-matrix-n20.txt`](../results/raw/headline-single-matrix-n20.txt) |
| the equivalence test and per-repetition ratios (n=30) | [`equivalence-n30-prereg.txt`](../results/raw/equivalence-n30-prereg.txt) |
| the ratio distribution replication, and excursion rates (n=60) | [`excursion-rate-n60.txt`](../results/raw/excursion-rate-n60.txt) |
| where each structure stops working, across budgets | [`thesis-confirmation-n20.txt`](../results/raw/thesis-confirmation-n20.txt), [`o1-o4-budget-geometry-churning-n20.txt`](../results/raw/o1-o4-budget-geometry-churning-n20.txt) |
| the geometry sweep | [`o1-o4-budget-geometry-churning-n20.txt`](../results/raw/o1-o4-budget-geometry-churning-n20.txt) |
| identity churn breaking the mechanism | [`r4-identity-bestshot-n10.txt`](../results/raw/r4-identity-bestshot-n10.txt) |

The equivalence test was pre-registered before the data existed:
[`PREREGISTRATION_equivalence.md`](../benchmark/PREREGISTRATION_equivalence.md),
analysed by [`analyse_equivalence.py`](../benchmark/analyse_equivalence.py).

Thirteen claims were made and withdrawn on the way to this one. Each is
recorded with the file that produced it and the file that overturned it:
[`REVISIONS.md`](../results/REVISIONS.md). Measurement environment:
[`ENVIRONMENT.md`](../results/ENVIRONMENT.md).

## What I'd like to know next

Three things this couldn't answer, in order of how much I want them.

**Whether it survives real hardware.** Everything here is a VM on 4
aarch64 cores. I've written down in advance which findings should hold
and which should move — the memory result should survive, the tail
penalty is the one most at risk, since it depends on rare events and a
noisy environment produces those. The predictions are dated. When the
hardware arrives, they're either right or they aren't.

**Whether it saves energy.** This is the one that nags. The established
reason to track wakeup frequency is that wakeups cost joules — a core
leaving a deep idle state — and that's a far more direct argument than
the latency chain I spent all this time on. A sketch's overestimation
would also matter much less to a batching decision than to a scheduling
one. My guest exposes no energy counters, so I measured the wrong thing
well rather than the right thing at all.

**Whether other tracked signals survive the same control.** A
count-blind penalty reproduced 82% of what I'd credited to wakeup
tracking. Schedulers track run length, migration rate, cache warmth,
waker-wakee locality. The control is forty lines. I'd be curious, and
slightly apprehensive, to see it run against those.


==============================================================================
## FILE: blog/01-benchmark-was-lying.md
## path: blog/01-benchmark-was-lying.md
==============================================================================

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


==============================================================================
## FILE: blog/02-the-control-that-killed-my-speedup.md
## path: blog/02-the-control-that-killed-my-speedup.md
==============================================================================

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
| *(on the arithmetic: both source runs give 6.9x — 88,192/12,784 at n=15 and 80,640/11,744 at n=20. I quote 6.8x throughout because that is how I stated the claim at the time, and this post is about that claim. It rounds down, not up.)* | |
| the count-blind control, swept at 2/4/8ms | [`r2b-flat-control-n8.txt`](../results/raw/r2b-flat-control-n8.txt) |
| both re-measured under randomised ordering (n=20) | [`r2d-randomised-order-n20.txt`](../results/raw/r2d-randomised-order-n20.txt) |

The control is `--mechanism flat` in
[`flat.bpf.c`](https://github.com/blackjable/scx-cms/blob/main/src/bpf/mechanisms/flat.bpf.c),
roughly forty lines.

**On the p50 figures:** that harness prints a p99 summary table but not a
p50 one, so the medians quoted here (3,920µs and 11,776µs) are computed
from the `wu_p50=` values on the per-repetition lines, which are all
present in the file. Grep for `wu_p50` and take the median of twenty.


==============================================================================
## FILE: blog/03-when-your-bpf-map-runs-out-of-room.md
## path: blog/03-when-your-bpf-map-runs-out-of-room.md
==============================================================================

# What happens when your BPF map runs out of room

Every BPF scheduler that keeps per-task state eventually faces the same
question: what happens when there are more tasks than you budgeted for?

I ended up measuring this by accident, while testing something else. The
answer turned out to be less about BPF than I first thought, and more
about a way of thinking about bounded state that I now find more useful
than any accuracy figure.

## Finding 1: two map types, two different kinds of useless

I was tracking per-task wakeup counts in a `BPF_MAP_TYPE_LRU_HASH`,
sizing it deliberately small to see how gracefully it degraded. At 42
entries, against roughly 330 live task identities, the mean tracked count
per query fell to **1.6** — as if almost nothing was retained between one
increment and the next.

A plain `BPF_MAP_TYPE_HASH` at **identical capacity**, same workload,
reported **189.8**.

I wrote that up as a finding about BPF: that the per-CPU free lists
underlying `LRU_HASH` make a small map smaller than its own bookkeeping,
so it stops behaving like an LRU. **It's wrong.**

A correct LRU *also* reports ~1 in that situation. With 330 identities
competing for 42 slots, every insert evicts something about to be needed
again, entries are dropped between their own increments, and counts never
accumulate. That's textbook thrashing, not a bug.

Shrinking the identity population separates the two explanations. Five
runs per cell, median and range:

| identities | slots | `LRU_HASH` | plain `HASH` |
|---|---|---|---|
| 8 | 42 | **843.8** (835–848) | 820.3 (804–856) |
| 20 | 42 | **410.2** (385–476) | 535.4 (531–550) |
| 100 | 42 | 2.5 (2.3–2.6) | 209.8 (206–212) |
| 300 | 42 | 1.5 (1.5–1.7) | 0.1 (0.0–0.2) |

**A 42-entry LRU works perfectly well when the working set fits** — 164x
separation between the fitting rows and the overcommitted ones. If the
free lists were responsible it would fail at 42 entries regardless of how
many identities were competing. It doesn't. The collapse tracks
*overcommitment*, not map size — which is a property of LRUs, not of BPF.

(One cell moved between the first run and these five: the plain hash at
300 identities read 200.4 once and 0.0–0.2 afterwards. It changes a
sentence below, not the finding here.)

### What's actually worth knowing

The interesting part isn't that an undersized cache degrades. It's that
these two structures degrade into **different kinds of useless**, and the
difference determines what you can still infer.

**LRU thrashes uniformly.** Nothing accumulates, every query reads near
zero, every key is equally invisible.

**A plain hash locks in early arrivals.** Whichever keys got there first
keep accumulating while everything arriving after the map filled is
permanently invisible. In my measurements, 83% of queries returned zero
while a minority carried counts in the thousands.

How *legible* that is depends on how badly overcommitted you are. At 100
identities against 42 slots the mean reads ~210 — the locked-in keys are
still active, so the signature is obvious. At 300 it reads ~0.1, because
the 42 keys it locked in are mostly no longer the ones waking. Push it
far enough and the plain hash stops looking like itself and starts
looking like the LRU.

That difference mattered practically: it's what let me tell "the tracker
has stopped working" apart from "the tracker is working and these tasks
genuinely aren't busy." With LRU, a low count is ambiguous. With the
plain hash, a zero means *not tracked* and a large number means
*tracked since the beginning*, which is less accurate but more legible.

Neither is usable below its working set. But if you're going to be
undersized anyway, it's worth knowing which failure you'd rather debug.

## Finding 2: silent failure and loud failure

This is the part I think generalises.

I had two bounded structures tracking the same thing: an exact hash with
eviction, and a Count-Min Sketch. Both were correct implementations. Both
had a fixed memory budget. Under pressure they failed completely
differently, and the difference mattered more than their accuracy did.

**The exact hash fails silently.** Entries evict, subsequent lookups
miss, missing keys read as zero, and the mechanism consuming those counts
quietly stops acting. Nothing signals this. The scheduler simply reverts
to whatever its underlying policy was.

**The sketch fails loudly.** It never evicts anything — that's the whole
design. Instead, under-provisioning means collisions, collisions mean
overestimation, and eventually *every* task looks like a heavy waker. The
mechanism doesn't stop acting. It acts confidently on garbage, and
applies the penalty meant for background churn to the task you were
trying to protect.

### A third mode I thought I'd found, and hadn't

I originally listed a third failure mode here: one run in thirty where a
sketch performing normally returned a victim p99 of 240,384µs, twenty-four
times its own median, with its median untouched. Rare, severe, invisible
to typical-case monitoring.

A dedicated run at 60 repetitions per condition killed it. **Exact
counting produces the same excursions at the same rate** — 1/60 against
1/60 — and the 24x never recurred across 360 further measurements. The
excursions belong to this environment, not to approximation. Details in
[`REVISIONS.md`](../results/REVISIONS.md) revision 9.

So there are two failure modes, not three.

### Why this framing is more useful than accuracy

If you compare these structures on error at a given size, you get a
table of numbers that depends on your workload and tells you little
about what happens when your assumptions break.

If you compare them on **failure mode**, you get a design rule:

> Silent failure degrades to your underlying policy. Loud failure
> actively misdirects it.

A scheduler that stops adjusting is a scheduler you still understand. A
scheduler confidently penalising the wrong tasks is worse than one doing
nothing, and it will look fine in any metric that doesn't happen to
watch the victim.

So the question to ask of a bounded counting structure isn't *which is
more accurate at 8 KB*. It's **what does this do when it runs out of
room, and can I tell from the outside that it has?**

## A footnote on conservative update

The obvious fix for a sketch's overestimation is conservative update —
raise each row's cell to `max(cell, min_before + 1)` rather than
incrementing all of them, so cells already above the minimum stop
absorbing unrelated mass. It costs no extra memory, and when I measured
it, it reduced overestimation by 15–35%.

**It can't be implemented safely in BPF for an array-backed sketch.**

Conservative update has to read all *d* cells, take the minimum, and
write back as a single atomic unit — the invariant spans cells, so
per-cell atomics don't help. Each cell needs its own
`bpf_map_lookup_elem`, and the verifier rejects a `bpf_spin_lock` held
across those calls:

```
function calls are not allowed while holding a lock
```

The lock-free version I fell back on — compare-and-swap with an
atomic-increment fallback — **races observably**. Two CPUs observing the
same minimum both write `min+1`, one increment is lost, and the guarantee
that justified choosing a Count-Min Sketch in the first place is gone.

Thousands of violations show up in every run I've done. I'd quote a rate,
except it doesn't replicate: the same configuration gave 1,749 violations
in one run and 1,036 in another, and a neighbouring variant went from 197
to 1,750. One violation is enough to prove unsoundness, so the conclusion
doesn't need a number — but I'd have quoted one as though it were stable
if I hadn't re-run it.

Correct-and-slow isn't available; only fast-and-wrong. You could
restructure the entire table into a single map value to get one lookup
under one lock, which would work — at the cost of changing what you're
measuring, and of a global lock on a per-wakeup hot path.

I mention it because "just use conservative update" is the natural
response to a sketch overestimating, and on this platform it isn't
available.

## Data

| claim | file |
|---|---|
| `LRU_HASH` vs plain `HASH` at identical capacity | [`r6-sketch-variants-n3.txt`](../results/raw/r6-sketch-variants-n3.txt) |
| the same control on scheduling outcomes | [`r7-r9-throughput-mapcontrol-geometry.txt`](../results/raw/r7-r9-throughput-mapcontrol-geometry.txt) |
| **the working-set test that separated thrashing from a map-type bug** | [`lru-working-set-test.txt`](../results/raw/lru-working-set-test.txt), harness [`lru_test.py`](../benchmark/lru_test.py) |
| the 240,384µs outlier itself, at repetition 21 | [`equivalence-n30-prereg.txt`](../results/raw/equivalence-n30-prereg.txt) |
| the withdrawn third failure mode (n=60 per condition) | [`excursion-rate-n60.txt`](../results/raw/excursion-rate-n60.txt) |
| conservative update measurements | [`r6-sketch-variants-n3.txt`](../results/raw/r6-sketch-variants-n3.txt) |

The overcommitment thresholds here are specific to this workload's
identity population, not to the hardware. See
[`ENVIRONMENT.md`](../results/ENVIRONMENT.md), and
[`REVISIONS.md`](../results/REVISIONS.md) revision 12 for the version of
this finding that had to be withdrawn.


==============================================================================
## FILE: blog/04-identities-that-wont-hold-still.md
## path: blog/04-identities-that-wont-hold-still.md
==============================================================================

# Your per-task tracking assumes identities hold still

If your scheduler remembers something about each task, you've made an
assumption you probably didn't write down: that "each task" means
something stable enough to accumulate a history against.

Under task churn it doesn't, and the ways it fails are worse than just
losing the signal.

## The setup

I had a BPF scheduler tracking per-task wakeup frequency over a rolling
window, penalising frequent wakers so a latency-sensitive task could get
CPU sooner. Tracking was keyed on an identity, and the identity was
selectable at load time: `pid`, `tgid`, or a hash of `comm`.

Against long-lived background tasks it worked well — the victim's tail
latency improved several-fold and its median was untouched.

Then I changed the background load from 128 long-lived tasks to 128
*slots* that continuously respawned short-lived processes. Same
concurrency, same wakeup rate, same CPU demand. The only difference was
that the identities turned over.

Every variant of the mechanism became **worse than doing nothing.**

## Failure 1: fine-grained keys can't see churn

With `--identity-key pid`, every respawned process is a brand-new
identity starting at zero.

A task that lives 250ms and wakes 200 times a second accumulates a count
of about 50 before it exits and its successor starts from scratch. It is
never around long enough to look like a frequent waker. So it is never
penalised, and it runs at a full time slice — while the mechanism dutifully
tracks it.

Nothing controls the tail. Across every memory budget I tested, the
penalty mechanism landed within noise of the do-nothing baseline. The
tracker was working perfectly and seeing nothing worth acting on.

Meanwhile the *long-lived* task in the system — the latency-sensitive one
— accumulates a real history, because it's the only thing that persists.

## Failure 2: coarse keys mis-attribute

The obvious fix is a coarser identity. Respawned processes share a
`comm`, so `--identity-key comm` should see through the churn.

It does. The tail recovered from 68,608µs to 28,032µs, non-overlapping
ranges. Exactly as predicted.

It also destroyed the thing that made the mechanism worth having:

```
                    p50        p99      discrimination
flat (count-blind) 14,336us  30,752us      1.00x
penalty (pid)       3,980us  68,608us      3.60x
penalty (comm)     12,416us  28,032us      1.15x
```

Discrimination — how well the tracker separates the protected task from
background load — collapsed from 3.60x to 1.15x. The mechanism became
statistically indistinguishable from a penalty that ignores the tracked
count entirely.

The reason is structural, and it's the part I'd want someone to take
away from this:

**A coarse identity key aggregates a multithreaded latency-sensitive
application into the heaviest waker on the system.**

My victim was a four-thread `schbench` instance. All four threads share
one `comm`. Their wakeups sum — roughly 400/s against each background
slot's 200/s. Under `comm`, the task the mechanism exists to protect
becomes the single most-penalised identity on the machine.

It's not a tuning problem. It's what aggregation *means*.

## So there isn't a middle setting

That's the uncomfortable conclusion. The two failures come from opposite
ends of the same axis:

- **Fine keys** (pid) track a unit too short-lived to accumulate history.
  Churn is invisible.
- **Coarse keys** (comm, tgid) accumulate history across a unit that
  bundles unrelated behaviour together. Multithreaded victims are
  mis-attributed.

Anything in between trades one for the other. `tgid` would see through
thread churn but not process respawning, and would still aggregate a
multithreaded app.

The real requirement — and I've not seen it stated, including in my own
design — is that **identities
persist across the tracking window and correspond to the granularity at
which you want to make decisions.** Those are two separate properties,
and workloads with high task turnover break the first while
multithreaded applications break the second.

## What this means practically

**Check your workload's identity turnover before trusting any
behavioural tracking.** I measured mine by counting distinct insertions
into a map big enough that nothing evicts, so the number describes the
workload rather than the tracker. Across three runs the long-lived
workload minted about 2 new identities per second; the churning one
about 380. That's a two-orders-of-magnitude difference — roughly 190x —
in what your tracker is actually accumulating, and it's invisible from
the scheduler's own metrics.

It took me three attempts to have a number here I'd stand behind. The
first version of this paragraph used an *assumed* identity count that
turned out to be wrong by a factor of four. The second used a measured
one whose output I then failed to archive, so it couldn't be checked.
The figures above are the third pass, with all three runs in the
archive, and the churning rate came back about 8% below what I'd
reported from memory.

**Check whether your protected workload is multithreaded** before
reaching for a coarse key. If it is, coarse identity may invert your
mechanism rather than merely blunt it.

**Consider whether a different identity exists.** Cgroup, executable
path, or parent lineage might give persistence without aggregating
threads. I didn't test these — it's the obvious next question and I
don't know the answer.

## The broader point

Behaviour-tracking schedulers are having a moment, and sched_ext makes
them easy to build. I built one without once asking what "per task"
committed me to, and I doubt I'm unusual in that — the abstraction is so
natural that the assumption inside it is invisible until a workload
breaks it.

Every one of those carries this assumption, mine included, and mine
didn't state it either — I discovered it by running a workload where it
failed, not by reasoning about the design. If your evaluation uses
long-lived synthetic load, and most do because it's the easy thing to
write, you will never encounter it.

That's the part worth checking in your own work: not whether your
tracking is accurate, but whether the thing you're tracking stays still
long enough to be worth tracking at all.

## Data

| claim | file |
|---|---|
| pid vs comm, penalty vs boost (n=10) | [`r4-identity-bestshot-n10.txt`](../results/raw/r4-identity-bestshot-n10.txt) |
| identity turnover rates, measured not assumed (n=3) | [`identity-turnover-n3.txt`](../results/raw/identity-turnover-n3.txt) |
| sketch inflation in both regimes — note this file's header carries the *assumed* identity counts, since it predates the measurement above | [`r5-inflation-and-stable-sweep.txt`](../results/raw/r5-inflation-and-stable-sweep.txt) |
| both structures failing under churn (n=20) | [`o1-o4-budget-geometry-churning-n20.txt`](../results/raw/o1-o4-budget-geometry-churning-n20.txt) |


==============================================================================
## FILE: blog/05-p99-and-p50-told-different-stories.md
## path: blog/05-p99-and-p50-told-different-stories.md
==============================================================================

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

It sounds right, and it would make a good talk slide. Then I checked it
against my own data and it didn't hold up.

I went back through every comparison I'd run and asked: would p99 alone
have given the *wrong ranking*?

| workload | p99-only would pick | wrong? |
|---|---|---|
| stable identities | the count-based mechanism | no — correct |
| high task churn | the count-blind mechanism | arguably correct, for a deadline-sensitive task |
| one run at n=15 | *inconclusive* — ranges overlapped | not wrong, just silent |

**In no run did p99 alone produce a clearly wrong ranking.** It produced
an *inconclusive* one, once. That's a much smaller claim, and the
difference matters: "this metric is misleading" and "this metric is
sometimes insufficient" call for different responses.

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

Two notes on checking these against the files, since this is a post about
not taking summary statistics on trust:

- `r2d`'s summary table prints p99 only. The p50 medians quoted here
  (3,920µs and 11,776µs) come from the `wu_p50=` values on its
  per-repetition lines — grep `wu_p50` and take the median of twenty.
- The 2 KB sketch's collapsed median is 9,936µs in the file; I round it
  to ~9,900µs in the text.


==============================================================================
## FILE: blog/06-overlapping-ranges-are-not-equivalence.md
## path: blog/06-overlapping-ranges-are-not-equivalence.md
==============================================================================

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

**The matched-memory control is the diagnostic.** Sketch at 32 KB
against exact at 32 KB — same budget, no memory saving involved — comes
out indistinguishable: median ratios of **1.03x and 1.04x** across two
independent runs. Give the sketch the same memory and it performs the
same. So the tail cost is what you pay for using less memory, not an
intrinsic tax on approximating, and that's a trade you can actually
evaluate.

It took me a while to read that control correctly. It *failed* its
equivalence test on the first run, and a failing control feels like a
finding, so I treated it as one and concluded the penalty was intrinsic.
It had failed because of a single 240,384µs observation that a later
60-repetition run showed to be environmental
([`REVISIONS.md`](../results/REVISIONS.md) revisions 9 and 10).

Two lessons:

**A control that fails is not automatically informative.** Find out
*why* before you build on it.

**An equivalence test is still a mean-based test.** TOST correctly told
me I couldn't claim equivalence. It did not tell me one observation in
thirty was doing the work.

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
  find out *why* before you build on it. A failing control feels like a
  finding in a way a passing one never does, which is exactly when to be
  careful. Mine was asking a question about the host and I heard it
  asking about the sketch.

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

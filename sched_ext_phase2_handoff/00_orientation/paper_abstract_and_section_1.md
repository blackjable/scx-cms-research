# Paper Draft — Abstract and Section 1

Companion to `paper_sections_2_to_6_draft.md`. An earlier introduction
was drafted before the Phase 2 results existed; it framed the work as
proposing an approach. That framing no longer matches the outcome and
this replaces it.

---

## Abstract

BPF schedulers written against `sched_ext` frequently track per-task
behavioural state, and the memory cost of doing so grows with the number
of distinct tasks the system sees. Probabilistic counting structures
are the standard answer to that problem elsewhere in systems software,
so it is natural to ask whether a Count-Min Sketch can replace exact
per-task counters in a scheduler: fixed memory, bounded error, no
growth with task count.

We built the scheduler to find out. `scx_cms` tracks per-task wakeup
frequency using either exact counters or a Count-Min Sketch, selectable
at load time with everything else held constant, and uses the tracked
count to adjust scheduling. We evaluated it on a real kernel across
matched memory budgets from 128 KB down to 2 KB.

The sketch extends the usable memory range below the exact tracker's
floor, and charges a tail-latency premium for it. Where identities
persist, both structures work at 32 KB and above; at 85 entries --
against roughly 330 live identities -- the exact tracker becomes
statistically indistinguishable from not acting on the count at all,
while the sketch still delivers a 3.65x tail improvement over inaction
(n=20, non-overlapping). Replacing the LRU hash with a plain one
postpones that failure by about one budget step but does not prevent it.

The premium is real, was established by a pre-registered equivalence
test rather than assumed away, and does not arrive as a steady tax.
Median latency is equivalent within 20% (90% CI [0.974, 1.060]); tail
latency is not (90% CI [1.114, 1.394] on the mean ratio, n=30 paired).
But the per-repetition ratios replicate across two independent runs
with a shape a mean conceals: median 1.18x and 1.14x, with the sketch
**better than exact counting in 37% and 40% of repetitions** and more
than 50% worse in 30% and 33%. What 4x less memory buys is not a
predictable premium but a coin weighted slightly against you.

A matched-memory control locates the cost. At the *same* budget the two
structures are indistinguishable (1.03x and 1.04x across the two runs),
so the tail premium is the price of the memory saving rather than an
intrinsic cost of approximating. The result is therefore a trade whose shape matters: roughly a quarter
of the memory, statistically identical typical latency, and a tail that
is worse on average and considerably noisier. A distribution in which a
third of runs are 50% worse is harder to design around than a known
premium of the same mean.

The result is bounded rather than general. Where task identities churn
rather than persist, the exact tracker is inert at every budget tested
and the sketch, while still acting, becomes blunt: it degrades median
latency to the level of a penalty that ignores the tracked count
entirely. So approximate counting buys memory headroom in the regime the
technique works in at all, and neither structure rescues the regime it
does not.

The mechanisms differ in a way that determines which regime suits
which. An exact tracker under a hard entry bound *fails silently*: it
evicts, queries miss, counts read as zero, and the mechanism stops
acting without any signal that it has. A sketch *fails loudly*: it
never evicts, so under-provisioning inflates estimates until every task
looks like a heavy waker and the penalty intended for background work
lands on the task being protected. Silent failure is survivable --
scheduling reverts to the underlying policy. Loud failure is not.
That asymmetry, rather than any accuracy figure, is what should decide
between them.

We also report two results independent of the sketch question. First,
wakeup-frequency tracking requires identities that persist across the
tracking window, an assumption absent from the design: under high task
turnover, fine-grained identity keys cannot observe churning tasks
while coarse keys aggregate a multithreaded latency-sensitive
application into the heaviest waker on the system, and no key choice
escapes the pair. Second, a count-blind control -- the same vtime
perturbation applied without reference to the tracked count --
reproduced roughly 82% of what initially appeared to be a 6.8x
scheduling improvement from tracking. None of the standard baseline
tiers we had specified would have caught that, because all of them vary
the scheduler rather than varying only whether the signal is consulted.

---

## 1. Introduction

A scheduler that adapts to task behaviour has to remember something
about each task. `sched_ext` makes this easy to attempt: a BPF
scheduler can keep per-task storage, hash tables keyed on pid or tgid,
and arbitrary counters, and can consult them from the scheduling
callbacks. The cost is that the memory footprint of that state grows
with the number of distinct tasks the system has seen, which on a busy
machine with short-lived processes is neither small nor predictable.

Bounding that cost is a solved problem in other parts of systems
software. Count-Min Sketches and related structures give fixed-size
approximate counting with a one-sided error guarantee, and they are
routinely deployed in network telemetry, database query planning, and
stream processing for exactly this purpose. Applying one inside a
scheduler is an obvious idea, and as far as we can determine (Section
2.4) nobody had tried it: no existing `sched_ext` scheduler uses
approximate data structures for behavioural tracking.

This paper reports what happened when we did. The short answer is that
it works, at a price we can state precisely: roughly a quarter of the
memory, statistically identical median latency, and a tail that is worse
on average and considerably noisier. The boundaries of that result --
where each structure stops working, and what each does when it does --
turn out to matter more than any accuracy figure, and they suggest a
check practitioners should run before reaching for a sketch anywhere
that resembles this problem.

### 1.1 What was built

`scx_cms` is a working `sched_ext` scheduler that tracks per-task
wakeup frequency over a rotating window and uses the tracked count to
adjust scheduling decisions. Three things about its construction matter
for the evaluation:

- **The counting method is a load-time constant**, not a compile-time
  choice. Exact counters and the Count-Min Sketch are both compiled in,
  and `--tracker` selects between them with the verifier eliminating
  the unselected branch. Everything else -- the policy, the window, the
  identity key, the adjustment applied -- is identical between the two.
  The counting method is the study's independent variable and nothing
  else moves with it.
- **The scheduling mechanism is pluggable**, with each policy in its own
  file and a single registration point that the build validates. This
  was originally an engineering convenience. It became essential when
  the evaluation required a control policy that consults no count at all.
- **Both memory budgets are settable at load time**, which the first
  version was not. Without that, both trackers' maps exist regardless of
  which is selected, every configuration reports identical memory, and a
  memory comparison measures nothing.

### 1.2 What was measured, and what it took to measure it honestly

The evaluation compares scheduling quality for a latency-sensitive task
running against wakeup-heavy background churn, across matched memory
budgets, on a real kernel.

Reaching a trustworthy answer took more methodological work than we
expected, and we report that work because two of the problems seem
likely to recur in any scheduler evaluation:

- **A count-blind control is necessary and is not among the standard
  baselines.** The natural comparison -- the mechanism on versus off --
  conflates consulting the tracked count with perturbing scheduling at
  all. Our first result was a 6.8x improvement that a control applying
  the same perturbation without the count reproduced almost entirely.
  The four baseline tiers we had specified from current `sched_ext`
  evaluation practice all vary *the scheduler*; none varies only
  *whether the signal is used*.
- **An anomaly is not an explanation, and we spent a day proving it.**
  Two matrices disagreed about the same configuration -- maxima of
  21,664us and 14,000us -- and one of them ran a pathological ~80ms
  condition immediately before the measured one. We attributed the
  difference to carryover from fixed condition ordering, reported it as
  a methodological finding, and recommended randomising order.

  The two matrices differed in three ways: order, condition subset, and
  sample size. A controlled test (`results/raw/ordering-controlled-n20.txt`,
  pre-registered) holds everything but ordering constant, with the ~80ms
  condition adjacent in 20 of 20 repetitions in the fixed arm. It finds
  nothing: medians 0.98x apart, Mann-Whitney p = 0.86, and the fixed arm
  is the *less* variable of the two. A within-arm check, where adjacency
  was randomised and which is therefore a genuine experiment on the same
  question, agrees (p = 0.46). The condition-subset test is null too
  (0.99x, p = 0.55).

  Across six measurements of that configuration the median varies by
  1.09x and the maximum by 2.82x, with no relation to either variable.
  The original evidence compared two maxima. **The finding was that we
  had over-read a noisy statistic, and the correct lesson is about the
  reasoning rather than the harness** (`results/REVISIONS.md`,
  revision 13). We still randomise condition order, as insurance against
  a real phenomenon we could not demonstrate here, and the
  recommendation is stated at that strength rather than the original one.

### 1.3 Contributions

1. **Approximate counting extends the usable memory range, at a
   measured cost.** At a budget where exact counting has stopped
   affecting scheduling at all, a sketch still delivers a 3.65x tail
   improvement over inaction (n=20, non-overlapping). It is not
   equivalent to exact counting: a pre-registered paired equivalence
   test puts the mean p99 ratio at 11-39% worse while equivalent on p50.
   The cost is a distribution rather than a flat penalty: per-run ratios
   span 0.69x to 3.08x, and across two independent runs the sketch is
   better in 37% and 40% of repetitions and more than 50% worse in 30%
   and 33%. A matched-memory control locates that cost -- at the same
   budget the two structures are indistinguishable, so the tail premium
   is the price of the memory saving rather than an intrinsic cost of
   approximating (Section 4.2.2). The
   structures also fail in different kinds -- exact silently, reverting
   to the underlying policy; the sketch loudly, misdirecting it -- which
   matters as much as the memory figure when choosing between them.

2. **An explanation that transfers.** The two structures fail at
   different budgets and in different kinds, and that -- not accuracy at
   a given size -- is what decides between them. An entry-bounded exact
   map degrades by falling off a capacity cliff and then going silent; a
   sketch degrades continuously and then starts misdirecting. So the
   question to ask of a bounded counting structure is at what size each
   stops working and whether you can tell from outside that it has. An
   earlier version of this contribution argued the opposite -- that an
   undersized LRU keeps the active set and therefore beats a sketch at
   small budgets. It does not: below its working set an LRU thrashes and
   the tracker goes inert (Sections 4.2.2, 4.2.4).

3. **A design constraint on wakeup-frequency tracking.** The technique
   requires identities that persist across the tracking window. Under
   task turnover, fine-grained keys cannot see churning tasks and coarse
   keys mis-attribute multithreaded victims, and no key choice avoids
   both (Section 4.2.3).

4. **One methodological finding** applicable to scheduler evaluation
   generally: the count-blind control described above. A second --
   condition-ordering bias -- was claimed, recommended, and then
   withdrawn when a controlled test found no such effect (Section 1.2,
   revision 13). What replaces it is narrower and about reasoning rather
   than tooling: when two runs disagree, count the ways they differ
   before explaining why, and note that the maximum of a sample is the
   noisiest summary available and the one the eye is drawn to.

5. **A working, instrumented `sched_ext` scheduler** with swappable
   trackers, mechanisms and identity keys, plus the benchmark harnesses,
   released so the negative result can be checked and the platform
   reused.

### 1.4 What this paper does not claim

The evaluation is latency-based, and the established motivation for
tracking wakeup frequency is energy: reducing idle-transition cost, the
"wakeup tax". A sketch's overestimation is considerably less damaging
to a batching heuristic than to a scheduling decision, so **the
negative result here does not transfer to the energy case**, which
remains open. We did not measure it because the virtualised environment
used exposes neither RAPL counters nor a battery gauge, and host-level
power measurement would be dominated by virtualisation overhead.

Results come from a single virtualised environment with four CPUs. That
environment's timer-delivery floor was high enough to invalidate one of
our two candidate victim workloads outright (Section 4.2), which is
itself reason to treat environment-specific effects as present until
checked elsewhere.

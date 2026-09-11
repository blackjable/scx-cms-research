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

The premium is real and was established by a pre-registered equivalence
test rather than assumed away. Median latency is equivalent within 20%
(90% CI [0.974, 1.060]); **tail latency is not** (90% CI [1.114,
1.394], n=30 paired) -- the sketch is 11-39% worse on p99. A
matched-memory control locates the cause: the sketch is also
non-equivalent at the *same* budget as exact counting, so the premium is
what approximation costs rather than what the memory saving costs. So
the result is a trade, not a substitution: roughly a quarter of the
memory, the same typical latency, a worse tail.

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
it does not work, that we can say precisely why, and that the reason
suggests a check practitioners should run before reaching for a sketch
anywhere that resembles this problem.

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
- **Condition ordering biases results systematically.** Our harness ran
  conditions in fixed order within each repetition, so carryover from
  the preceding condition landed on the same condition every time. It
  was large enough to reverse a conclusion: the same configuration's
  tail latency differed by 55% depending on what ran before it.
  Randomising condition order fixes it, and we recommend it as default
  practice.

### 1.3 Contributions

1. **Approximate counting extends the usable memory range, at a
   measured cost.** At a budget where exact counting has stopped
   affecting scheduling at all, a sketch still delivers a 3.65x tail
   improvement over inaction (n=20, non-overlapping). It is not
   equivalent to exact counting: a pre-registered paired equivalence
   test puts it 11-39% worse on p99 while equivalent on p50, and a
   matched-memory control shows that premium is a property of
   approximation rather than of the memory saving (Section 4.2.2). The
   structures also fail in different kinds -- exact silently, reverting
   to the underlying policy; the sketch loudly, misdirecting it -- which
   matters as much as the memory figure when choosing between them.

2. **An explanation that transfers.** Scheduling needs the active set,
   not the identity population. An undersized LRU keeps what is running
   and discards what is not, which is the correct thing to discard; a
   sketch keeps everything approximately. Before adopting a
   probabilistic counter, check whether an undersized exact structure
   with a sensible eviction policy already solves the problem -- where
   only the active set matters, it likely does.

3. **A design constraint on wakeup-frequency tracking.** The technique
   requires identities that persist across the tracking window. Under
   task turnover, fine-grained keys cannot see churning tasks and coarse
   keys mis-attribute multithreaded victims, and no key choice avoids
   both (Section 4.2.3).

4. **Two methodological findings** applicable to scheduler evaluation
   generally: the count-blind control described above, and the
   condition-ordering bias.

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

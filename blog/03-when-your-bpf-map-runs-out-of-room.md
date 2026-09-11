# What happens when your BPF map runs out of room

Every BPF scheduler that keeps per-task state eventually faces the same
question: what happens when there are more tasks than you budgeted for?

I ended up measuring this properly, by accident, while testing something
else. Two findings came out of it. One is a trap in a map type that
sched_ext programs use constantly. The other is a way of thinking about
bounded state that I found more useful than any accuracy figure.

## Finding 1: `LRU_HASH` stops being an LRU when it's small

I was tracking per-task wakeup counts in a `BPF_MAP_TYPE_LRU_HASH`,
sizing it deliberately small to see how gracefully it degraded. The
answer was: not gracefully at all, and not for the reason I assumed.

At small entry counts the tracker essentially stopped working. Mean
tracked count per query fell to **1.6** — as if almost nothing was ever
retained between one increment and the next.

I assumed that was capacity. It isn't. Here's the same tracker backed by
a plain `BPF_MAP_TYPE_HASH` at **identical capacity**, on the same
workload, which has roughly 330 live task identities:

| entries | `LRU_HASH` | plain `HASH` |
|---|---|---|
| 85 | 184.2 | 192.4 |
| **42** | **1.6** | **189.8** |
| 21 | 1.0 | 0.2 |

At 42 entries the LRU map reports a mean count of 1.6 where a plain hash
reports 189.8.

And a true LRU *should* be fine here. Retaining the 42 most-recently-used
of ~330 identities, you'd expect a mean somewhere around 48. Instead you
get 1.6 — roughly **30x worse than LRU semantics predict.**

The cliff on my 4-CPU machine falls somewhere between 42 and 85 entries.

### Why

BPF's LRU implementation maintains **per-CPU free lists**, each targeting
a batch of entries, so that CPUs don't contend on a global list for every
insertion. That's a sensible design and it's why `LRU_HASH` scales.

But it means the bookkeeping has a size. On a multi-core machine, a map
sized in the low tens of entries is *smaller than the machinery managing
it*. Entries get pulled onto per-CPU lists and recycled long before
anything resembling least-recently-used ordering applies. You aren't
getting approximate LRU. You're getting churn.

Nothing tells you this. The map is created successfully. Lookups
succeed. Inserts succeed. Counts come back. They're just wrong, in a
direction that makes your tracker look like it's doing nothing.

### What to do about it

If you're sizing an `LRU_HASH` in the low tens or low hundreds of entries
on a multi-core system, measure whether you're actually getting LRU
behaviour before relying on it. The check is cheap: run a known workload
with a known number of distinct keys and see whether retained values
match what an LRU of that size should hold.

If you're under the cliff, a plain `HASH` may serve you better — but read
the next section first, because it fails differently rather than better.

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

The plain hash, incidentally, has a third mode: first-come-first-served.
Once full, inserts fail, so the keys that arrived early keep accumulating
counts forever while everything that arrives later is invisible. In my
measurements 83% of queries returned zero while a locked-in minority
carried counts in the thousands.

### A third mode I missed the first time

I originally wrote this post with two failure modes. There's a third,
and it's the one I'd now worry about most.

Even when a sketch is *adequately* provisioned — not blunt, not
overwhelmed, discriminating normally — it occasionally mis-ranks a small
number of individual events badly. In one repetition out of thirty, at a
budget where the sketch was performing identically to exact counting,
the victim's p99 hit **240,384µs**: twenty-four times that condition's
own median.

Here's what makes it nasty:

```
                  p50        p99
exact counting  3,844us    10,032us
sketch          3,828us   240,384us
```

**The median was perfectly normal.** Identical to exact counting's,
identical to the do-nothing baseline's. The structure had not stopped
discriminating — it was working correctly for essentially every wakeup,
and then a handful of them waited a quarter of a second.

So the three modes are:

| mode | what you see | can you detect it? |
|---|---|---|
| **silent** (exact, over capacity) | mechanism quietly stops acting | only by comparing against a do-nothing baseline |
| **loud** (sketch, badly over capacity) | median collapses, everything penalised equally | yes — the median moves |
| **sporadic** (sketch, any capacity) | median normal, rare catastrophic tail events | **no** — nothing in typical-case monitoring moves |

The third is the worst for an operator, because every dashboard you'd
normally watch says the system is healthy. A collision inflates one
task's count on one occasion, it gets deprioritised severely, and a
quarter of a second disappears — while your median, your mean, and your
p90 all look exactly as they should.

And unlike the first two, it doesn't go away with a bigger map. It's a
property of hashing collisions being probabilistic: make the table
larger and you make it rarer, not absent.

### Why this framing is more useful than accuracy

If you compare these structures on error at a given size, you get a
table of numbers that depends on your workload and tells you little
about what happens when your assumptions break.

If you compare them on **failure mode**, you get a design rule:

> Silent failure degrades to your underlying policy. Loud failure
> actively misdirects it. Sporadic failure misdirects it rarely, and
> tells you nothing.

A scheduler that stops adjusting is a scheduler you still understand. A
scheduler confidently penalising the wrong tasks is worse than one doing
nothing, but at least the damage is visible in aggregate. A scheduler
that behaves correctly 999 times and catastrophically on the thousandth
is the one that will survive your evaluation and then surprise you in
production.

So the question to ask of a bounded counting structure isn't *which is
more accurate at 8 KB*. It's **what does this do when it runs out of
room, can I tell from the outside that it has, and does it fail all at
once or occasionally?**

That last clause is the one I'd have skipped a week ago. It's also the
one that decides whether a structure is safe to put in a scheduler,
because "usually fine" is not a property you can reason about when the
exceptions are invisible.

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
atomic-increment fallback — races observably. In my runs it produced
**1,749 never-undercount violations against a baseline of 116**. Two CPUs
observing the same minimum both write `min+1`, one increment is lost, and
the guarantee that justified choosing a Count-Min Sketch in the first
place is gone.

Correct-and-slow isn't available; only fast-and-wrong. You could
restructure the entire table into a single map value to get one lookup
under one lock, which would work — at the cost of changing what you're
measuring, and of a global lock on a per-wakeup hot path.

I mention it because "just use conservative update" is the natural
response to a sketch overestimating, and on this platform it isn't
available.

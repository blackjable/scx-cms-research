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

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

The real requirement — the one nobody writes down — is that **identities
persist across the tracking window and correspond to the granularity at
which you want to make decisions.** Those are two separate properties,
and workloads with high task turnover break the first while
multithreaded applications break the second.

## What this means practically

**Check your workload's identity turnover before trusting any
behavioural tracking.** I measured mine by counting distinct insertions:
the long-lived workload minted about 4 new identities per second, the
churning one about 413. That's a two-orders-of-magnitude difference in
what your tracker is actually accumulating, and it's invisible from the
scheduler's own metrics.

**Check whether your protected workload is multithreaded** before
reaching for a coarse key. If it is, coarse identity may invert your
mechanism rather than merely blunt it.

**Consider whether a different identity exists.** Cgroup, executable
path, or parent lineage might give persistence without aggregating
threads. I didn't test these — it's the obvious next question and I
don't know the answer.

## The broader point

Behaviour-tracking schedulers are having a moment, and sched_ext makes
them easy to build. Most of the interesting ones accumulate some history
per task and act on it.

Every one of those carries this assumption. I've not seen it stated in
any of them, including mine — I discovered it by running a workload
where it failed, not by reasoning about the design. If your evaluation
uses long-lived synthetic load (and most do, because it's the easy thing
to write), you will never encounter it.

That's the part worth checking in your own work: not whether your
tracking is accurate, but whether the thing you're tracking stays still
long enough to be worth tracking at all.

## Data

| claim | file |
|---|---|
| pid vs comm, penalty vs boost (n=10) | [`r4-identity-bestshot-n10.txt`](../results/raw/r4-identity-bestshot-n10.txt) |
| identity turnover rates, measured not assumed | [`r5-inflation-and-stable-sweep.txt`](../results/raw/r5-inflation-and-stable-sweep.txt) |
| both structures failing under churn (n=20) | [`o1-o4-budget-geometry-churning-n20.txt`](../results/raw/o1-o4-budget-geometry-churning-n20.txt) |

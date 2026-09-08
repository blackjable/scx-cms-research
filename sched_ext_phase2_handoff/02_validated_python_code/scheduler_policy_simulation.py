"""
scheduler_policy_simulation.py

EARLY, DIRECTIONAL comparison of scheduling POLICIES in pure Python —
NOT a substitute for real Phase 2 kernel benchmarking (schbench/
cyclictest/hackbench against real EEVDF/scx_simple/scx_lavd, per the
paper's Section 3.3 baseline plan).

*** WHAT THIS CANNOT TELL YOU, stated here and repeated in every result
printout: real hardware timing, context-switch cost, cache effects,
BPF verifier constraints, or real kernel behavior. Numbers are in
abstract simulated time units, not microseconds. This answers "does
this policy protect the latency-sensitive task better than that
policy, under the SAME synthetic arrival process" — nothing more. ***

DESIGN HISTORY / BUG FIXED: the first version of this simulation
processed exactly one arrival-check per scheduling decision, then
jumped time forward by the chosen task's full run duration with NO
arrivals modeled during that jump. This meant the runnable queue was
drained in lockstep with arrivals and essentially never built up
backlog — producing a degenerate result (scx_simple-like FIFO showing
EXACTLY 0.0 latency on every single sample, and three different
policies producing byte-identical output). Caught by the same
discipline applied throughout this project: a suspiciously clean
result triggered investigation rather than being reported as-is.
Rebuilt below as a proper discrete-event simulation with a real event
queue (heapq), where arrivals are generated independently of CPU
scheduling decisions via a Poisson process, and can genuinely queue up
while the CPU is busy.

Policies simulated (see each policy's selection logic for what's
faithfully modeled vs. approximated):

1. EEVDF_LIKE: pick the runnable task with lowest virtual runtime.
2. SCX_SIMPLE_LIKE: global FIFO — faithful to the real scx_simple's
   FIFO mode, which we've directly studied from source.
3. ISOLATION_EXACT: EEVDF-like, plus a penalty for high recent wakeup
   frequency, tracked EXACTLY — the actual scheduling application of
   this project's core hypothesis.
4. OUR_SKETCH: identical to #3, but wakeup frequency is tracked via
   the validated Count-Min Sketch instead of an exact counter.
5. SCX_LAVD_LIKE_APPROXIMATE: boosts tasks with short/frequent recent
   bursts (a common "interactive task" heuristic). Explicitly NOT
   derived from scx_lavd's actual source — a plausible simplification
   only, for rough directional sense.
"""

import heapq
import random
import statistics
from dataclasses import dataclass, field
from enum import Enum

from sketch_lib import RotatingCountMinSketch, RotatingExactCounter


class Policy(Enum):
    EEVDF_LIKE = "eevdf_like"
    SCX_SIMPLE_LIKE = "scx_simple_like"
    ISOLATION_EXACT = "isolation_exact_tracking"
    OUR_SKETCH = "our_sketch_tracking"
    SCX_LAVD_LIKE = "scx_lavd_like_APPROXIMATE"


@dataclass
class TaskState:
    task_id: str
    is_latency_sensitive: bool = False
    vruntime: float = 0.0
    recent_burst_lengths: list = field(default_factory=list)


@dataclass
class RunnableInstance:
    task_id: str
    wake_time: float
    burst: float


@dataclass
class SimResult:
    latencies: list = field(default_factory=list)
    total_arrivals: int = 0
    max_queue_depth: int = 0


def run_scheduler_simulation(
    policy: Policy,
    seed: int = 0,
    sim_duration: float = 50000.0,
    latency_task_period: float = 100.0,
    latency_task_burst: float = 5.0,
    churn_mean_interarrival: float = 8.0,   # tuned for ~0.6 utilization — see note below
    churn_burst_range: tuple = (1.0, 8.0),
    churn_pool_size: int = 40,
) -> SimResult:
    """
    NOTE on churn_mean_interarrival: an earlier version used 3.0,
    which combined with the average churn burst (~4.5) gives a
    service-demand rate of ~1.5 — an OVERLOADED, unstable queue
    (arrival rate exceeds CPU capacity) where backlog grows
    unboundedly regardless of policy. This was caught because it
    produced a degenerate result (only 1 latency-task dispatch across
    the entire simulation, out of ~500 expected). Fixed to 8.0, giving
    a service-demand rate of ~0.5625 (plus ~0.05 from the latency
    task itself) — a stable, ~61% utilized system where genuine but
    bounded contention exists for policies to actually resolve
    differently.

    NOTE on churn_pool_size: an earlier version generated a brand-new,
    NEVER-REPEATING task identity for every churn arrival. This meant
    every churn task's tracked wakeup frequency was uniformly ~1 —
    there was no actual "heavy waker" signal for the tracking-based
    policies (ISOLATION_EXACT, OUR_SKETCH) to detect, so they produced
    results byte-identical to plain EEVDF. This defeats the entire
    purpose of the comparison. Fixed by drawing churn arrivals from a
    FIXED POOL of persistent identities (some inherently "chattier"
    than others via a skewed draw distribution, matching the Phase 1
    skewed-churn model) — so recurring heavy wakers actually exist for
    the tracking policies to differentiate.
    """
    rng = random.Random(seed)
    result = SimResult()

    exact_tracker = RotatingExactCounter()
    sketch_tracker = RotatingCountMinSketch(width=256, depth=4)
    rotate_interval = 1000.0

    task_states: dict[str, TaskState] = {
        "latency_sensitive": TaskState(task_id="latency_sensitive", is_latency_sensitive=True)
    }

    # Event queue: (time, event_type, payload). event_type in
    # {"latency_wake", "churn_wake", "rotate", "cpu_free"}.
    events = []
    heapq.heappush(events, (latency_task_period, "latency_wake", None))
    heapq.heappush(events, (rotate_interval, "rotate", None))

    # Pre-generate churn arrivals as a genuine Poisson process —
    # independent of CPU state, so they accumulate correctly while
    # the CPU is busy running something else. Draw from a FIXED POOL
    # of persistent identities, weighted so some are inherently
    # chattier than others (matching Phase 1's skewed-churn model) —
    # this is what gives the tracking-based policies an actual signal
    # to differentiate on.
    pool = [f"churn_pool_{i}" for i in range(churn_pool_size)]
    # Skew: first 15% of the pool draws 5x as often as the rest —
    # these become the "heavy wakers" the tracking policies should
    # learn to deprioritize.
    num_heavy = max(1, int(churn_pool_size * 0.15))
    weights = [5.0] * num_heavy + [1.0] * (churn_pool_size - num_heavy)
    heavy_pool_ids = set(pool[:num_heavy])

    t_churn = 0.0
    while t_churn < sim_duration:
        t_churn += rng.expovariate(1.0 / churn_mean_interarrival)
        if t_churn >= sim_duration:
            break
        cid = rng.choices(pool, weights=weights, k=1)[0]
        heapq.heappush(events, (t_churn, "churn_wake", cid))

    runnable_queue: list[RunnableInstance] = []
    cpu_busy_until = 0.0
    cpu_idle = True

    def maybe_dispatch(now: float):
        nonlocal cpu_busy_until, cpu_idle
        if not cpu_idle or not runnable_queue:
            return
        chosen = _select_task(policy, runnable_queue, task_states, exact_tracker, sketch_tracker)
        runnable_queue.remove(chosen)
        ts = task_states[chosen.task_id]

        if ts.is_latency_sensitive:
            result.latencies.append(now - chosen.wake_time)
            run_time = latency_task_burst
        else:
            run_time = chosen.burst

        # Burst history recorded for EVERY task, including the
        # latency-sensitive one — needed so any heuristic that infers
        # "interactivity" from observed burst pattern (rather than a
        # cheating oracle flag) has real data to work with for every
        # task, not just churn tasks.
        ts.recent_burst_lengths.append(run_time)
        if len(ts.recent_burst_lengths) > 5:
            ts.recent_burst_lengths.pop(0)

        ts.vruntime += run_time
        cpu_busy_until = now + run_time
        cpu_idle = False
        heapq.heappush(events, (cpu_busy_until, "cpu_free", None))

    while events:
        now, ev_type, payload = heapq.heappop(events)
        if now > sim_duration:
            break

        if ev_type == "rotate":
            exact_tracker.rotate()
            sketch_tracker.rotate()
            heapq.heappush(events, (now + rotate_interval, "rotate", None))

        elif ev_type == "latency_wake":
            runnable_queue.append(RunnableInstance("latency_sensitive", now, latency_task_burst))
            exact_tracker.increment("latency_sensitive")
            sketch_tracker.increment("latency_sensitive")
            result.total_arrivals += 1
            heapq.heappush(events, (now + latency_task_period, "latency_wake", None))

        elif ev_type == "churn_wake":
            cid = payload
            if cid not in task_states:
                task_states[cid] = TaskState(task_id=cid, is_latency_sensitive=False)
            # Heavy (frequent) identities get SHORT bursts — matching
            # the actual motivating scenario (Wu's LPC talk, cited in
            # this project's related work): frequent wakeups with LOW
            # per-wakeup CPU cost, which vruntime-based fairness alone
            # does NOT naturally penalize, since vruntime only grows
            # from actual run time, not wakeup count. An earlier
            # version used the SAME burst range for heavy and light
            # identities, meaning heavy identities also accumulated
            # more vruntime proportionally — correlating frequency
            # with vruntime and making the frequency-based penalty
            # largely redundant with what EEVDF already captures. This
            # is the actually-interesting test of the hypothesis.
            is_heavy_pool_member = cid in heavy_pool_ids
            if is_heavy_pool_member:
                burst = rng.uniform(0.1, 0.5)  # short burst, low vruntime cost
            else:
                burst = rng.uniform(*churn_burst_range)
            runnable_queue.append(RunnableInstance(cid, now, burst))
            exact_tracker.increment(cid)
            sketch_tracker.increment(cid)
            result.total_arrivals += 1

        elif ev_type == "cpu_free":
            cpu_idle = True

        result.max_queue_depth = max(result.max_queue_depth, len(runnable_queue))
        maybe_dispatch(now)

    return result


def _select_task(policy: Policy, runnable: list, task_states: dict,
                  exact_tracker, sketch_tracker) -> RunnableInstance:
    if policy == Policy.SCX_SIMPLE_LIKE:
        return runnable[0]  # true FIFO — order of arrival in the list

    if policy == Policy.EEVDF_LIKE:
        return min(runnable, key=lambda r: task_states[r.task_id].vruntime)

    if policy in (Policy.ISOLATION_EXACT, Policy.OUR_SKETCH):
        def score(r):
            ts = task_states[r.task_id]
            if policy == Policy.ISOLATION_EXACT:
                freq = exact_tracker.estimate(r.task_id)
            else:
                freq = sketch_tracker.estimate(r.task_id)
            penalty = 0.0 if ts.is_latency_sensitive else freq * 0.5
            return ts.vruntime + penalty
        return min(runnable, key=score)

    if policy == Policy.SCX_LAVD_LIKE:
        # FIXED: no more oracle knowledge of is_latency_sensitive.
        # Infers "interactivity" purely from observed recent burst
        # length, on equal footing with every other task — the
        # latency task must earn its boost from its own genuinely
        # short, consistent bursts (5.0 units), same as any real task
        # would have to under an actual burst-length heuristic.
        def lavd_score(r):
            ts = task_states[r.task_id]
            avg_burst = statistics.mean(ts.recent_burst_lengths) if ts.recent_burst_lengths else 5.0
            return ts.vruntime + avg_burst
        return min(runnable, key=lavd_score)

    raise ValueError(f"unknown policy {policy}")


def run_comparison(num_seeds: int = 10) -> dict:
    print("=" * 76)
    print("EARLY DIRECTIONAL COMPARISON — scheduling POLICY simulation")
    print("=" * 76)
    print()
    print("  *** Pure-Python, abstract-time-unit POLICY comparison only.")
    print("  No connection to real hardware timing. Does NOT replace or")
    print("  preview real Phase 2 kernel benchmarking (Section 3.3). ***")
    print()

    results = {}
    for policy in Policy:
        p50s, p99s, queue_depths, arrivals = [], [], [], []
        for seed in range(num_seeds):
            r = run_scheduler_simulation(policy, seed=seed)
            if len(r.latencies) < 10:
                continue
            sorted_lat = sorted(r.latencies)
            p50s.append(sorted_lat[len(sorted_lat) // 2])
            p99s.append(sorted_lat[int(len(sorted_lat) * 0.99)])
            queue_depths.append(r.max_queue_depth)
            arrivals.append(r.total_arrivals)
        results[policy.value] = {
            "p50_mean": statistics.mean(p50s),
            "p50_std": statistics.stdev(p50s) if len(p50s) > 1 else 0,
            "p99_mean": statistics.mean(p99s),
            "p99_std": statistics.stdev(p99s) if len(p99s) > 1 else 0,
            "avg_max_queue_depth": statistics.mean(queue_depths),
            "avg_arrivals": statistics.mean(arrivals),
        }

    print(f"  Sanity check — avg arrivals/run: "
          f"{results[Policy.EEVDF_LIKE.value]['avg_arrivals']:.0f}, "
          f"avg max queue depth: "
          f"{results[Policy.EEVDF_LIKE.value]['avg_max_queue_depth']:.1f}")
    print("  (max queue depth should be well above 1 if contention is")
    print("  genuinely being modeled — a repeat of the earlier bug would")
    print("  show this near 1.)")
    print()

    print(f"{'Policy':>30}  {'P50 latency':>14}  {'P99 latency':>14}")
    for name, r in results.items():
        print(f"{name:>30}  {r['p50_mean']:>8.1f}±{r['p50_std']:<4.1f}  "
              f"{r['p99_mean']:>8.1f}±{r['p99_std']:<4.1f}")

    print()
    baseline_p99 = results[Policy.EEVDF_LIKE.value]["p99_mean"]
    print("  Relative to EEVDF-like baseline (P99):")
    for name, r in results.items():
        rel = r["p99_mean"] / baseline_p99
        print(f"    {name:>30}: {rel:.2f}x")
    print()

    return results


if __name__ == "__main__":
    run_comparison()

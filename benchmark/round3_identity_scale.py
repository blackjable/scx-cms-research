#!/usr/bin/env python3
"""
Round 3: does the sketch actually save memory, and at what quality cost?

WHY ROUND 3 EXISTS

Round 2 did NOT establish that approximate tracking preserves scheduling
quality -- its negative control showed the apparent benefit was almost
entirely count-blind vtime perturbation, leaving sketch-vs-exact
comparisons with little to resolve. It established nothing about memory
either, and the way it appeared to is worth stating plainly because it
would have gone into the paper:

  sketch, at defaults      2 x 256 x 4 cells x 4B  =   ~8 KB
  exact, as provisioned    CMS_MAX_TRACKED = 16384 =  ~800 KB

That reads as a 100x saving. It is an artifact. Round 2's workload had
~132 distinct identities -- under 1% of the exact map's provisioned
capacity. An exact map honestly sized for 132 tasks is about 6 KB, which
is SMALLER than the sketch. At round 2's scale the sketch is not a
memory optimisation at all; it is a memory regression.

A sketch earns its keep only where the identity count is large and
unpredictable, because its footprint is constant while exact counting
grows with the number of distinct things counted. Round 2 never entered
that regime, so it could not have measured the tradeoff the paper is
about. This round enters it deliberately.

THE INDEPENDENT VARIABLE: MEMORY BUDGET, NOT IDENTITY COUNT

The first design swept identity count, trying to overwhelm a fixed-size
exact map. Two things killed it, both found by a smoke test rather than
by reasoning, which is why the smoke test was worth running:

  1. Both cms_counts and cms_sketch exist in the BPF object whichever
     tracker is selected, so every condition reported identical memory
     (1,559.9 KB). Selecting the sketch, as the implementation stood,
     saved exactly zero bytes.
  2. The interesting regime is unreachable that way. Exceeding 16,384
     identities within a 1s window at 64 concurrent slots needs process
     lifetimes under 4ms, which fork cannot deliver on this machine.

So the sweep is over the memory budget itself. `--max-tracked` (added
for this experiment) sizes the exact hash; the sketch is sized to
comparable memory at each budget; both run the same workload. Shrink the
budget until something breaks, and see which breaks first.

That is also the better question. "How many identities before exact
fails" is machine-specific. "At a fixed memory budget, which counting
scheme delivers better scheduling" is the question a system designer
actually faces, and it is the one this paper claims to answer.

WHAT IS MEASURED AT EACH BUDGET

  1. Victim p50 and p99. p50 because round 2 established that tail
     latency alone cannot distinguish a discriminating policy from a
     blunt one -- a mechanism that degrades everything uniformly also
     compresses the tail.
  2. Actual memlock per map from bpftool, reported separately for exact
     and sketch, never summed. Summing is what produced the meaningless
     identical figures above.

WHAT WOULD FALSIFY THE PROJECT'S PREMISE

If exact counting holds quality at every scale this machine can reach,
while costing memory the system does not notice, then the sketch solves
a problem nobody has here. That is a legitimate outcome and must be
reported as one rather than buried -- the memory pressure argument is an
assumption this project has not yet tested, and Section 5's limitations
already flag it.

THE BASELINE IS `flat`, NOT `none`

Round 2's negative control showed ~84% of the apparent benefit came from
vtime perturbation rather than from consulting the count. Comparing
sketch against exact relative to `none` therefore has almost no
resolving power: both are dominated by a component the sketch cannot
degrade. Every quality comparison here is stated relative to `flat` at
matched strength, isolating the count-attributable component, which is
the only part the sketch could possibly harm.
"""

import argparse
import os
import random
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/tmp")

import round2_mixed_workload as r2  # noqa: E402


def churn_respawner(slot: int, rate: float, duration: float, burn_us: int,
                    lifetime_s: float):
    """One slot that continuously replaces its worker process.

    Concurrency stays at one task per slot; identity count grows with
    time, because each replacement gets a fresh pid. This is what lets
    the sweep vary identity population independently of load.
    """
    end = time.time() + duration
    while time.time() < end:
        remaining = end - time.time()
        pid = os.fork()
        if pid == 0:
            r2.churn_worker(slot, rate, min(lifetime_s, remaining), burn_us)
            os._exit(0)
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass


def spawn_scaling_churn(slots: int, rate: float, duration: float,
                        burn_us: int, lifetime_s: float) -> list:
    pids = []
    for i in range(slots):
        pid = os.fork()
        if pid == 0:
            churn_respawner(i, rate, duration, burn_us, lifetime_s)
            os._exit(0)
        pids.append(pid)
    return pids


def map_memory(name_substr: str) -> dict:
    """Resident cost of the tracker's map, as the kernel reports it.

    Quoting configured dimensions instead of this would understate the
    exact tracker, which pays hash and LRU overhead the sketch's flat
    array does not.
    """
    try:
        out = subprocess.run(["bpftool", "map", "show"], capture_output=True,
                             text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}
    # `bpftool map show` emits two lines per map: an id/type/name header,
    # then an indented line carrying key/value/max_entries/memlock. The
    # figure we want is on the SECOND line, so match on the header and
    # read the line after it.
    lines = out.splitlines()
    found = {}
    for i, line in enumerate(lines):
        if name_substr not in line or not line[:1].isdigit():
            continue
        name = line.split("name")[-1].split()[0] if "name" in line else f"map{i}"
        detail = lines[i + 1] if i + 1 < len(lines) else ""
        d = {}
        toks = detail.replace("B", " ").split()
        for j, t in enumerate(toks):
            if t in ("key", "value", "max_entries", "memlock") and j + 1 < len(toks):
                try:
                    d[t] = int(toks[j + 1])
                except ValueError:
                    pass
        if d:
            found[name] = d
    return found


def run_scale_point(binary, sched_args, args, slots, lifetime_s) -> dict:
    with r2.SchedulerHandle(binary, sched_args):
        churn = spawn_scaling_churn(slots, args.churn_rate, args.duration + 2,
                                    args.churn_burn_us, lifetime_s)
        time.sleep(1.0)
        res = r2.run_schbench_victim(args)
        mem = map_memory("cms_")
        for p in churn:
            try:
                os.kill(p, 9)
            except ProcessLookupError:
                pass
        for p in churn:
            try:
                os.waitpid(p, 0)
            except ChildProcessError:
                pass
    # Report per map, never a sum. Both cms_counts and cms_sketch exist in
    # the BPF object whichever tracker is selected, so summing them is
    # identical across conditions and measures nothing -- the first version
    # of this script reported 1,559.9 KB for every row for exactly that
    # reason. The number that means something is the selected tracker's own
    # map.
    #
    # Match the name EXACTLY rather than by substring. There are two exact
    # maps -- cms_counts (LRU) and cms_counts_plain -- and a substring test
    # for "count" matches both, including the plain one under the truncated
    # name bpftool reports (BPF_OBJ_NAME_LEN is 16, so "cms_counts_plain"
    # shows as "cms_counts_plai"). Which one dict iteration reached first
    # then decided the reported figure. Both are sized to --max-tracked so
    # the entry count was right either way, but LRU_HASH and HASH have
    # different per-entry overhead, so the BYTES could have come from the
    # map that was not in use.
    plain = "--plain-map" in (sched_args or [])
    want = "cms_counts_plai" if plain else "cms_counts"
    res["mem_exact"] = next((d.get("memlock", 0) for n, d in mem.items()
                             if n == want), 0)
    if not res["mem_exact"]:
        # Name reporting differs across bpftool versions; fall back rather
        # than silently reporting 0, but exclude the map we did not select.
        res["mem_exact"] = next(
            (d.get("memlock", 0) for n, d in mem.items()
             if "count" in n and ("plai" in n) == plain), 0)
    res["mem_sketch"] = next((d.get("memlock", 0) for n, d in mem.items()
                              if "sketch" in n), 0)
    res["identities_est"] = int(slots * (args.duration / lifetime_s))
    return res


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--slots", type=int, default=128,
                    help="concurrent churn tasks; held CONSTANT across the "
                         "sweep so load does not vary with identity count")
    ap.add_argument("--churn-rate", type=float, default=200.0)
    ap.add_argument("--churn-burn-us", type=int, default=200)
    ap.add_argument("--victim-threads", type=int, default=4)
    ap.add_argument("--victim-rps", type=int, default=100)
    ap.add_argument("--window-ms", type=int, default=1000)
    ap.add_argument("--penalty-ns", type=int, default=20287)
    ap.add_argument("--flat-ns", type=int, default=4_000_000)
    ap.add_argument("--sketch-width", type=int, default=256)
    ap.add_argument("--sketch-depth", type=int, default=4)
    ap.add_argument("--repeat", type=int, default=8)
    ap.add_argument("--lifetime", type=float, default=0.25,
                    help="churn task lifetime in seconds; short enough that "
                         "identities turn over continuously")
    ap.add_argument("--budgets-kb", default="128,32,8,2",
                    help="memory budgets in KB; exact and sketch are each "
                         "sized to cost about this much, from measured "
                         "per-entry and per-cell cost")
    ap.add_argument("--order-seed", type=int, default=1)
    ap.add_argument("--extra", default="",
                    help="extra scheduler flags appended to every condition, "
                         "space separated (e.g. --extra=--plain-map). Used to "
                         "re-run a sweep under a control without duplicating "
                         "the harness.")
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx_cms = r2._find("scx-target/debug/scx_cms")
    common = ["--identity-key", "pid", "--window-ms", str(args.window_ms)]
    if args.extra:
        common = common + args.extra.split()

    print("Round 3: identity-count scaling -- the memory question")
    print(f"load held constant at {args.slots} concurrent churn tasks; "
          f"identity count varied by task lifetime\n")

    budgets_kb = [int(x) for x in args.budgets_kb.split(",")]

    # Matched budgets, derived from MEASURED per-unit cost rather than
    # from configured dimensions. The exact hash costs ~96 bytes per
    # entry (key + value + bucket overhead); the sketch ~8 bytes per
    # cell. Sizing either from its nominal dimensions is how round 2
    # ended up comparing an 8 KB sketch against an 800 KB map and
    # calling it a 100x saving.
    EXACT_B_PER_ENTRY = 96
    SKETCH_B_PER_CELL = 8

    # Same lesson as round 2 (commit 623762e): a fixed condition order
    # makes carryover systematic bias that repetitions cannot average
    # away. This file was written with that bug still in it.
    order_rng = random.Random(args.order_seed)
    print(f"condition order randomised per repetition, seed={args.order_seed}")
    print("budgets matched on measured memlock; check the map column\n")

    for kb in budgets_kb:
        budget_b = kb * 1024
        entries = max(16, budget_b // EXACT_B_PER_ENTRY)
        cells = max(64, budget_b // SKETCH_B_PER_CELL)
        width = max(16, min(4096, cells // (2 * args.sketch_depth)))

        print(f"### budget ~{kb} KB   exact {entries} entries   "
              f"sketch 2x{width}x{args.sketch_depth} ###")
        conds = [
            # `none` tracks but never acts. Without it, a tracker that has
            # degenerated into doing nothing is indistinguishable from one
            # that discriminates perfectly: both leave the victim's median
            # untouched, and both therefore score well against `flat`,
            # which is worse than doing nothing. Round 3 omitted it and
            # could not tell those cases apart.
            ("none", ["--tracker", "exact", "--mechanism", "none",
                      "--max-tracked", str(entries)] + common),
            ("flat", ["--tracker", "exact", "--mechanism", "flat",
                      "--flat-ns", str(args.flat_ns),
                      "--max-tracked", str(entries)] + common),
            ("exact_penalty", ["--tracker", "exact", "--mechanism", "penalty",
                               "--penalty-ns", str(args.penalty_ns),
                               "--max-tracked", str(entries)] + common),
            ("sketch_penalty", ["--tracker", "sketch", "--mechanism", "penalty",
                                "--penalty-ns", str(args.penalty_ns),
                                "--sketch-width", str(width),
                                "--sketch-depth", str(args.sketch_depth)] + common),
        ]
        acc = {label: {"p50": [], "p99": [], "mem": []} for label, _ in conds}
        for _ in range(args.repeat):
            shuffled = list(conds)
            order_rng.shuffle(shuffled)
            for label, sched_args in shuffled:
                try:
                    r = run_scale_point(scx_cms, sched_args, args, args.slots,
                                        args.lifetime)
                except Exception as e:  # noqa: BLE001
                    print(f"  {label:<16} ERROR: {e}")
                    continue
                acc[label]["p50"].append(r["wu_p50"])
                acc[label]["p99"].append(r["wu_p99"])
                acc[label]["mem"].append(r["mem_sketch"] if "sketch" in label
                                         else r["mem_exact"])
        base = None
        for label, _ in conds:
            a = acc[label]
            if not a["p99"]:
                continue
            med99 = statistics.median(a["p99"])
            if label == "flat":
                base = med99
            rel = f"{med99 / base:>5.2f}x" if base else "  --  "
            print(f"  {label:<16} p50 {statistics.median(a['p50']):>6.0f}us  "
                  f"p99 {med99:>7.0f}us {rel}  "
                  f"p50 rng {min(a['p50']):>5}-{max(a['p50']):<5} "
                  f"p99 rng {min(a['p99']):>6}-{max(a['p99']):<6} "
                  f"map {statistics.median(a['mem'])/1024.0:>7.1f}KB")
        print()

    print("HOW TO READ THIS:")
    print("  Compare sketch_penalty against exact_penalty AT EACH LIFETIME,")
    print("  both relative to flat. The count-attributable benefit is the")
    print("  gap from flat; the sketch's cost is how much of that gap it")
    print("  fails to reproduce. Ranges overlapping = no difference shown.")
    print("  Then compare the maps column: the sketch's whole claim is that")
    print("  its number does not move as identities grow while exact's must.")
    print("  If exact's quality holds at every scale AND its memory stays")
    print("  affordable, the sketch is solving a problem this machine does")
    print("  not have, and that is the finding.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

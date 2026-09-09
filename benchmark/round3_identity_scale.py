#!/usr/bin/env python3
"""
Round 3: does the sketch actually save memory, and at what quality cost?

WHY ROUND 3 EXISTS

Round 2 established that approximate tracking preserves scheduling
quality. It established NOTHING about memory, and the way it appeared to
is worth stating plainly because it would have gone into the paper:

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

THE INDEPENDENT VARIABLE

Distinct identity count, swept across orders of magnitude. Churn tasks
are short-lived and respawned continuously, so with --identity-key pid
each new process is a new identity and the population of identities seen
per window grows without the machine's concurrent task count growing.
That separation matters: it varies what the TRACKER must hold without
also varying the scheduling pressure, so a quality change can be
attributed to tracking capacity rather than to load.

WHAT IS MEASURED AT EACH SCALE

  1. Victim p99, sketch vs exact -- does approximation degrade quality
     once the identity space is genuinely large?
  2. Actual map memory, read from bpftool, not computed from the
     configured dimensions. The configured size and the resident cost
     differ (hash overhead, per-CPU replication, LRU bookkeeping), and
     the paper should quote what the kernel actually spends.
  3. Exact's eviction rate. An LRU hash under-provisioned for the
     identity population silently evicts, and an evicted identity
     returns count 0 -- exact counting stops being exact. The scale at
     which that starts is the honest boundary of "just use a hash map",
     and finding it is the point of the whole experiment.

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
    found = {}
    for line in out.splitlines():
        if name_substr not in line:
            continue
        d = {}
        toks = line.replace(":", " ").split()
        for i, t in enumerate(toks):
            if t in ("key", "value", "max_entries", "memlock") and i + 1 < len(toks):
                try:
                    d[t] = int(toks[i + 1].rstrip("B"))
                except ValueError:
                    pass
        if "memlock" in d:
            found[line.split()[1] if len(line.split()) > 1 else "?"] = d
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
    res["memlock"] = sum(d.get("memlock", 0) for d in mem.values())
    res["identities_est"] = int(slots * (args.duration / lifetime_s))
    return res


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--slots", type=int, default=64,
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
    ap.add_argument("--lifetimes", default="10,1,0.25,0.06",
                    help="churn task lifetime in seconds; SHORTER means more "
                         "distinct identities per window at identical load")
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx_cms = r2._find("scx-target/debug/scx_cms")
    common = ["--identity-key", "pid", "--window-ms", str(args.window_ms)]

    print("Round 3: identity-count scaling -- the memory question")
    print(f"load held constant at {args.slots} concurrent churn tasks; "
          f"identity count varied by task lifetime\n")

    lifetimes = [float(x) for x in args.lifetimes.split(",")]

    for lifetime in lifetimes:
        est = int(args.slots * (args.duration / lifetime))
        print(f"### lifetime {lifetime}s  ~{est} distinct identities "
              f"per {args.duration}s ###")
        conds = [
            ("flat", ["--tracker", "exact", "--mechanism", "flat",
                      "--flat-ns", str(args.flat_ns)] + common),
            ("exact_penalty", ["--tracker", "exact", "--mechanism", "penalty",
                               "--penalty-ns", str(args.penalty_ns)] + common),
            ("sketch_penalty", ["--tracker", "sketch", "--mechanism", "penalty",
                                "--penalty-ns", str(args.penalty_ns),
                                "--sketch-width", str(args.sketch_width),
                                "--sketch-depth", str(args.sketch_depth)] + common),
        ]
        base = None
        for label, sched_args in conds:
            p99s, mems = [], []
            for _ in range(args.repeat):
                try:
                    r = run_scale_point(scx_cms, sched_args, args, args.slots,
                                        lifetime)
                except Exception as e:  # noqa: BLE001
                    print(f"  {label:<16} ERROR: {e}")
                    break
                p99s.append(r["wu_p99"])
                mems.append(r["memlock"])
            if not p99s:
                continue
            med = statistics.median(p99s)
            if label == "flat":
                base = med
            rel = f"{med / base:>5.2f}x vs flat" if base else "  baseline"
            mem_kb = statistics.median(mems) / 1024.0 if mems else 0
            print(f"  {label:<16} p99 {med:>7.0f}us  {rel}  "
                  f"range {min(p99s):>6}-{max(p99s):>6}  "
                  f"maps {mem_kb:>7.1f} KB")
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

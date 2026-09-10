#!/usr/bin/env python3
"""
Round 5: measure the inflation that the collapse was blamed on.

Round 3 found the sketch losing all discrimination at 8 KB, and
explained it by collisions inflating the protected task's count so the
penalty meant for churn lands on the victim. That explanation was never
measured -- it was inferred from scheduling outcomes. The scheduler
already carries `--compare`, which runs both trackers over the same
wakeup stream and reports mean exact count, mean sketch count, and the
worst single overestimate, so the inference is directly checkable and
was simply not checked.

This also measures inflation in BOTH identity regimes, which is the
other thing round 3 left open. The budget sweep ran only against
continuously respawning churn (~5,000 identities). Round 2d's workload
had ~132 identities and there an ~16 KB sketch performed identically to
exact -- a counterexample to "the sketch loses at every budget" sitting
in the paper's own results table.

If inflation tracks the identity-to-cell ratio rather than the byte
budget, then the honest claim is not "loses at every memory budget" but
"loses whenever the identity population greatly exceeds capacity" --
which is a stronger refutation, because that regime is precisely where
a sketch is supposed to earn its keep.

Reported per budget per regime:

  exact_mean   mean true count per query
  sketch_mean  mean sketch estimate for the same queries
  inflation    sketch_mean / exact_mean; 1.0 means no error
  max_over     worst single overestimate observed
  underest     count of never-undercount violations (must be 0)
"""

import argparse
import os
import re
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/tmp")

import round2_mixed_workload as r2  # noqa: E402
import round3_identity_scale as r3  # noqa: E402

CMP = re.compile(
    r"compare: samples=(\d+) exact_mean=([\d.]+) sketch_mean=([\d.]+)")
OVER = re.compile(r"max_over=(\d+)")
UNDER = re.compile(r"(\d+) UNDERESTIMATES")


def measure(scx_cms, args, entries, width, depth, slots, lifetime):
    """One compare-mode run; returns the divergence it reported."""
    sched_args = [
        "--tracker", "exact", "--mechanism", "none", "--compare",
        "--identity-key", "pid", "--window-ms", str(args.window_ms),
        "--max-tracked", str(entries),
        "--sketch-width", str(width), "--sketch-depth", str(depth),
        "--stats", "2",
    ]
    h = r2.SchedulerHandle(scx_cms, sched_args)
    with h:
        churn = r3.spawn_scaling_churn(slots, args.churn_rate,
                                       args.duration + 2,
                                       args.churn_burn_us, lifetime)
        time.sleep(args.duration)
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
    try:
        log = open(h.log).read()
    except OSError:
        return None
    rows = CMP.findall(log)
    if not rows:
        return None
    # Last sample is the most settled; the first covers scheduler startup.
    samples, exact_mean, sketch_mean = rows[-1]
    over = OVER.findall(log)
    under = UNDER.findall(log)
    em, sm = float(exact_mean), float(sketch_mean)
    return {
        "samples": int(samples),
        "exact_mean": em,
        "sketch_mean": sm,
        "inflation": (sm / em) if em else float("nan"),
        "max_over": int(over[-1]) if over else 0,
        "underest": int(under[-1]) if under else 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--slots", type=int, default=128)
    ap.add_argument("--churn-rate", type=float, default=200.0)
    ap.add_argument("--churn-burn-us", type=int, default=200)
    ap.add_argument("--victim-threads", type=int, default=4)
    ap.add_argument("--victim-rps", type=int, default=100)
    ap.add_argument("--window-ms", type=int, default=1000)
    ap.add_argument("--sketch-depth", type=int, default=4)
    ap.add_argument("--budgets-kb", default="128,32,8,2")
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx_cms = r2._find("scx-target/debug/scx_cms")

    regimes = [
        ("stable  (~128 identities)", 60.0),
        ("churning(~5000 identities)", 0.25),
    ]

    print("Round 5: measured sketch inflation, both identity regimes")
    print("compare mode runs BOTH trackers over the same wakeup stream,")
    print("so exact_mean and sketch_mean describe identical queries.\n")

    for label, lifetime in regimes:
        print(f"### regime: {label} ###")
        print(f"  {'budget':>8} {'cells':>7} {'exact':>9} {'sketch':>9} "
              f"{'inflation':>10} {'max_over':>9} {'underest':>9}")
        for kb in [int(x) for x in args.budgets_kb.split(",")]:
            b = kb * 1024
            entries = max(16, b // 96)
            cells = max(64, b // 8)
            width = max(16, min(4096, cells // (2 * args.sketch_depth)))
            runs = []
            for _ in range(args.repeat):
                r = measure(scx_cms, args, entries, width, args.sketch_depth,
                            args.slots, lifetime)
                if r:
                    runs.append(r)
            if not runs:
                print(f"  {kb:>6}KB  (no compare samples)")
                continue
            med = lambda k: statistics.median(x[k] for x in runs)  # noqa: E731
            print(f"  {kb:>6}KB {2*width*args.sketch_depth:>7} "
                  f"{med('exact_mean'):>9.1f} {med('sketch_mean'):>9.1f} "
                  f"{med('inflation'):>9.2f}x {med('max_over'):>9.0f} "
                  f"{max(x['underest'] for x in runs):>9}")
        print()

    print("HOW TO READ THIS:")
    print("  inflation 1.0x = the sketch agrees with exact counting.")
    print("  If inflation is near 1.0 in the stable regime at a budget where")
    print("  round 3 saw the sketch collapse, then identity count -- not the")
    print("  byte budget -- is the variable that breaks it, and the paper's")
    print("  'loses at every budget' framing is wrong as stated.")
    print("  underest MUST be 0: a non-zero value means the never-undercount")
    print("  guarantee was violated on real kernel data, which would be a")
    print("  correctness bug, not an accuracy result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

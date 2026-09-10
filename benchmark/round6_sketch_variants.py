#!/usr/bin/env python3
"""
Round 6: can the sketch be fixed, and is the exact tracker's failure real?

Four questions, all previously answered by assertion rather than
measurement, and all now testable because the scheduler grew the flags
to test them.

1. CONSERVATIVE UPDATE (--conservative). The sketch's failure mode is
   overestimation: collisions inflate the protected task's count until
   the penalty meant for background work lands on it. Conservative
   update raises each row's cell to max(cell, min_before + 1) instead of
   incrementing all of them, so cells already above the minimum stop
   absorbing unrelated mass. It costs no memory. If it closes the gap,
   the negative result applies to the standard construction only, which
   is a much narrower claim than the one currently written down.

2. HASH MIXING (--hash-mix). Every width here is a power of two, so the
   modulo keeps FNV-1a's least-mixed bits. Simulation put the cost at
   <=13% at the narrowest width. That was a model; this measures it on
   the kernel.

3. MAP TYPE (--plain-map). The finding that exact counting degrades at
   small entry counts was explained by BPF LRU behaviour -- per-CPU free
   lists targeting 128 entries each, against maps sized in the tens --
   and that explanation was never tested. A plain hash has the same
   capacity and no eviction. If degradation persists it is capacity; if
   it vanishes the explanation was the LRU implementation, which is a
   practical trap worth reporting on its own.

4. COUNT DISTRIBUTION. The churning workload reports a mean tracked
   count of ~220 where the model predicts ~64, and the measured identity
   population did not close the gap. A mean cannot distinguish "most
   queries see 220" from "most see nothing and a few see thousands".
   The scheduler now buckets the counts, so this is answerable instead
   of inferrable.

Compare mode runs both trackers over the same wakeup stream, so the
exact and sketch figures describe identical queries.
"""

import argparse
import os
import re
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/tmp")

import round2_mixed_workload as r2  # noqa: E402
import round3_identity_scale as r3  # noqa: E402

CMP = re.compile(r"compare: samples=(\d+) exact_mean=([\d.]+) sketch_mean=([\d.]+)")
HIST = re.compile(
    r"distribution: zero=(\d+) 1-9=(\d+) 10-99=(\d+) 100-999=(\d+) "
    r"1k-10k=(\d+) 10k\+=(\d+)")
UNDER = re.compile(r"(\d+) UNDERESTIMATES")


def measure(scx, args, entries, width, depth, lifetime, extra):
    sched = ["--tracker", "exact", "--mechanism", "none", "--compare",
             "--identity-key", "pid", "--window-ms", str(args.window_ms),
             "--max-tracked", str(entries),
             "--sketch-width", str(width), "--sketch-depth", str(depth),
             "--stats", "2"] + extra
    h = r2.SchedulerHandle(scx, sched)
    with h:
        churn = r3.spawn_scaling_churn(args.slots, args.churn_rate,
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
    _, em, sm = rows[-1]
    hist = HIST.findall(log)
    under = UNDER.findall(log)
    return {
        "exact": float(em),
        "sketch": float(sm),
        "ratio": float(sm) / float(em) if float(em) else float("nan"),
        "hist": [int(x) for x in hist[-1]] if hist else None,
        "under": int(under[-1]) if under else 0,
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
    ap.add_argument("--budgets-kb", default="32,16,8,4,2")
    ap.add_argument("--repeat", type=int, default=3)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx = r2._find("scx-target/debug/scx_cms")

    variants = [
        ("baseline", []),
        ("hash_mix", ["--hash-mix"]),
        ("conservative", ["--conservative"]),
        ("both", ["--hash-mix", "--conservative"]),
        ("plain_map", ["--plain-map"]),
    ]
    regimes = [("stable", 60.0), ("churning", 0.25)]

    print("Round 6: sketch fixes and the map-type control")
    print("compare mode; exact and sketch figures describe identical queries\n")

    for rlabel, lifetime in regimes:
        print(f"########## regime: {rlabel} ##########")
        for kb in [int(x) for x in args.budgets_kb.split(",")]:
            b = kb * 1024
            entries = max(16, b // 96)
            cells = max(64, b // 8)
            width = max(16, min(4096, cells // (2 * args.sketch_depth)))
            print(f"\n### {kb} KB -- exact {entries} entries, "
                  f"sketch 2x{width}x{args.sketch_depth} ###")
            print(f"  {'variant':<14}{'exact':>9}{'sketch':>9}"
                  f"{'sk/ex':>8}{'under':>7}   count distribution")
            for vlabel, extra in variants:
                runs = [measure(scx, args, entries, width, args.sketch_depth,
                                lifetime, extra)
                        for _ in range(args.repeat)]
                runs = [r for r in runs if r]
                if not runs:
                    print(f"  {vlabel:<14} (no samples)")
                    continue
                ex = statistics.median(r["exact"] for r in runs)
                sk = statistics.median(r["sketch"] for r in runs)
                ratio = statistics.median(r["ratio"] for r in runs)
                under = max(r["under"] for r in runs)
                h = runs[-1]["hist"]
                hs = ("z%d/%d/%d/%d/%d/%d" % tuple(h)) if h else "-"
                print(f"  {vlabel:<14}{ex:>9.1f}{sk:>9.1f}{ratio:>7.2f}x"
                      f"{under:>7}   {hs}")

    print("\nHOW TO READ THIS:")
    print("  conservative vs baseline: does conservative update reduce the")
    print("    sketch's overestimate? If yes, the negative result applies")
    print("    only to the standard construction.")
    print("  hash_mix vs baseline: is the power-of-two modulo costing")
    print("    accuracy on real data, as simulation predicted (<=13%)?")
    print("  plain_map vs baseline (exact column): if exact stops")
    print("    collapsing without an LRU, the collapse was the LRU")
    print("    implementation rather than capacity.")
    print("  under MUST be 0. Conservative update preserves")
    print("    never-undercount only if its read-min-write is atomic;")
    print("    a non-zero value means the spin lock is not doing its job.")
    print("  distribution buckets: zero/1-9/10-99/100-999/1k-10k/10k+ of")
    print("    the EXACT count seen per query.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

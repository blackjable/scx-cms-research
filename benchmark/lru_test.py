#!/usr/bin/env python3
"""
Does a small LRU_HASH work when the working set FITS?

This separates two explanations for a measurement that was correct and
badly explained. At 42 entries against ~330 live identities the LRU map
reported a mean tracked count of 1.6 where a plain hash of identical
capacity reported 189.8. That was written up as a property of BPF --
per-CPU free lists targeting LOCAL_FREE_TARGET (128) entries each,
making a map sized in the tens smaller than its own bookkeeping, so it
stops ordering by recency.

The competing explanation was never ruled out: **a correct LRU thrashes
when the working set exceeds capacity.** Every insert evicts something
about to be needed again, entries are dropped between their own
increments, and counts never accumulate. A mean near 1 is what thrashing
looks like, not what a bug looks like.

The two make opposite predictions, which is what makes this cheap. Hold
the map size fixed at 42 entries and shrink the identity population:

  - If the free lists are responsible, the map is broken at 42 entries
    REGARDLESS of how many identities compete for it, and the LRU column
    stays near 1 in every row.
  - If it is ordinary overcommitment, the LRU column tracks the RATIO of
    identities to slots -- normal while the working set fits, collapsing
    only once it does not.

The second is what happens. See `../results/REVISIONS.md` revision 12,
and `../results/raw/lru-working-set-test.txt` for the archived output.

NOTE ON PROVENANCE: the original script was written in a session
scratchpad and not preserved -- the same failure that
`../results/MANIFEST.md` was created to stop. This is a reconstruction
from the archived output's own header (compare mode, exact_mean per
query, 10s per measurement, stable identities) and from
`round6_sketch_variants.py`, which drives compare mode the same way.
The parameters match what the archived run recorded; treat re-run
numbers as a replication rather than as a reproduction bit-for-bit.
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

# (distinct churn identities, map entries). The 42-entry rows are the
# comparison that matters; the 128-entry rows are the control showing the
# same identity counts are unremarkable when given room.
CELLS = [(8, 128), (8, 42), (20, 128), (20, 42), (100, 42), (300, 42)]


def measure(scx, args, identities, entries, plain):
    """Mean exact tracked count per query, for one map type.

    --mechanism none: this measures what the tracker retains, not what a
    policy does with it. --compare runs both trackers over the same
    wakeup stream, and only the exact column is read here.
    """
    sched = ["--tracker", "exact", "--mechanism", "none", "--compare",
             "--identity-key", "pid", "--window-ms", str(args.window_ms),
             "--max-tracked", str(entries),
             "--stats", "2"] + (["--plain-map"] if plain else [])
    h = r2.SchedulerHandle(scx, sched)
    with h:
        churn = r3.spawn_scaling_churn(identities, args.churn_rate,
                                       args.duration + 2,
                                       args.churn_burn_us, args.lifetime)
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
    return float(rows[-1][1])


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--churn-rate", type=float, default=200.0)
    ap.add_argument("--churn-burn-us", type=int, default=200)
    ap.add_argument("--window-ms", type=int, default=1000)
    ap.add_argument("--lifetime", type=float, default=60.0,
                    help="stable identities; must exceed --duration so "
                         "nothing respawns mid-run and the population is "
                         "the number of slots")
    ap.add_argument("--repeat", type=int, default=1)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx = r2._find("scx-target/debug/scx_cms")

    print("Does a small LRU_HASH work when the working set FITS?\n")
    print(" identities  slots  LRU mean  plain mean   verdict")
    print("-" * 62)

    for identities, entries in CELLS:
        vals = {}
        for plain in (False, True):
            runs = [measure(scx, args, identities, entries, plain)
                    for _ in range(args.repeat)]
            runs = [r for r in runs if r is not None]
            vals[plain] = statistics.median(runs) if runs else float("nan")
        verdict = "fits" if identities <= entries else "OVER capacity"
        print(f"{identities:>11}{entries:>7}{vals[False]:>10.1f}"
              f"{vals[True]:>12.1f}   {verdict}")

    print(f"\nCompare mode, exact_mean per query, {args.duration}s per "
          f"measurement, stable\nidentities. Harness: lru_test.py. Analysed "
          f"in REVISIONS.md revision 12.")
    print("\nHOW TO READ THIS:")
    print("  The LRU column is the whole test. If it stays near 1 in every")
    print("  row, the map type is broken at this size and the original")
    print("  claim stands. If it is normal while identities <= slots and")
    print("  collapses only above it, the failure is overcommitment --")
    print("  which is what any LRU does below its working set, and is not")
    print("  a property of BPF.")
    print("  The plain-hash column is the control: it should hold roughly")
    print("  steady throughout, because a non-evicting map locks in")
    print("  whichever keys arrived first and lets those accumulate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

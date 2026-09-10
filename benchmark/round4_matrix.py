#!/usr/bin/env python3
"""
Round 4: flexible condition matrix over round 3's respawning workload.

Round 3 answered the memory question and raised two more that need
answering before any of it is written up.

MATRIX "identity" -- does the mechanism assume identity stability?

Round 3 found every penalty variant 2-3x WORSE than the count-blind
baseline on p99 at every memory budget. The likely cause is that
`--identity-key pid` cannot see continuously respawning churn: each new
process is a fresh identity at count 0, is never penalised, and runs at
full slice, so nothing controls the tail. The count-blind penalty does
better precisely because it does not need to recognise anything.

If that is right, `--identity-key comm` should recover it, since
respawned churn shares a comm. This is a real design assumption --
identity stability -- that the project never stated, so it belongs in
the paper's limitations either way.

This matrix also runs `--mechanism boost`, which has existed since the
mechanism abstraction was built and has appeared in **zero** experiments.
Given round 2's finding that the penalty's real value is avoiding
collateral damage rather than reducing the tail, boosting infrequent
wakers may be the better-shaped policy. Shipping a paper with an
untested mechanism sitting in the repository is not defensible.

MATRIX "bestshot" -- did we give the sketch its best shot?

Round 3's refutation rests on ONE sketch configuration per budget: depth
4, width scaled to fit. A refutation is only as strong as the effort
made to make the thing work, and three obvious objections are currently
unanswerable:

  - Why depth 4? At a fixed budget, width and depth trade off directly.
    Phase 1 found width buys more accuracy than depth, but that was
    synthetic and was never re-tested on the kernel.
  - Does seed rotation help? It is implemented and was tested against
    ADVERSARIAL collisions (delivery plan 9.6), never against the
    accidental collisions that caused the 8 KB collapse.
  - The collapse was diagnosed as inflation from collisions. Both knobs
    above target exactly that, so if either recovers discrimination the
    conclusion changes from "sketches lose here" to "this sketch
    configuration loses here", which is a much weaker and much more
    honest claim.

Run at the budget where round 3 saw the sketch collapse (8 KB), because
that is where the disagreement is decided. At 128 KB everything works
and at 2 KB nothing does; neither is informative.

WHY THE SAME WORKLOAD AS ROUND 3

Comparability. Round 3's numbers are the reference these are read
against, and changing the workload at the same time as the conditions
would leave nothing attributable.
"""

import argparse
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/tmp")

import round2_mixed_workload as r2  # noqa: E402
import round3_identity_scale as r3  # noqa: E402


def build_identity_matrix(args, common):
    """pid vs comm, penalty vs boost, against the count-blind reference."""
    pen = ["--penalty-ns", str(args.penalty_ns)]
    bst = ["--boost-ns", str(args.boost_ns),
           "--boost-threshold", str(args.boost_threshold)]
    ex = ["--tracker", "exact", "--max-tracked", str(args.max_tracked)]
    return [
        ("flat_ref", ex + ["--mechanism", "flat",
                           "--flat-ns", str(args.flat_ns)] + common),
        ("penalty_pid", ex + ["--mechanism", "penalty",
                              "--identity-key", "pid"] + pen + common),
        ("penalty_comm", ex + ["--mechanism", "penalty",
                               "--identity-key", "comm"] + pen + common),
        ("boost_pid", ex + ["--mechanism", "boost",
                            "--identity-key", "pid"] + bst + common),
        ("boost_comm", ex + ["--mechanism", "boost",
                             "--identity-key", "comm"] + bst + common),
    ]


def build_bestshot_matrix(args, common):
    """Every sketch shape that fits the budget where it collapsed.

    Cells are held constant so every sketch row costs the same memory;
    only the width/depth split changes. That is the comparison that
    isolates shape from budget.
    """
    budget_b = args.bestshot_kb * 1024
    cells = max(64, budget_b // 8)
    pen = ["--penalty-ns", str(args.penalty_ns)]
    entries = max(16, budget_b // 96)
    conds = [
        ("exact_ref", ["--tracker", "exact", "--mechanism", "penalty",
                       "--max-tracked", str(entries)] + pen + common),
        ("flat_ref", ["--tracker", "exact", "--mechanism", "flat",
                      "--max-tracked", str(entries),
                      "--flat-ns", str(args.flat_ns)] + common),
    ]
    for depth in (1, 2, 4, 8):
        width = max(16, min(4096, cells // (2 * depth)))
        conds.append((f"sketch_d{depth}_w{width}",
                      ["--tracker", "sketch", "--mechanism", "penalty",
                       "--sketch-width", str(width),
                       "--sketch-depth", str(depth)] + pen + common))
    # Seed rotation at the shape round 3 actually used, so the only
    # difference from round 3's collapsing row is the rotation itself.
    w4 = max(16, min(4096, cells // 8))
    conds.append(("sketch_d4_rotate",
                  ["--tracker", "sketch", "--mechanism", "penalty",
                   "--sketch-width", str(w4), "--sketch-depth", "4",
                   "--seed-rotation"] + pen + common))
    return conds


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("matrix", choices=["identity", "bestshot"])
    ap.add_argument("--duration", type=int, default=10)
    ap.add_argument("--slots", type=int, default=128)
    ap.add_argument("--lifetime", type=float, default=0.25)
    ap.add_argument("--churn-rate", type=float, default=200.0)
    ap.add_argument("--churn-burn-us", type=int, default=200)
    ap.add_argument("--victim-threads", type=int, default=4)
    ap.add_argument("--victim-rps", type=int, default=100)
    ap.add_argument("--window-ms", type=int, default=1000)
    ap.add_argument("--penalty-ns", type=int, default=20287)
    ap.add_argument("--flat-ns", type=int, default=4_000_000)
    ap.add_argument("--boost-ns", type=int, default=20287)
    ap.add_argument("--boost-threshold", type=int, default=8)
    ap.add_argument("--max-tracked", type=int, default=16384)
    ap.add_argument("--bestshot-kb", type=int, default=8)
    ap.add_argument("--sketch-depth", type=int, default=4)
    ap.add_argument("--repeat", type=int, default=10)
    ap.add_argument("--order-seed", type=int, default=1)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx_cms = r2._find("scx-target/debug/scx_cms")
    common = ["--window-ms", str(args.window_ms)]
    if args.matrix == "bestshot":
        common = ["--identity-key", "pid"] + common

    conds = (build_identity_matrix(args, common) if args.matrix == "identity"
             else build_bestshot_matrix(args, common))

    print(f"Round 4 matrix: {args.matrix}")
    print(f"workload: {args.slots} respawning churn slots, lifetime "
          f"{args.lifetime}s, schbench victim (same as round 3)")
    print(f"n={args.repeat}, condition order randomised, "
          f"seed={args.order_seed}\n")

    rng = random.Random(args.order_seed)
    acc = {name: {"p50": [], "p99": []} for name, _ in conds}
    for rep in range(args.repeat):
        shuffled = list(conds)
        rng.shuffle(shuffled)
        for name, sched_args in shuffled:
            try:
                r = r3.run_scale_point(scx_cms, sched_args, args, args.slots,
                                       args.lifetime)
            except Exception as e:  # noqa: BLE001
                print(f"  rep{rep} {name}: ERROR {e}")
                continue
            acc[name]["p50"].append(r["wu_p50"])
            acc[name]["p99"].append(r["wu_p99"])
        print(f"  ... repetition {rep + 1}/{args.repeat} done", flush=True)

    flat50 = (statistics.median(acc["flat_ref"]["p50"])
              if acc.get("flat_ref", {}).get("p50") else None)

    print("\n" + "=" * 82)
    print(f"{'condition':<20}{'p50 med':>9}{'p50 range':>16}"
          f"{'p99 med':>9}{'p99 range':>18}{'discrim':>9}")
    print("=" * 82)
    for name, _ in conds:
        a = acc[name]
        if not a["p50"]:
            continue
        m50 = statistics.median(a["p50"])
        m99 = statistics.median(a["p99"])
        disc = f"{flat50 / m50:>8.2f}x" if flat50 else "     --"
        print(f"{name:<20}{m50:>9.0f}"
              f"{str(min(a['p50']))+'-'+str(max(a['p50'])):>16}"
              f"{m99:>9.0f}"
              f"{str(min(a['p99']))+'-'+str(max(a['p99'])):>18}{disc}")

    print("\nDISCRIM = flat_ref p50 / this row's p50. It measures how well the")
    print("tracker separates the victim from churn, with the count-blind")
    print("penalty as the zero point. 1.0x means no discrimination at all;")
    print("below 1.0x means worse than not discriminating.")
    if args.matrix == "identity":
        print("\nKEY COMPARISON: penalty_comm vs penalty_pid on p99. If comm")
        print("recovers the tail, the mechanism's failure in round 3 was")
        print("identity turnover, not the mechanism. Also check whether boost")
        print("beats penalty at all -- it has never been run before this.")
    else:
        print("\nKEY COMPARISON: every sketch row vs exact_ref. If ANY sketch")
        print("shape reaches exact's discrimination at this budget, round 3's")
        print("refutation must be narrowed to 'this configuration' rather than")
        print("stated about sketches generally.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

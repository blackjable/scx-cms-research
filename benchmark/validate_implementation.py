#!/usr/bin/env python3
"""
Implementation validation: is the kernel sketch a faithful Count-Min Sketch?

WHY THIS EXISTS

The strongest objection to this project's central comparison is that it
compares one implementation against another implementation, both written
by the same author, rather than comparing the algorithms. Every
implementation-level concern found on review is an instance of that:
a hash that may under-mix, a map type whose behaviour at small sizes is
its own, a value encoding that spends bytes on bookkeeping.

The answer is not to argue the implementations are fine. It is to check
each against an independent reference before comparing them, so the
kernel code stops being an unvalidated variable.

This script does two checks that need no kernel and no VM:

  1. SIMULATION. Replicate the BPF hash exactly -- FNV-1a over the eight
     bytes of the u64 identity, seed mixed into the basis, modulo width
     -- drive the measured workload through it, and compare the
     resulting estimates against what the kernel actually reported. If
     they agree, the kernel implementation behaves as the model says a
     Count-Min Sketch should.

  2. HASH QUALITY. Run the identical simulation with a well-mixed hash
     (FNV-1a plus a final avalanche). Every width used here is a power
     of two, so `h % width` keeps only the low bits, and FNV-1a is
     documented as mixing its low bits weakest. If the avalanche version
     produces materially less error, the paper's negative result is
     partly a hash artifact and the hash must be fixed before the result
     can be reported. If it does not, that objection is answered with
     data instead of argument.

WORKLOAD MODELLED

Taken from the measured configuration, not invented: 128 churn
identities waking 200 times per second, a 4-thread victim waking ~100
times per second per thread, a 1000ms window, and an estimate summing
the current and previous windows -- so a churn identity's true count
per query is ~400.
"""

import statistics

FNV32_BASIS = 0x811C9DC5
FNV32_PRIME = 0x01000193
MASK32 = 0xFFFFFFFF


def bpf_hash(identity: int, seed: int, width: int) -> int:
    """Byte-for-byte reimplementation of cms_sketch_col() in sketch.bpf.c."""
    h = (FNV32_BASIS ^ seed) & MASK32
    for i in range(8):
        h ^= (identity >> (i * 8)) & 0xFF
        h = (h * FNV32_PRIME) & MASK32
    return h % width


def avalanched_hash(identity: int, seed: int, width: int) -> int:
    """Same hash plus a final mixing step, so the modulo sees mixed bits.

    This is the proposed fix, and running the sweep with it is how the
    hash-quality objection gets answered rather than asserted.
    """
    h = (FNV32_BASIS ^ seed) & MASK32
    for i in range(8):
        h ^= (identity >> (i * 8)) & 0xFF
        h = (h * FNV32_PRIME) & MASK32
    h ^= h >> 16
    h = (h * 0x7FEB352D) & MASK32
    h ^= h >> 15
    return h % width


def simulate(width, depth, n_churn, churn_wakes, victim_threads,
             victim_wakes, hashfn, seed_base=12345):
    """One window's worth of inserts, estimated as the kernel estimates.

    The kernel keeps two buffers and sums them, which is equivalent to a
    single sketch holding both windows' events, so a single table loaded
    with two windows of traffic is the correct model.
    """
    seeds = [(seed_base * (row + 1)) | 1 for row in range(depth)]
    table = [[0] * width for _ in range(depth)]

    truth = {}
    # Two windows of traffic, because an estimate spans both.
    for ident in range(1, n_churn + 1):
        count = churn_wakes * 2
        truth[ident] = count
        for row in range(depth):
            table[row][hashfn(ident, seeds[row], width)] += count
    for t in range(victim_threads):
        ident = 100000 + t
        count = victim_wakes * 2
        truth[ident] = count
        for row in range(depth):
            table[row][hashfn(ident, seeds[row], width)] += count

    ests = {}
    for ident in truth:
        ests[ident] = min(table[row][hashfn(ident, seeds[row], width)]
                          for row in range(depth))
    return truth, ests


def main() -> int:
    depth = 4
    n_churn, churn_wakes = 128, 200
    victim_threads, victim_wakes = 4, 100

    # What the kernel reported, from round 5 part A, stable regime.
    # exact_mean is the reference count; sketch_mean is the estimate.
    measured = {
        2048: (366.7, 366.6),
        1024: (363.1, 363.5),
        512: (365.9, 366.9),
        256: (299.3, 366.6),
        128: (193.7, 434.9),
        64: (1.5, 613.7),
        32: (1.0, 1042.6),
    }

    total_mass = (n_churn * churn_wakes + victim_threads * victim_wakes) * 2

    print("Implementation validation: kernel sketch vs model")
    print(f"model: {n_churn} churn identities x {churn_wakes}/s, "
          f"{victim_threads} victim threads x {victim_wakes}/s, depth {depth}")
    print(f"true count per churn identity per query: {churn_wakes * 2}")
    print(f"total mass in table: {total_mass}\n")

    print(f"{'width':>6} {'true':>7} {'sim(bpf)':>9} {'sim(mixed)':>11} "
          f"{'kernel':>8} {'sim/true':>9} {'ker/true':>9} {'CM bound':>9}")
    print("-" * 80)

    rows = []
    for width in sorted(measured, reverse=True):
        truth, est_bpf = simulate(width, depth, n_churn, churn_wakes,
                                  victim_threads, victim_wakes, bpf_hash)
        _, est_mix = simulate(width, depth, n_churn, churn_wakes,
                              victim_threads, victim_wakes, avalanched_hash)
        true_mean = statistics.mean(truth.values())
        sim_b = statistics.mean(est_bpf.values())
        sim_m = statistics.mean(est_mix.values())
        _, ker_sketch = measured[width]
        # Classical Count-Min bound: overestimate <= e*N/width with
        # probability 1 - e^-depth. Quoted as a mean-relative figure.
        bound = 2.71828 * total_mass / width
        print(f"{width:>6} {true_mean:>7.1f} {sim_b:>9.1f} {sim_m:>11.1f} "
              f"{ker_sketch:>8.1f} {sim_b/true_mean:>8.2f}x "
              f"{ker_sketch/true_mean:>8.2f}x {bound:>9.0f}")
        rows.append((width, true_mean, sim_b, sim_m, ker_sketch))

    print("\n--- CHECK 1: does the kernel match the model? ---")
    devs = [abs(k - s) / s for _, _, s, _, k in rows if s]
    print(f"  mean |kernel - sim| / sim = {statistics.mean(devs):>6.1%}")
    print("  Close agreement means the BPF code implements the same sketch")
    print("  the model does, so the comparison is between algorithms rather")
    print("  than between one author's two implementations.")

    print("\n--- CHECK 2: is the hash costing accuracy? ---")
    for width, true_mean, sim_b, sim_m, _ in rows:
        excess_b = sim_b - true_mean
        excess_m = sim_m - true_mean
        if excess_b > 0.5 or excess_m > 0.5:
            ratio = (excess_b / excess_m) if excess_m > 0.01 else float("inf")
            print(f"  width {width:>5}: overestimate bpf={excess_b:>8.1f} "
                  f"mixed={excess_m:>8.1f}  bpf/mixed={ratio:>6.2f}x")
    print("  >1.0x means the current hash collides more than a mixed one,")
    print("  and the reported sketch error is partly a hash artifact.")

    print("\n--- CHECK 3: is the 'inflation' column measuring the sketch? ---")
    print("  Round 5 reported inflation as sketch_mean/exact_mean. Where the")
    print("  exact tracker itself degraded, that ratio moves for reasons that")
    print("  have nothing to do with the sketch. Against TRUE counts:")
    for width in sorted(measured, reverse=True):
        ex, sk = measured[width]
        true_ct = churn_wakes * 2
        print(f"  width {width:>5}: reported {sk/ex if ex else 0:>8.2f}x   "
              f"actual sketch error {sk/true_ct:>5.2f}x   "
              f"(exact was at {ex:>6.1f} vs true {true_ct})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

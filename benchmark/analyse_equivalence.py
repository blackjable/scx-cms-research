#!/usr/bin/env python3
"""
Analysis for PREREGISTRATION_equivalence.md. Implements exactly what
that document specifies and nothing else.

The point of writing this before looking at the data is that every
choice which could bend a result -- metric, pairing, margin, test,
what counts as an outlier -- is already fixed. Running it is then
mechanical.

Usage: analyse_equivalence.py <harness output file>
"""

import math
import re
import statistics
import sys

REP = re.compile(r"REP (\d+) (\S+) p50=(\d+) p99=(\d+)")

# Everything below is from the pre-registration. Do not edit to fit data.
MARGIN = 0.20                      # +/-20% equivalence margin
LO, HI = math.log(1 / 1.20), math.log(1.20)
ALPHA = 0.05                       # TOST alpha; 90% CI is the equivalent
TREATMENT = "sketch_8k_d2"
REFERENCE = "exact_32k"
MATCHED = "sketch_32k_d2"          # matched-memory control
BLUNT_THRESHOLD = 6000             # us; sketch p50 above this = lost discrimination
OUTLIER_FACTOR = 10                # x own median


def load(path):
    runs = {}
    for line in open(path):
        m = REP.search(line)
        if m:
            rep, name, p50, p99 = int(m.group(1)), m.group(2), int(m.group(3)), int(m.group(4))
            runs.setdefault(name, {})[rep] = (p50, p99)
    return runs


def paired_log_ratios(runs, treat, ref, idx):
    """Per-repetition log ratio, only for repetitions where both exist."""
    common = sorted(set(runs.get(treat, {})) & set(runs.get(ref, {})))
    return [math.log(runs[treat][r][idx] / runs[ref][r][idx])
            for r in common if runs[ref][r][idx] > 0]


def tost(logs):
    """90% CI on the mean log-ratio. Equivalent to TOST at alpha=0.05."""
    n = len(logs)
    if n < 3:
        return None
    mean = statistics.mean(logs)
    sd = statistics.stdev(logs)
    se = sd / math.sqrt(n)
    # t(0.95, n-1); table is adequate for the n this study uses.
    t90 = {9: 1.833, 14: 1.761, 19: 1.729, 24: 1.711, 29: 1.699,
           30: 1.697, 39: 1.685, 49: 1.677}
    crit = t90.get(n - 1, 1.70)
    return mean, mean - crit * se, mean + crit * se


def bootstrap_ci(logs, iters=20000, seed=7):
    import random
    rng = random.Random(seed)
    n = len(logs)
    means = []
    for _ in range(iters):
        means.append(statistics.mean(rng.choices(logs, k=n)))
    means.sort()
    return means[int(0.05 * iters)], means[int(0.95 * iters)]


def report(runs, treat, ref, label, idx, metric):
    logs = paired_log_ratios(runs, treat, ref, idx)
    if not logs:
        print(f"  {label}: no paired data")
        return None
    res = tost(logs)
    if not res:
        print(f"  {label}: too few pairs ({len(logs)})")
        return None
    mean, lo, hi = res
    blo, bhi = bootstrap_ci(logs)
    equiv_param = lo > LO and hi < HI
    equiv_boot = blo > LO and bhi < HI
    agree = equiv_param == equiv_boot
    print(f"  {label} ({metric}, n={len(logs)} pairs)")
    print(f"    median ratio      {math.exp(statistics.median(logs)):.3f}x")
    print(f"    mean log-ratio    {mean:+.4f}  -> {math.exp(mean):.3f}x")
    print(f"    90% CI (param)    [{math.exp(lo):.3f}, {math.exp(hi):.3f}]x"
          f"   inside margin: {equiv_param}")
    print(f"    90% CI (bootstrap)[{math.exp(blo):.3f}, {math.exp(bhi):.3f}]x"
          f"   inside margin: {equiv_boot}")
    if not agree:
        print("    *** parametric and bootstrap DISAGREE -- per the")
        print("        pre-registration, equivalence is NOT declared ***")
    verdict = equiv_param and equiv_boot
    print(f"    EQUIVALENT within {int(MARGIN*100)}%: {verdict}")
    return verdict


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    runs = load(sys.argv[1])
    if not runs:
        print("no REP lines found", file=sys.stderr)
        return 1

    print(f"Equivalence analysis -- margin +/-{int(MARGIN*100)}%, "
          f"TOST alpha={ALPHA} via 90% CI")
    print(f"conditions found: {', '.join(sorted(runs))}\n")

    print("PRIMARY (pre-registered, confirmatory)")
    primary = report(runs, TREATMENT, REFERENCE,
                     f"{TREATMENT} vs {REFERENCE}", 1, "p99")

    print("\nSECONDARY (reported, not confirmatory)")
    report(runs, TREATMENT, REFERENCE, f"{TREATMENT} vs {REFERENCE}", 0, "p50")
    report(runs, MATCHED, REFERENCE, f"{MATCHED} vs {REFERENCE}", 1, "p99")

    print("\nSKETCH STABILITY (pre-specified characterisation)")
    sk = runs.get(TREATMENT, {})
    blunt = [r for r, (p50, _) in sk.items() if p50 > BLUNT_THRESHOLD]
    n = len(sk)
    if n:
        rate = len(blunt) / n
        # Wilson 90% interval, adequate and distribution-free enough here.
        z = 1.645
        denom = 1 + z * z / n
        centre = (rate + z * z / (2 * n)) / denom
        half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denom
        print(f"  repetitions with p50 > {BLUNT_THRESHOLD}us: "
              f"{len(blunt)}/{n} = {rate:.1%}")
        print(f"  90% CI on that rate: "
              f"[{max(0, centre-half):.1%}, {min(1, centre+half):.1%}]")
        if blunt:
            print(f"  affected repetitions: {sorted(blunt)}")

    print("\nOUTLIERS (pre-specified check)")
    flagged = {}
    for name, per in runs.items():
        p99s = [v[1] for v in per.values()]
        med = statistics.median(p99s)
        for rep, (_, p99) in per.items():
            if med > 0 and p99 > OUTLIER_FACTOR * med:
                flagged.setdefault(rep, []).append(f"{name}={p99}us")
    if not flagged:
        print(f"  none above {OUTLIER_FACTOR}x own median")
    else:
        for rep in sorted(flagged):
            print(f"  rep {rep}: {', '.join(flagged[rep])}")
        multi = [r for r, v in flagged.items() if len(v) > 1]
        print(f"  repetitions with MULTIPLE conditions affected: "
              f"{sorted(multi) if multi else 'none'}")
        print("  (clustering across conditions implies an environmental")
        print("   disturbance rather than a scheduler property)")

    print("\n" + "=" * 60)
    print(f"PRE-REGISTERED VERDICT: "
          f"{'EQUIVALENCE DEMONSTRATED' if primary else 'NOT DEMONSTRATED'}")
    if not primary:
        print("Per the pre-registration, the memory claim is then stated as")
        print("'the sketch continues to function at a budget where exact")
        print("counting does not', without the equivalence figure.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

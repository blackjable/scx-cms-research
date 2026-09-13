#!/usr/bin/env python3
"""
Analysis for PREREGISTRATION_ordering.md. Implements exactly what that
document specifies and nothing else.

Takes the combined log of the two arms and splits it on the harness's
own order banner, so the arms are identified by what the harness printed
rather than by anything chosen here.

Usage: analyse_ordering.py <combined harness output>
"""

import math
import re
import statistics
import sys

REP = re.compile(r"^\s+(\S+)\s+wu_p50=\s*(\d+)us wu_p99=\s*(\d+)us", re.M)
FIXED_BANNER = "condition order FIXED"
RANDOM_BANNER = "condition order randomised"

CONDITION = "cms_exact_penalty"   # pre-registered primary
THRESHOLD = 14000                 # us; the figure the original claim used


def split_arms(text):
    """Split on the harness's own banner. Returns (fixed_text, random_text)."""
    marks = []
    for m in re.finditer(r"condition order (FIXED|randomised)", text):
        marks.append((m.start(), m.group(1)))
    arms = {}
    for i, (pos, kind) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(text)
        arms.setdefault(kind, "")
        arms[kind] += text[pos:end]
    return arms.get("FIXED", ""), arms.get("randomised", "")


def series(text, condition, idx=2):
    return [int(m.group(idx + 1)) for m in REP.finditer(text)
            if m.group(1) == condition]


def mwu(a, b):
    """Mann-Whitney U with tie-corrected ranks, normal approximation."""
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    vals = [v for v, _ in allv]
    r = [0.0] * len(vals)
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[k] = avg
        i = j + 1
    ra = sum(rank for rank, (_, g) in zip(r, allv) if g == 0)
    n1, n2 = len(a), len(b)
    u = ra - n1 * (n1 + 1) / 2
    mu = n1 * n2 / 2
    sd = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    if sd == 0:
        return u, 0.0, 1.0
    z = (u - mu) / sd
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return u, z, p


def cv(v):
    return statistics.stdev(v) / statistics.mean(v) if len(v) > 2 else float("nan")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    text = open(sys.argv[1]).read()
    ftext, rtext = split_arms(text)
    if not ftext or not rtext:
        print("could not find both arms in that file", file=sys.stderr)
        return 1

    print("Ordering bias -- controlled comparison")
    print(f"primary condition: {CONDITION}, metric p99\n")

    F, R = series(ftext, CONDITION), series(rtext, CONDITION)
    if len(F) < 3 or len(R) < 3:
        print(f"too few repetitions: fixed={len(F)} random={len(R)}",
              file=sys.stderr)
        return 1

    print(f"  fixed arm      n={len(F)}  {sorted(F)}")
    print(f"  randomised arm n={len(R)}  {sorted(R)}\n")

    rows = [("median", statistics.median), ("mean", statistics.mean),
            ("maximum", max), ("minimum", min)]
    print(f"  {'statistic':<12}{'fixed':>10}{'randomised':>12}{'ratio':>9}")
    for name, fn in rows:
        a, b = fn(F), fn(R)
        print(f"  {name:<12}{a:>10.0f}{b:>12.0f}{a/b:>8.2f}x")
    print(f"  {'CV':<12}{cv(F):>10.2f}{cv(R):>12.2f}")
    fa = sum(1 for v in F if v > THRESHOLD)
    rb = sum(1 for v in R if v > THRESHOLD)
    print(f"  {'>' + str(THRESHOLD) + 'us':<12}{str(fa)+'/'+str(len(F)):>10}"
          f"{str(rb)+'/'+str(len(R)):>12}")

    u, z, p = mwu(F, R)
    wins = sum(1 for x in F for y in R if x > y) / (len(F) * len(R))
    print(f"\n  Mann-Whitney U={u:.0f}  z={z:.2f}  two-sided p={p:.4f}")
    print(f"  P(fixed run > randomised run) = {wins:.2f}")

    print("\nPRE-REGISTERED PREDICTIONS")
    checks = [
        ("1. fixed arm has higher CV", cv(F) > cv(R)),
        ("2. fixed arm has more runs above threshold", fa > rb),
        ("3. medians within 15% of each other",
         abs(statistics.median(F) / statistics.median(R) - 1) <= 0.15),
        ("4. Mann-Whitney p < 0.05", p < 0.05),
    ]
    for label, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

    print("\nOTHER CONDITIONS (context, not the pre-registered test)")
    for c in ["cms_none", "cms_sketch_penalty", "flat_4ms"]:
        a, b = series(ftext, c), series(rtext, c)
        if len(a) > 2 and len(b) > 2:
            print(f"  {c:<20} fixed med {statistics.median(a):>7.0f} "
                  f"(CV {cv(a):.2f})   random med {statistics.median(b):>7.0f} "
                  f"(CV {cv(b):.2f})")

    print("\nSame comparison on p50, to check the 'tail not centre' framing:")
    F50, R50 = series(ftext, CONDITION, idx=1), series(rtext, CONDITION, idx=1)
    if len(F50) > 2 and len(R50) > 2:
        print(f"  p50 median  fixed {statistics.median(F50):.0f}  "
              f"randomised {statistics.median(R50):.0f}  "
              f"ratio {statistics.median(F50)/statistics.median(R50):.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())

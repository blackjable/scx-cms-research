#!/usr/bin/env python3
"""
Round 7: the throughput check the delivery plan asked for in Section 4.

Every scheduling-quality number in this project is a latency figure from
schbench. Section 3.3 specified hackbench and cyclictest alongside it,
precisely so that a scheduler winning on the targeted latency metric
could be checked for quietly losing on general throughput. Neither was
ever run across the tiers.

That gap matters more here than it would elsewhere, because this
project's mechanism works by *delaying* tasks. A penalty that improves a
latency-sensitive task's tail by pushing everything else back has an
obvious way to look good on the only metric being watched while making
the machine worse at getting work done. The one throughput check that
was run measured rate-limited churn, so it could detect a regression but
could not observe a loss of headroom.

  hackbench   process/thread pairs communicating over pipes; reports
              total time to complete a fixed volume of messages. Lower
              is better, and it is a throughput measure rather than a
              latency one, which is the point.

  cyclictest  wakeup latency of a periodic real-time thread, reported as
              max and 99th percentile. Included because it measures the
              timer-driven wakeup path that rt-app could not measure
              here (Section 4.2) -- on this VM its absolute numbers are
              floored by timer delivery, so it is read for RELATIVE
              differences between schedulers only.

Conditions cover the tiers that matter: stock EEVDF, mechanism=none
(tracking overhead with no action), the count-blind penalty, and the
count-proportional penalty. If the penalty tiers cost throughput, that
belongs beside the latency results rather than in a footnote.
"""

import argparse
import os
import re
import shutil
import statistics
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/tmp")

import round2_mixed_workload as r2  # noqa: E402

HB_TIME = re.compile(r"Time:\s*([\d.]+)")
CT_MAX = re.compile(r"Max Latencies:\s*([\d\s]+)")
CT_LINE = re.compile(r"Min:\s*(\d+).*?Avg:\s*(\d+).*?Max:\s*(\d+)")


def run_hackbench(groups, loops):
    hb = shutil.which("hackbench")
    if not hb:
        return None
    out = subprocess.run([hb, "-g", str(groups), "-l", str(loops)],
                         capture_output=True, text=True)
    m = HB_TIME.search(out.stdout)
    return float(m.group(1)) if m else None


def run_cyclictest(duration_s, threads):
    ct = shutil.which("cyclictest")
    if not ct:
        return None
    out = subprocess.run(
        [ct, "-t", str(threads), "-p", "80", "-i", "1000", "-D",
         f"{duration_s}", "-q", "-m"],
        capture_output=True, text=True)
    maxes = [int(m.group(3)) for m in CT_LINE.finditer(out.stdout)]
    avgs = [int(m.group(2)) for m in CT_LINE.finditer(out.stdout)]
    if not maxes:
        return None
    return {"max": max(maxes), "avg": statistics.mean(avgs)}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--groups", type=int, default=10)
    ap.add_argument("--loops", type=int, default=1000)
    ap.add_argument("--ct-duration", type=int, default=15)
    ap.add_argument("--ct-threads", type=int, default=4)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--penalty-ns", type=int, default=20287)
    ap.add_argument("--flat-ns", type=int, default=4_000_000)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    scx = r2._find("scx-target/debug/scx_cms")
    common = ["--identity-key", "pid", "--window-ms", "1000"]

    conds = [
        ("eevdf", None, []),
        ("cms_none", scx, ["--tracker", "exact", "--mechanism", "none"] + common),
        ("flat", scx, ["--tracker", "exact", "--mechanism", "flat",
                       "--flat-ns", str(args.flat_ns)] + common),
        ("exact_penalty", scx, ["--tracker", "exact", "--mechanism", "penalty",
                                "--penalty-ns", str(args.penalty_ns)] + common),
        ("sketch_penalty", scx, ["--tracker", "sketch", "--mechanism", "penalty",
                                 "--penalty-ns", str(args.penalty_ns)] + common),
    ]

    have_hb = shutil.which("hackbench") is not None
    have_ct = shutil.which("cyclictest") is not None
    print("Round 7: throughput and RT-wakeup checks across the tiers")
    print(f"hackbench: {'yes' if have_hb else 'MISSING'}   "
          f"cyclictest: {'yes' if have_ct else 'MISSING'}")
    if not have_hb and not have_ct:
        print("neither tool present; nothing to do", file=sys.stderr)
        return 1
    print(f"hackbench -g {args.groups} -l {args.loops}, n={args.repeat}\n")

    import random
    rng = random.Random(1)
    acc = {n: {"hb": [], "ct_max": [], "ct_avg": []} for n, _, _ in conds}
    for rep in range(args.repeat):
        order = list(conds)
        rng.shuffle(order)
        for name, binary, sched_args in order:
            try:
                with r2.SchedulerHandle(binary, sched_args):
                    if have_hb:
                        t = run_hackbench(args.groups, args.loops)
                        if t:
                            acc[name]["hb"].append(t)
                    if have_ct:
                        c = run_cyclictest(args.ct_duration, args.ct_threads)
                        if c:
                            acc[name]["ct_max"].append(c["max"])
                            acc[name]["ct_avg"].append(c["avg"])
            except Exception as e:  # noqa: BLE001
                print(f"  rep{rep} {name}: ERROR {e}")
        print(f"  ... repetition {rep + 1}/{args.repeat}", flush=True)

    base = None
    print("\n" + "=" * 72)
    print(f"{'condition':<18}{'hackbench s':>13}{'vs eevdf':>10}"
          f"{'ct avg us':>11}{'ct max us':>11}")
    print("=" * 72)
    for name, _, _ in conds:
        a = acc[name]
        hb = statistics.median(a["hb"]) if a["hb"] else float("nan")
        if name == "eevdf" and a["hb"]:
            base = hb
        rel = f"{hb / base:>9.2f}x" if base and a["hb"] else "        --"
        cta = statistics.median(a["ct_avg"]) if a["ct_avg"] else float("nan")
        ctm = statistics.median(a["ct_max"]) if a["ct_max"] else float("nan")
        print(f"{name:<18}{hb:>13.2f}{rel}{cta:>11.0f}{ctm:>11.0f}")

    print("\nHOW TO READ THIS:")
    print("  hackbench is a THROUGHPUT measure: lower is better, and a")
    print("  penalty tier above 1.0x vs eevdf is buying its latency wins")
    print("  with throughput. That belongs beside the latency results, not")
    print("  in a footnote.")
    print("  cyclictest absolute values are floored by this VM's timer")
    print("  delivery (~1.7ms, Section 4.2); read the columns for relative")
    print("  differences between schedulers only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

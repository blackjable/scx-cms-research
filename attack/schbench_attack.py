#!/usr/bin/env python3
"""
Does corrupting the tracked signal manipulate scheduling? -- with schbench.

This is the redo of latency_attack.py demanded by its own result: that
experiment could not detect an effect, but its victim was a Python sleep
loop, so interpreter overhead, timer granularity and GC sat in the
measurement alongside the scheduling latency. schbench exists to measure
wakeup-to-execution latency and reports percentiles directly, which is
why Section 3.3 of the delivery plan specifies it. Using it is the
difference between "we could not measure this" and an answer.

THE THREAT, CONCRETELY

  The penalty mechanism deprioritizes tasks that wake often. If an
  attacker can inflate the victim's *estimated* wakeup count, the
  scheduler penalizes the victim for wakeups it never made, and the
  victim's own latency should suffer. That is the manipulation. It only
  bites if the mechanism reads the corruptible count -- which is exactly
  what the control isolates.

  schbench's threads all share the comm "schbench", so under
  --identity-key comm the whole victim is one identity, and the attacker
  sets its own comm to collide with it. No probe or victim cooperation is
  needed; the victim identity is simply fnv1a("schbench").

THE CONTROL

  Attacker load is identical in all three conditions; only the counter
  the mechanism reads changes:

    sketch + penalty   victim's inflated estimate drives the penalty
    exact  + penalty   victim's true count drives the penalty, same load
    sketch + none      estimate inflated, but nothing acts on it

  Manipulation shows up as sketch+penalty having a worse victim p99 than
  the other two. If all three agree, the corrupted signal is not reaching
  the scheduling decision at this operating point.

  Conditions are interleaved across repetitions so slow drift hits them
  alike, and the comparison reported is between conditions at matched
  load, never a within-run before/after.
"""

import argparse
import glob
import json
import os
import pwd
import statistics
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collision_attack import (  # noqa: E402
    fnv1a_comm,
    find_colliding_comms,
    read_seeds,
    spawn,
)


def _find(rel: str) -> str:
    cands = []
    user = os.environ.get("SUDO_USER")
    if user:
        try:
            cands.append(os.path.join(pwd.getpwnam(user).pw_dir, rel))
        except KeyError:
            pass
    cands.append(os.path.expanduser(f"~/{rel}"))
    cands.extend(glob.glob(f"/home/*/{rel}"))
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit(f"not found: {rel} (looked in {cands})")


SCHED = _find("scx-target/debug/scx_cms")
SCHBENCH = _find("schbench/schbench")


def wait_state(want: str, timeout: float = 12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open("/sys/kernel/sched_ext/state") as f:
                if f.read().strip() == want:
                    return True
        except OSError:
            pass
        time.sleep(0.4)
    return False


def start_scheduler(tracker: str, mechanism: str, args) -> subprocess.Popen:
    subprocess.run(["pkill", "-9", "scx_cms"], capture_output=True)
    if not wait_state("disabled"):
        raise RuntimeError("previous scheduler still attached")
    proc = subprocess.Popen(
        [SCHED, "--compare", "--tracker", tracker, "--mechanism", mechanism,
         "--identity-key", "comm", "--penalty-ns", str(args.penalty_ns),
         "--adjust-max-ns", str(args.adjust_max_ns),
         "--window-ms", str(args.window_ms), "--stats", "5"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    if not wait_state("enabled"):
        proc.kill()
        raise RuntimeError(f"scheduler failed to attach ({tracker}/{mechanism})")
    return proc


def run_schbench(args) -> dict:
    out = f"/tmp/sb_{os.getpid()}_{time.time()}.json"
    subprocess.run(
        [SCHBENCH, "-m", str(args.message_threads), "-t", str(args.worker_threads),
         "-R", str(args.rps), "-w", str(args.warmup), "-r", str(args.runtime),
         "-j", out],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
    )
    with open(out) as f:
        data = json.load(f)
    os.unlink(out)
    return data["int"]


def condition(tracker: str, mechanism: str, args) -> dict:
    proc = start_scheduler(tracker, mechanism, args)
    time.sleep(1.0)

    # Attackers collide with the victim's identity: comm "schbench".
    victim_id = fnv1a_comm(b"schbench")
    seeds = read_seeds()
    colliding = find_colliding_comms(victim_id, seeds, args.width, args.depth,
                                     args.attackers)
    names = [n for n, _ in colliding]
    attackers = [spawn(n, args.attacker_rate, args.warmup + args.runtime + 5)
                 for n in names]
    time.sleep(0.5)

    result = run_schbench(args)

    for pid in attackers:
        try:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
    proc.send_signal(2)
    proc.wait(timeout=10)

    return {
        "tracker": tracker,
        "mechanism": mechanism,
        # request latency is the reported metric: it has ~1000 samples and is
        # stable, whereas wakeup-latency percentiles in -R mode are computed
        # from ~17 samples and their tail is dominated by startup outliers
        # (p99 pins to a ~900ms histogram-ceiling artifact regardless of
        # condition). wakeup p50 is kept only as a sanity value.
        "request_p50": result["request_latency_pct50.0"],
        "request_p99": result["request_latency_pct99.0"],
        "request_p999": result["request_latency_pct99.9"],
        "wakeup_p50": result["wakeup_latency_pct50.0"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--attackers", type=int, default=16)
    ap.add_argument("--attacker-rate", type=float, default=20.0)
    ap.add_argument("--message-threads", type=int, default=2)
    ap.add_argument("--worker-threads", type=int, default=8)
    ap.add_argument("--rps", type=int, default=100)
    ap.add_argument("--warmup", type=int, default=3)
    ap.add_argument("--runtime", type=int, default=12)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--penalty-ns", type=int, default=20000)
    ap.add_argument("--adjust-max-ns", type=int, default=200_000_000)
    ap.add_argument("--window-ms", type=int, default=2000)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    conditions = [("sketch", "penalty"), ("exact", "penalty"), ("sketch", "none")]
    runs = []
    for rep in range(args.repeat):
        print(f"\n########## repetition {rep + 1}/{args.repeat} ##########")
        for t, m in conditions:
            r = condition(t, m, args)
            runs.append(r)
            print(f"  {t:>6}/{m:<8}  request "
                  f"p50={r['request_p50']:>6}us  p99={r['request_p99']:>7}us  "
                  f"p99.9={r['request_p999']:>7}us")

    print("\n" + "=" * 72)
    print(f"Victim (schbench) wakeup latency under identical attack load, "
          f"{args.repeat} runs")
    print("=" * 72)
    summary = {}
    for t, m in conditions:
        rs = [r for r in runs if r["tracker"] == t and r["mechanism"] == m]
        p99s = sorted(r["request_p99"] for r in rs)
        summary[(t, m)] = p99s
        med = statistics.median(p99s)
        print(f"  {t:>6}/{m:<8}  request p99 median {med:>7.0f}us   "
              f"range {p99s[0]:>6}-{p99s[-1]:>6}us")

    sk = summary[("sketch", "penalty")]
    ex = summary[("exact", "penalty")]
    msk, mex = statistics.median(sk), statistics.median(ex)
    print(f"\n  corrupted vs truthful count driving the penalty (victim request p99):")
    print(f"    sketch/penalty {msk:.0f}us   exact/penalty {mex:.0f}us   "
          f"({(msk - mex) / mex * 100:+.1f}%)")

    # Whether that difference means anything, stated without overclaiming.
    # A single run per condition cannot separate signal from noise -- two
    # different points always have non-overlapping one-point ranges, which
    # is not evidence of anything. Require repetition, and compare the
    # medians against the within-condition spread rather than eyeballing.
    if args.repeat < 3:
        print(f"    (only {args.repeat} run(s) per condition; too few to claim "
              f"an effect either way -- rerun with --repeat 5+)")
    else:
        overlap = max(sk[0], ex[0]) <= min(sk[-1], ex[-1])
        sep = abs(msk - mex)
        spread = (max(sk) - min(sk) + max(ex) - min(ex)) / 2
        if overlap or sep < spread:
            print(f"    ranges overlap or the gap ({sep:.0f}us) is within the "
                  f"noise ({spread:.0f}us): no effect demonstrated")
        else:
            print(f"    ranges disjoint and gap ({sep:.0f}us) exceeds noise "
                  f"({spread:.0f}us): effect is real at this operating point")
    return 0


if __name__ == "__main__":
    sys.exit(main())

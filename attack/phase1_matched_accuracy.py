#!/usr/bin/env python3
"""
Accuracy measurement matched to Phase 1's methodology, not just its
parameters.

Item 26's earlier real-kernel figure (+11.0% under hackbench) was
explicitly flagged as NOT comparable to Phase 1's +31.9%: different churn
level, and a different statistic (aggregate ratio over all queried
identities vs. the error on one tracked latency-sensitive task). This
replicates Phase 1's actual setup (paper Section 3.1): ~5,000 short-lived
churn identities per window, each generating a handful of wakeups, plus
one persistent latency-sensitive identity whose error is the reported
number -- via the probe, the same single-target statistic Phase 1 used.

Real OS processes stand in for Phase 1's synthetic events: each churn
"identity" is a short-lived process with a distinct comm, firing 1-20
wakeups (matching Phase 1's per-identity range) before exiting.
"""

import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collision_attack import (  # noqa: E402
    read_identity_key,
    read_probe,
    set_comm,
    set_probe_pid,
)


def _find_scheduler() -> str:
    import glob
    import pwd
    cands = []
    user = os.environ.get("SUDO_USER")
    if user:
        try:
            cands.append(os.path.join(pwd.getpwnam(user).pw_dir,
                                      "scx-target/debug/scx_cms"))
        except KeyError:
            pass
    cands.append(os.path.expanduser("~/scx-target/debug/scx_cms"))
    cands.extend(glob.glob("/home/*/scx-target/debug/scx_cms"))
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit(f"scx_cms not found; looked in: {cands}")


def churn_worker(n_wakeups: int) -> None:
    set_comm(f"churn{os.getpid() % 100000}")
    for _ in range(n_wakeups):
        time.sleep(0.001)


def victim_worker(rate: float, duration: float) -> None:
    set_comm("latency_sensitive")
    end = time.time() + duration
    while time.time() < end:
        time.sleep(1.0 / rate)


def spawn_churn(n_wakeups: int) -> int:
    pid = os.fork()
    if pid == 0:
        churn_worker(n_wakeups)
        os._exit(0)
    return pid


def spawn_victim(rate: float, duration: float) -> int:
    pid = os.fork()
    if pid == 0:
        victim_worker(rate, duration)
        os._exit(0)
    return pid


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--churn", type=int, default=5000,
                    help="churn identities per window, matching Phase 1's "
                         "~5,000 (paper Section 4.1)")
    ap.add_argument("--windows", type=int, default=3)
    ap.add_argument("--window-ms", type=int, default=3000,
                    help="wider than the attack tests' 2000ms, since 5000 "
                         "real fork()s per window takes real wall time")
    ap.add_argument("--victim-rate", type=float, default=10.0)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    assert read_identity_key() == "comm", \
        "run scx_cms with --identity-key comm --tracker sketch --compare first"

    total_duration = args.window_ms / 1000 * (args.windows + 1) + 5
    victim = spawn_victim(args.victim_rate, total_duration)
    time.sleep(0.5)
    set_probe_pid(victim)

    print(f"Phase-1-matched accuracy: {args.churn} churn identities/window, "
          f"{args.windows} windows, victim @ {args.victim_rate}/s\n")

    errors = []
    for w in range(args.windows):
        window_start = time.time()
        churn_pids = []
        # Spread churn arrivals across the window rather than firing all
        # at once, closer to Phase 1's model of churn arriving over time
        # rather than in one instantaneous burst.
        window_s = args.window_ms / 1000
        for i in range(args.churn):
            churn_pids.append(spawn_churn(random.randint(1, 20)))
            if i % 200 == 0:
                time.sleep(window_s / (args.churn / 200) * 0.3)

        # Let stragglers finish, then read the probe at window end.
        remaining = window_start + window_s - time.time()
        if remaining > 0:
            time.sleep(remaining)

        p = read_probe()
        exact, sketch = int(p["exact"]), int(p["sketch"])
        over = (sketch - exact) / exact * 100 if exact else 0.0
        errors.append(over)
        print(f"  window {w}: exact={exact} sketch={sketch} "
              f"overestimate={over:+.1f}%")

        for pid in churn_pids:
            try:
                os.waitpid(pid, 0)
            except ChildProcessError:
                pass

    try:
        os.kill(victim, 9)
        os.waitpid(victim, 0)
    except (ProcessLookupError, ChildProcessError):
        pass

    settled = errors[1:] if len(errors) > 1 else errors
    mean_error = sum(settled) / len(settled)
    print(f"\nMean overestimate (excluding window 0's partial-window edge "
          f"case, matching Phase 1's own exclusion): {mean_error:+.1f}%")
    print("Phase 1's Python result at matched parameters: +31.9%")
    return 0


if __name__ == "__main__":
    sys.exit(main())

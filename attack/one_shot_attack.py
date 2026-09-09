#!/usr/bin/env python3
"""
Phase 1's ORIGINAL multi-window decay test, replicated on a real kernel.

seed_rotation_attack.py tests the "replay stale keys" variant: attacker
keeps firing precomputed identities across many windows. Phase 1's paper
(4.1.4) also has a distinct, simpler variant this repo hadn't yet
replicated: attacker fires ONCE, in a single window, then goes silent.
Phase 1 found: window 0 (attack) +400%, window 1 (stale carry-over via
the "previous" buffer) +200%, window 2+ exactly 0.0% -- the rotating
dual-buffer scheme carries poisoned data forward for exactly one extra
window, no more.

This checks whether that precise "one window, no more" carry-over model
holds on the real sketch, with --seed-rotation OFF (Phase 1's original
test had no seed rotation at all, so this is the fairer comparison) and
ON (does reseeding shorten or otherwise change the one-window decay).
"""

import argparse
import glob
import json
import os
import pwd
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from collision_attack import (  # noqa: E402
    find_colliding_comms,
    read_bss,
    read_identity_key,
    read_probe,
    read_seeds,
    set_probe_pid,
    spawn,
)


def _find_scheduler() -> str:
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


SCHED = _find_scheduler()


def epoch() -> int:
    return int(read_bss().get("cms_epoch", 0))


def wait_for_epoch(target: int, timeout: float = 6.0) -> int:
    end = time.time() + timeout
    e = epoch()
    while e < target and time.time() < end:
        time.sleep(0.05)
        e = epoch()
    return e


def wait_state(want: str, timeout: float = 12.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with open("/sys/kernel/sched_ext/state") as f:
                if f.read().strip() == want:
                    return True
        except OSError:
            pass
        time.sleep(0.3)
    return False


def run(seed_rotation: bool, window_ms: int, attackers: int, rate: float,
       width: int, depth: int, windows: int) -> list:
    subprocess.run(["pkill", "-9", "scx_cms"], capture_output=True)
    if not wait_state("disabled"):
        raise RuntimeError("previous scheduler still attached")
    args = [SCHED, "--compare", "--tracker", "sketch", "--identity-key", "comm",
            "--window-ms", str(window_ms), "--stats", "2"]
    if seed_rotation:
        args.append("--seed-rotation")
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not wait_state("enabled"):
        proc.kill()
        raise RuntimeError("scheduler failed to attach")
    time.sleep(1.0)
    assert read_identity_key() == "comm"

    victim = spawn("victim", 20, window_ms / 1000 * (windows + 1) + 5)
    time.sleep(0.5)
    set_probe_pid(victim)

    ep_start = epoch()
    seeds = read_seeds()
    victim_id = int(read_probe()["identity"])
    names = [n for n, _ in find_colliding_comms(victim_id, seeds, width, depth,
                                                 attackers)]
    ep_after_search = epoch()
    if ep_after_search != ep_start:
        print(f"  [rotated during search: {ep_start}->{ep_after_search}]",
              file=sys.stderr)
        ep_start = ep_after_search

    # ONE-SHOT: fire for a bit less than one window, then stop entirely --
    # unlike seed_rotation_attack.py, nothing replays after this.
    fire_duration = window_ms / 1000 * 0.7
    attackers_pids = [spawn(n, rate, fire_duration) for n in names]

    samples = []
    for w in range(windows):
        wait_for_epoch(ep_start + w + 1)
        p = read_probe()
        exact, sketch = int(p["exact"]), int(p["sketch"])
        over = (sketch - exact) / exact * 100 if exact else 0.0
        samples.append((over, epoch()))

    for pid in attackers_pids + [victim]:
        try:
            os.kill(pid, 9)
            os.waitpid(pid, 0)
        except (ProcessLookupError, ChildProcessError):
            pass
    proc.send_signal(2)
    proc.wait(timeout=10)
    return samples


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=int, default=256)
    ap.add_argument("--depth", type=int, default=4)
    ap.add_argument("--attackers", type=int, default=64)
    ap.add_argument("--attacker-rate", type=float, default=200.0)
    ap.add_argument("--window-ms", type=int, default=2000)
    ap.add_argument("--windows", type=int, default=4)
    args = ap.parse_args()

    if os.geteuid() != 0:
        print("needs root", file=sys.stderr)
        return 1

    print(f"One-shot attack (fire once, go silent), {args.attackers} "
          f"attackers @ {args.attacker_rate}/s\n")

    print("seed-rotation OFF:")
    off = run(False, args.window_ms, args.attackers, args.attacker_rate,
              args.width, args.depth, args.windows)
    for i, (v, ep) in enumerate(off):
        print(f"  window {i} (epoch {ep}): {v:+.1f}%")

    print("\nseed-rotation ON:")
    on = run(True, args.window_ms, args.attackers, args.attacker_rate,
             args.width, args.depth, args.windows)
    for i, (v, ep) in enumerate(on):
        print(f"  window {i} (epoch {ep}): {v:+.1f}%")

    print("\n" + "=" * 56)
    print(f"{'window':<8}{'rotation OFF':>15}{'rotation ON':>15}")
    for i in range(args.windows):
        print(f"{i:<8}{off[i][0]:>14.1f}%{on[i][0]:>14.1f}%")
    print("\nPhase 1 (Python, no rotation) found: window0 +400%, "
          "window1 +200%, window2+ 0.0%")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/bin/bash
# Each condition gets a freshly started scheduler, and we verify the old
# one is gone before starting the next -- an earlier run was contaminated
# by a stale scheduler still holding sched_ext.
#
# SCX_CMS is resolved once, absolutely, rather than as ~/... -- under sudo
# ~ expands to /root, not the build's actual home, and this exact mistake
# has recurred three times across different scripts in this repo before
# being fixed here instead of patched around again.
SCX_CMS=$(ls "$HOME"/scx-target/debug/scx_cms 2>/dev/null || ls /home/*/scx-target/debug/scx_cms 2>/dev/null | head -1)
[ -x "$SCX_CMS" ] || { echo "scx_cms binary not found" >&2; exit 1; }

run_case() {
  local label="$1"; shift
  local ikey="$1"; shift

  sudo pkill -9 scx_cms 2>/dev/null
  for _ in $(seq 20); do
    [ "$(cat /sys/kernel/sched_ext/state)" = "disabled" ] && break
    sleep 0.5
  done
  if [ "$(cat /sys/kernel/sched_ext/state)" != "disabled" ]; then
    echo "REFUSING: previous scheduler still attached"; return 1
  fi

  sudo "$SCX_CMS" --compare --tracker sketch \
       --identity-key "$ikey" --window-ms 2000 --stats 60 > /tmp/s.log 2>&1 &
  sleep 4

  if [ "$(cat /sys/kernel/sched_ext/state)" != "enabled" ]; then
    echo "REFUSING: scheduler failed to attach"; cat /tmp/s.log; return 1
  fi

  echo "################ $label ################"
  sudo python3 /tmp/collision_attack.py "$@" 2>&1 | grep -v "^$"
  echo
}

run_case "comm / white-box (seeds known)"      comm --mode white-box --attackers 64
run_case "comm / blind, same volume"           comm --mode blind --attackers 64
run_case "comm / blind, heavy volume"          comm --mode blind --attackers 256 --attacker-rate 1000
run_case "pid / white-box attempt"             pid  --mode white-box --attackers 64
run_case "pid / blind, heavy volume"           pid  --mode blind --attackers 256 --attacker-rate 1000

sudo pkill -INT scx_cms 2>/dev/null; sleep 1

# --- TGID additions (was pid/comm only) ---
run_case "tgid / white-box attempt"  tgid --mode white-box --attackers 64
run_case "tgid / blind, heavy volume" tgid --mode blind --attackers 256 --attacker-rate 1000

sudo pkill -INT scx_cms 2>/dev/null; sleep 1

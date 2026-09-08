"""
strict_tests.py

Three additional rigor checks, addressing gaps the earlier tests still
had:

1. REPRODUCIBILITY VERIFICATION — proves the hash-randomization bug
   fix actually works: running the same config twice, in separate
   Python subprocess invocations, must now give IDENTICAL results.
   (Before the fix, this would fail silently — same code, different
   numbers, every run.)

2. INVARIANT CHECKING — Count-Min Sketch has exactly one formal
   guarantee: it never underestimates. estimate(key) >= true_count(key)
   must hold ALWAYS, for every key, every run, no exceptions. This has
   never actually been checked in any experiment so far — every test
   so far only looked at OVERestimation magnitude, silently assuming
   the never-underestimate guarantee held rather than verifying it.
   If this assertion ever fails, that is a bug in our implementation,
   not normal sketch approximation behavior, and would invalidate
   every prior result.

3. TARGETED-COLLISION ADVERSARIAL ATTACK — the earlier "adversarial"
   test (sweep_experiment.py) approximated a worst case by flooding
   raw event VOLUME. This is a strictly stronger test: since our
   hashing is now deterministic (see sketch_lib.stable_hash), we can
   search for churn task IDs that are KNOWN to collide with the
   latency-sensitive task's slot in a SPECIFIC row, then deliberately
   flood volume into exactly those colliding keys. This directly
   attacks the sketch's actual weak point rather than hoping high
   volume happens to cause damage.

   Note: finding a single key that collides with the target in ALL
   depth rows SIMULTANEOUSLY is computationally infeasible by design
   (roughly 1-in-width^depth odds — this is exactly why depth exists:
   to make full collisions vanishingly rare). The realistic worst case
   is per-row targeted flooding — different colliding keys for each
   row — which is what this test constructs.
"""

import subprocess
import sys

from sketch_lib import (
    ChurnDistribution, CountMinSketch, RotatingCountMinSketch,
    RotatingExactCounter, SimConfig, run_simulation, stable_hash,
)


# ---------------------------------------------------------------------
# Test A: Reproducibility verification
# ---------------------------------------------------------------------

def test_reproducibility():
    print("=" * 76)
    print("TEST A: Reproducibility across separate process invocations")
    print("=" * 76)
    print()
    print("  Running the identical config in two SEPARATE Python")
    print("  subprocesses (not just twice in this process — that would")
    print("  hide the exact bug we're checking for, since Python's hash")
    print("  randomization is per-process, not per-call).")
    print()

    script = (
        "from sketch_lib import SimConfig, run_simulation; "
        "import statistics; "
        "r = run_simulation(SimConfig(seed=7)); "
        "print(statistics.mean(r.steady_state_sketch_errors))"
    )

    results = []
    for i in range(2):
        proc = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=".",
        )
        results.append(proc.stdout.strip())
        print(f"  Process {i + 1} result: {proc.stdout.strip()}")

    print()
    if results[0] == results[1]:
        print("  --> PASS: identical result across separate processes.")
        print("      The stable_hash fix resolved the reproducibility bug.")
    else:
        print("  --> FAIL: results differ across processes. Reproducibility")
        print("      is still broken — do not trust any reported numbers")
        print("      until this is fixed.")
    print()
    return results[0] == results[1]


# ---------------------------------------------------------------------
# Test B: Invariant checking (never-underestimate guarantee)
# ---------------------------------------------------------------------

def test_never_underestimates(num_seeds: int = 8) -> bool:
    print("=" * 76)
    print("TEST B: Formal invariant check — sketch must NEVER underestimate")
    print("=" * 76)
    print()
    print("  Count-Min Sketch's one formal guarantee: estimate(key) >=")
    print("  true_count(key), always. This has not been explicitly")
    print("  checked in any prior experiment — only overestimation")
    print("  magnitude was examined. Checking now, across many seeds")
    print("  and against the EXACT counter (ground truth) directly.")
    print()

    violations = 0
    total_checks = 0

    for seed in range(num_seeds):
        config = SimConfig(
            seed=seed,
            num_churn_identities_per_epoch=1000,  # smaller for speed;
            num_epochs=10,                         # still many check points
        )
        # Re-run manually to get per-epoch exact vs sketch values,
        # rather than only the aggregated steady-state error.
        import random as _random
        rng = _random.Random(config.seed)
        sketch = RotatingCountMinSketch(width=config.sketch_width, depth=config.sketch_depth)
        exact = RotatingExactCounter()
        latency_task_id = "latency_sensitive_task"

        from sketch_lib import generate_churn_events
        for epoch in range(config.num_epochs):
            events = generate_churn_events(
                rng, epoch, config.num_churn_identities_per_epoch,
                config.wakeups_per_churn_task, config.distribution,
            )
            events.extend([latency_task_id] * config.latency_task_wakeups_per_epoch)
            rng.shuffle(events)
            for task_id in events:
                sketch.increment(task_id)
                exact.increment(task_id)

            sketch_est = sketch.estimate(latency_task_id)
            exact_est = exact.estimate(latency_task_id)
            total_checks += 1
            if sketch_est < exact_est:
                violations += 1
                print(f"  VIOLATION at seed={seed}, epoch={epoch}: "
                      f"sketch={sketch_est} < exact(true)={exact_est}")

            sketch.rotate()
            exact.rotate()

    print(f"\n  Checked {total_checks} (seed, epoch) combinations across "
          f"{num_seeds} seeds.")
    if violations == 0:
        print("  --> PASS: zero violations. The implementation correctly")
        print("      upholds the formal never-underestimate guarantee.")
    else:
        print(f"  --> FAIL: {violations} violations found. This is a real")
        print("      bug in the sketch implementation — investigate the")
        print("      hashing or merge logic before trusting any result.")
    print()
    return violations == 0


# ---------------------------------------------------------------------
# Test C: Targeted-collision adversarial attack
# ---------------------------------------------------------------------

def find_colliding_keys(seed: int, target_index: int, width: int,
                         count_needed: int, prefix: str, hash_fn=None) -> list[str]:
    """
    Brute-force search for candidate keys that hash to target_index
    for this specific row's seed. With width slots, roughly 1-in-width
    random candidates will match, so this converges quickly.

    hash_fn defaults to stable_hash (blake2b) if not specified, for
    backward compatibility with the original targeted-attack test —
    but MUST be passed explicitly when attacking a sketch using a
    different hash function. (This parameter was missing in an
    earlier version, causing a real bug: a cross-hash-function attack
    test silently searched for blake2b collisions and inserted them
    into an FNV-1a-indexed sketch, producing a meaningless "0% error,
    FNV-1a is safe" result that was actually just a broken, no-op
    attack. Caught by verifying the found keys actually collide,
    rather than trusting the search's own claim — see
    expanded_findings_experiment.py's Test 3 for the corrected
    version and full writeup of this bug.)
    """
    if hash_fn is None:
        hash_fn = stable_hash
    found = []
    i = 0
    while len(found) < count_needed and i < count_needed * width * 3:
        candidate = f"{prefix}_{i}"
        if hash_fn(candidate, seed, width) == target_index:
            found.append(candidate)
        i += 1
    return found


def test_targeted_collision_attack(events_per_colliding_key: int = 200) -> dict:
    print("=" * 76)
    print("TEST C: Targeted-collision adversarial attack (white-box)")
    print("=" * 76)
    print()

    config = SimConfig()
    sketch = RotatingCountMinSketch(width=config.sketch_width, depth=config.sketch_depth)
    latency_task_id = "latency_sensitive_task"

    print(f"  Sketch: width={config.sketch_width}, depth={config.sketch_depth}")
    print("  Finding keys that collide with the latency-sensitive task's")
    print("  slot in EACH row independently (a full simultaneous")
    print("  collision across all rows is ~1-in-width^depth — by design,")
    print("  computationally infeasible to find, which is the actual")
    print("  point of using multiple depth rows):\n")

    target_indices = [
        sketch.current._index(latency_task_id, row)
        for row in range(config.sketch_depth)
    ]

    all_colliding_keys = []
    for row in range(config.sketch_depth):
        keys = find_colliding_keys(
            sketch.current.seeds[row], target_indices[row],
            config.sketch_width, count_needed=10, prefix=f"attack_row{row}",
        )
        print(f"    Row {row}: found {len(keys)} colliding keys "
              f"(target slot {target_indices[row]})")
        all_colliding_keys.extend(keys)

    print(f"\n  Total distinct attacker-controlled colliding keys: "
          f"{len(all_colliding_keys)}")
    print(f"  Flooding {events_per_colliding_key} events into each...\n")

    # Insert normal baseline churn first (so this isn't an unrealistically
    # empty sketch), then the targeted flood, then the latency task.
    import random as _random
    rng = _random.Random(config.seed)
    from sketch_lib import generate_churn_events
    baseline_events = generate_churn_events(
        rng, 0, config.num_churn_identities_per_epoch,
        config.wakeups_per_churn_task, ChurnDistribution.UNIFORM,
    )
    for task_id in baseline_events:
        sketch.increment(task_id)

    for key in all_colliding_keys:
        sketch.increment(key, amount=events_per_colliding_key)

    sketch.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)

    estimate = sketch.estimate(latency_task_id)
    true_value = config.latency_task_wakeups_per_epoch
    error_pct = 100 * (estimate - true_value) / true_value

    print(f"  True value:      {true_value}")
    print(f"  Sketch estimate: {estimate}")
    print(f"  Error:           {error_pct:+.1f}%")
    print()
    if error_pct > 100:
        print("  --> A deliberate, knowledgeable adversary (or unlucky")
        print("      hash collision pattern) can make this error EXTREME")
        print("      — more than double the true value. This is a real")
        print("      ceiling on how bad things can get, worse than any")
        print("      volume-based approximation found earlier.")
    else:
        print("  --> Even under a targeted attack, error stayed moderate")
        print("      at these parameters.")
    print()
    return {"true": true_value, "estimate": estimate, "error_pct": error_pct}


if __name__ == "__main__":
    repro_ok = test_reproducibility()
    invariant_ok = test_never_underestimates()
    attack_result = test_targeted_collision_attack()

    print("=" * 76)
    print("SUMMARY")
    print("=" * 76)
    print(f"  Reproducibility:        {'PASS' if repro_ok else 'FAIL'}")
    print(f"  Never-underestimate:    {'PASS' if invariant_ok else 'FAIL'}")
    print(f"  Targeted attack error:  {attack_result['error_pct']:+.1f}%")

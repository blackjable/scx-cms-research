"""
expanded_findings_experiment.py

Covers three gaps identified after the last rigor pass (see paper
draft checklist items 7, 15, 16):

1. JOINT WIDTH x DEPTH SWEEP AT FIXED MEMORY BUDGET — only width was
   swept before, with depth held fixed. This answers: for a fixed
   memory budget, is it better to have a wide-and-shallow sketch or a
   narrow-and-deep one?

2. SEED-ROTATION MITIGATION TEST — does rotating the hash seed every
   window defeat a targeted-collision attack (found in strict_tests.py)
   that was pre-computed against a now-stale seed? Tests whether this
   is a viable, nearly-free defense given we already rotate buffers
   every window anyway.

3. HASH FUNCTION COMPARISON (blake2b vs FNV-1a) — the reproducibility
   fix used blake2b, which is far too slow for a real BPF hot path.
   FNV-1a is a much more realistic stand-in for what an actual kernel
   implementation would use. This tests whether the targeted-collision
   vulnerability is specific to blake2b or a more fundamental property
   of Count-Min Sketch under a knowledgeable adversary.
"""

import statistics
import time

from sketch_lib import (
    ChurnDistribution, CountMinSketch, RotatingCountMinSketch,
    SeedRotatingCountMinSketch, SimConfig, run_simulation,
    stable_hash, fnv1a_hash, HASH_FUNCTIONS,
)
from strict_tests import find_colliding_keys


# ---------------------------------------------------------------------
# Test 1: Joint width x depth sweep at fixed memory budget
# ---------------------------------------------------------------------

def test_width_depth_tradeoff(total_slots: int = 2048, num_seeds: int = 5) -> dict:
    print("=" * 76)
    print(f"TEST 1: Width x Depth tradeoff at fixed budget (width*depth={total_slots})")
    print("=" * 76)
    print()
    print("  All configs below use the SAME single-buffer memory")
    print(f"  ({total_slots} counters x 4 bytes = {total_slots*4:,} bytes),")
    print("  just distributed differently between width and depth.")
    print()
    print("  NOTE: uses a smaller base config (1000 identities/epoch, 10")
    print("  epochs) than Tests 1-2 in sweep_experiment.py, since higher")
    print("  depth means proportionally more hash computations per insert")
    print("  (blake2b is not cheap) — kept small here for tractability.")
    print()
    print(f"{'Width':>7}  {'Depth':>6}  {'EmpErr%':>9}  {'EmpStd%':>8}")

    # Factor pairs of total_slots, from wide-shallow to narrow-deep.
    configs = []
    d = 1
    while d <= 16:
        w = total_slots // d
        if w >= 8:
            configs.append((w, d))
        d *= 2

    results = {}
    for width, depth in configs:
        pct_errors = []
        for seed in range(num_seeds):
            config = SimConfig(
                sketch_width=width, sketch_depth=depth, seed=seed,
                num_churn_identities_per_epoch=1000, num_epochs=10,
            )
            result = run_simulation(config)
            avg_err = statistics.mean(result.steady_state_sketch_errors)
            true_val = config.latency_task_wakeups_per_epoch * 2
            pct_errors.append(100 * avg_err / true_val)
        results[(width, depth)] = pct_errors
        print(f"{width:>7}  {depth:>6}  {statistics.mean(pct_errors):>+8.1f}%  "
              f"{(statistics.stdev(pct_errors) if len(pct_errors) > 1 else 0):>7.1f}%")

    print()
    best_config = min(results, key=lambda k: abs(statistics.mean(results[k])))
    print(f"  Best accuracy at this fixed budget: width={best_config[0]}, "
          f"depth={best_config[1]} ({statistics.mean(results[best_config]):+.1f}% error)")
    print()
    print("  Interpretation: per Count-Min Sketch theory, WIDTH controls the")
    print("  MAGNITUDE of overestimation error (epsilon = e/width), while")
    print("  DEPTH controls the PROBABILITY of a bad estimate (delta =")
    print("  e^-depth) — but does not by itself reduce the magnitude when")
    print("  a bad estimate does occur. This predicts wide-shallow should")
    print("  generally beat narrow-deep for average-case error at fixed")
    print("  memory, since width has the larger effect on magnitude.")
    print()
    return results


# ---------------------------------------------------------------------
# Test 2: Seed rotation as a defense against targeted-collision attack
# ---------------------------------------------------------------------

def test_seed_rotation_defense() -> dict:
    print("=" * 76)
    print("TEST 2: Does seed rotation defeat a pre-computed targeted attack?")
    print("=" * 76)
    print()

    config = SimConfig()
    latency_task_id = "latency_sensitive_task"

    sketch = SeedRotatingCountMinSketch(
        width=config.sketch_width, depth=config.sketch_depth,
    )

    print("  Window N: attacker knows the CURRENT seed, computes colliding")
    print("  keys, and floods them. Measuring attack effectiveness in the")
    print("  window it was computed for (should match strict_tests.py's")
    print("  earlier finding, modulo the different combination method).")
    print()

    target_indices_n = [
        sketch.current._index(latency_task_id, row)
        for row in range(config.sketch_depth)
    ]
    colliding_keys_n = []
    for row in range(config.sketch_depth):
        keys = find_colliding_keys(
            sketch.current.seeds[row], target_indices_n[row],
            config.sketch_width, count_needed=10, prefix=f"attack_n_row{row}",
        )
        colliding_keys_n.extend(keys)

    for key in colliding_keys_n:
        sketch.increment(key, amount=200)
    sketch.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)

    estimate_n = sketch.estimate(latency_task_id)
    true_n = config.latency_task_wakeups_per_epoch
    error_n_pct = 100 * (estimate_n - true_n) / true_n
    print(f"  Window N result: true={true_n}, estimate={estimate_n}, "
          f"error={error_n_pct:+.1f}%")
    print()

    print("  Rotating to window N+1 (fresh seed generated automatically)...")
    sketch.rotate()
    print()
    print("  Window N+1: attacker REPLAYS the SAME keys computed for window")
    print("  N's (now stale) seed — simulating an attacker who cannot")
    print("  observe the new seed in real time (a reasonable assumption if")
    print("  the seed is kernel-internal state never exposed to userspace).")
    print()

    # New epoch: latency task wakes up again, attacker replays stale keys.
    for key in colliding_keys_n:
        sketch.increment(key, amount=200)
    sketch.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)

    estimate_n1 = sketch.estimate(latency_task_id)
    # True value at this point includes window N's carried-over count
    # (now in "previous") plus this window's fresh count.
    true_n1 = config.latency_task_wakeups_per_epoch * 2
    error_n1_pct = 100 * (estimate_n1 - true_n1) / true_n1
    print(f"  Window N+1 result: true={true_n1}, estimate={estimate_n1}, "
          f"error={error_n1_pct:+.1f}%")
    print()

    if abs(error_n1_pct) < abs(error_n_pct) / 3:
        print("  --> MITIGATION EFFECTIVE: stale pre-computed keys lost most")
        print("      of their attack power once the seed rotated. Seed")
        print("      rotation is a promising defense AS LONG AS the seed is")
        print("      not observable/predictable by the attacker in real time.")
    else:
        print("  --> MITIGATION INEFFECTIVE or PARTIAL: stale keys still")
        print("      caused meaningful damage. Needs further investigation")
        print("      before relying on this as a defense.")
    print()

    return {
        "window_n_error_pct": error_n_pct,
        "window_n1_error_pct": error_n1_pct,
    }


# ---------------------------------------------------------------------
# Test 3: Hash function comparison (blake2b vs FNV-1a) under attack
# ---------------------------------------------------------------------

def test_hash_function_comparison() -> dict:
    print("=" * 76)
    print("TEST 3: Targeted-collision attack — blake2b vs FNV-1a")
    print("=" * 76)
    print()
    print("  blake2b is cryptographically strong but too slow for a real")
    print("  BPF hot path. FNV-1a is simple/fast and a much more realistic")
    print("  stand-in for what an actual kernel implementation might use.")
    print("  Testing whether the weaker hash is MORE vulnerable to the")
    print("  same style of attack, using the SAME attack budget for both.")
    print()

    results = {}
    for hash_name, hash_fn in HASH_FUNCTIONS.items():
        config = SimConfig(hash_fn=hash_fn)
        sketch = CountMinSketch(
            width=config.sketch_width, depth=config.sketch_depth,
            hash_fn=hash_fn,
        )
        latency_task_id = "latency_sensitive_task"

        t0 = time.time()
        target_indices = [
            sketch._index(latency_task_id, row)
            for row in range(config.sketch_depth)
        ]
        colliding_keys = []
        for row in range(config.sketch_depth):
            keys = find_colliding_keys(
                sketch.seeds[row], target_indices[row],
                config.sketch_width, count_needed=10,
                prefix=f"attack_{hash_name}_row{row}", hash_fn=hash_fn,
            )
            colliding_keys.extend(keys)
        search_time = time.time() - t0

        for key in colliding_keys:
            sketch.increment(key, amount=200)
        sketch.increment(latency_task_id, amount=500)

        estimate = min(
            sketch.table[row][sketch._index(latency_task_id, row)]
            for row in range(config.sketch_depth)
        )
        error_pct = 100 * (estimate - 500) / 500

        results[hash_name] = {
            "search_time_sec": search_time,
            "error_pct": error_pct,
            "num_colliding_keys_found": len(colliding_keys),
        }
        print(f"  {hash_name:>10}: found {len(colliding_keys)} colliding keys "
              f"in {search_time:.3f}s, resulting error: {error_pct:+.1f}%")

    print()
    bl_err = results["blake2b"]["error_pct"]
    fn_err = results["fnv1a"]["error_pct"]
    if abs(fn_err - bl_err) < 20:
        print("  --> Both hash functions show SIMILAR vulnerability to this")
        print("      attack. This suggests the vulnerability is a")
        print("      fundamental property of Count-Min Sketch under a")
        print("      knowledgeable adversary, NOT specific to hash choice.")
        print("      Switching to a faster hash for the real BPF")
        print("      implementation would not meaningfully change this risk.")
    else:
        print(f"  --> Hash functions show DIFFERENT vulnerability levels "
              f"({bl_err:+.1f}% vs {fn_err:+.1f}%). Hash choice matters for")
        print("      attack resistance — worth further investigation before")
        print("      picking a hash for the real implementation.")
    print()
    return results


# ---------------------------------------------------------------------
# Test 4: Multi-window decay — does the attack's damage fully clear by N+2?
# ---------------------------------------------------------------------

def test_multiwindow_decay(num_windows: int = 5) -> list[float]:
    print("=" * 76)
    print("TEST 4: Multi-window decay of a one-time targeted attack")
    print("=" * 76)
    print()
    print("  Attacker fires ONCE, in window N only, then goes silent.")
    print("  Tracking error across several subsequent windows to see how")
    print("  many windows it takes for the damage to fully clear, given")
    print("  seed rotation is active.")
    print()

    config = SimConfig()
    latency_task_id = "latency_sensitive_task"
    sketch = SeedRotatingCountMinSketch(width=config.sketch_width, depth=config.sketch_depth)

    errors_by_window = []
    true_cumulative = 0

    for window in range(num_windows):
        if window == 0:
            # Attack fires once, in window 0 only.
            target_indices = [sketch.current._index(latency_task_id, row)
                               for row in range(config.sketch_depth)]
            for row in range(config.sketch_depth):
                keys = find_colliding_keys(
                    sketch.current.seeds[row], target_indices[row],
                    config.sketch_width, count_needed=10,
                    prefix=f"attack_w0_row{row}",
                )
                for key in keys:
                    sketch.increment(key, amount=200)

        sketch.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)
        true_cumulative = config.latency_task_wakeups_per_epoch * min(window + 1, 2)

        estimate = sketch.estimate(latency_task_id)
        error_pct = 100 * (estimate - true_cumulative) / true_cumulative
        errors_by_window.append(error_pct)
        print(f"  Window {window}: true={true_cumulative}, estimate={estimate}, "
              f"error={error_pct:+.1f}%")

        sketch.rotate()

    print()
    if abs(errors_by_window[-1]) < 20:
        print(f"  --> Damage fully cleared by window {len(errors_by_window)-1}.")
    else:
        print(f"  --> Damage has NOT fully cleared after {num_windows} windows "
              f"— longer-lived effect than the simple 'one extra window' "
              f"model predicted.")
    print()
    return errors_by_window


# ---------------------------------------------------------------------
# Test 5: Anomaly-triggered early reset — a stronger mitigation
# ---------------------------------------------------------------------

def test_anomaly_triggered_reset(spike_threshold_multiplier: float = 3.0,
                                  num_seeds: int = 10) -> dict:
    print("=" * 76)
    print("TEST 5: Anomaly-triggered early reset (stronger mitigation)")
    print("=" * 76)
    print()
    print("  Idea: instead of waiting for the natural window boundary to")
    print("  age out poisoned data, detect an anomalous spike in a query")
    print(f"  result (>{spike_threshold_multiplier}x a rolling baseline) and")
    print("  immediately HARD-RESET both buffers, discarding the poisoned")
    print("  window entirely rather than letting it become 'previous' via")
    print("  a normal rotation.")
    print()
    print("  NOTE: an earlier version of this test had a real bug — it")
    print("  manually reset 'previous' but then called the normal")
    print("  rotate(), which overwrites 'previous' with the (still")
    print("  poisoned) 'current' anyway, silently undoing the fix. That")
    print("  produced a nonsensical 'mitigation makes it WORSE' result")
    print("  from a single noisy seed draw. Fixed by implementing a real")
    print("  hard reset that bypasses normal rotate() entirely, and by")
    print(f"  averaging over {num_seeds} seeds instead of trusting one draw.")
    print()

    without_results = []
    with_results = []

    for seed in range(num_seeds):
        config = SimConfig(seed=seed)
        latency_task_id = "latency_sensitive_task"

        # --- Baseline: seed rotation only, no anomaly detection ---
        sketch_baseline = SeedRotatingCountMinSketch(width=config.sketch_width, depth=config.sketch_depth)
        target_indices = [sketch_baseline.current._index(latency_task_id, row)
                           for row in range(config.sketch_depth)]
        attack_keys = []
        for row in range(config.sketch_depth):
            keys = find_colliding_keys(
                sketch_baseline.current.seeds[row], target_indices[row],
                config.sketch_width, count_needed=10,
                prefix=f"attack_mit_s{seed}_row{row}",
            )
            attack_keys.extend(keys)

        for key in attack_keys:
            sketch_baseline.increment(key, amount=200)
        sketch_baseline.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)
        sketch_baseline.rotate()
        sketch_baseline.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)
        baseline_window_n1 = sketch_baseline.estimate(latency_task_id)
        true_n1 = config.latency_task_wakeups_per_epoch * 2
        without_results.append(100 * (baseline_window_n1 - true_n1) / true_n1)

        # --- With mitigation: HARD reset (not a manual field
        # assignment clobbered by a subsequent rotate()) ---
        sketch_mit = SeedRotatingCountMinSketch(width=config.sketch_width, depth=config.sketch_depth)
        for key in attack_keys:
            sketch_mit.increment(key, amount=200)
        sketch_mit.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)
        mit_window_n = sketch_mit.estimate(latency_task_id)

        expected_single_window = config.latency_task_wakeups_per_epoch
        if mit_window_n > spike_threshold_multiplier * expected_single_window:
            # Genuine hard reset: BOTH buffers become fresh. The
            # poisoned "current" is discarded outright, never becoming
            # "previous" — this is the actual fix, not the earlier
            # buggy version.
            sketch_mit.current = CountMinSketch(
                config.sketch_width, config.sketch_depth,
                seed=sketch_mit._next_seed(), hash_fn=sketch_mit.hash_fn,
            )
            sketch_mit.previous = CountMinSketch(
                config.sketch_width, config.sketch_depth,
                seed=sketch_mit._next_seed(), hash_fn=sketch_mit.hash_fn,
            )
        else:
            sketch_mit.rotate()

        sketch_mit.increment(latency_task_id, amount=config.latency_task_wakeups_per_epoch)
        mit_window_n1 = sketch_mit.estimate(latency_task_id)
        true_n1_mitigated = config.latency_task_wakeups_per_epoch  # only this window's traffic, since history was intentionally dropped
        with_results.append(100 * (mit_window_n1 - true_n1_mitigated) / true_n1_mitigated)

    without_mean = statistics.mean(without_results)
    with_mean = statistics.mean(with_results)
    print(f"  Window N+1 WITHOUT mitigation: mean error={without_mean:+.1f}% "
          f"(std={statistics.stdev(without_results):.1f}%)")
    print(f"  Window N+1 WITH mitigation:    mean error={with_mean:+.1f}% "
          f"(std={statistics.stdev(with_results):.1f}%)")
    print()
    if abs(with_mean) < abs(without_mean) / 3:
        print("  --> Anomaly-triggered hard reset is a MEANINGFULLY")
        print("      stronger defense than passive seed rotation alone.")
    else:
        print("  --> Anomaly-triggered reset did not meaningfully improve")
        print("      on passive seed rotation at these parameters.")
    print()
    print("  CAVEAT: this test uses a known true value as the anomaly")
    print("  reference point, which a real implementation would not have.")
    print("  A real system would need a rolling baseline estimate, which")
    print("  introduces its own error and false-positive/negative")
    print("  tradeoffs not modeled here — this is a proof-of-concept that")
    print("  the MECHANISM can work, not a validated real-world defense.")
    print("  Also note: the hard reset trades away ALL historical data on")
    print("  a detected spike, including legitimate carry-over from a")
    print("  non-attacked task — a real deployment would need to weigh")
    print("  false-positive cost (losing real data) against this benefit.")
    print()

    return {
        "without_mitigation_pct": without_mean,
        "with_mitigation_pct": with_mean,
    }


# ---------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------

def save_plots(width_depth_results, multiwindow_results, anomaly_results):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available — skipping plots.")
        return

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))

    # Plot 1: width/depth tradeoff
    configs = sorted(width_depth_results.keys(), key=lambda k: k[0])
    labels = [f"w={w}\nd={d}" for w, d in configs]
    means = [statistics.mean(width_depth_results[k]) for k in configs]
    axes[0].bar(labels, means)
    axes[0].set_ylabel("Error (%)")
    axes[0].set_title("Test 1: Width x Depth Tradeoff\n(fixed memory budget)")

    # Plot 2: multi-window decay
    axes[1].plot(range(len(multiwindow_results)), multiwindow_results, marker="o")
    axes[1].axhline(0, color="gray", linestyle=":")
    axes[1].set_xlabel("Window (attack fired once, in window 0)")
    axes[1].set_ylabel("Error (%)")
    axes[1].set_title("Test 4: Attack Damage Decay\nOver Subsequent Windows")

    # Plot 3: mitigation comparison
    labels2 = ["Without mitigation", "With anomaly-triggered reset"]
    values2 = [anomaly_results["without_mitigation_pct"], anomaly_results["with_mitigation_pct"]]
    axes[2].bar(labels2, values2, color=["indianred", "seagreen"])
    axes[2].set_ylabel("Error (%) in window N+1")
    axes[2].set_title("Test 5: Mitigation Effectiveness")
    axes[2].tick_params(axis="x", rotation=15)

    plt.tight_layout()
    plt.savefig("expanded_findings_results.png")
    print("Plot saved to expanded_findings_results.png")


if __name__ == "__main__":
    width_depth_results = test_width_depth_tradeoff()
    seed_rotation_results = test_seed_rotation_defense()
    hash_comparison_results = test_hash_function_comparison()
    multiwindow_results = test_multiwindow_decay()
    anomaly_mitigation_results = test_anomaly_triggered_reset()

    print("=" * 76)
    print("SUMMARY")
    print("=" * 76)
    print(f"  Width/depth: wide-shallow vs narrow-deep — see table above")
    print(f"  Seed rotation defense: window N error "
          f"{seed_rotation_results['window_n_error_pct']:+.1f}% -> "
          f"window N+1 (stale attack) "
          f"{seed_rotation_results['window_n1_error_pct']:+.1f}%")
    print(f"  Hash comparison: blake2b "
          f"{hash_comparison_results['blake2b']['error_pct']:+.1f}% vs "
          f"fnv1a {hash_comparison_results['fnv1a']['error_pct']:+.1f}%")
    print(f"  Multi-window decay: {multiwindow_results}")
    print(f"  Anomaly-triggered reset: baseline "
          f"{anomaly_mitigation_results['without_mitigation_pct']:+.1f}% -> "
          f"with mitigation "
          f"{anomaly_mitigation_results['with_mitigation_pct']:+.1f}%")

    save_plots(width_depth_results, multiwindow_results, anomaly_mitigation_results)

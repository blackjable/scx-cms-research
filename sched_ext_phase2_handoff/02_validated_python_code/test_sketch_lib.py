"""
test_sketch_lib.py

Regression suite for sketch_lib.py, built per the Phase 2 delivery
plan's "before porting to BPF" requirement (see
01_delivery_plan/phase2_delivery_plan_update.md, Section 5).

Why this exists: Phase 1 was bitten twice by the same failure mode — a
fix applied in sketch_lib.py silently failed to propagate into
dependent scripts, and the drift was only caught by a manual audit
pass, sometimes several turns of work later (see paper Section 4.1's
audit note and Section 4.1.5). The upcoming BPF port will touch every
file in this directory; this suite exists so that kind of silent
correctness regression fails a test run instead of waiting for another
manual audit.

Two kinds of tests, deliberately kept distinct:

1. Invariant tests — properties that must hold by construction/theory,
   independent of any specific numeric result (e.g. Count-Min Sketch's
   never-underestimate guarantee, merge equivalence). These catch
   *logic* bugs and don't need updating when parameters change.
2. Frozen-value regression tests — exact numbers produced by the
   current, already-validated implementation at a fixed seed, captured
   as of this suite's creation and cross-checked against the figures
   already reported in the paper draft (e.g. the 537,901-byte exact
   counter figure in Section 4.1). These catch *drift* — if a future
   change silently alters behavior, one of these fails even if no
   invariant is violated. Intentional behavior changes should update
   these values deliberately, with a note on why, not treat a failure
   here as automatically wrong.
"""

import math

import pytest

import sketch_lib as sl


# ---------------------------------------------------------------------
# Hash functions
# ---------------------------------------------------------------------

class TestHashFunctions:
    def test_stable_hash_deterministic_across_calls(self):
        a = sl.stable_hash("latency_sensitive_task", 12345, 256)
        b = sl.stable_hash("latency_sensitive_task", 12345, 256)
        assert a == b

    def test_stable_hash_frozen_values(self):
        # Captured from the current implementation. A change here means
        # stable_hash's output changed for identical inputs — every
        # downstream accuracy figure in the paper depends on this being
        # stable, so this must be an intentional, reported change, not
        # silent drift.
        assert sl.stable_hash("latency_sensitive_task", 12345, 256) == 63
        assert sl.stable_hash("epoch0_churn_0", 999, 256) == 40

    def test_fnv1a_hash_deterministic_across_calls(self):
        a = sl.fnv1a_hash("latency_sensitive_task", 12345, 256)
        b = sl.fnv1a_hash("latency_sensitive_task", 12345, 256)
        assert a == b

    def test_fnv1a_hash_frozen_values(self):
        assert sl.fnv1a_hash("latency_sensitive_task", 12345, 256) == 143
        assert sl.fnv1a_hash("epoch0_churn_0", 999, 256) == 27

    def test_hash_output_within_modulus(self):
        for hash_fn in (sl.stable_hash, sl.fnv1a_hash):
            for key in ("a", "some_longer_task_identity", ""):
                idx = hash_fn(key, seed=7, modulus=64)
                assert 0 <= idx < 64

    def test_hash_registry_matches_functions(self):
        assert sl.HASH_FUNCTIONS["blake2b"] is sl.stable_hash
        assert sl.HASH_FUNCTIONS["fnv1a"] is sl.fnv1a_hash


# ---------------------------------------------------------------------
# CountMinSketch (single buffer)
# ---------------------------------------------------------------------

class TestCountMinSketch:
    @pytest.mark.parametrize("hash_fn", [sl.stable_hash, sl.fnv1a_hash])
    def test_never_underestimates(self, hash_fn):
        # The one formal correctness guarantee CMS makes (Cormode &
        # Muthukrishnan, 2005), verified in the paper across 80
        # (seed, epoch) combinations with zero violations (Section
        # 4.1.2), then extended to every key (Section 4.1.5). This test
        # re-checks the same invariant directly against the code.
        sketch = sl.CountMinSketch(width=64, depth=4, seed=1, hash_fn=hash_fn)
        rng_keys = [f"task_{i}" for i in range(200)]
        true_counts: dict[str, int] = {}
        for i, key in enumerate(rng_keys):
            amount = (i % 7) + 1
            sketch.increment(key, amount)
            true_counts[key] = true_counts.get(key, 0) + amount

        for key, true_count in true_counts.items():
            estimate = min(
                sketch.table[row][sketch._index(key, row)]
                for row in range(sketch.depth)
            )
            assert estimate >= true_count

    def test_memory_bytes_is_fixed_and_matches_formula(self):
        sketch = sl.CountMinSketch(width=256, depth=4)
        assert sketch.memory_bytes() == 256 * 4 * 4
        # Fixed regardless of how much data has been inserted — the
        # entire point of using a sketch over an exact counter.
        for i in range(10_000):
            sketch.increment(f"key_{i}")
        assert sketch.memory_bytes() == 256 * 4 * 4

    def test_seeds_derived_deterministically_from_seed(self):
        a = sl.CountMinSketch(width=64, depth=4, seed=42)
        b = sl.CountMinSketch(width=64, depth=4, seed=42)
        assert a.seeds == b.seeds

        c = sl.CountMinSketch(width=64, depth=4, seed=43)
        assert a.seeds != c.seeds


# ---------------------------------------------------------------------
# RotatingCountMinSketch (fixed-seed dual buffer)
# ---------------------------------------------------------------------

class TestRotatingCountMinSketch:
    def test_estimate_zero_before_any_insert(self):
        sketch = sl.RotatingCountMinSketch(width=64, depth=4, seed=1)
        assert sketch.estimate("anything") == 0

    def test_rotate_clears_stale_previous_data(self):
        # Two windows out, data from a one-shot event should be fully
        # gone (paper Section 4.1.4: rotating dual-buffer self-heals
        # after exactly one extra window).
        sketch = sl.RotatingCountMinSketch(width=64, depth=4, seed=1)
        sketch.increment("one_shot", 100)
        assert sketch.estimate("one_shot") == 100
        sketch.rotate()
        assert sketch.estimate("one_shot") == 100  # carried via "previous"
        sketch.rotate()
        assert sketch.estimate("one_shot") == 0  # fully rotated out

    def test_merge_equivalent_to_single_sketch_with_all_events(self):
        # The mathematical claim underpinning the whole windowing
        # design (paper Section 4.1's audit note): summing two
        # identically-seeded sketches' tables cell-wise is exactly
        # equivalent to having inserted all events into one sketch from
        # the start. Verified here byte-for-byte, not just "close."
        width, depth, seed = 128, 4, 7

        rotating = sl.RotatingCountMinSketch(width, depth, seed)
        rotating.increment("a", 5)
        rotating.increment("b", 3)
        rotating.rotate()
        rotating.increment("a", 2)
        rotating.increment("c", 9)

        reference = sl.CountMinSketch(width, depth, seed)
        for key, amount in [("a", 5), ("b", 3), ("a", 2), ("c", 9)]:
            reference.increment(key, amount)

        for row in range(depth):
            merged_row = [
                rotating.current.table[row][i] + rotating.previous.table[row][i]
                for i in range(width)
            ]
            assert merged_row == reference.table[row]

    def test_theoretical_epsilon_and_delta_match_formulas(self):
        sketch = sl.RotatingCountMinSketch(width=256, depth=4)
        assert sketch.theoretical_epsilon() == pytest.approx(math.e / 256)
        assert sketch.theoretical_delta() == pytest.approx(math.exp(-4))


# ---------------------------------------------------------------------
# SeedRotatingCountMinSketch
# ---------------------------------------------------------------------

class TestSeedRotatingCountMinSketch:
    def test_seeds_deterministic_given_construction_seed(self):
        a = sl.SeedRotatingCountMinSketch(width=64, depth=4, seed=5)
        b = sl.SeedRotatingCountMinSketch(width=64, depth=4, seed=5)
        assert a.current.seeds == b.current.seeds
        assert a.previous.seeds == b.previous.seeds

    def test_rotation_produces_a_fresh_seed(self):
        sketch = sl.SeedRotatingCountMinSketch(width=64, depth=4, seed=5)
        seeds_before = list(sketch.current.seeds)
        sketch.rotate()
        assert sketch.current.seeds != seeds_before

    def test_estimate_sums_independently_hashed_buffers(self):
        sketch = sl.SeedRotatingCountMinSketch(width=64, depth=4, seed=5)
        sketch.increment("k", 10)
        sketch.rotate()
        sketch.increment("k", 4)
        assert sketch.estimate("k") == 14


# ---------------------------------------------------------------------
# RotatingExactCounter
# ---------------------------------------------------------------------

class TestRotatingExactCounter:
    def test_zero_error_against_ground_truth(self):
        counter = sl.RotatingExactCounter()
        counter.increment("a", 3)
        counter.increment("a", 4)
        counter.increment("b", 1)
        assert counter.estimate("a") == 7
        assert counter.estimate("b") == 1
        assert counter.estimate("never_seen") == 0

    def test_rotate_carries_one_window_then_drops(self):
        counter = sl.RotatingExactCounter()
        counter.increment("a", 10)
        counter.rotate()
        assert counter.estimate("a") == 10
        counter.rotate()
        assert counter.estimate("a") == 0

    def test_memory_bytes_is_measured_not_guessed(self):
        # Regression guard for the bug found in savage_audit.py: an
        # earlier version used a guessed "~50 bytes/entry" constant.
        # This just checks memory_bytes() reflects actual insertions
        # via real measurement (sys.getsizeof), i.e. it grows with
        # distinct keys rather than returning a fixed/guessed value.
        counter = sl.RotatingExactCounter()
        empty_bytes = counter.memory_bytes()
        for i in range(1000):
            counter.increment(f"key_{i}")
        assert counter.memory_bytes() > empty_bytes


# ---------------------------------------------------------------------
# Churn event generation
# ---------------------------------------------------------------------

class TestGenerateChurnEvents:
    def test_uniform_reproducible_given_seed(self):
        events_a = sl.generate_churn_events(
            __import__("random").Random(1), epoch=0, num_identities=50,
            wakeups_range=(1, 5), distribution=sl.ChurnDistribution.UNIFORM,
        )
        events_b = sl.generate_churn_events(
            __import__("random").Random(1), epoch=0, num_identities=50,
            wakeups_range=(1, 5), distribution=sl.ChurnDistribution.UNIFORM,
        )
        assert events_a == events_b

    def test_uniform_event_count_within_expected_bounds(self):
        import random
        events = sl.generate_churn_events(
            random.Random(1), epoch=0, num_identities=100,
            wakeups_range=(1, 5), distribution=sl.ChurnDistribution.UNIFORM,
        )
        assert 100 * 1 <= len(events) <= 100 * 5

    def test_adversarial_clustered_maximizes_volume(self):
        import random
        num_identities = 50
        wakeups_range = (1, 5)

        uniform_max = sl.generate_churn_events(
            random.Random(1), epoch=0, num_identities=num_identities,
            wakeups_range=wakeups_range, distribution=sl.ChurnDistribution.UNIFORM,
        )
        adversarial = sl.generate_churn_events(
            random.Random(1), epoch=0, num_identities=num_identities,
            wakeups_range=wakeups_range,
            distribution=sl.ChurnDistribution.ADVERSARIAL_CLUSTERED,
        )
        # Adversarial: 5x identities, each at the range's max — always
        # strictly larger volume than uniform's best case.
        assert len(adversarial) == num_identities * 5 * wakeups_range[1]
        assert len(adversarial) > len(uniform_max)

    def test_skewed_has_a_small_heavy_minority(self):
        import random
        events = sl.generate_churn_events(
            random.Random(1), epoch=0, num_identities=100,
            wakeups_range=(1, 5), distribution=sl.ChurnDistribution.SKEWED,
        )
        counts: dict[str, int] = {}
        for e in events:
            counts[e] = counts.get(e, 0) + 1
        heavy = [c for c in counts.values() if c > 10]
        # 5% of 100 = 5 heavy identities, each drawn from (25, 50).
        assert len(heavy) == 5


# ---------------------------------------------------------------------
# run_simulation — end-to-end frozen-value regression
# ---------------------------------------------------------------------

class TestRunSimulationRegression:
    """
    Full end-to-end regression using the paper's own default parameters
    (width=256, depth=4, ~5,000 churn identities/epoch, 20 epochs,
    seed=42). Values below were captured from the current implementation
    and cross-checked against the paper draft's reported figures
    (Section 4.1: exact-counter memory ~537,901 bytes; sketch memory
    8,192 bytes) — they match, confirming this test's baseline is the
    same validated behavior the paper describes, not an arbitrary
    new snapshot.
    """

    def test_default_config_blake2b(self):
        result = sl.run_simulation(sl.SimConfig(hash_fn=sl.stable_hash))

        assert result.steady_state_exact_errors == [0] * 18
        assert result.sketch_memory_bytes == 8192
        assert result.exact_memory_bytes_final == 537901
        assert result.theoretical_epsilon == pytest.approx(math.e / 256)
        assert result.theoretical_delta == pytest.approx(math.exp(-4))

        assert result.steady_state_sketch_errors == [
            290, 183, 262, 243, 317, 372, 326, 291, 348, 344,
            260, 373, 392, 344, 300, 239, 258, 296,
        ]

    def test_default_config_fnv1a(self):
        result = sl.run_simulation(sl.SimConfig(hash_fn=sl.fnv1a_hash))

        assert result.steady_state_exact_errors == [0] * 18
        assert result.steady_state_sketch_errors == [
            295, 284, 301, 274, 263, 322, 307, 339, 319, 315,
            280, 308, 407, 346, 272, 295, 323, 252,
        ]

    def test_sketch_errors_never_negative(self):
        # Never-underestimate guarantee, exercised through the full
        # simulation harness rather than a synthetic unit test.
        for hash_fn in (sl.stable_hash, sl.fnv1a_hash):
            result = sl.run_simulation(sl.SimConfig(hash_fn=hash_fn))
            assert all(e >= 0 for e in result.steady_state_sketch_errors)

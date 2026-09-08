"""
sketch_lib.py

Shared Count-Min Sketch / exact-counter / simulation code, factored out
of experiment.py so both the basic demo (experiment.py) and the
expanded rigor tests (sweep_experiment.py) use the identical
implementation — no drift between "the version we validated" and "the
version we're stress-testing."

REPRODUCIBILITY NOTE: this module deliberately does NOT use Python's
built-in hash() for string keys. Python randomizes string hashing by
default (PYTHONHASHSEED, since 3.3, a security feature against
hash-flooding attacks) — meaning hash("some_key") returns a DIFFERENT
value every time a new Python process starts, even with identical
code and an identical simulation seed. This was discovered as a real
bug in an earlier version of this experiment: every result reported
up to that point was only internally consistent WITHIN one script
invocation, and would silently produce different absolute numbers on
every re-run — a genuine reproducibility failure for a research
result. We use hashlib.blake2b (fast, well-distributed, and — unlike
Python's hash() — has no process-level randomization) seeded
explicitly per row instead.
"""

import hashlib
import random
from dataclasses import dataclass, field
from enum import Enum


def stable_hash(key: str, seed: int, modulus: int) -> int:
    """
    Deterministic, process-independent hash. Unlike Python's built-in
    hash(), this returns the same value for the same (key, seed) pair
    on every run, on every machine, forever — a requirement for any
    result claiming reproducibility.
    """
    h = hashlib.blake2b(f"{seed}:{key}".encode(), digest_size=8)
    return int.from_bytes(h.digest(), "big") % modulus


def fnv1a_hash(key: str, seed: int, modulus: int) -> int:
    """
    FNV-1a: a simple, fast, non-cryptographic hash — much closer to
    what a real BPF program would actually use than blake2b (which is
    cryptographically strong but far more CPU-expensive than
    justified for a per-wakeup hot-path hash). Included specifically
    to test whether the targeted-collision vulnerability found with
    blake2b (Section 4.1.1) is specific to that hash choice, or a
    more fundamental property of Count-Min Sketch under a
    knowledgeable adversary regardless of hash quality.

    This is a simplified, seed-mixed variant: seed is XORed into the
    initial basis, which is a common lightweight way to get
    independent-ish hash functions from a single algorithm without
    the cost of a cryptographic hash per row.
    """
    FNV_PRIME = 0x01000193
    h = (0x811c9dc5 ^ seed) & 0xFFFFFFFF
    for byte in key.encode():
        h ^= byte
        h = (h * FNV_PRIME) & 0xFFFFFFFF
    return h % modulus


HASH_FUNCTIONS = {
    "blake2b": stable_hash,
    "fnv1a": fnv1a_hash,
}


# ---------------------------------------------------------------------
# Base Count-Min Sketch (single buffer)
# ---------------------------------------------------------------------

class CountMinSketch:
    def __init__(self, width: int = 256, depth: int = 4, seed: int = 0,
                 hash_fn=stable_hash):
        self.width = width
        self.depth = depth
        self.hash_fn = hash_fn
        self.table = [[0] * width for _ in range(depth)]
        rng = random.Random(seed)
        self.seeds = [rng.randint(1, 2**31 - 1) for _ in range(depth)]

    def _index(self, key: str, row: int) -> int:
        return self.hash_fn(key, self.seeds[row], self.width)

    def increment(self, key: str, amount: int = 1) -> None:
        for row in range(self.depth):
            idx = self._index(key, row)
            self.table[row][idx] += amount

    def memory_bytes(self) -> int:
        return self.width * self.depth * 4


class RotatingCountMinSketch:
    """Dual-buffer rotating sketch implementing a tumbling window."""

    def __init__(self, width: int = 256, depth: int = 4, seed: int = 0,
                 hash_fn=stable_hash):
        self.width = width
        self.depth = depth
        self.seed = seed
        self.hash_fn = hash_fn
        self.current = CountMinSketch(width, depth, seed, hash_fn)
        self.previous = CountMinSketch(width, depth, seed, hash_fn)

    def increment(self, key: str, amount: int = 1) -> None:
        self.current.increment(key, amount)

    def estimate(self, key: str) -> int:
        return min(
            self.current.table[row][self.current._index(key, row)]
            + self.previous.table[row][self.previous._index(key, row)]
            for row in range(self.depth)
        )

    def rotate(self) -> None:
        self.previous = self.current
        self.current = CountMinSketch(self.width, self.depth, self.seed, self.hash_fn)

    def memory_bytes(self) -> int:
        return self.current.memory_bytes() + self.previous.memory_bytes()

    def theoretical_epsilon(self) -> float:
        """
        From the formal Count-Min Sketch guarantee (Cormode &
        Muthukrishnan, 2005): width w = ceil(e/epsilon), so
        epsilon = e/w. This is the fraction of the total inserted
        volume (L1 norm) that the estimate may overshoot by, with
        probability at least (1 - theoretical_delta()).
        """
        import math
        return math.e / self.width

    def theoretical_delta(self) -> float:
        """depth d = ceil(ln(1/delta)), so delta = e^-d."""
        import math
        return math.exp(-self.depth)


class SeedRotatingCountMinSketch:
    """
    Variant of RotatingCountMinSketch that generates a FRESH random
    seed for the new "current" buffer on every rotation, rather than
    reusing the same seed forever.

    Motivation: the targeted-collision attack found in Section 4.1.1
    requires the attacker to know the hash seeds in order to
    pre-compute colliding keys. If the seed changes every window and
    is not exposed to userspace/untrusted callers (a reasonable
    assumption for a kernel-internal BPF map, analogous to how
    SipHash-based hash-flooding defenses rely on a secret,
    kernel-only key), a pre-computed attack becomes stale as soon as
    the window rotates — the attacker would need to re-discover
    colliding keys for the NEW seed before it can exploit it, and by
    the time it does, the window will rotate again.

    IMPORTANT CAVEAT modeled here: since current and previous now use
    DIFFERENT seeds (and therefore different hash functions), they
    can no longer be validly merged by summing tables cell-wise (that
    merge is only mathematically correct when both buffers share
    identical hash functions). Instead, each buffer is queried
    independently with its OWN hash function, and the two independent
    estimates are summed. This is still a valid way to combine two
    windows' worth of (independently hashed) approximate counts, just
    a different combination method than the fixed-seed version.
    """

    def __init__(self, width: int = 256, depth: int = 4, seed: int = 0,
                 hash_fn=stable_hash):
        self.width = width
        self.depth = depth
        self.hash_fn = hash_fn
        self._rng = random.Random(seed)
        self.current = CountMinSketch(width, depth, self._next_seed(), hash_fn)
        self.previous = CountMinSketch(width, depth, self._next_seed(), hash_fn)

    def _next_seed(self) -> int:
        return self._rng.randint(1, 2**31 - 1)

    def increment(self, key: str, amount: int = 1) -> None:
        self.current.increment(key, amount)

    def estimate(self, key: str) -> int:
        cur_est = min(
            self.current.table[row][self.current._index(key, row)]
            for row in range(self.depth)
        )
        prev_est = min(
            self.previous.table[row][self.previous._index(key, row)]
            for row in range(self.depth)
        )
        return cur_est + prev_est

    def rotate(self) -> None:
        self.previous = self.current
        self.current = CountMinSketch(self.width, self.depth, self._next_seed(), self.hash_fn)

    def memory_bytes(self) -> int:
        return self.current.memory_bytes() + self.previous.memory_bytes()


# ---------------------------------------------------------------------
# Exact counter baseline (same rotating dual-buffer scheme)
# ---------------------------------------------------------------------

class RotatingExactCounter:
    def __init__(self):
        self.current: dict[str, int] = {}
        self.previous: dict[str, int] = {}

    def increment(self, key: str, amount: int = 1) -> None:
        self.current[key] = self.current.get(key, 0) + amount

    def estimate(self, key: str) -> int:
        return self.current.get(key, 0) + self.previous.get(key, 0)

    def rotate(self) -> None:
        self.previous = self.current
        self.current = {}

    def memory_bytes(self) -> int:
        # REAL measurement via sys.getsizeof, not a guessed constant.
        # An earlier version used a guessed "~50 bytes per entry"
        # constant, never actually measured. A dedicated audit pass
        # (savage_audit.py) found this guess was wrong by 2.13x (real
        # measured overhead is ~107 bytes/entry for this key/value
        # shape) — a significant correction, since every memory-ratio
        # figure in the paper depends on this number.
        #
        # CAVEAT: this measures Python dict overhead, a proxy for
        # comparison within this prototype, not a literal prediction
        # of a real BPF hash map's cost — BPF maps have a far more
        # compact memory model with no Python object overhead.
        import sys as _sys
        total = _sys.getsizeof(self.current) + _sys.getsizeof(self.previous)
        for d in (self.current, self.previous):
            for k, v in d.items():
                total += _sys.getsizeof(k) + _sys.getsizeof(v)
        return total


# ---------------------------------------------------------------------
# Churn distributions
# ---------------------------------------------------------------------

class ChurnDistribution(Enum):
    UNIFORM = "uniform"
    SKEWED = "skewed"          # a few heavy churners, many light ones
    ADVERSARIAL_CLUSTERED = "adversarial_clustered"  # worst realistic case


def generate_churn_events(
    rng: random.Random,
    epoch: int,
    num_identities: int,
    wakeups_range: tuple[int, int],
    distribution: ChurnDistribution,
) -> list[str]:
    """
    Generates the list of churn task wakeup events for one epoch,
    under a given distribution assumption.

    UNIFORM: every churn identity gets a uniformly random wakeup count
        in wakeups_range. This is the original, fairly benign
        assumption used in the first experiment.

    SKEWED: models a more realistic embedded workload where most
        short-lived processes are quiet (1-2 wakeups) but a small
        fraction (5%) are much chattier (10x the range's upper bound).
        This is closer to real-world process behavior, where a handful
        of services genuinely dominate wakeup activity.

    ADVERSARIAL_CLUSTERED: deliberately tries to hurt the sketch. Since
        we can't reverse-engineer Python's hash() to force exact
        collisions with the latency-sensitive task's slots, this
        approximates a worst case by maximizing raw collision
        pressure: many MORE distinct identities than the uniform case
        (5x), each with the FULL upper-bound wakeup count (no low
        values diluting the noise) — i.e., maximum total event volume
        concentrated across many identities, which is the actual
        driver of sketch error (total inserted volume, not identity
        count per se, per the theoretical epsilon*L1 bound).
    """
    events: list[str] = []

    if distribution == ChurnDistribution.UNIFORM:
        for i in range(num_identities):
            task_id = f"epoch{epoch}_churn_{i}"
            n = rng.randint(*wakeups_range)
            events.extend([task_id] * n)

    elif distribution == ChurnDistribution.SKEWED:
        num_heavy = max(1, int(num_identities * 0.05))
        for i in range(num_identities):
            task_id = f"epoch{epoch}_churn_{i}"
            if i < num_heavy:
                n = rng.randint(wakeups_range[1] * 5, wakeups_range[1] * 10)
            else:
                n = rng.randint(wakeups_range[0], max(wakeups_range[0], 2))
            events.extend([task_id] * n)

    elif distribution == ChurnDistribution.ADVERSARIAL_CLUSTERED:
        # 5x the identity count, all at the upper end of the range —
        # maximizes total inserted volume without changing the
        # underlying hash function, which is the closest realistic
        # approximation of a "worst case" without white-box access to
        # the hash internals.
        for i in range(num_identities * 5):
            task_id = f"epoch{epoch}_churn_{i}"
            events.extend([task_id] * wakeups_range[1])

    return events


# ---------------------------------------------------------------------
# Configurable simulation
# ---------------------------------------------------------------------

@dataclass
class SimConfig:
    num_epochs: int = 20
    num_churn_identities_per_epoch: int = 5000
    wakeups_per_churn_task: tuple[int, int] = (1, 20)
    latency_task_wakeups_per_epoch: int = 500
    sketch_width: int = 256
    sketch_depth: int = 4
    seed: int = 42
    distribution: ChurnDistribution = ChurnDistribution.UNIFORM
    hash_fn: object = stable_hash
    sketch_class: object = RotatingCountMinSketch


@dataclass
class SimResult:
    steady_state_sketch_errors: list[int] = field(default_factory=list)
    steady_state_exact_errors: list[int] = field(default_factory=list)
    sketch_memory_bytes: int = 0
    exact_memory_bytes_final: int = 0
    theoretical_epsilon: float = 0.0
    theoretical_delta: float = 0.0


def run_simulation(config: SimConfig) -> SimResult:
    rng = random.Random(config.seed)
    sketch = config.sketch_class(
        width=config.sketch_width, depth=config.sketch_depth,
        hash_fn=config.hash_fn,
    )
    exact = RotatingExactCounter()
    result = SimResult()
    import math
    result.theoretical_epsilon = math.e / config.sketch_width
    result.theoretical_delta = math.exp(-config.sketch_depth)

    latency_task_id = "latency_sensitive_task"

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

        prior = config.latency_task_wakeups_per_epoch if epoch >= 1 else 0
        true_window = config.latency_task_wakeups_per_epoch + prior

        if epoch >= 2:  # skip partial-window edge cases at the start
            result.steady_state_sketch_errors.append(
                sketch.estimate(latency_task_id) - true_window
            )
            result.steady_state_exact_errors.append(
                exact.estimate(latency_task_id) - true_window
            )

        sketch.rotate()
        exact.rotate()

    result.sketch_memory_bytes = sketch.memory_bytes()
    result.exact_memory_bytes_final = exact.memory_bytes()
    return result

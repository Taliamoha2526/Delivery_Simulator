"""Centralised, reproducible randomness.
This is the only module that creates random number generators.
Every other component receives ann instance.
"""

import hashlib
import random


def derive_seed(seed: int, name: str) -> int:
    digest = hashlib.sha256(f"{seed}:{name}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


class RandomStreams:
    """Factory of independent, named, seeded random streams."""

    def __init__(self, seed: int):
        self.seed = seed
        self._streams: dict[str, random.Random] = {}

    def stream(self, name: str) -> random.Random:
        """Return the name stream."""
        if name not in self._streams:
            self._streams[name] = random.Random(derive_seed(self.seed, name))
        return self._streams[name]

    def fresh(self, name: str) -> random.Random:
        """A new generator for the name, restarted from its initial state."""
        return random.Random(derive_seed(self.seed, name))


def poisson(rng: random.Random, lam: float) -> int:
    """Sample a Poisson(lam) count."""
    if lam <= 0:
        return 0
    import math

    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1

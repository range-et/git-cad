"""Bounded generated cases; CI is reproducible for a fixed lockfile and Python."""

from hypothesis import settings

settings.register_profile("ci", max_examples=100, derandomize=True, deadline=None)
settings.register_profile("deep", max_examples=1000, deadline=None)

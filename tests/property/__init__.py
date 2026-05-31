"""Property-based tests for the deep-system-integration spec.

Requires Hypothesis. Each test module guards its imports with
``pytest.importorskip("hypothesis")`` so the suite degrades gracefully
when Hypothesis is not installed.
"""

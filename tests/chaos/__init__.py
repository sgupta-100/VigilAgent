"""Chaos / resilience tests for the deep-system-integration spec.

These tests inject controlled failures (random subsets of dependency calls
raising) and assert the surrounding infrastructure (coordinator, circuit
breakers, batch drainer) degrades gracefully rather than crashing.
"""

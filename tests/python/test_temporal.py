"""Offline tests for native-backed time observations."""

import unittest

from odin.observations.temporal import TEMPORAL_FEATURE_NAMES, observe_temporal


class FakeRuntime:
    def __init__(self):
        self.results = {
            "this.get_time()": "125.5",
            "this.state.timeToNextWinter()": "40.0",
            "this.state.timeToWinterEnd()": "70.0",
        }

    def call_native(self, expression):
        return self.results[expression]


class TemporalTests(unittest.TestCase):
    def test_builds_ordered_native_temporal_tensor(self):
        report = observe_temporal(FakeRuntime())

        self.assertEqual(report["feature_names"], TEMPORAL_FEATURE_NAMES)
        self.assertEqual(report["x"], [125.5, 40.0, 70.0])


if __name__ == "__main__":
    unittest.main()

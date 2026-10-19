"""Offline tests for the native-backed economy tensor."""

import json
import unittest

from odin.observations.economy import FEATURE_NAMES, RESOURCES, observe_economy, resolve_resource_keys


class FakeRuntime:
    def __init__(self):
        self.identifiers = [identifier for _, identifier in RESOURCES] + ["Population"]
        self.native_calls = []

    def array_length(self, expression):
        self.assert_expression = expression
        return len(self.identifiers)

    def evaluate(self, expression):
        index = int(expression.removeprefix("Data.resource.all[").split("]", 1)[0])
        return json.dumps(self.identifiers[index])

    def call_native(self, expression):
        self.native_calls.append(expression)
        if ".getResource(" in expression:
            return "100.0"
        if ".getFlux(" in expression:
            return "2.5"
        if expression.endswith(".getHappiness()"):
            return "4.0"
        if expression.endswith(".get_population()"):
            return "12"
        if ".getMax(" in expression:
            return "20"
        if expression.endswith(".getNextVillagerTime()"):
            return "8.0"
        if expression.endswith(".getNextVillagerProgress()"):
            return "0.25"
        raise AssertionError(f"Unexpected native call: {expression}")


class EconomyTests(unittest.TestCase):
    def test_resolves_resource_arguments_once_from_debugger_metadata(self):
        runtime = FakeRuntime()
        keys = resolve_resource_keys(runtime)

        self.assertEqual(runtime.assert_expression, "Data.resource.all")
        self.assertEqual(keys["Money"], "Data.resource.all[2].id")

    def test_builds_ordered_native_economy_tensor(self):
        runtime = FakeRuntime()
        report = observe_economy(runtime, resolve_resource_keys(runtime))

        self.assertEqual(report["feature_names"], FEATURE_NAMES)
        self.assertEqual(len(report["x"]), 19)
        self.assertEqual(report["x"][-3:], [1.0, 0.25, 8.0])
        # villager_growth_active is derived from the nullable time result.
        self.assertEqual(len(runtime.native_calls), 18)


if __name__ == "__main__":
    unittest.main()

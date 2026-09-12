"""Prepared receiving context preserves snapshot, authority and isolation laws."""
from dataclasses import replace
import unittest

import control_plane_kit_core as core
from control_plane_kit_server_sdk._control_dispatch import (
    _prepare_control_dispatch, _validate_control_configuration,
)
from control_plane_kit_server_sdk.health import WorkloadNodeHealthReadDispatcher
from tests import test_fastapi_control_routes as legacy
from tests import test_health_verification as health_credentials


class PreparedControlDispatchTests(unittest.TestCase):
    def test_preparation_snapshots_once_isolates_hosts_and_omits_health_only_replay(self):
        old = legacy.FastApiControlRouteTests()
        old.setUpClass()
        fixture = health_credentials.SignedHealthReadVerificationTests()
        fixture.setUp()
        calls = []

        def observe():
            calls.append(1)
            return core.NodeHealthReadOutcome.HEALTHY

        def arguments(declaration, variables, command_verifier):
            dispatcher = WorkloadNodeHealthReadDispatcher(
                target=fixture.target, runtime_id=fixture.runtime,
                declaration=declaration, verifier=fixture.verifier(),
                liveness=observe, readiness=observe,
            )
            return dict(
                target=fixture.target, declaration=declaration, variables=variables,
                command_verifier=command_verifier,
                surface_read_verifier=old._surface_verifier(), health_dispatcher=dispatcher,
            )

        declaration = replace(fixture.declaration, surface=replace(
            fixture.declaration.surface, variables=(legacy._descriptor("routing"),),
        ))
        contexts = []
        for _ in range(2):
            variable = legacy.RecordingVariable("routing")
            settings = arguments(declaration, (variable,), old._command_verifier())
            self.assertEqual(_validate_control_configuration(**settings), (True, True))
            self.assertEqual(variable.descriptor_calls, 0)
            with self.assertRaises(ValueError):
                _prepare_control_dispatch(**{**settings, "surface_read_verifier": None})
            self.assertEqual(variable.descriptor_calls, 0)
            context = _prepare_control_dispatch(**settings)
            contexts.append(context)
            self.assertEqual(variable.descriptor_calls, 1)
            self.assertEqual(tuple(name.value for name in context.installed_variable_names), ("routing",))
            self.assertIs(context.registry["routing"][0], variable)
            self.assertIs(context.health_dispatcher, settings["health_dispatcher"])
            self.assertIs(context.surface_read_verifier, settings["surface_read_verifier"])
            self.assertIsNotNone(context.replay)
            self.assertEqual(repr(context), "_PreparedControlDispatch()")
            with self.assertRaises(AttributeError):
                context.target = fixture.target
        self.assertIsNot(contexts[0].registry, contexts[1].registry)
        self.assertIsNot(contexts[0].replay, contexts[1].replay)
        health_only = _prepare_control_dispatch(**arguments(fixture.declaration, (), None))
        self.assertEqual(health_only.registry, {})
        self.assertEqual(health_only.installed_variable_names, ())
        self.assertIsNone(health_only.command_verifier)
        self.assertIsNone(health_only.replay)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()

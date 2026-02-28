"""
Tests for gateway_agent.__init__ — Module exports
====================================================

Verifies that the package's public API is correctly exported.
"""

import pytest


class TestModuleExports:

    def test_version(self):
        import gateway_agent
        assert gateway_agent.__version__ == "1.2.0"

    def test_author(self):
        import gateway_agent
        assert gateway_agent.__author__ == "EUNMIN Park"

    def test_email(self):
        import gateway_agent
        assert gateway_agent.__email__ == "admin@swiftquantumnative.com"

    def test_license(self):
        import gateway_agent
        assert gateway_agent.__license__ == "MIT"

    def test_exports_gateway_message(self):
        from gateway_agent import GatewayMessage
        assert GatewayMessage is not None

    def test_exports_message_type(self):
        from gateway_agent import MessageType
        assert MessageType is not None

    def test_exports_device_interface(self):
        from gateway_agent import DeviceInterface
        assert DeviceInterface is not None

    def test_exports_local_simulator(self):
        from gateway_agent import LocalSimulator
        assert LocalSimulator is not None

    def test_exports_gateway_server(self):
        from gateway_agent import GatewayServer
        assert GatewayServer is not None

    def test_all_list_contents(self):
        import gateway_agent
        expected = [
            "__version__",
            "GatewayMessage",
            "MessageType",
            "DeviceInterface",
            "LocalSimulator",
            "GatewayServer",
        ]
        for name in expected:
            assert name in gateway_agent.__all__

    def test_all_list_length(self):
        import gateway_agent
        assert len(gateway_agent.__all__) == 6

    def test_classes_are_importable_and_usable(self):
        from gateway_agent import GatewayMessage, MessageType, LocalSimulator

        # Can create instances
        msg = GatewayMessage(type=MessageType.HEALTH_CHECK)
        assert msg.type == MessageType.HEALTH_CHECK

        sim = LocalSimulator()
        info = sim.get_device_info()
        assert info.num_qubits == 20

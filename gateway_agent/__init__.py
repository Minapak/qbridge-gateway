"""
SwiftQuantum Gateway Agent
===========================

Standalone gateway service for researchers to self-host on their own
quantum hardware servers. Implements the SwiftQuantum Gateway Protocol,
enabling seamless integration with the SwiftQuantum ecosystem.

Quick Start:
    $ pip install swiftquantum-gateway-agent
    $ gateway-agent start --config device_config.yaml

Or programmatically:
    from gateway_agent import GatewayServer

    server = GatewayServer(config_path="device_config.yaml")
    server.start(host="0.0.0.0", port=8765)
"""

__version__ = "1.0.0"
__author__ = "EUNMIN Park"
__email__ = "admin@swiftquantumnative.com"
__license__ = "MIT"

from .protocol import GatewayMessage, MessageType
from .device_interface import DeviceInterface, LocalSimulator
from .server import GatewayServer

__all__ = [
    "__version__",
    "GatewayMessage",
    "MessageType",
    "DeviceInterface",
    "LocalSimulator",
    "GatewayServer",
]

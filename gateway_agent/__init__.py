"""
Q-Bridge Gateway Agent
========================

Standalone gateway service for researchers to self-host on their own
quantum hardware servers. Implements the SwiftQuantum Gateway Protocol,
enabling seamless integration with the SwiftQuantum ecosystem.

Quick Start:
    $ pip install qbridge-gateway
    $ qbridge-gateway init --config=config.json
    $ qbridge-gateway start --config=config.json

Or programmatically:
    from gateway_agent import GatewayServer

    server = GatewayServer(config_path="config.json")
    server.start(host="0.0.0.0", port=8090)
"""

__version__ = "1.2.0"
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

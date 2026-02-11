"""
Shared pytest fixtures for SwiftQuantum Gateway Agent tests.
"""

import os
import sys
import time
import pytest
import json
import tempfile
from typing import Dict, Any
from unittest.mock import MagicMock, patch

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from gateway_agent.protocol import GatewayMessage, MessageType
from gateway_agent.device_interface import (
    DeviceInfo,
    ExecutionResult,
    DeviceInterface,
    LocalSimulator,
)
from gateway_agent.server import GatewayServer


# ─── Fixtures: Protocol ───

@pytest.fixture
def sample_message_dict():
    """A raw dict that can be deserialized into a GatewayMessage."""
    return {
        "type": "execute_circuit",
        "version": "1.0",
        "timestamp": "2025-06-01T00:00:00+00:00",
        "source": "test_client",
        "target": "gateway_agent",
        "payload": {
            "circuit": {"num_qubits": 2, "gates": [{"gate": "h", "qubits": [0]}]},
            "shots": 100,
        },
        "correlation_id": "test-corr-001",
    }


@pytest.fixture
def sample_gateway_message():
    """A pre-built GatewayMessage instance."""
    return GatewayMessage(
        type=MessageType.EXECUTE_CIRCUIT,
        payload={"circuit": {"num_qubits": 2, "gates": []}, "shots": 512},
        source="test_source",
        target="test_target",
    )


# ─── Fixtures: Device ───

@pytest.fixture
def local_simulator():
    """A fresh LocalSimulator instance."""
    return LocalSimulator(name="test_sim", num_qubits=10)


@pytest.fixture
def device_info():
    """Standard DeviceInfo for testing."""
    return DeviceInfo(
        name="test_device",
        num_qubits=5,
        technology="superconducting",
        connectivity="linear",
        supported_gates=["h", "cx", "x", "rz"],
        max_shots=10000,
        status="online",
    )


@pytest.fixture
def bell_circuit():
    """Bell state circuit: H on q0, CX on q0->q1."""
    return {
        "num_qubits": 2,
        "gates": [
            {"gate": "h", "qubits": [0]},
            {"gate": "cx", "qubits": [0, 1]},
        ],
    }


@pytest.fixture
def ghz_circuit():
    """3-qubit GHZ circuit."""
    return {
        "num_qubits": 3,
        "gates": [
            {"gate": "h", "qubits": [0]},
            {"gate": "cx", "qubits": [0, 1]},
            {"gate": "cx", "qubits": [1, 2]},
        ],
    }


@pytest.fixture
def invalid_circuit_too_many_qubits():
    """Circuit requiring more qubits than device has."""
    return {
        "num_qubits": 100,
        "gates": [{"gate": "h", "qubits": [99]}],
    }


@pytest.fixture
def invalid_circuit_bad_gate():
    """Circuit with unsupported gate."""
    return {
        "num_qubits": 2,
        "gates": [{"gate": "unsupported_gate_xyz", "qubits": [0]}],
    }


@pytest.fixture
def execution_result():
    """A sample successful ExecutionResult."""
    return ExecutionResult(
        job_id="test_job_001",
        counts={"00": 500, "11": 524},
        shots=1024,
        execution_time_ms=12.5,
        success=True,
        metadata={"simulator": "test"},
    )


@pytest.fixture
def failed_execution_result():
    """A sample failed ExecutionResult."""
    return ExecutionResult(
        job_id="test_job_fail",
        counts={},
        shots=100,
        execution_time_ms=1.0,
        success=False,
        error="Circuit validation failed",
    )


# ─── Fixtures: Config ───

@pytest.fixture
def sample_yaml_config(tmp_path):
    """Create a temporary YAML config file."""
    config_content = """
server:
  name: "test_gateway"
  id: "gw_test_001"
  host: "127.0.0.1"
  port: 9999
  cors_origins:
    - "http://localhost:3000"

device:
  name: "test_simulator"
  num_qubits: 8
  technology: "simulator"
  connectivity: "full"

auth:
  enabled: false
  token: "${GATEWAY_AUTH_TOKEN}"

logging:
  level: "DEBUG"
"""
    config_file = tmp_path / "test_config.yaml"
    config_file.write_text(config_content)
    return str(config_file)


@pytest.fixture
def sample_json_config(tmp_path):
    """Create a temporary JSON config file."""
    config = {
        "server": {
            "name": "json_gateway",
            "id": "gw_json_001",
            "host": "127.0.0.1",
            "port": 7777,
        },
        "device": {
            "name": "json_simulator",
            "num_qubits": 12,
        },
    }
    config_file = tmp_path / "test_config.json"
    config_file.write_text(json.dumps(config))
    return str(config_file)


# ─── Fixtures: Server ───

@pytest.fixture
def gateway_server():
    """A GatewayServer with default LocalSimulator (no config file)."""
    return GatewayServer()


@pytest.fixture
def gateway_server_with_config(sample_yaml_config):
    """A GatewayServer initialized from a YAML config."""
    return GatewayServer(config_path=sample_yaml_config)


# ─── Fixtures: FastAPI test client ───

@pytest.fixture
def test_client(gateway_server):
    """HTTPX AsyncClient for testing FastAPI endpoints."""
    from httpx import AsyncClient, ASGITransport
    import asyncio

    transport = ASGITransport(app=gateway_server.app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture
def test_client_with_config(gateway_server_with_config):
    """HTTPX AsyncClient for a configured server."""
    from httpx import AsyncClient, ASGITransport

    transport = ASGITransport(app=gateway_server_with_config.app)
    return AsyncClient(transport=transport, base_url="http://testserver")

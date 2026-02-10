# SwiftQuantum Gateway Agent

Self-hosted quantum hardware gateway for researchers. The Gateway Agent is a standalone FastAPI server that implements the SwiftQuantum Gateway Protocol, allowing researchers to expose their quantum hardware (or simulators) to the SwiftQuantum ecosystem through a standardized REST API.

## Overview

The Gateway Agent bridges researcher-owned quantum devices with the SwiftQuantum platform. Researchers run this agent alongside their quantum hardware, and the agent handles circuit execution, transpilation, job management, and health monitoring through a uniform API surface.

**Key Features:**
- 10 REST API endpoints conforming to the SwiftQuantum Gateway Protocol (including QEC delegation)
- Pluggable `DeviceInterface` for connecting any quantum hardware
- Built-in `LocalSimulator` for testing and development
- YAML/JSON configuration with `${ENV_VAR}` placeholder resolution
- CLI tool for server management, status checking, and cloud registration
- CORS support for cross-origin access

---

## Quick Start

### Install

```bash
# From PyPI
pip install swiftquantum-gateway-agent

# From source
git clone https://github.com/SwiftQuantum/gateway-agent.git
cd gateway-agent
pip install -e .
```

### Configure

Edit `device_config.yaml` to match your hardware setup:

```yaml
server:
  name: "my_lab_gateway"
  id: "gw_001"
  host: "0.0.0.0"
  port: 8765

device:
  name: "my_qpu"
  num_qubits: 20
  technology: "superconducting"
  connectivity: "grid"
  supported_gates:
    - h
    - cx
    - rx
    - ry
    - rz
    - x
    - y
    - z
    - measure
  max_shots: 100000
```

### Run

```bash
# Using the CLI
gateway-agent start --config device_config.yaml --port 8765

# Using Python directly
python -c "
from gateway_agent.server import GatewayServer
server = GatewayServer(config_path='device_config.yaml')
server.start(host='0.0.0.0', port=8765)
"
```

### Verify

```bash
# Check server health
gateway-agent status --url http://localhost:8765

# Or with curl
curl http://localhost:8765/gateway/health
```

---

## Endpoint Documentation

The Gateway Agent exposes 10 REST API endpoints under the `/gateway/` prefix:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gateway/health` | GET | Health check with uptime, device status, and protocol version |
| `/gateway/backends` | GET | List available quantum backends with qubit count, gates, and status |
| `/gateway/execute` | POST | Execute a quantum circuit on the device |
| `/gateway/transpile` | POST | Transpile a circuit for device-native gates |
| `/gateway/job/{job_id}` | GET | Get job status and results by job ID |
| `/gateway/providers` | GET | List provider information (type, technology, backends) |
| `/gateway/message` | POST | Handle generic gateway protocol messages |
| `/gateway/qec/simulate` | POST | Full QEC simulation (surface/color codes, MWPM/Union-Find/Lookup decoders) |
| `/gateway/qec/decode-syndrome` | POST | Single syndrome measurement decoding |
| `/gateway/qec/bb-decoder` | POST | BB Code qLDPC decoder (4 families: bb_72_12_6, bb_90_8_10, bb_144_12_12, bb_288_12_18) |

### POST /gateway/execute

Execute a quantum circuit.

**Request Body:**
```json
{
  "circuit": {
    "num_qubits": 2,
    "gates": [
      {"gate": "h", "qubits": [0]},
      {"gate": "cx", "qubits": [0, 1]},
      {"gate": "measure", "qubits": [0]},
      {"gate": "measure", "qubits": [1]}
    ]
  },
  "shots": 1024,
  "backend": "",
  "options": {}
}
```

**Response:**
```json
{
  "job_id": "sim_a1b2c3d4",
  "counts": {"00": 512, "11": 512},
  "shots": 1024,
  "execution_time_ms": 2.34,
  "success": true,
  "backend": "local_simulator",
  "provider": "custom",
  "server": "researcher_gateway",
  "metadata": {"simulator": "local_simulator", "evidence_hash": "sha256..."}
}
```

### POST /gateway/transpile

Transpile a circuit for the device's native gate set.

**Request Body:**
```json
{
  "circuit": {
    "num_qubits": 2,
    "gates": [{"gate": "h", "qubits": [0]}]
  },
  "backend": "",
  "optimization_level": 1
}
```

### POST /gateway/message

Handle a generic gateway protocol message (envelope format).

**Request Body:**
```json
{
  "type": "execute_circuit",
  "payload": {
    "circuit": {"num_qubits": 2, "gates": [...]},
    "shots": 1024
  },
  "version": "1.0",
  "source": "swiftquantum_backend",
  "target": "researcher_lab",
  "correlation_id": "uuid"
}
```

**Supported Message Types:**
- `health_check` -- Returns health status
- `list_backends` -- Returns backend information
- `execute_circuit` -- Executes circuit and returns results

---

## Configuration Reference (`device_config.yaml`)

```yaml
# Server settings
server:
  name: "researcher_gateway"     # Server display name
  id: "gw_001"                   # Unique server identifier
  host: "0.0.0.0"               # Bind address
  port: 8765                     # Listen port
  cors_origins:                  # Allowed CORS origins
    - "*"

# Device hardware settings
device:
  name: "local_simulator"       # Device/backend name
  num_qubits: 20                # Number of qubits
  technology: "simulator"       # Technology type (simulator, superconducting, trapped_ion, etc.)
  connectivity: "full"          # Connectivity topology (full, grid, heavy_hex, linear, etc.)
  supported_gates:              # List of supported gate types
    - h
    - x
    - y
    - z
    - cx
    - rx
    - ry
    - rz
    - measure
  max_shots: 1000000            # Maximum shots per execution

# Authentication (optional)
auth:
  enabled: false                # Enable token authentication
  token: "${GATEWAY_AUTH_TOKEN}" # Auth token (resolved from environment)

# Cloud registration (optional)
registration:
  auto_register: false          # Auto-register with SwiftQuantum cloud on startup
  swiftquantum_url: "https://api.swiftquantum.com"
  api_key: "${SWIFTQUANTUM_API_KEY}"

# Logging
logging:
  level: "INFO"                 # DEBUG, INFO, WARNING, ERROR
  format: "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
```

**Environment Variable Resolution:** Any value in the format `${ENV_VAR}` is automatically resolved from the corresponding environment variable at startup.

---

## Custom Device Interface Implementation Guide

To connect your own quantum hardware to the Gateway Agent, implement the `DeviceInterface` abstract base class.

### Step 1: Create your device class

```python
from gateway_agent.device_interface import DeviceInterface, DeviceInfo, ExecutionResult

class MyLabDevice(DeviceInterface):
    """Custom device interface for my lab's quantum hardware."""

    def __init__(self, hardware_url: str):
        self.hardware_url = hardware_url

    def get_device_info(self) -> DeviceInfo:
        """Return device hardware information."""
        return DeviceInfo(
            name="my_lab_qpu",
            num_qubits=5,
            technology="superconducting",
            connectivity="linear",
            supported_gates=["h", "cx", "rx", "ry", "rz", "x", "z", "measure"],
            max_shots=10000,
            status="online",
            metadata={"lab": "Quantum Physics Lab", "version": "2.0"},
        )

    def execute(self, circuit, shots, options=None):
        """Execute a quantum circuit on your hardware."""
        import time, hashlib

        start = time.time()
        job_id = f"lab_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"

        # --- Replace this with your actual hardware execution ---
        # result_counts = my_hardware_api.run(circuit, shots)
        result_counts = {"00": shots // 2, "11": shots // 2}  # placeholder
        # --------------------------------------------------------

        elapsed = (time.time() - start) * 1000
        return ExecutionResult(
            job_id=job_id,
            counts=result_counts,
            shots=shots,
            execution_time_ms=elapsed,
            success=True,
            metadata={"device": "my_lab_qpu"},
        )

    def get_status(self):
        """Return current device status."""
        return {
            "status": "online",
            "device": "my_lab_qpu",
            "type": "superconducting",
            "num_qubits": 5,
        }

    def transpile(self, circuit, optimization_level=1):
        """Optional: transpile circuit to device-native gates."""
        # Implement device-specific transpilation here
        return circuit

    def validate_circuit(self, circuit):
        """Optional: add custom validation rules."""
        errors = super().validate_circuit(circuit)
        # Add your own validation
        return errors
```

### Step 2: Use your device with the server

```python
from gateway_agent.server import GatewayServer
from my_device import MyLabDevice

device = MyLabDevice(hardware_url="http://my-hardware:9000")
server = GatewayServer(config_path="device_config.yaml", device=device)
server.start(host="0.0.0.0", port=8765)
```

### DeviceInterface Methods

| Method | Required | Description |
|--------|----------|-------------|
| `get_device_info()` | Yes | Return `DeviceInfo` with hardware specifications |
| `execute(circuit, shots, options)` | Yes | Execute circuit and return `ExecutionResult` |
| `get_status()` | Yes | Return current device status dictionary |
| `transpile(circuit, optimization_level)` | No | Transpile circuit to native gates (default: passthrough) |
| `validate_circuit(circuit)` | No | Validate circuit constraints (default: qubit count + gate support) |

---

## CLI Reference

```bash
# Start the gateway server
gateway-agent start [--config PATH] [--host HOST] [--port PORT] [--reload] [--log-level LEVEL]

# Check server status
gateway-agent status [--url URL]

# Register with SwiftQuantum cloud
gateway-agent register --url API_URL [--token TOKEN] [--config PATH]
```

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| fastapi | >=0.104.0 | REST API framework |
| uvicorn | >=0.24.0 | ASGI server |
| pydantic | >=2.0.0 | Request/response validation |
| pyyaml | >=6.0 | YAML configuration parsing |

**Python:** >=3.10

---

## License

MIT License
# gateway-agent

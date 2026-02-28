# Q-Bridge Gateway Agent

Self-hosted quantum hardware gateway for researchers. The Gateway Agent is a standalone FastAPI server that implements the SwiftQuantum Gateway Protocol, allowing researchers to expose their quantum hardware (or simulators) to the SwiftQuantum ecosystem through a standardized REST API.

## Overview

The Gateway Agent bridges researcher-owned quantum devices with the SwiftQuantum platform. Researchers run this agent alongside their quantum hardware, and the agent handles circuit execution, transpilation, job management, and health monitoring through a uniform API surface.

**Key Features:**
- 10 REST API endpoints conforming to the SwiftQuantum Gateway Protocol (including QEC delegation)
- Pluggable `DeviceInterface` for connecting any quantum hardware
- Built-in `LocalSimulator` for testing and development
- JSON/YAML configuration with `${ENV_VAR}` placeholder resolution
- CLI tool for server management, status checking, and cloud registration
- Docker support for containerized deployment
- CORS support for cross-origin access

---

## Quick Start

### Install

```bash
# From PyPI
pip install qbridge-gateway

# From source
git clone https://github.com/Minapak/qbridge-gateway.git
cd qbridge-gateway
pip install -e .
```

### Initialize Config

```bash
qbridge-gateway init --config=config.json
```

### Configure

Edit `config.json` to match your hardware setup:

```json
{
  "server": {
    "name": "my_lab_gateway",
    "id": "gw_001",
    "host": "0.0.0.0",
    "port": 8090
  },
  "device": {
    "name": "my_qpu",
    "num_qubits": 20,
    "technology": "superconducting",
    "connectivity": "grid",
    "supported_gates": ["h", "cx", "rx", "ry", "rz", "x", "y", "z", "measure"],
    "max_shots": 100000
  }
}
```

### Run

```bash
# Using the CLI
qbridge-gateway start --config=config.json

# Using Python directly
python -c "
from gateway_agent.server import GatewayServer
server = GatewayServer(config_path='config.json')
server.start(host='0.0.0.0', port=8090)
"
```

### Docker

```bash
# Build
docker build -t qbridge/gateway:latest .

# Run
docker run -d -p 8090:8090 \
  -v ./config.json:/app/config.json \
  qbridge/gateway:latest
```

### Verify

```bash
# Check server health
qbridge-gateway status --url http://localhost:8090

# Or with curl
curl http://localhost:8090/gateway/health
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

---

## Configuration Reference

The gateway supports both JSON (`config.json`) and YAML (`device_config.yaml`) configuration files.

```json
{
  "server": {
    "name": "researcher_gateway",
    "id": "gw_001",
    "host": "0.0.0.0",
    "port": 8090,
    "cors_origins": ["*"]
  },
  "device": {
    "name": "local_simulator",
    "num_qubits": 20,
    "technology": "simulator",
    "connectivity": "full",
    "supported_gates": ["h", "x", "y", "z", "cx", "rx", "ry", "rz", "measure"],
    "max_shots": 1000000
  },
  "auth": {
    "enabled": false,
    "token": "${GATEWAY_AUTH_TOKEN}"
  },
  "registration": {
    "auto_register": false,
    "swiftquantum_url": "https://api.swiftquantum.tech",
    "api_key": "${SWIFTQUANTUM_API_KEY}"
  }
}
```

**Environment Variable Resolution:** Any value in the format `${ENV_VAR}` is automatically resolved from the corresponding environment variable at startup.

---

## Custom Device Interface

To connect your own quantum hardware, implement the `DeviceInterface` abstract base class:

```python
from gateway_agent.device_interface import DeviceInterface, DeviceInfo, ExecutionResult

class MyLabDevice(DeviceInterface):
    def get_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name="my_lab_qpu", num_qubits=5,
            technology="superconducting", connectivity="linear",
            supported_gates=["h", "cx", "rx", "ry", "rz", "measure"],
            max_shots=10000,
        )

    def execute(self, circuit, shots, options=None):
        # Connect to your hardware here
        return ExecutionResult(job_id="lab_001", counts={"00": 512, "11": 512},
                               shots=shots, execution_time_ms=2.3, success=True)

    def get_status(self):
        return {"status": "online", "device": "my_lab_qpu", "num_qubits": 5}
```

```python
from gateway_agent.server import GatewayServer
device = MyLabDevice()
server = GatewayServer(config_path="config.json", device=device)
server.start(host="0.0.0.0", port=8090)
```

---

## CLI Reference

```bash
# Generate config file
qbridge-gateway init [--config PATH] [--force]

# Start the gateway server
qbridge-gateway start [--config PATH] [--host HOST] [--port PORT] [--reload] [--log-level LEVEL]

# Check server status
qbridge-gateway status [--url URL]

# Register with SwiftQuantum cloud
qbridge-gateway register --url API_URL [--token TOKEN] [--config PATH]
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

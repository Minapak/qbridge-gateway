# Gateway Agent Architecture

**Version:** 1.1.0 | **Last Updated:** 2026-02-11

## Overview

The Gateway Agent is a gRPC-based device gateway that bridges the SwiftQuantum ecosystem with quantum hardware backends. It provides provider discovery, backend management, and job execution capabilities.

## Architecture

```
+-------------------------------------------------------------+
|                    Gateway Agent                              |
+-------------------------------------------------------------+
|                                                              |
|  +--------------+  +--------------+  +------------------+   |
|  |  Provider     |  |  Backend     |  |  Job Execution   |   |
|  |  Discovery    |  |  Management  |  |  Engine          |   |
|  |  - List       |  |  - List      |  |  - Submit        |   |
|  |  - Filter     |  |  - Status    |  |  - Execute       |   |
|  |  - Resolve    |  |  - Health    |  |  - Monitor       |   |
|  +--------------+  +--------------+  +------------------+   |
|                                                              |
|  +------------------------------------------------------+    |
|  |              Device Configuration                     |    |
|  |  - YAML-based config (device_config.yaml)             |    |
|  |  - Provider type, endpoint, auth token                |    |
|  |  - Protocol (REST/gRPC/Qiskit Runtime)                |    |
|  |  - Qubit count, native gate set, topology             |    |
|  +------------------------------------------------------+    |
|                                                              |
+-------------------------------------------------------------+
                            |
                            v
+-------------------------------------------------------------+
|                  Quantum Hardware Backends                    |
+----------+----------+----------+-----------+----------------+
|   IBM    |   IonQ   | Rigetti  |Quantinuum |  Custom Lab    |
+----------+----------+----------+-----------+----------------+
```

## QEC Delegation Flow (v8.1.0)

```
┌──────────┐  HTTPS   ┌──────────────────┐  HTTP   ┌──────────────────┐
│ iOS App  │ ────────▶│ Fargate Backend  │ ───────▶│  Gateway Agent   │
│(Q-Bridge)│          │ (routing layer)  │         │  (computation)   │
└──────────┘          └──────────────────┘         │                  │
                                                   │ /qec/simulate    │
                                                   │ /qec/decode      │
                                                   │ /qec/bb-decoder  │
                                                   └──────────────────┘
```

Gateway Agent serves as the computation engine for:
- **QEC Simulation**: Surface/color code simulation with MWPM, Union-Find, Lookup decoders
- **Syndrome Decoding**: Single syndrome measurement analysis with correction proposals
- **BB Code Decoding**: Bivariate bicycle code qLDPC decoder (4 code families)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gateway/providers` | GET | List available quantum providers |
| `/gateway/backends` | GET | List available backends |
| `/gateway/execute` | POST | Execute quantum job on backend |
| `/gateway/submit` | POST | Submit job (alias for execute) |

## Configuration

### Device Config (`device_config.yaml`)
```yaml
devices:
  - name: "device_name"
    provider: "ibm"
    endpoint: "https://..."
    auth_token: "..."
    protocol: "qiskit_runtime"
    qubits: 127
    native_gates: ["id", "rz", "sx", "x", "ecr"]
    topology: "heavy_hex"
```

### Environment Variables (`.env.example`)
- `GATEWAY_HOST` — Gateway server host
- `GATEWAY_PORT` — Gateway server port
- `LOG_LEVEL` — Logging level
- `AUTH_SECRET` — Authentication secret

## Integration

The Gateway Agent integrates with:
- **SwiftQuantumBackend**: Registered as gateway router in main.py
- **Q-Bridge iOS App**: Consumed via QBJobService gateway endpoints
- **QuantumBridge**: Plugin-based hardware tools integration
- **swiftquantum-java**: HardwareConfigAdapter interface
- **swiftquantum-link-python**: XanaduHUDAdapter for photonic backends

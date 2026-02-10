# Gateway Agent Features

**Version:** 1.1.0 | **Last Updated:** 2026-02-11

## Core Features

### Provider Discovery
- Dynamic quantum provider listing
- Provider metadata (technology, connectivity, native gates)
- Multi-provider support (IBM, IonQ, Rigetti, Quantinuum, Custom)

### Backend Management
- Backend listing with status monitoring
- Health check and connectivity testing
- Qubit count and topology information
- Native gate set reporting

### Job Execution
- Quantum circuit submission to hardware backends
- Job status monitoring and result retrieval
- Multi-protocol support (REST, gRPC, Qiskit Runtime)

### Device Configuration
- YAML-based device configuration
- Dynamic device discovery
- Hot-reload configuration support

### QEC Delegation (v8.1.0)
- QEC simulation: Surface/color code with MWPM, Union-Find, Lookup decoders
- Syndrome decoding: Single syndrome measurement analysis with correction proposals
- BB Code decoding: Bivariate bicycle qLDPC decoder (4 code families)
- 6 new protocol MessageTypes for WebSocket QEC communication
- Automatic computation delegation from Fargate backend

## API Reference

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/gateway/providers` | GET | List providers | Yes |
| `/gateway/backends` | GET | List backends | Yes |
| `/gateway/execute` | POST | Execute job | Yes |
| `/gateway/submit` | POST | Submit job | Yes |
| `/gateway/qec/simulate` | POST | QEC simulation | Yes |
| `/gateway/qec/decode-syndrome` | POST | Syndrome decoding | Yes |
| `/gateway/qec/bb-decoder` | POST | BB Code decoder | Yes |

## Supported Providers

| Provider | Technology | Protocol |
|----------|-----------|----------|
| IBM Quantum | Superconducting | Qiskit Runtime |
| IonQ | Trapped Ion | REST |
| Rigetti | Superconducting | REST |
| Quantinuum | QCCD | REST |
| Custom Lab | Configurable | gRPC |
| Xanadu | Photonic (CV) | REST |

## Integration Points

- SwiftQuantumBackend gateway router
- Q-Bridge iOS QBJobService
- QuantumBridge hardware tools plugin
- swiftquantum-java HardwareConfigAdapter
- swiftquantum-link-python XanaduHUDAdapter

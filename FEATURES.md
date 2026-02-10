# Gateway Agent Features

**Version:** 1.0.0 | **Last Updated:** 2026-02-10

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

## API Reference

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/gateway/providers` | GET | List providers | Yes |
| `/gateway/backends` | GET | List backends | Yes |
| `/gateway/execute` | POST | Execute job | Yes |
| `/gateway/submit` | POST | Submit job | Yes |

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

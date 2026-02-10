# Changelog

All notable changes to Gateway Agent will be documented in this file.

## [1.1.0] - 2026-02-11

### Added - QEC Delegation Endpoints (v8.1.0)

#### Protocol
- `gateway_agent/protocol.py` — 6 new MessageType enum values: QEC_SIMULATE, QEC_SIMULATE_RESULT, QEC_DECODE_SYNDROME, QEC_DECODE_RESULT, BB_DECODER, BB_DECODER_RESULT

#### QEC REST Endpoints
- `POST /gateway/qec/simulate` — Full QEC simulation with threshold model (surface/color codes, MWPM/Union-Find/Lookup decoders)
- `POST /gateway/qec/decode-syndrome` — Single syndrome measurement decoding
- `POST /gateway/qec/bb-decoder` — BB Code qLDPC decoder with 4 families (bb_72_12_6, bb_90_8_10, bb_144_12_12, bb_288_12_18)

#### WebSocket Message Routing
- QEC_SIMULATE, QEC_DECODE_SYNDROME, BB_DECODER message types added to `handle_message()`

### Modified Files
- `gateway_agent/protocol.py` — QEC MessageType additions
- `gateway_agent/server.py` — QEC endpoint handlers and message routing

---

## [1.0.0] - 2026-02-10

### Added - Initial Release
- **gRPC Device Gateway Agent**: Core gateway agent for quantum backend communication
- **Device Configuration**: YAML-based device configuration (device_config.yaml)
- **Provider Discovery**: Dynamic quantum provider/backend discovery
- **Job Execution**: Submit quantum circuits to backend devices
- **Job Submission Alias**: POST /submit endpoint for simplified job submission
- **Environment Configuration**: .env.example with required settings
- **Python Package**: pyproject.toml with project metadata and dependencies

### Files
- gateway_agent/ - Core agent module
- device_config.yaml - Device configuration
- pyproject.toml - Package configuration
- requirements.txt - Python dependencies
- .env.example - Environment template
- README.md - Project documentation

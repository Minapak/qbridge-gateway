# Tab Guide -- Q-Bridge Gateway Agent

> Endpoint reference for the Q-Bridge Gateway Agent REST API. The Gateway Agent is a standalone FastAPI server implementing the SwiftQuantum Gateway Protocol, run by researchers alongside their quantum hardware.

---

## Service Information

- **Service**: Q-Bridge Gateway Agent v1.3.0
- **Framework**: FastAPI
- **Port**: 8090 (default)
- **Protocol**: SwiftQuantum Gateway Protocol v1.0
- **Base URL**: `http://localhost:8090`
- **CLI**: `qbridge-gateway start --config=config.json`
- **License**: MIT

---

## Section 1: Core Gateway Endpoints

Basic gateway operations -- health check, backend discovery, and provider listing.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Health check (uptime, device, protocol version) | GET | `/gateway/health` | No |
| List available quantum backends | GET | `/gateway/backends` | No |
| List provider information | GET | `/gateway/providers` | No |

### Health Response Fields

- `status` -- "healthy"
- `server_name` -- configured server name
- `server_id` -- configured server ID
- `version` -- protocol version
- `uptime_seconds` -- server uptime
- `device` -- device status object

---

## Section 2: Circuit Execution & Transpilation

Endpoints for executing quantum circuits on the connected device and transpiling circuits for device-native gates.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Execute quantum circuit | POST | `/gateway/execute` | No |
| Transpile circuit for device | POST | `/gateway/transpile` | No |

### Execute Request Body

```json
{
  "circuit": {
    "num_qubits": 2,
    "gates": [
      {"gate": "h", "qubits": [0]},
      {"gate": "cx", "qubits": [0, 1]}
    ]
  },
  "shots": 1024,
  "backend": "",
  "options": {}
}
```

### Execute Response Fields

- `job_id` -- unique job identifier
- `counts` -- measurement outcome counts
- `shots` -- number of shots executed
- `execution_time_ms` -- execution duration
- `success` -- execution success flag
- `backend` -- backend name used
- `provider` -- "custom"
- `server` -- server name
- `metadata` -- additional metadata (evidence hash, etc.)

### Transpile Request Body

```json
{
  "circuit": {"num_qubits": 2, "gates": [...]},
  "backend": "",
  "optimization_level": 1
}
```

---

## Section 3: Job Management

Endpoints for tracking and managing submitted quantum jobs.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Get job status and results | GET | `/gateway/job/{job_id}` | No |
| Cancel a running job | POST | `/gateway/job/{job_id}/cancel` | No |

### Job Status Values

- `COMPLETED` -- job finished successfully
- `FAILED` -- job execution failed

---

## Section 4: QEC Delegation (v8.1.0)

QEC (Quantum Error Correction) simulation endpoints delegated from the SwiftQuantum Engine Service. These run threshold-model QEC decoder simulations locally on the gateway.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Full QEC simulation | POST | `/gateway/qec/simulate` | No |
| Decode single syndrome | POST | `/gateway/qec/decode-syndrome` | No |
| BB Code qLDPC decoder | POST | `/gateway/qec/bb-decoder` | No |

### QEC Simulate Request Fields

- `code_type` -- "surface" or "color"
- `decoder_type` -- "mwpm", "union_find", or "lookup"
- `code_distance` -- integer (e.g., 5)
- `physical_error_rate` -- float (e.g., 0.001)
- `shots` -- number of simulation shots
- `num_cycles` -- number of error correction cycles
- `noise_model` -- "depolarizing", "measurement_error", or "idle_error"

### QEC Simulate Response Fields

- `logical_error_rate` -- measured logical error rate
- `physical_error_rate` -- input physical error rate
- `success_count` / `failure_count` / `total_shots`
- `syndrome_history` -- per-cycle syndrome grid with detected errors
- `avg_decoding_time_ms` -- average decoder time
- `engine_used` -- "gateway_agent_qec_sim"
- `delegated` -- true (indicates gateway delegation)

### BB Decoder Code Families

| Family | n (data qubits) | k (logical qubits) | d (distance) | Encoding Rate |
|--------|-----------------|---------------------|--------------|---------------|
| `bb_72_12_6` | 72 | 12 | 6 | 16.7% |
| `bb_90_8_10` | 90 | 8 | 10 | 8.9% |
| `bb_144_12_12` | 144 | 12 | 12 | 8.3% |
| `bb_288_12_18` | 288 | 12 | 18 | 4.2% |

### BB Decoder Types

- `bp_osd` -- Belief Propagation + Ordered Statistics Decoding
- `mwpm` -- Minimum Weight Perfect Matching
- `union_find` -- Union-Find decoder
- `lookup_table` -- Lookup table decoder

---

## Section 5: Generic Protocol Message

A unified endpoint for handling any SwiftQuantum Gateway Protocol message. Dispatches internally based on message type.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Handle protocol message | POST | `/gateway/message` | No |

### Supported Message Types

| Message Type | Description |
|-------------|-------------|
| `HEALTH_CHECK` | Health check via protocol |
| `LIST_BACKENDS` | List backends via protocol |
| `EXECUTE_CIRCUIT` | Execute circuit via protocol |
| `QEC_SIMULATE` | QEC simulation via protocol |
| `QEC_DECODE_SYNDROME` | Syndrome decode via protocol |
| `BB_DECODER` | BB code decoder via protocol |

### Message Request Body

```json
{
  "type": "EXECUTE_CIRCUIT",
  "payload": {"circuit": {...}, "shots": 1024},
  "version": "1.0",
  "source": "client_id",
  "target": "gateway_id",
  "correlation_id": "req_123"
}
```

---

## All Endpoints Summary

| # | Method | URL | Description |
|---|--------|-----|-------------|
| 1 | GET | `/gateway/health` | Health check |
| 2 | GET | `/gateway/backends` | List backends |
| 3 | GET | `/gateway/providers` | List providers |
| 4 | POST | `/gateway/execute` | Execute circuit |
| 5 | POST | `/gateway/transpile` | Transpile circuit |
| 6 | GET | `/gateway/job/{job_id}` | Job status |
| 7 | POST | `/gateway/job/{job_id}/cancel` | Cancel job |
| 8 | POST | `/gateway/qec/simulate` | QEC simulation |
| 9 | POST | `/gateway/qec/decode-syndrome` | Syndrome decode |
| 10 | POST | `/gateway/qec/bb-decoder` | BB code decoder |
| 11 | POST | `/gateway/message` | Protocol message |

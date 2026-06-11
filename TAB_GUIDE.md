# Tab Guide -- Q-Bridge Gateway Agent

> Endpoint reference for the Q-Bridge Gateway Agent REST API. The Gateway Agent is a standalone FastAPI server implementing the SwiftQuantum Gateway Protocol, run by researchers alongside their quantum hardware.

---

## Service Information

- **Service**: Q-Bridge Gateway Agent v1.4.0 (real numpy compute, ECS `qbridge-gateway:4`)
- **Framework**: FastAPI
- **Port**: 8090 (default)
- **Protocol**: SwiftQuantum Gateway Protocol v1.0
- **Base URL**: `http://localhost:8090` (production: `https://qbridge-api.swiftquantum.tech`, AWS ECS Fargate)
- **CLI**: `qbridge-gateway start --config=config.json`
- **License**: MIT

---

## Section 1: Core Gateway Endpoints

Basic gateway operations -- health check, backend discovery, and provider listing.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Health check (uptime, device, protocol version) | GET | `/gateway/health` (+ `/health` alias) | No (public) |
| List available quantum backends | GET | `/gateway/backends` | Yes |
| List provider information | GET | `/gateway/providers` | Yes |

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

> **Real compute (v1.4.0):** `/gateway/execute` runs a real dense numpy
> statevector engine — real gate unitaries → Born-rule probabilities →
> seeded RNG sampling (same circuit + shots = identical counts), capped at
> **20 qubits**, unsupported gates error out (no fabrication). A Bell circuit
> yields a reproducible ~50/50 over `{00, 11}`. `/gateway/transpile` is a real
> basis-decomposition pass (SWAP → 3×CX, etc.) returning real gate-count /
> depth metrics.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Execute quantum circuit (real statevector sim) | POST | `/gateway/execute` | No |
| Transpile circuit (real basis decomposition) | POST | `/gateway/transpile` | No |

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

## Section 4: QEC Delegation (real compute, v1.4.0)

QEC (Quantum Error Correction) endpoints delegated from the Q-Bridge backend (bridge-service, via `QUANTUMBRIDGE_GATEWAY_URL`). Per-endpoint real status:

- **`/gateway/qec/simulate`** — REAL seeded distance-d **repetition-code Monte-Carlo**: inject X errors over rounds → parity-check syndromes → MWPM/union-find/lookup decode → empirical logical error rate. `method = monte_carlo_repetition_code_seeded`. Deterministic for fixed inputs.
- **`/gateway/qec/decode-syndrome`** — REAL deterministic per-stabilizer decode. `method = deterministic_repetition_decode`.
- **`/gateway/qec/bb-decoder`** — HONEST deterministic **analytic** threshold estimate, **NOT** a full BP-OSD Monte-Carlo. `method = analytic_threshold_estimate` + a `notes` field saying so.

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Repetition-code Monte-Carlo QEC sim | POST | `/gateway/qec/simulate` | No |
| Decode single syndrome (deterministic) | POST | `/gateway/qec/decode-syndrome` | No |
| BB qLDPC analytic threshold estimate | POST | `/gateway/qec/bb-decoder` | No |

### QEC Simulate Request Fields

- `code_type` -- "surface" or "color"
- `decoder_type` -- "mwpm", "union_find", or "lookup"
- `code_distance` -- integer (e.g., 5)
- `physical_error_rate` -- float (e.g., 0.001)
- `shots` -- number of simulation shots
- `num_cycles` -- number of error correction cycles
- `noise_model` -- "depolarizing", "measurement_error", or "idle_error"

### QEC Simulate Response Fields

- `logical_error_rate` -- **empirically measured** logical error rate over the shots
- `physical_error_rate` -- input physical error rate
- `success_count` / `failure_count` / `total_shots`
- `syndrome_history` -- per-cycle syndrome grid with detected errors
- `avg_decoding_time_ms` -- average decoder time
- `engine_used` -- "gateway_agent_qec_sim"
- `method` -- "monte_carlo_repetition_code_seeded"
- `delegated` -- true (indicates gateway delegation)

### BB Decoder Code Families

Full names only — short forms / unknown families → **400**.

| Family | n (data qubits) | k (logical qubits) | d (distance) | Encoding Rate |
|--------|-----------------|---------------------|--------------|---------------|
| `bb_72_12_6` | 72 | 12 | 6 | 16.7% |
| `bb_90_8_10` | 90 | 8 | 10 | 8.9% |
| `bb_144_12_12` | 144 | 12 | 12 | 8.3% |
| `bb_288_12_18` | 288 | 12 | 18 | 4.2% |

> **Honesty note:** this endpoint returns a **deterministic analytic
> threshold estimate** (`method = analytic_threshold_estimate`), NOT a full
> BP-OSD Monte-Carlo — the `notes` field in the response says so. The logical
> error rate uses `p_L = 0.03·(p/p_th)^ceil(d/2)` accumulated over `rounds`.
> Example: `bb_144_12_12` at `p=0.001` (decoder `bp_osd`, d=12, p_th=0.0110)
> → per-round `p_L ≈ 1.6934e-08` (`1.69342e-07` over 10 rounds).

### BB Decoder Types (selects the threshold p_th used in the analytic model)

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

## Section 5b: Q-Logos Backend Proxy (v1.4.0)

A pass-through proxy that forwards requests to the Q-Logos backend (`QLOGOS_BACKEND_URL`, prod `https://qlogos-api.swiftquantum.tech`).

### API Endpoints

| Action | Method | URL | Auth |
|--------|--------|-----|------|
| Proxy to Q-Logos backend | GET/POST/PUT/PATCH/DELETE | `/gateway/qlogos/{path:path}` | Yes |

---

## Section 6: Auth & Rate Limiting

All endpoints require Bearer token authentication via the `GatewayAuthRateLimitMiddleware`, except the public paths `/gateway/health`, `/docs`, and `/openapi.json`. (When `GATEWAY_API_KEY` is empty the gateway runs in dev mode with auth disabled.)

### Authentication

| Header | Value |
|--------|-------|
| `Authorization` | `Bearer {GATEWAY_API_KEY}` |

- **GATEWAY_API_KEY** can be set via environment variable or config file
- Token comparison uses `hmac.compare_digest` (constant-time) to prevent timing attacks

### Rate Limiting

- **Default**: 60 requests/minute per client (sliding window)
- **Configurable**: Override via config file
- **Response**: `429 Too Many Requests` when limit exceeded

### CORS Policy

- **Allowed origins**: swiftquantum.tech domains (+ localhost) only (previously `["*"]`)
- **Allowed methods**: GET, POST, OPTIONS
- **Blocked methods**: PUT, DELETE, PATCH (at the CORS layer; the `/gateway/qlogos` proxy still accepts these server-side)

---

## All Endpoints Summary

| # | Method | URL | Description |
|---|--------|-----|-------------|
| 1 | GET | `/gateway/health` (+ `/health` alias) | Health check |
| 2 | GET | `/gateway/backends` | List backends |
| 3 | GET | `/gateway/providers` | List providers |
| 4 | POST | `/gateway/execute` | Execute circuit |
| 5 | POST | `/gateway/transpile` | Transpile circuit |
| 6 | GET | `/gateway/job/{job_id}` | Job status |
| 7 | POST | `/gateway/job/{job_id}/cancel` | Cancel job |
| 8 | POST | `/gateway/qec/simulate` | QEC simulation |
| 9 | POST | `/gateway/qec/decode-syndrome` | Syndrome decode |
| 10 | POST | `/gateway/qec/bb-decoder` | BB code decoder |
| 11 | ANY | `/gateway/qlogos/{path:path}` | Q-Logos backend proxy |
| 12 | POST | `/gateway/message` | Protocol message |

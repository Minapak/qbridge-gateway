# Gateway Agent Architecture

**Version:** 1.4.0 (real numpy compute) | **Last Updated:** 2026-06-11

## Overview

The Gateway Agent is a FastAPI REST device gateway that bridges the SwiftQuantum ecosystem with quantum hardware backends (or simulators). It provides provider discovery, backend management, real circuit execution, QEC delegation, and a Q-Logos backend pass-through proxy. In production it runs on AWS ECS Fargate behind the shared `sq-unified-alb`.

As of **v1.4.0 (2026-06-11)** the compute paths are no longer mocked. The `LocalSimulator` is a real dense numpy statevector engine, QEC simulation is a real seeded repetition-code Monte-Carlo, and the BB qLDPC endpoint is an honest deterministic analytic threshold estimate (clearly labelled, not a full BP-OSD simulation).

## Compute Engines (v1.4.0)

### Real statevector simulator (`device_interface.py` → `LocalSimulator`)
- Builds the exact complex statevector on `|0…0⟩` by applying real numpy gate unitaries: H, X, Y, Z, S, Sdg, T, Tdg, RX/RY/RZ (with angle), CX/CNOT, CZ, SWAP, CCX/Toffoli; measure/barrier/id are no-ops for state evolution.
- Little-endian bit ordering (qubit 0 = least-significant bit of the basis index).
- Computes Born-rule `|amplitude|²` probabilities and samples `shots` outcomes with a numpy RNG **seeded** from the SHA-256 of a canonical JSON encoding of `{circuit, shots}` → reproducible (same circuit + shots = identical counts).
- Capped at **20 qubits** (`MAX_STATEVECTOR_QUBITS`; a 20-qubit complex128 statevector is ≈16 MB). Unsupported gates raise `ValueError` — no fabricated output.
- `transpile()` is a real basis-decomposition pass (SWAP → 3×CX, Sdg/Tdg → RZ, CNOT → CX) that reports real single-/two-qubit gate counts, basis-gate list, and depth (greedy per-qubit layering).

### Real QEC Monte-Carlo (`server.py` → `_qec_monte_carlo`)
- Distance-d repetition code: `d` data qubits, `d−1` parity checks. Injects X errors at rate `p` (× a noise-model multiplier) per data qubit per round across `num_cycles` rounds with a **seeded** numpy RNG, computes parity-check syndromes (`s_i = e_i ⊕ e_{i+1}`), and decodes:
  - **mwpm / union_find** — minimum-weight pairing of adjacent syndrome defects on the 1-D chain;
  - **lookup** — majority-vote / threshold decode.
- Counts a logical-X failure when the decoded register has odd residual parity, and reports the **empirical** logical error rate over the shots. `method = monte_carlo_repetition_code_seeded`. All `random.gauss`/`random.uniform` removed.
- `/gateway/qec/decode-syndrome` performs a deterministic per-stabilizer decode (`method = deterministic_repetition_decode`).

### Honest BB analytic model (`server.py` → `/gateway/qec/bb-decoder`)
- Bivariate-Bicycle qLDPC analysis for 4 families: `bb_72_12_6`, `bb_90_8_10`, `bb_144_12_12`, `bb_288_12_18`.
- **Deterministic analytic** sub-threshold scaling `p_L = 0.03·(p/p_th)^ceil(d/2)`, accumulated over `rounds` (saturating toward 0.5 above threshold). Example: `bb_144_12_12` at `p=0.001` (bp_osd, d=12, p_th=0.0110) → per-round `p_L ≈ 1.6934e-08` (`1.69342e-07` over 10 rounds).
- Response carries `method = "analytic_threshold_estimate"` and a `notes` field stating it is **NOT** a full BP-OSD Monte-Carlo. Full-name-only validation: short forms / unknown families → 400.
- Requires `numpy>=1.24` (hard dependency).

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
|  |  - JSON/YAML config (config.json or device_config.yaml)|    |
|  |  - Provider type, endpoint, auth token                |    |
|  |  - Protocol (REST)                                    |    |
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

Gateway Agent serves as the **real computation engine** for the Q-Bridge backend (bridge-service). The backend delegates to this gateway via the `QUANTUMBRIDGE_GATEWAY_URL` env var (pointing at `qbridge-api.swiftquantum.tech`); it does not compute QEC/BB locally. The gateway runs:
- **QEC Simulation**: real seeded distance-d repetition-code Monte-Carlo with MWPM / Union-Find / Lookup decoders (empirical logical error rate)
- **Syndrome Decoding**: deterministic single-syndrome decode with correction proposals
- **BB Code Decoding**: honest deterministic **analytic** qLDPC threshold estimate (4 code families) — explicitly labelled, NOT a full BP-OSD Monte-Carlo

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/gateway/providers` | GET | List available quantum providers |
| `/gateway/backends` | GET | List available backends |
| `/gateway/execute` | POST | Execute quantum job on backend |
| `/gateway/transpile` | POST | Transpile circuit for device-native gates |
| `/gateway/job/{job_id}` | GET | Get job status and results |
| `/gateway/job/{job_id}/cancel` | POST | Cancel a running job |
| `/gateway/qec/simulate` | POST | Real seeded repetition-code Monte-Carlo |
| `/gateway/qec/decode-syndrome` | POST | Deterministic single-syndrome decode |
| `/gateway/qec/bb-decoder` | POST | Honest analytic BB qLDPC threshold estimate |
| `/gateway/qlogos/{path:path}` | ANY | Q-Logos backend pass-through proxy |
| `/gateway/message` | POST | Generic gateway protocol message |

> Note: there is no `/gateway/submit` endpoint — job submission is done via `/gateway/execute`.

## Configuration

### Device Config (`device_config.yaml`)
```yaml
devices:
  - name: "device_name"
    provider: "custom"
    endpoint: "https://..."
    auth_token: "..."
    protocol: "rest"
    qubits: 20
    native_gates: ["h", "x", "y", "z", "cx", "rx", "ry", "rz", "measure"]
    topology: "full"
```

### Environment Variables (`.env.example`)
- `GATEWAY_HOST` — Gateway server host
- `GATEWAY_PORT` — Gateway server port
- `LOG_LEVEL` — Logging level
- `AUTH_SECRET` — Authentication secret

## Auth & Rate Limiting Middleware

```
Request → GatewayAuthRateLimitMiddleware
           ├── Bearer token validation (hmac.compare_digest, constant-time)
           ├── Sliding-window rate limiter (60 req/min default, configurable)
           └── CORS: swiftquantum.tech domains (+ localhost) only, GET/POST/OPTIONS
```

- **GATEWAY_API_KEY**: Loaded from environment variable or config file; auth disabled (dev mode) when empty
- **Rate limit**: 60 requests/minute default, configurable per deployment
- **CORS**: Restricted from `["*"]` to swiftquantum.tech production domains (+ localhost)
- **Allowed methods**: GET, POST, OPTIONS only (CORS)
- **PUBLIC_PATHS** (no auth): `/gateway/health`, `/docs`, `/openapi.json` (note: the `/health` alias is not in PUBLIC_PATHS)

## Production Deployment (AWS ECS Fargate)

Production runs on AWS ECS Fargate, region ap-northeast-2, account 470485006174. The v1.4.0 real-compute build deployed as task def `qbridge-gateway:4` on 2026-06-11.

```
qbridge-api.swiftquantum.tech ──▶ sq-unified-alb (listener rule priority 21)
                                       │
                                       ▼  uni-qbridge-gw-tg (port 8090, hc /gateway/health)
                                  ECS service qbridge-gateway-service
                                  (cluster swiftquantum-production-cluster)
                                  task def qbridge-gateway:4 · ARM64 256 CPU / 512 MB · 1 task
                                       │  image: ECR swiftquantum/qbridge-gateway
                                       ▼
                                  CloudWatch /ecs/qbridge-gateway (30d)
```

- The `qbridge.swiftquantum.tech` host routes the web app via `uni-bridge-web-tg`.
- A `/health` alias is registered so `qbridge-api` passes the 9/9 sq-unified-alb health matrix.
- Env: `QLOGOS_BACKEND_URL=https://qlogos-api.swiftquantum.tech` (used by the `/gateway/qlogos/{path}` proxy).
- The Q-Bridge backend (bridge-service) reaches this gateway via `QUANTUMBRIDGE_GATEWAY_URL` for QEC/BB delegation.

---

## Integration

The Gateway Agent integrates with:
- **SwiftQuantumBackend**: Registered as gateway router in main.py
- **Q-Bridge iOS App**: Consumed via QBJobService gateway endpoints
- **QuantumBridge**: Plugin-based hardware tools integration
- **swiftquantum-java**: HardwareConfigAdapter interface
- **swiftquantum-link-python**: XanaduHUDAdapter for photonic backends

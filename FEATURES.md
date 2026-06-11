# Gateway Agent Features

**Version:** 1.4.0 (real numpy compute) | **Last Updated:** 2026-06-11

## Core Features

### Provider Discovery
- Dynamic quantum provider listing
- Provider metadata (technology, connectivity, native gates)
- Pluggable `DeviceInterface` with a built-in `LocalSimulator`; researchers attach their own hardware backend

### Backend Management
- Backend listing with status monitoring
- Health check and connectivity testing
- Qubit count and topology information
- Native gate set reporting

### Job Execution
- **Real quantum circuit execution** on the connected backend (`/gateway/execute`). The built-in `LocalSimulator` is a real dense numpy statevector engine: it applies real gate unitaries (H/X/Y/Z/S/T/RX/RY/RZ, CX/CZ/SWAP/CCX), computes Born-rule probabilities, and samples outcomes with a **seeded** numpy RNG (same circuit + shots → identical counts). Capped at **20 qubits**; unsupported gates raise an error rather than fabricating output. A Bell circuit yields a reproducible ~50/50 over `{00, 11}`.
- **Real transpilation** (`/gateway/transpile`): a basis-decomposition pass (SWAP → 3×CX, etc.) reporting real gate counts and circuit depth — not a no-op passthrough.
- Job status monitoring, result retrieval, and cancellation
- REST API over FastAPI

### Q-Logos Proxy
- `ANY /gateway/qlogos/{path}` pass-through proxy to the Q-Logos backend
- Forwards GET/POST/PUT/PATCH/DELETE to `QLOGOS_BACKEND_URL` (added v1.4.0)

### Device Configuration
- JSON/YAML-based device configuration
- `${ENV_VAR}` placeholder resolution at startup
- Dynamic device discovery

### QEC Delegation (real compute, v1.4.0)
- **QEC simulation**: real seeded distance-d **repetition-code Monte-Carlo** (`/gateway/qec/simulate`). Injects X errors at rate `p` over `num_cycles` rounds, computes parity-check syndromes, and decodes via MWPM / Union-Find (min-weight pairing of adjacent defects) or Lookup (majority vote), measuring the **empirical** logical error rate. All `random.*` fudge removed; reproducible via a seeded numpy RNG.
- **Syndrome decoding**: deterministic per-stabilizer decode (`/gateway/qec/decode-syndrome`) with correction proposals — a genuine decode, not a random draw.
- **BB Code decoding**: honest, **deterministic analytic** qLDPC threshold estimate (`/gateway/qec/bb-decoder`) for 4 families (bb_72_12_6, bb_90_8_10, bb_144_12_12, bb_288_12_18). Uses `p_L = 0.03·(p/p_th)^ceil(d/2)` accumulated over rounds; the response carries `method = analytic_threshold_estimate` and a `notes` field stating it is **NOT** a full BP-OSD Monte-Carlo. Full-name-only validation (short forms → 400).
- 6 protocol MessageTypes for QEC communication via `/gateway/message`
- The Q-Bridge backend (bridge-service) delegates this compute to the gateway via `QUANTUMBRIDGE_GATEWAY_URL`

## API Reference

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/gateway/health` (+ `/health` alias) | GET | Health check | No (public) |
| `/gateway/providers` | GET | List providers | Yes |
| `/gateway/backends` | GET | List backends | Yes |
| `/gateway/execute` | POST | Execute job | Yes |
| `/gateway/transpile` | POST | Transpile circuit | Yes |
| `/gateway/job/{job_id}` | GET | Job status | Yes |
| `/gateway/job/{job_id}/cancel` | POST | Cancel job | Yes |
| `/gateway/qec/simulate` | POST | Real seeded repetition-code Monte-Carlo | Yes |
| `/gateway/qec/decode-syndrome` | POST | Deterministic single-syndrome decode | Yes |
| `/gateway/qec/bb-decoder` | POST | Honest analytic BB qLDPC estimate (not BP-OSD) | Yes |
| `/gateway/qlogos/{path}` | ANY | Q-Logos proxy | Yes |
| `/gateway/message` | POST | Protocol message | Yes |

> There is no `/gateway/submit` endpoint; use `/gateway/execute`.

## Supported Providers

Hardware is connected through a single pluggable `DeviceInterface` exposed over
the REST API. Any of the technologies below can be wired in by implementing that
interface; the gateway itself speaks REST.

| Provider | Technology | Protocol |
|----------|-----------|----------|
| IBM Quantum | Superconducting | REST (via DeviceInterface) |
| IonQ | Trapped Ion | REST (via DeviceInterface) |
| Rigetti | Superconducting | REST (via DeviceInterface) |
| Quantinuum | QCCD | REST (via DeviceInterface) |
| Custom Lab | Configurable | REST (via DeviceInterface) |
| Xanadu | Photonic (CV) | REST (via DeviceInterface) |
| Local Simulator | Built-in | In-process |

### Auth & Rate Limiting
- **GatewayAuthRateLimitMiddleware**: Bearer token authentication with sliding-window rate limiter
- CORS restricted to swiftquantum.tech domains (+ localhost; previously `["*"]`)
- Allowed methods: GET, POST, OPTIONS only
- 60 req/min default rate limit, configurable
- GATEWAY_API_KEY support via env var and config file; auth disabled (dev mode) when empty
- hmac.compare_digest constant-time token comparison
- Public paths (no auth): `/gateway/health`, `/docs`, `/openapi.json`

### Production Deployment (v1.4.0 real compute)
- LIVE on AWS ECS Fargate (ap-northeast-2); v1.4.0 real-compute build deployed 2026-06-11
- Cluster `swiftquantum-production-cluster`, service `qbridge-gateway-service`, task def `qbridge-gateway:4` (ARM64, 256 CPU / 512 MB)
- Behind `sq-unified-alb` (target group `uni-qbridge-gw-tg`, port 8090) for host `qbridge-api.swiftquantum.tech`
- `/health` alias present for the 9/9 sq-unified-alb health matrix
- Hard dependency: `numpy>=1.24` (statevector + QEC compute)

## Integration Points

- SwiftQuantumBackend gateway router
- Q-Bridge iOS QBJobService
- QuantumBridge hardware tools plugin
- swiftquantum-java HardwareConfigAdapter
- swiftquantum-link-python XanaduHUDAdapter

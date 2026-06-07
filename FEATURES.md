# Gateway Agent Features

**Version:** 1.5.1 | **Last Updated:** 2026-05-23

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
- Quantum circuit execution on the connected backend (`/gateway/execute`)
- Job status monitoring, result retrieval, and cancellation
- REST API over FastAPI

### Q-Logos Proxy
- `ANY /gateway/qlogos/{path}` pass-through proxy to the Q-Logos backend
- Forwards GET/POST/PUT/PATCH/DELETE to `QLOGOS_BACKEND_URL` (added v1.4.0)

### Device Configuration
- JSON/YAML-based device configuration
- `${ENV_VAR}` placeholder resolution at startup
- Dynamic device discovery

### QEC Delegation (v8.1.0)
- QEC simulation: Surface/color code with MWPM, Union-Find, Lookup decoders
- Syndrome decoding: Single syndrome measurement analysis with correction proposals
- BB Code decoding: Bivariate bicycle qLDPC decoder (4 code families)
- 6 protocol MessageTypes for QEC communication via `/gateway/message`
- Automatic computation delegation from the Fargate backend

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
| `/gateway/qec/simulate` | POST | QEC simulation | Yes |
| `/gateway/qec/decode-syndrome` | POST | Syndrome decoding | Yes |
| `/gateway/qec/bb-decoder` | POST | BB Code decoder | Yes |
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

### Production Deployment (v1.5.0+)
- LIVE on AWS ECS Fargate (ap-northeast-2) since 2026-05-19
- Cluster `swiftquantum-production-cluster`, service `qbridge-gateway-service`, task def `qbridge-gateway:2` (ARM64, 256 CPU / 512 MB)
- Behind `sq-unified-alb` (target group `uni-qbridge-gw-tg`, port 8090) for host `qbridge-api.swiftquantum.tech`
- v1.5.1 added `/health` alias for the 9/9 sq-unified-alb health matrix

## Integration Points

- SwiftQuantumBackend gateway router
- Q-Bridge iOS QBJobService
- QuantumBridge hardware tools plugin
- swiftquantum-java HardwareConfigAdapter
- swiftquantum-link-python XanaduHUDAdapter

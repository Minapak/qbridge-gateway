# Gateway Agent Architecture

**Version:** 1.5.1 | **Last Updated:** 2026-05-23

## Overview

The Gateway Agent is a FastAPI REST device gateway that bridges the SwiftQuantum ecosystem with quantum hardware backends (or simulators). It provides provider discovery, backend management, job execution, QEC delegation, and a Q-Logos backend pass-through proxy. In production it runs on AWS ECS Fargate behind the shared `sq-unified-alb`.

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
| `/gateway/transpile` | POST | Transpile circuit for device-native gates |
| `/gateway/job/{job_id}` | GET | Get job status and results |
| `/gateway/job/{job_id}/cancel` | POST | Cancel a running job |
| `/gateway/qec/simulate` | POST | Full QEC simulation |
| `/gateway/qec/decode-syndrome` | POST | Single syndrome decoding |
| `/gateway/qec/bb-decoder` | POST | BB Code qLDPC decoder |
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

Production has run on AWS ECS Fargate since v1.5.0 (2026-05-19), region ap-northeast-2, account 470485006174.

```
qbridge-api.swiftquantum.tech ──▶ sq-unified-alb (listener rule priority 21)
                                       │
                                       ▼  uni-qbridge-gw-tg (port 8090, hc /gateway/health)
                                  ECS service qbridge-gateway-service
                                  (cluster swiftquantum-production-cluster)
                                  task def qbridge-gateway:2 · ARM64 256 CPU / 512 MB · 1 task
                                       │  image: ECR swiftquantum/qbridge-gateway
                                       ▼
                                  CloudWatch /ecs/qbridge-gateway (30d)
```

- The `qbridge.swiftquantum.tech` host routes the web app via `uni-bridge-web-tg`.
- v1.5.1 added a `/health` alias so `qbridge-api` passes the 9/9 sq-unified-alb health matrix (verified 200 on 2026-05-23).
- Env: `QLOGOS_BACKEND_URL=https://qlogos-api.swiftquantum.tech` (used by the `/gateway/qlogos/{path}` proxy).

---

## Integration

The Gateway Agent integrates with:
- **SwiftQuantumBackend**: Registered as gateway router in main.py
- **Q-Bridge iOS App**: Consumed via QBJobService gateway endpoints
- **QuantumBridge**: Plugin-based hardware tools integration
- **swiftquantum-java**: HardwareConfigAdapter interface
- **swiftquantum-link-python**: XanaduHUDAdapter for photonic backends

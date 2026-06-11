# Operations — qbridge-gateway

Day-to-day operations for the Q-Bridge Gateway Agent (SwiftQuantum
ecosystem node #2). See `MONITORING.md` for signals and
`INCIDENT_RUNBOOK.md` for incident playbooks.

## Environment summary

| Item | Value |
|------|-------|
| Region / Account | `ap-northeast-2` / `470485006174` |
| Cluster | `swiftquantum-production-cluster` |
| Service | `qbridge-gateway-service` |
| Task def | `qbridge-gateway:4` (ARM64, 256 CPU / 512 MB, 1 task; v1.4.0 real numpy compute) |
| ECR repo | `swiftquantum/qbridge-gateway` |
| Host | `qbridge-api.swiftquantum.tech` |
| ALB / TG | `sq-unified-alb` (shared SPOF) / `uni-qbridge-gw-tg` :8090 |
| Listener rule | priority 21 |
| Log group | `/ecs/qbridge-gateway` (30d) |
| Key env | `QLOGOS_BACKEND_URL=https://qlogos-api.swiftquantum.tech`, `GATEWAY_API_KEY` |

## Real compute (v1.4.0, since 2026-06-11)

The gateway now does **real numerical compute** — it is the delegation target
for the Q-Bridge backend's BB/QEC work (bridge-service reaches it via
`QUANTUMBRIDGE_GATEWAY_URL`):
- `/gateway/execute` runs a real **numpy** dense statevector simulator
  (seeded RNG, reproducible). **Capped at 20 qubits** (`MAX_STATEVECTOR_QUBITS`;
  20-qubit complex128 statevector ≈16 MB) — a 20-qubit circuit is the heaviest
  single request and the main driver of `MemoryUtilization`.
- `/gateway/qec/simulate` + `/decode-syndrome` run a real seeded
  repetition-code Monte-Carlo (CPU-bound; scales with `shots × num_cycles`).
- `/gateway/qec/bb-decoder` is a cheap **deterministic analytic** estimate
  (no Monte-Carlo) — explicitly NOT a full BP-OSD sim.
- Hard dependency: **`numpy>=1.24`** (in `requirements.txt` + `pyproject.toml`).
  A missing/broken numpy import breaks execute + QEC at boot — check logs.

## Versioning note (read before reasoning about "current version")

There is known version drift in this repo:
- `pyproject.toml` now says **1.4.0** (the real-compute release);
  `gateway_agent/__init__.py` + FastAPI app version + egg-info still lag at
  **1.3.0**.
- `CHANGELOG.md` / `DEPLOYMENT_LOG.md` record the **v1.4.0 real-compute deploy
  (2026-06-11, ECS `qbridge-gateway:4`)** — this is the **real latest release**
  and what runs in prod. (Older CHANGELOG entries labelled v1.5.x predate this
  re-baselining; the deployed task-def revision `:4` is authoritative.)
- `/gateway/health` returns a hardcoded `"version": "1.0.0"`.

Trust CHANGELOG/DEPLOYMENT_LOG and the deployed ECR image tag / task-def
revision (`qbridge-gateway:4`), not the in-code version strings or the health
payload.

## Build & push image

Dockerfile uses `python:3.11-slim`; build target is ARM64 for Fargate.

```bash
# Authenticate to ECR
aws ecr get-login-password --region ap-northeast-2 \
  | docker login --username AWS --password-stdin \
    470485006174.dkr.ecr.ap-northeast-2.amazonaws.com

# Build ARM64 image (tag pattern: <gitsha>-<UTCstamp>-<label>)
TAG=$(git rev-parse --short HEAD)-$(date -u +%Y%m%d-%H%M%S)
docker buildx build --platform linux/arm64 \
  -t 470485006174.dkr.ecr.ap-northeast-2.amazonaws.com/swiftquantum/qbridge-gateway:$TAG \
  --push .
```

## Deploy

Register a new task def revision pointing at the new image tag, then
update the service. (Console/ARN specifics are environment-dependent.)

```bash
# Roll the service to the new task def revision
aws ecs update-service --cluster swiftquantum-production-cluster \
  --service qbridge-gateway-service \
  --task-definition qbridge-gateway:<new-revision> \
  --region ap-northeast-2

# Or force a fresh task on the current revision
aws ecs update-service --cluster swiftquantum-production-cluster \
  --service qbridge-gateway-service --force-new-deployment \
  --region ap-northeast-2
```

### Post-deploy verification (required)

```bash
# Both health paths must be 200 (9/9 sq-unified-alb matrix)
curl -m 6 -i https://qbridge-api.swiftquantum.tech/gateway/health
curl -m 6 -i https://qbridge-api.swiftquantum.tech/health

# Auth enforced (non-public path without token → 401/403)
curl -m 6 -i https://qbridge-api.swiftquantum.tech/gateway/backends

# Real-compute smoke: Bell circuit → counts over {00,11} only, ~50/50
curl -m 6 -s -X POST https://qbridge-api.swiftquantum.tech/gateway/execute \
  -H "Authorization: Bearer $GATEWAY_API_KEY" -H 'Content-Type: application/json' \
  -d '{"circuit":{"num_qubits":2,"gates":[{"gate":"h","qubits":[0]},{"gate":"cx","qubits":[0,1]}]},"shots":1024}'
```

Never ship an image that lacks the `/health` alias (earlier builds drop the
host to 8/9 on the sq-unified-alb matrix) or that predates the v1.4.0
real-compute build (task def `qbridge-gateway:4`) — older images return mocked
execute/QEC output.

## Configuration & secrets

- **`GATEWAY_API_KEY`** — Bearer-token auth (constant-time
  `hmac.compare_digest`). Empty = auth DISABLED (dev mode). **Must be set
  in production.** Provided via the task def env (or config `server.api_key`).
- **Rate limiting** — sliding-window, default 60 req/min per client IP.
  Tune via config `server.rate_limit.{max_requests,window_seconds}`.
- **CORS** — restricted to `swiftquantum.tech` domains + localhost;
  methods GET/POST/OPTIONS only.
- **Public paths (no auth)** — `/gateway/health`, `/docs`, `/openapi.json`.
  The `/health` alias is not in `PUBLIC_PATHS` (the ALB HC uses the public
  `/gateway/health`, so this is fine).
- **`QLOGOS_BACKEND_URL`** — upstream for the `/gateway/qlogos/{path}`
  pass-through proxy.

## Endpoints (server.py, port 8090, all under `/gateway/`)

`GET /gateway/health` (+ `/health` alias) · `GET /gateway/backends` ·
`POST /gateway/execute` · `POST /gateway/transpile` ·
`GET /gateway/job/{id}` · `POST /gateway/job/{id}/cancel` ·
`GET /gateway/providers` · `POST /gateway/qec/simulate` ·
`POST /gateway/qec/decode-syndrome` · `POST /gateway/qec/bb-decoder` ·
`ANY /gateway/qlogos/{path:path}` (proxy) · `POST /gateway/message`.

> `/gateway/submit` appears in `ARCHITECTURE.md`/`FEATURES.md` but does
> **NOT** exist in code — ignore it.

## Scaling

Currently fixed at 1 task. To scale (CPU/memory-bound execute or QEC):

```bash
aws ecs update-service --cluster swiftquantum-production-cluster \
  --service qbridge-gateway-service --desired-count <n> \
  --region ap-northeast-2
```

Note the rate limiter is **in-memory per task** — with >1 task, the
effective per-client limit is multiplied and is not shared across tasks.
Memory is 512 MB; watch `MemoryUtilization` before adding load — the real
statevector engine allocates up to ~16 MB per 20-qubit circuit, and QEC
Monte-Carlo is CPU-bound in `shots × num_cycles`.

## Routine tasks

- **Logs**: `aws logs tail /ecs/qbridge-gateway --since 1h --region ap-northeast-2`
- **Local boot (dev box)**:
  ```bash
  python -m gateway_agent.cli init --config=/tmp/qbridge.json
  python -m gateway_agent.cli start --config=/tmp/qbridge.json --port 8090
  ```
  The bundled `venv/` is Python 3.9 with a shebang from another user
  account and may be broken on this machine — recreate if needed:
  `rm -rf venv && /usr/bin/python3 -m venv venv && pip install -e .`
- **Tests**: `pytest` (221 tests; pytest-asyncio). CI in
  `.github/workflows/ci.yml` runs Py 3.10/3.11/3.12 + ruff/black/mypy +
  Docker build check.

## Release distribution

Build artifacts are staged on S3 `sq-gateway-releases` (ap-northeast-2):
`qbridge_gateway-1.3.0` wheel + tar.gz + `latest` alias. PyPI publish is
pending (maintainer-owned token): `twine upload dist/qbridge_gateway-*`.
iOS/macOS Q-Bridge app pairs with a running agent via OTP/QR.

## Guardrails

- The **shared `sq-unified-alb` is a platform SPOF**. Do not modify its
  listener rules (incl. prio 21) or routing to disable just this service.
  Use `--desired-count 0` to isolate the gateway safely.
- No app-level kill-switch / feature flags exist — operational control is
  via ECS (scale, redeploy, rollback) only.
- Gateway content is **not** on the auth/payments/core-data path; full
  outage is **SEV2**, not SEV1 — unless a change cascades into shared ALB
  routing affecting other hosts.

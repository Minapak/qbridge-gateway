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
| Task def | `qbridge-gateway:2` (ARM64, 256 CPU / 512 MB, 1 task) |
| ECR repo | `swiftquantum/qbridge-gateway` |
| Host | `qbridge-api.swiftquantum.tech` |
| ALB / TG | `sq-unified-alb` (shared SPOF) / `uni-qbridge-gw-tg` :8090 |
| Listener rule | priority 21 |
| Log group | `/ecs/qbridge-gateway` (30d) |
| Key env | `QLOGOS_BACKEND_URL=https://qlogos-api.swiftquantum.tech`, `GATEWAY_API_KEY` |

## Versioning note (read before reasoning about "current version")

There is known version drift in this repo:
- `pyproject.toml`, `gateway_agent/__init__.py`, FastAPI app version, and
  egg-info all say **1.3.0**.
- `CHANGELOG.md` / `DEPLOYMENT_LOG.md` record releases through **v1.5.1
  (2026-05-23)** — this is the **real latest release** and what runs in prod.
- `/gateway/health` returns a hardcoded `"version": "1.0.0"`.

Trust CHANGELOG/DEPLOYMENT_LOG and the deployed ECR image tag, not the
in-code version strings or the health payload.

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
```

Never ship an image older than v1.5.1 — earlier builds lack the `/health`
alias and drop the host to 8/9.

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
Memory is 512 MB; watch `MemoryUtilization` before adding load.

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

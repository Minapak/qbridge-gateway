# Incident Runbook — qbridge-gateway

Operational runbook for the Q-Bridge Gateway Agent in SwiftQuantum
production. Pair with `MONITORING.md` (signals) and `OPS.md` (routine ops).

## Service identity

| Item | Value |
|------|-------|
| Region / Account | `ap-northeast-2` / `470485006174` |
| Cluster | `swiftquantum-production-cluster` |
| Service | `qbridge-gateway-service` |
| Task def | `qbridge-gateway:6` (ARM64, 256 CPU / 512 MB, 1 task; v1.6.0 real numpy compute) |
| Host | `qbridge-api.swiftquantum.tech` (ALB `sq-unified-alb`, rule prio 21) |
| Target group | `uni-qbridge-gw-tg` (port 8090, HC `/gateway/health`) |
| Log group | `/ecs/qbridge-gateway` |
| ECR repo | `swiftquantum/qbridge-gateway` |

## Severity mapping

- **SEV1** — only if a gateway change cascades into the shared `sq-unified-alb`
  routing and breaks auth/payments/data-bearing hosts. Gateway content
  itself is not revenue/auth critical.
- **SEV2** — gateway fully down: execute/transpile/QEC + Q-Logos proxy
  unavailable; or host drops the 9/9 health matrix.
- **SEV3** — partial/degraded: elevated latency, Q-Logos proxy down but
  native endpoints up, intermittent 5xx.
- **SEV4** — cosmetic (e.g. wrong version string in `/health` payload).

## First response (any incident)

```bash
# 1. Is the host answering through the ALB?
curl -m 6 -i https://qbridge-api.swiftquantum.tech/gateway/health
curl -m 6 -i https://qbridge-api.swiftquantum.tech/health

# 2. Service / deployment state
aws ecs describe-services --cluster swiftquantum-production-cluster \
  --services qbridge-gateway-service --region ap-northeast-2 \
  --query 'services[0].{running:runningCount,desired:desiredCount,events:events[0:3].message}'

# 3. Target health
aws elbv2 describe-target-health --target-group-arn <uni-qbridge-gw-tg-arn> \
  --region ap-northeast-2 --query 'TargetHealthDescriptions[].TargetHealth'

# 4. Recent logs
aws logs tail /ecs/qbridge-gateway --since 20m --region ap-northeast-2
```

---

## Playbooks

### A. Health check failing / target unhealthy / 502-503 at the host

Most likely: task crashed, OOM (512 MB is tight), a bad image rolled out, or a
**numpy import failure** (v1.4.0 added `numpy>=1.24` as a hard dependency —
execute + QEC fail to import without it).

1. Check `events` (step 2) and logs (step 4) for crash/OOM/restart loop or
   `ModuleNotFoundError: numpy` / `ImportError` at boot.
2. If a recent deploy correlates → **roll back** (see Rollback below). For a
   numpy import error, rebuild the image with `numpy>=1.24` installed
   (`requirements.txt` already pins it) and redeploy.
3. If no deploy, force a fresh task:
   ```bash
   aws ecs update-service --cluster swiftquantum-production-cluster \
     --service qbridge-gateway-service --force-new-deployment \
     --region ap-northeast-2
   ```
4. Re-verify both `/gateway/health` and `/health` return 200.

### B. `/health` returns 404 but `/gateway/health` is 200

The `/health` alias is a second decorator on `health_check()` (commit
`7639a57`/`277e90b`). If only `/gateway/health` answers, the running image
predates that alias — the host will fail the 9/9 matrix.

- Confirm the deployed image carries the `/health` alias (and is the v1.4.0
  real-compute build, task def `qbridge-gateway:4`, or later).
- Roll forward to the correct image (do not roll back to a build without the
  alias).

### C. Q-Logos proxy errors (`/gateway/qlogos/*` 5xx / timeouts)

Native gateway endpoints are independent — this is a downstream issue.

1. Confirm native endpoints still work:
   ```bash
   curl -m 6 https://qbridge-api.swiftquantum.tech/gateway/backends \
     -H "Authorization: Bearer <GATEWAY_API_KEY>"
   ```
2. Check `qlogos-api.swiftquantum.tech` health (separate service).
3. Verify `QLOGOS_BACKEND_URL` env in the task def points at the live
   backend. Severity SEV3 while native endpoints are healthy.

### C2. Execute/QEC returns errors or wrong shape (real-compute regression)

v1.4.0 made execute/QEC **real compute** (numpy statevector + repetition-code
Monte-Carlo). Symptoms and checks:

1. `success: false` with an error like `Unsupported … gate` or
   `… capped at 20` → expected behaviour: the statevector engine rejects
   unsupported gates and circuits over **20 qubits** rather than fabricating
   output. Not an incident — the client sent an out-of-bounds circuit.
2. A Bell circuit (`H 0; CX 0,1`) that does **not** return ~50/50 over
   `{00, 11}`, or returns non-reproducible counts for identical requests →
   the running image is not the v1.4.0 real-compute build, or numpy is broken.
   Confirm the deployed task def is `qbridge-gateway:4` (or later) and roll
   forward.
3. `/gateway/qec/bb-decoder` is an **analytic estimate** — if a caller expects
   a full BP-OSD Monte-Carlo, that is a client misexpectation, not a gateway
   fault. The response `method = analytic_threshold_estimate` + `notes`
   document this.

### D. Auth disabled in production (security)

As of v1.6.0 the empty-key behaviour is environment-aware:
- Log line `Gateway authentication DISABLED (development mode)` = the host is
  judged `development` (no `ENVIRONMENT`/`APP_ENV=production|staging` set) and
  the API is **open**. If this is really a prod host, **treat as SEV2**.
- Log line `GATEWAY_API_KEY is EMPTY on a production host — FAIL-CLOSED …`
  (CRITICAL) = the host is correctly judged production/staging and delegated
  endpoints are already returning `503 auth_not_configured` (health stays up).

⚠️ Per `DEPLOYMENT_LOG.md` the live task def `:6` sets **neither**
`ENVIRONMENT` nor `GATEWAY_API_KEY`, so the fail-closed path is **dormant** and
the gateway is currently dev-open. To actually enforce auth:

- Set **both** `ENVIRONMENT=production` and a `GATEWAY_API_KEY` secret on the
  `qbridge-gateway` task def (and the same `GATEWAY_API_KEY` on
  `swiftquantum-bridge-service`, which sends it as Bearer), then redeploy:
  ```bash
  aws ecs update-service --cluster swiftquantum-production-cluster \
    --service qbridge-gateway-service --force-new-deployment \
    --region ap-northeast-2
  ```
- Confirm a non-public path returns 401/403 without a token, e.g.
  `curl -i https://qbridge-api.swiftquantum.tech/gateway/backends`.
- Note: `PUBLIC_PATHS = {/gateway/health, /health, /docs, /openapi.json}` — the
  `/health` alias is public (added in v1.6.0), so the ALB HC (`/gateway/health`)
  and the `/health` parity probe both keep answering once auth is enforced.

### E. Rate-limit storm (429s)

Sliding-window limiter defaults to 60 req/min per client IP.

1. Identify the offending `client_ip` in logs (`rate_limited`).
2. If a legitimate client needs more, raise
   `server.rate_limit.max_requests` in config and redeploy. Do not remove
   the limiter in production.

---

## Rollback (canonical)

ECS rolls back by pointing the service at a previously-good task def
revision (which references a previously-good ECR image tag).

```bash
# List recent task def revisions
aws ecs list-task-definitions --family-prefix qbridge-gateway \
  --sort DESC --region ap-northeast-2

# Roll back to the last known-good revision (must still have the /health alias
# AND be the v1.4.0 real-compute build = task def qbridge-gateway:4 or later)
aws ecs update-service --cluster swiftquantum-production-cluster \
  --service qbridge-gateway-service \
  --task-definition qbridge-gateway:<good-revision> \
  --region ap-northeast-2

# Watch rollout
aws ecs describe-services --cluster swiftquantum-production-cluster \
  --services qbridge-gateway-service --region ap-northeast-2 \
  --query 'services[0].deployments[].{state:rolloutState,desired:desiredCount,running:runningCount}'
```

Do not roll back to an image that lacks the `/health` alias (drops the health
matrix to 8/9) or that predates the v1.4.0 real-compute build (task def
`qbridge-gateway:4`) — older images return mocked execute/QEC output.

## Kill / disable

There is no app-level kill-switch or feature flag. To take the gateway
out of rotation without affecting other hosts on the shared ALB:

```bash
# Scale to zero (host returns 503; other ALB hosts unaffected)
aws ecs update-service --cluster swiftquantum-production-cluster \
  --service qbridge-gateway-service --desired-count 0 \
  --region ap-northeast-2

# Restore
aws ecs update-service --cluster swiftquantum-production-cluster \
  --service qbridge-gateway-service --desired-count 1 \
  --region ap-northeast-2
```

> Do NOT delete or reorder the `sq-unified-alb` listener rule (prio 21) or
> touch the shared ALB to disable just this service — the ALB is a platform
> SPOF and a mistake there can break unrelated `*-api.swiftquantum.tech`
> hosts. Scale-to-zero is the safe isolation lever.

## Escalation

- Q-Logos downstream → owner of `qlogos-api.swiftquantum.tech`.
- Shared ALB / listener-rule / cross-host routing → platform infra owner
  (changes here can hit auth/payments hosts = SEV1 territory).

# Incident Runbook — qbridge-gateway

Operational runbook for the Q-Bridge Gateway Agent in SwiftQuantum
production. Pair with `MONITORING.md` (signals) and `OPS.md` (routine ops).

## Service identity

| Item | Value |
|------|-------|
| Region / Account | `ap-northeast-2` / `470485006174` |
| Cluster | `swiftquantum-production-cluster` |
| Service | `qbridge-gateway-service` |
| Task def | `qbridge-gateway:2` (ARM64, 256 CPU / 512 MB, 1 task) |
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

Most likely: task crashed, OOM (512 MB is tight), or a bad image rolled out.

1. Check `events` (step 2) and logs (step 4) for crash/OOM/restart loop.
2. If a recent deploy correlates → **roll back** (see Rollback below).
3. If no deploy, force a fresh task:
   ```bash
   aws ecs update-service --cluster swiftquantum-production-cluster \
     --service qbridge-gateway-service --force-new-deployment \
     --region ap-northeast-2
   ```
4. Re-verify both `/gateway/health` and `/health` return 200.

### B. `/health` returns 404 but `/gateway/health` is 200

This is the exact v1.5.1 regression class. The `/health` alias is a second
decorator on `health_check()`. If only `/gateway/health` answers, the
running image predates v1.5.1 (commit `7639a57`/`277e90b`) — the host will
fail the 9/9 matrix.

- Confirm the deployed image tag is v1.5.1 or later.
- Roll forward to the correct image (do not roll back below v1.5.1).

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

### D. Auth disabled in production (security)

Log line `Gateway authentication DISABLED — set GATEWAY_API_KEY env var`
in `/ecs/qbridge-gateway` = the API is open (dev mode). **Treat as SEV2**.

- Auth disables only when `GATEWAY_API_KEY` is empty (env or config).
- Set `GATEWAY_API_KEY` in the task def and redeploy:
  ```bash
  aws ecs update-service --cluster swiftquantum-production-cluster \
    --service qbridge-gateway-service --force-new-deployment \
    --region ap-northeast-2
  ```
- Confirm a non-public path returns 401/403 without a token, e.g.
  `curl -i https://qbridge-api.swiftquantum.tech/gateway/backends`.
- Note: `PUBLIC_PATHS = {/gateway/health, /docs, /openapi.json}`. The
  `/health` alias is **not** in `PUBLIC_PATHS`, but with a key set it is
  still reachable only if auth allows — verify it answers for the ALB HC
  (ALB HC uses `/gateway/health`, which is public, so this is fine).

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

# Roll back to the last known-good revision (must be >= the v1.5.1 image)
aws ecs update-service --cluster swiftquantum-production-cluster \
  --service qbridge-gateway-service \
  --task-definition qbridge-gateway:<good-revision> \
  --region ap-northeast-2

# Watch rollout
aws ecs describe-services --cluster swiftquantum-production-cluster \
  --services qbridge-gateway-service --region ap-northeast-2 \
  --query 'services[0].deployments[].{state:rolloutState,desired:desiredCount,running:runningCount}'
```

Do not roll back below the v1.5.1 image — earlier images lack the `/health`
alias and will drop the health matrix to 8/9.

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

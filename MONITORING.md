# Monitoring & Observability

> SwiftQuantum 16개 앱(네이티브 8 + Web 8) 공통 모니터링 표준.
> 원칙: **사용자가 별점 1점을 주기 전에, 내가 먼저 안다.** 감지가 곧 대응 속도다(→ INCIDENT_RUNBOOK).
> 모니터링은 INCIDENT_RUNBOOK 의 "감지 0분"을 책임지는 계층이다.

## Principle

| 안티패턴 | 표준 |
| -------- | ---- |
| 사용자 불만/리뷰로 장애를 안다 | **알림이 사용자보다 먼저 운다** |
| "잘 되겠지" (무계측) | 모든 핵심 경로에 지표 + 임계치 |
| 로그만 쌓고 안 본다 | 임계 초과 시 **푸시/SMS 능동 알림** |

## Coverage Matrix (레이어별 — 16개 앱 공통)

| 레이어 | 측정 항목 | 도구 | 임계 알림 |
| ------ | --------- | ---- | --------- |
| **Native crash** | 크래시율·ANR·세션당 오류 | 크래시 리포팅 SDK (privacy manifest 등록 필수) | 크래시율 > 1% 또는 신규 크래시 시그니처 |
| **Web** | JS 에러·코어 웹 바이탈·라우트 5xx | RUM + 에러 트래킹 | 에러율 급증 / LCP 악화 |
| **Backend (ECS)** | 5xx율·p95 지연·CPU·Mem·Task 헬스 | CloudWatch (ap-northeast-2, cluster `swiftquantum-production-cluster`, 21개 Fargate 서비스) | 5xx > 1% · p95 > 임계 · Task 비정상 |
| **ALB / DNS** | Target 헬스·요청수·4xx/5xx | CloudWatch (`sq-unified-alb`, 단일 ALB — `*-api`+다수 Web의 SPOF) | UnhealthyHostCount ≥ 1 |
| **Database** | 연결 수·CPU·느린 쿼리·여유 스토리지 | CloudWatch (RDS `swiftquantum-db`, db.t4g.small — 다수 앱 공유) | 연결 포화 · CPU 高 · 스토리지 低 |
| **Auth** (`auth-api`) | 로그인 성공률·401/403 스파이크·토큰 갱신 실패 | CloudWatch + 로그 메트릭 | **성공률 급락 = SEV1 (전 8개 앱 영향)** |
| **Payment** (Stripe/StoreKit) | 결제 실패율·webhook 실패·SN v2 처리 실패 | Stripe Dashboard 알림 + 백엔드 로그 | 실패율 급증 · webhook 4xx/5xx (단, ASN/SN v2 는 설계상 항상 HTTP 200/`success:false` — 5xx 로 알림 금지) |
| **Uptime (synthetic)** | 외부에서 헬스 핑 | 외부 업타임 체크 | 다운/지연 |

## Native Crash Reporting

```swift
// 앱 부팅 시 크래시/에러 리포터 초기화 (PrivacyInfo.xcprivacy 에 SDK manifest 포함)
// 핵심 사용자 경로에 breadcrumb 남기기:
//  - 로그인, 결제(Checkout/IAP), AI 추론, 회로 실행/시뮬, 데이터 저장
// 규칙: 크래시 발생 시 app_id, tier, OS, 기기, 마지막 액션을 함께 수집.
```
- 8개 네이티브 앱 모두 **출시 전 ON** (출시 후 켜면 초기 크래시를 놓친다).
- 신규 버전 배포 후 **24~48시간 집중 관찰** (크래시율·신규 시그니처).

## Backend Health Checks (규약)

대부분의 백엔드는 `swiftquantum_common` `service_app.py` 기반 표준 헬스 엔드포인트를 노출한다:
```bash
GET https://{service}.swiftquantum.tech/health      # liveness (200, auth/OFAC 면제)
GET https://{service}.swiftquantum.tech/health/ready # readiness: DB·의존성 포함
GET https://{service}.swiftquantum.tech/health/live  # liveness
# 외부 업타임 체커가 /health 를 1분 주기로 핑 → 다운 시 즉시 알림
```
> ⚠️ 헬스 규약은 앱마다 다르다 — §Per-App Health Endpoints 표를 정본으로 본다.
> - 일부 백엔드는 `/v1/health` 만 노출(공통 service_app 미사용): qlogos-backend(`/v1/health` 또는 `/health`, ready/live 없음), qbio-api(`/v1/health`).
> - 일부 서비스는 단일 `/health` 가 없고 라우터별 헬스만 있다(Q-Bridge bridge-service: `/api/v1/quantum-tools/health`·`/qec/health`·`/pipeline/health`=200, `/jobs/health`=401 정상; 200 이면 auth gate 해제 이상신호).
> - Web 은 전용 `/health` 라우트가 없는 경우가 많다 → verify 스크립트가 `/`·`/health` 의 **3xx 를 정상으로 허용**, 페이지 응답으로 판정. 단 EDU Web 은 `/api/health`, Q-Logos Web 은 `/api/health` 사용.

```bash
# 수동 점검 — ECS 서비스 상태 (ap-northeast-2, cluster swiftquantum-production-cluster)
aws ecs describe-services --cluster swiftquantum-production-cluster --services {SERVICE} \
  --query 'services[0].{running:runningCount,desired:desiredCount,deploy:deployments[0].rolloutState}' \
  --region ap-northeast-2

# ALB 타겟 헬스
aws elbv2 describe-target-health --target-group-arn {TG_ARN} --region ap-northeast-2
```

## Alert Thresholds (시작값 — 트래픽 보며 보정)

| 지표 | 경고(Warning) | 긴급(SEV1~2) |
| ---- | ------------- | ------------ |
| Backend 5xx 비율 | > 0.5% (5분) | > 2% (5분) |
| API p95 지연 | > 1s | > 3s |
| ECS Task 헬스 | desired ≠ running | running = 0 |
| ALB UnhealthyHost | ≥ 1 | 전 타겟 unhealthy |
| Auth 로그인 성공률 | < 98% | < 90% |
| Native 크래시율 | > 1% | > 5% / 신규 시그니처 급증 |
| Stripe 결제 실패율 | > 5% | webhook 연속 실패 / 전면 실패 |
| DB CPU / 연결 | > 70% / > 80% | > 90% / 포화 |
| 스토리지 여유 | < 20% | < 10% |

## Alert Routing (Solo Operator)

| 등급 | 채널 | 시간 |
| ---- | ---- | ---- |
| **긴급 (SEV1~2)** | 휴대폰 푸시 + SMS (방해금지 무시) | 24/7 즉시 |
| **경고 (SEV3)** | 푸시/이메일 | 업무시간 |
| **정보** | 이메일 다이제스트 | 일/주 단위 |

> Solo 운영이므로 **알림 피로 방지**가 중요: 긴급만 SMS, 나머지는 묶어서. 임계치는 *진짜 행동이 필요한 선*으로만.

## Dashboards (한눈 보기)

권장 단일 대시보드(앱×레이어 그리드):
- 행 = 8개 앱(각 Native+Web), 열 = [Native 크래시 | Web 에러 | Backend 5xx/p95 | Auth 성공률 | Stripe 실패율 | Uptime]
- **신호등(녹/황/적)** 으로 즉시 식별. 출시일·배포 직후엔 이 보드를 상시 띄워둔다.

## Payment / Stripe Monitoring

- Stripe Dashboard 알림: **failed payment 급증, webhook delivery 실패, dispute** ON.
- Stripe LIVE 컷오버 적용됨(8개 앱, env-only: Secrets Manager 키 + `STRIPE_TEST_MODE=false`). LIVE 무결성: `cs_live_*` 정상 생성·`swiftquantum-payments-service` forward 수신·SN v2 멱등 처리.
- 결제 경로: (a) Web Stripe → Auth Internal API 로 tier forward, (b) `swiftquantum-payments-service`(유일한 2-replica) → `uni-payments-tg`. 멱등성은 `stripe_event_log`(evt id UNIQUE) — **DB 오류/세션 부재 시 fails-OPEN**(중복 처리 위험). 완화: ① `PAYMENT_DOUBLE_PROCESS` 로그 토큰 → `Payments-DoubleProcess-SEV1` 알람(threshold 1, 동일 evt id 이중 처리 0), ② 시간당 DB 백스톱 쿼리(동일 `stripe_payment_intent` 2건+ 탐지), ③ 여유 시 처리부를 **fails-CLOSED**(확인 불가 시 webhook 보류·Stripe 재전송 유도)로 전환 검토.
- ⚠️ **payments-service 이미지 태그 `incomplete-fix-2491b66-20260605`** — 미완성 fix 가능성, **인시던트 종료 전 반드시 라이브 검증**.
- canonical webhook 은 payments-service `/api/v1/payment/webhook` 단일 SOT. 각 Web 앱의 `/api/webhooks/stripe` 는 **410 Gone**(설계) → 410 자체는 알림 금지, 410 트래픽 급증은 Stripe Dashboard 등록 오설정 신호.
- Apple ASN/SN v2 webhook 은 설계상 항상 HTTP 200(실패 시 `success:false`) → **`success:false` 를 5xx 로 알림 금지**.
- 백엔드 메트릭: 결제 라우트 5xx, 이중 과금/중복 환불 0 (멱등 키 로그).

## Release-Time Watch (배포 직후 의식)

```
[배포 직후 0~2시간] 대시보드 상주, 크래시율·5xx·결제 실패 집중 관찰
[+24h] 신규 크래시 시그니처 0 확인 → "안정" 판정
[이상 시] INCIDENT_RUNBOOK 의 완화 절차 즉시 진입 (롤백/킬스위치)
```
- 네이티브 신규 버전은 가능하면 **단계적 출시(phased release)** 로 노출 비율을 키우며 관찰.

## Per-App Health Endpoints

| 앱 | app_id | 백엔드 health 대상 (정본) | Web health |
| -- | ------ | ------------------------ | ---------- |
| SwiftQuantum IDE | swiftquantum | Engine(`engine-api`) `/health`+`/ready`+`/live` & 라우터별 `/health`; Auth·Legal 각 `/health` | ide.swiftquantum.tech — 전용 라우트 없음, `/` 3xx 허용 |
| QuantumNative EDU | quantumnative | edu-api `/health`+`/health/ready`+`/health/live` (port 8000) | edu.swiftquantum.tech — **`/api/health`** (status/version/stripeMode) |
| Q-Bridge | qbridge | bridge-service 라우터별: `/api/v1/quantum-tools/health`·`/qec/health`·`/pipeline/health`=200, `/jobs/health`=401 정상 | bridge.swiftquantum.tech `/health` (3xx 허용) |
| QuantumCareer | quantumcareer | career-svc `/health`+`/health/ready`+`/health/live` | career.swiftquantum.tech — 전용 라우트 없음, `/` 3xx 허용 |
| Q-Alpha | qalpha | alpha-api `/health`+`/ready`+`/live`+`/ping` & `/api/v1/alpha/health{,/ready,/live}` | sq-alpha-web — 전용 라우트 없음, `/`·`/login`=200, unauth `/dashboard`→307 |
| Q-Shield | qshield | qshield-api(port 8006) `/health`+`/health/ready`; `/ping` Docker healthcheck | shield.·qshield. (uni-qshield-web-tg) |
| Q-Logos | qlogos | qlogos-backend(port 8007) **`/v1/health`** 또는 `/health` (ready/live 없음) | qlogos-api 호스트; Web `/api/health` (백엔드 /health 3s 프로브 + maintenance 플래그) |
| Q-Bio | qbio | qbio-api(port 8008) **`/v1/health`** (status·version·pqc_active·node_8) | bio.swiftquantum.tech (alias qbio.) — 전용 라우트 없음, `/` 3xx 허용 |
| (공유) | — | **auth-api `/health`·`/health/ready`·`/health/live` (8개 앱 전부 의존 — 최우선 감시)** | — |

> 모든 백엔드: ECS Fargate · cluster `swiftquantum-production-cluster` · `ap-northeast-2` · account `470485006174` (21개 Fargate 서비스, 단일 `sq-unified-alb`, 공유 RDS `swiftquantum-db`).
> ⚠️ **payments-service 이미지 태그 `incomplete-fix-2491b66-20260605`** 는 미완성 fix 가능성이 있어 **신뢰 전 라이브 검증** 필요(멱등성 `fails-OPEN` → `Payments-DoubleProcess-SEV1` 알람 상시 가동).
> 〔정정〕 `auth-api` task def 리비전 `:352`(라이브)와 `SwiftQuantumIDE` README 의 `:346` 은 **서로 다른 대상**(전자 = `SwiftQuantumBackend_common` 의 Auth 서비스 배포 리비전, 후자 = IDE 앱 문서 버전 표기)이므로 **불일치가 아니다 — 비교 대상이 아님.**

## Weekly Review (운영 리듬)

매주 1회 15분:
- [ ] 크래시율·5xx·결제 실패율 추세 (악화 항목?)
- [ ] 미해결 SEV3~4 백로그 정리
- [ ] 임계치 오탐/누락 보정
- [ ] 지난 인시던트 재발 방지 항목 이행 확인 (INCIDENT_RUNBOOK Postmortem)


---

# 📇 앱별 운영 카드 (OPS Card) — 100% 포함

> 아래는 이 프로젝트 전용 OPS 카드 전문이다. 위 공통 표준과 함께 읽는다.

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

# Gateway Agent 배포 기록 가이드

## 2026-05-23 — verification sweep · gateway local boot OK on dev box

Part of the eleven-project cross-stack verification sweep. No code
change. Verified:

- `python -m gateway_agent.cli init --config=/tmp/qbridge.json` writes
  a working LocalSimulator config.
- `python -m gateway_agent.cli start --config=/tmp/qbridge.json --port 8090`
  serves 13 endpoints under `/gateway/*`: `/health`, `/backends`,
  `/execute`, `/transpile`, `/job/{id}`, `/job/{id}/cancel`,
  `/message`, `/providers`, `/qec/simulate`, `/qec/decode-syndrome`,
  `/qec/bb-decoder`, `/qlogos/{path}` + the root `/health`.
- `/gateway/health` returns `local_simulator` + 20 qubit caps + the
  `GATEWAY_API_KEY`-gated `/gateway/config` endpoint stays 403 without
  a Bearer token (constant-time `hmac.compare_digest` path).
- Dev-only artefact: had to recreate the venv because the bundled one
  had a shebang from a different `eunmin` user account — `rm -rf venv
  && /usr/bin/python3 -m venv venv && pip install -e . uvicorn fastapi`
  restored a working install.

## 2026-05-11 — v1.3.0 release artifacts staged on S3 + iOS pairing UI shipped

This session prepared the qbridge-gateway 1.3.0 release for distribution
without exposing any new code surface (the gateway code itself is
unchanged from `4f507d4`).

Build artifacts:
- `python3 -m build` produced
  `dist/qbridge_gateway-1.3.0-py3-none-any.whl` (26 KB) and
  `dist/qbridge_gateway-1.3.0.tar.gz` (41 KB).

S3 upload — new bucket `sq-gateway-releases` (ap-northeast-2):
- `s3://sq-gateway-releases/gateway/qbridge_gateway-1.3.0-py3-none-any.whl`
- `s3://sq-gateway-releases/gateway/qbridge_gateway-1.3.0.tar.gz`
- `s3://sq-gateway-releases/gateway/latest` (alias for the wheel)

iOS / macOS Q-Bridge app (commit `bd9450e` in `Minapak/Q-Bridge`):
- New `QBGatewayPairingService` `@MainActor` singleton — POST
  `/api/v1/pair/exchange` exchanges a 6-digit OTP for a long-lived
  device token + canonical gateway URL. UserDefaults-persisted.
- New `QBQRScannerView` — AVFoundation back-camera scanner on iOS,
  paste-payload fallback on macOS.
- `QBGatewaySetupView` gains a `pairingSection` with Scan QR / manual
  URL + 6-digit OTP form / paired-device card with Unpair.

After the user completes `twine upload dist/*` (PyPI API token is
user-owned), end-users can `pip install qbridge-gateway`, run the agent
locally, and the iOS app pairs in seconds via OTP/QR.

Optional next step (infra owner): CloudFront distribution + Route53
alias `releases.swiftquantum.tech` → `sq-gateway-releases`. Not required
— PyPI publish alone unblocks the install path.

See sister guide `~/Desktop/REAL/Q-Bridge_PyPI_publish_가이드.html`
for the full step-by-step (steps 2-5 + 8 are auto-completed in this
session; 0, 1, 6, 7, 9 require user PyPI credentials).

## v1.4.0-session -- 2026-04-06

### Auth & Rate Limiting Middleware + CORS Hardening
- **GatewayAuthRateLimitMiddleware**: Bearer token auth + sliding-window rate limiter (60 req/min default)
- **CORS restricted**: `["*"]` → swiftquantum.tech domains only
- **allow_methods**: GET/POST/OPTIONS only
- **GATEWAY_API_KEY**: Environment variable + config file support
- **hmac.compare_digest**: Constant-time token comparison
- **Result:** (pending)

---

## v1.3.0-patch -- 2026-04-02

### 버전 동기화 + Pydantic 수정 + CI/CD 파이프라인 생성
- cli.py 버전 표시 v1.2.0 → v1.3.0 동기화
- test_init.py 기대값 1.2.0 → 1.3.0 동기화
- Pydantic deprecated API 수정: `request.dict()` → `request.model_dump()`
- GitHub Actions CI/CD 파이프라인 생성 (`.github/workflows/ci.yml`)
  - Python 3.10, 3.11, 3.12 매트릭스 테스트
  - ruff, black, mypy 코드 품질 검사
  - Docker 빌드 검증
- **Tests**: 221 passed (100%)
- **Build**: Success

---

## v1.3.0 -- 2026-03-05

### i18n 모듈 추가
- `gateway_agent/i18n/__init__.py` 신규 생성 (44 translation keys, 7 languages)
- `get_translation()` 함수: 3-tier fallback (요청 언어 → 영어 → 키)
- 8개 카테고리: server, connection, protocol, device, auth, error, cli, status
- 문서 6개 업데이트

---

## 배포 인프라

| 항목 | 값 |
|------|-----|
| 플랫폼 | 로컬 서버 / Docker (독립 실행) |
| 기본 포트 | 8765 |
| 프로토콜 | HTTP REST + WebSocket + gRPC |
| 패키지 | `pip install -e .` (pyproject.toml 기반) |
| CI/CD | GitHub Actions (ci.yml: Python 3.10/3.11/3.12 매트릭스) |
| 연동 | SwiftQuantumBackend → Gateway Agent → 양자 백엔드 |

---

## 배포 기록

### [v1.1.0] - 2026-02-11

#### 성공 여부: 성공
- `afb8efb` 커밋으로 배포
- QEC Delegation 전용 엔드포인트 추가
- SwiftQuantumBackend에서 Gateway Agent로 QEC 시뮬레이션 위임 구조 완성

#### 변경 사항
- `gateway_agent/protocol.py`: QEC 관련 MessageType 6개 추가
  - `QEC_SIMULATE`, `QEC_SIMULATE_RESULT`
  - `QEC_DECODE_SYNDROME`, `QEC_DECODE_RESULT`
  - `BB_DECODER`, `BB_DECODER_RESULT`
- `gateway_agent/server.py`: QEC 전용 엔드포인트 3개 추가
  - `POST /gateway/qec/simulate` — QEC 시뮬레이션
  - `POST /gateway/qec/decode-syndrome` — 신드롬 디코딩
  - `POST /gateway/qec/bb-decoder` — BB 코드 디코더
- `gateway_agent/handlers/__init__.py`: QEC 핸들러 등록

#### 연동 검증 결과
- `GET /gateway/health` → 200 OK
- `POST /gateway/execute` → 200 OK (회로 실행)
- `POST /gateway/qec/simulate` → 200 OK (QEC 시뮬레이션)
- `POST /gateway/qec/decode-syndrome` → 200 OK (신드롬 디코딩)
- `POST /gateway/qec/bb-decoder` → 200 OK (BB 디코더)

---

### [v1.0.0] - 2026-02-10

#### 성공 여부: 성공
- `cc32f0a` 커밋으로 배포
- gRPC device gateway agent 초기 버전
- LocalSimulator 기반 양자 회로 실행
- WebSocket 실시간 통신 지원
- 디바이스 설정 (`device_config.yaml`) 관리

---

## 배포 체크리스트

### 배포 전
- [ ] 패키지 설치: `pip install -e .`
- [ ] 의존성 확인: `pip install -r requirements.txt`
- [ ] 문법 검증: `python3 -c "from gateway_agent.server import app"`
- [ ] 로컬 서버 시작 테스트: `python3 -m gateway_agent.cli serve --port 8765`
- [ ] `/gateway/health` 엔드포인트 응답 확인
- [ ] QEC 엔드포인트 테스트: `POST /gateway/qec/simulate`
- [ ] `device_config.yaml` 디바이스 설정 확인

### 배포 후
- [ ] 서버 프로세스 실행 확인: `ps aux | grep gateway_agent`
- [ ] 포트 리스닝 확인: `lsof -i :8765`
- [ ] 헬스 체크: `curl http://localhost:8765/gateway/health`
- [ ] SwiftQuantumBackend에서 연동 확인: custom provider 상태 체크

### 롤백
```bash
# 이전 버전으로 롤백
git checkout <PREVIOUS_COMMIT>
pip install -e .
# 서버 재시작
pkill -f gateway_agent
python3 -m gateway_agent.cli serve --port 8765 &
```

---

## 주요 교훈

1. **Gateway Agent는 독립 프로세스** — ECS가 아닌 별도 서버/컨테이너에서 실행, SwiftQuantumBackend의 custom provider로 연결
2. **포트 설정 일치** — Gateway Agent 포트(8765)와 SwiftQuantumBackend `backend_config.json`의 `endpoint_url` 포트가 일치해야 함
3. **MessageType 추가 시 양쪽 동기화** — `protocol.py`에 새 MessageType 추가 시, `server.py`의 `handle_message()`에도 라우팅 추가 필수
4. **gRPC와 REST 동시 지원** — 클라이언트별로 REST 또는 gRPC 선택 가능, 둘 다 테스트 필요
5. **LocalSimulator 한계** — 큐빗 20개 이상 시뮬레이션은 메모리 제한에 주의

## 2026-05-17 — v1.4.0 code shipped (manual deploy required)

Code merged to main. qbridge-gateway runs as a sidecar / standalone server (no ECS service yet on
the SwiftQuantum production cluster — `aws ecs list-services` shows no matching service). To
roll out, redeploy the gateway host with the new code and the env var
`QLOGOS_BACKEND_URL=https://qlogos-api.swiftquantum.tech` (default applies if unset).

## 2026-05-19 16:55 KST — v1.5.0 FIRST PRODUCTION DEPLOY

ECS service brought up for the first time. Steps performed:
  1. ECR repo created
  2. docker buildx build --platform linux/arm64 + push (image 20260519-163721)
  3. CloudWatch log group /ecs/qbridge-gateway + 30d retention
  4. ALB target group uni-qbridge-gw-tg (port 8090, healthcheck /gateway/health)
  5. ECS task def revision 1 + service qbridge-gateway-service
  6. ALB listener rule priority 21 for qbridge-api.swiftquantum.tech (host
     `qbridge.swiftquantum.tech` is taken by Q-Bridge web app rule at 330)
  7. SG sg-003b9967a09935103 opened inbound 8090 from ALB SG
  8. QLOGOS_BACKEND_URL env wired in task def so /gateway/qlogos/{path} proxy
     reaches the production Q-Logos backend automatically

Smoke tests post-deploy: /gateway/health, /gateway/backends both 200.

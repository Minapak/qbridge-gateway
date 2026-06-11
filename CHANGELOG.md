## v1.4.0 — 2026-06-11 — Real numpy statevector sim + real QEC Monte-Carlo + honest BB analytic (ECS `qbridge-gateway:4`)

The gateway stopped faking quantum compute. Every `/gateway/execute` and
`/gateway/qec/*` path now runs genuine numerical physics instead of the old
pattern-matched / `random.*` mocks. Shipped at git HEAD `5d294da`, pyproject
`1.4.0`, deployed as ECS task def `qbridge-gateway:4` (ARM64) on
`qbridge-api.swiftquantum.tech`.

**What shipped:**

- **`gateway_agent/device_interface.py` — `LocalSimulator` is now a real
  dense statevector engine.** The previous gate-name PATTERN-MATCHING +
  random-noise mock is gone. It builds the exact complex statevector on
  `|0…0⟩` from real numpy gate unitaries — H/X/Y/Z/S/Sdg/T/Tdg/RX/RY/RZ
  (with angle), CX/CNOT, CZ, SWAP, CCX/Toffoli, plus measure/barrier/id
  no-ops — computes Born-rule `|amplitude|²` probabilities, and samples
  `shots` outcomes with a numpy RNG **seeded deterministically** from the
  SHA-256 of a canonical JSON encoding of `{circuit, shots}` (same circuit +
  shots → identical counts, reproducible). Little-endian bit ordering (qubit
  0 = LSB). Capped at **20 qubits** (`MAX_STATEVECTOR_QUBITS`; a 20-qubit
  complex128 statevector is ≈16 MB). Unsupported gates raise `ValueError`
  (surfaced as an error — no fabrication). Verified: a Bell circuit
  (`H 0; CX 0,1`) yields ~50/50 over `{00, 11}` only, byte-for-byte
  reproducible across runs.
- **`transpile` is now a real basis-decomposition pass.** Was an identity
  no-op. It decomposes composite gates into the native basis (SWAP → 3×CX,
  Sdg/Tdg → RZ(±π/2 ·, ±π/4), CNOT → CX) and computes **real** gate counts
  (single-/two-qubit), basis-gate list, and circuit depth via greedy
  per-qubit layering — not a fabricated metric.
- **`gateway_agent/server.py` QEC `/gateway/qec/simulate` + `/gateway/qec/decode-syndrome`
  now run a real distance-d repetition-code Monte-Carlo.** `_qec_monte_carlo`
  injects X errors at rate `p` (× a noise-model multiplier) on each of `d`
  data qubits across `num_cycles` rounds with a **seeded** numpy RNG,
  computes the `d−1` parity-check syndromes (`s_i = e_i ⊕ e_{i+1}`), and
  decodes — MWPM/union_find as minimum-weight pairing of adjacent syndrome
  defects on the 1-D chain, or lookup as majority-vote — then measures the
  empirical logical-X error rate (odd residual parity = failure). All
  `random.gauss`/`random.uniform` fudge removed. `method` =
  `monte_carlo_repetition_code_seeded`. `decode-syndrome` is a deterministic
  per-stabilizer decode (`method = deterministic_repetition_decode`).
- **`/gateway/qec/bb-decoder` is an honest, DETERMINISTIC analytic qLDPC
  threshold estimate** for the 4 Bivariate-Bicycle families (`bb_72_12_6`,
  `bb_90_8_10`, `bb_144_12_12`, `bb_288_12_18`). Logical error rate uses the
  standard sub-threshold scaling `p_L = 0.03·(p/p_th)^ceil(d/2)` accumulated
  over `rounds` (saturating toward 0.5 above threshold). The response carries
  `method = "analytic_threshold_estimate"` plus a `notes` field that clearly
  states it is **NOT** a full BP-OSD Monte-Carlo. Example: `bb_144_12_12` at
  `p=0.001` (bp_osd, d=12, threshold 0.0110) gives a per-round
  `p_L ≈ 1.6934e-08` (`1.69342e-07` accumulated over 10 rounds). Full-name-only
  validation kept (short forms / unknown families → 400).
- **numpy added** as a hard dependency (`numpy>=1.24` in both
  `requirements.txt` and `pyproject.toml`). All bare `random.*` removed from
  compute paths.
- **Tests: 221 passing.** Five tests that asserted the old mock behaviour were
  updated to assert the real statevector / Monte-Carlo behaviour.

Unchanged: auth middleware, sliding-window rate limiting, `/gateway/health`
(+ `/health` alias), `/gateway/backends`, `/gateway/providers`, the
`/gateway/qlogos/{path}` proxy, and the `/gateway/message` dispatcher.

---

## [docs] - 2026-05-31 — Honesty-First + Legal Integrity Gate 엔지니어링 표준 채택

SwiftQuantum 생태계 전반에 **Honesty-First 원칙 + Legal Integrity Gate(L1~L4)** 를
엔지니어링 표준으로 채택. 본 프로젝트(Q-Bridge 게이트웨이 에이전트) 적용:
- **L1 지수 IP 분리 · L2 시장데이터 라이선스/스크레이핑 금지**: 시장·증권 데이터 표면 없음 → **해당 없음(N/A)**.
- **L3 비-자문 게이트**: 예측/전망/추천/보장/매수/매도 의미 0건.
- **L4 표시·광고 무결**: 검증 불가 통계·과장 0건. 시뮬레이션은 시뮬레이션으로 명시.
- **인용 정직성**: 날조 출처/숫자 0건. · **8-locale 패리티**: en/ko/ja/zh-Hans/zh-Hant/de/fr/es 확장 가능.

이번 세션 변경: **문서만**(코드/런타임 0). 다른 앱 영향 0.

## v1.5.1 — 2026-05-23 — `/health` alias for sq-unified-alb parity (9/9 health matrix)

**Why:** `qbridge-api.swiftquantum.tech/health` returned 404 because the gateway only registered `/gateway/health`. The other 8 `*-api.swiftquantum.tech` services on sq-unified-alb all expose `/health` directly, leaving qbridge-api as the only host failing the production health probe (8/9 → 9/9 ask).

**What shipped:**
- `gateway_agent/server.py` — second `@app.get("/health")` decorator on the existing `health_check()` handler so both `/health` and `/gateway/health` return the same payload (status, server_name, server_id, version, protocol_version, uptime_seconds, device).
- Image: `qbridge-gateway:7639a57-20260523-121027-health-alias` → ECS `qbridge-gateway:2`.

**Live verification 2026-05-23:** `curl -m 6 https://qbridge-api.swiftquantum.tech/health` → 200 with full JSON body. Production 9/9 health matrix green.

## v1.5.0 — 2026-05-19 — Production ECS deployment LIVE

Brought the gateway up in production on the SwiftQuantum ECS cluster for
the first time:

- ECR repo `swiftquantum/qbridge-gateway` created · ARM64 image
  `qbridge-gateway:20260519-163721` pushed
- ECS service `qbridge-gateway-service` on `swiftquantum-production-cluster`
  (Fargate, 256 CPU / 512 MB, ARM64, 1 task healthy)
- ALB target group `uni-qbridge-gw-tg` (port 8090, healthcheck
  `/gateway/health`), listener rule priority 21 on `sq-unified-alb`
  matching `qbridge-api.swiftquantum.tech` (the existing
  `qbridge.swiftquantum.tech` rule already routes the Q-Bridge web app to
  `uni-bridge-web-tg`, so the gateway gets its own host)
- Security group inbound 8090 opened from ALB SG `sg-005c3f5722e9797c3`
- CloudWatch log group `/ecs/qbridge-gateway` (30-day retention)
- `QLOGOS_BACKEND_URL=https://qlogos-api.swiftquantum.tech` env var passed
  in via the task def so `/gateway/qlogos/{path}` proxy routes to the live
  Q-Logos backend without manual configuration

**Production verification (2026-05-19 16:55 KST):**
- `GET /gateway/health` → 200, returns `{"status":"healthy","server_name":"my-gateway",…}`
- `GET /gateway/backends` → 200, returns the local_simulator info
## v5.0.8 — 2026-05-17 — iOS/macOS clients verified against fixed backend

No client code change in this version — the JWT-`aud` bug that was
hitting the auth lifecycle was on the backend (`middleware/auth.py` on
`Q-Logos_Backend`). Once that landed (task def `qlogos-backend:38`)
the iOS `AuthManager.login()` + `register()` + `getProfile()` flows
work end-to-end through the same `APIClient` Bearer-token plumbing.

iOS + macOS builds re-verified clean:
- `xcodebuild -scheme Q-Logos_iOS -destination 'generic/platform=iOS Simulator'` → BUILD SUCCEEDED
- `xcodebuild -scheme Q-Logos_macOS -destination 'generic/platform=macOS'` → BUILD SUCCEEDED

## v1.4.1 — 2026-05-17 — No code change; verified Q-Logos proxy route compiles

The v1.4.0 `/gateway/qlogos/{path}` proxy from yesterday's release was
re-confirmed clean (no compile/import regressions) during the
Q-Logos v5.0.8 backend hotfix cycle. The gateway itself doesn't yet
have a production ECS service; the proxy code is ready to ship when the
gateway is brought up.

## v1.4.0 — 2026-05-17 — Q-Logos backend proxy at `/gateway/qlogos/{path:path}`

Before this release, qbridge-gateway exposed only quantum-compute endpoints (`/gateway/execute`,
`/gateway/transpile`, `/gateway/job/*`, `/gateway/qec/*`) and had zero routing into the Q-Logos
logistics backend. Clients hit `qlogos-api.swiftquantum.tech` directly. v1.4.0 introduces a
pass-through proxy so a single gateway-issued bearer token works against both compute and
logistics endpoints, and rate-limiting is centralized.

- `GET/POST/PUT/PATCH/DELETE /gateway/qlogos/{path:path}` — forwards the request to
  `${QLOGOS_BACKEND_URL}/v1/{path}` (default `https://qlogos-api.swiftquantum.tech`)
- Authorization, content-type, Accept-Language, and X-PQC-* headers are propagated
- Upstream JSON is returned verbatim; non-JSON errors are wrapped in a `{detail}` envelope
- Network failures → 502 with the original exception in `detail`
- `_safe_json()` helper added at module top so non-JSON 500 pages don't crash the proxy

Backward-compatible: all existing endpoints unchanged. New env var `QLOGOS_PROXY_TIMEOUT_SEC`
(default 10.0).
# Changelog

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

All notable changes to Q-Bridge Gateway Agent will be documented in this file.

## [1.4.0-session] - 2026-04-06

### Added
- **GatewayAuthRateLimitMiddleware**: Bearer token authentication + sliding-window rate limiter (60 req/min default, configurable)
- **GATEWAY_API_KEY**: Environment variable + config file support for API key management
- **hmac.compare_digest**: Constant-time token comparison to prevent timing attacks

### Security
- **CORS Restricted**: `allow_origins=["*"]` replaced with swiftquantum.tech domain whitelist
- **allow_methods**: Restricted to GET, POST, OPTIONS only
- **Rate limit**: 60 requests/minute default, configurable via config

---

## [1.3.0-patch] - 2026-04-02
### Fixed
- cli.py 버전 표시 v1.2.0 → v1.3.0 동기화
- test_init.py 기대값 1.2.0 → 1.3.0 동기화
- Pydantic deprecated API 수정: request.dict() → request.model_dump()

### Added
- GitHub Actions CI/CD 파이프라인 생성 (.github/workflows/ci.yml)
  - Python 3.10, 3.11, 3.12 매트릭스 테스트
  - ruff, black, mypy 코드 품질 검사
  - Docker 빌드 검증

### Verified
- 221 tests passed (기존 1 실패 → 전량 통과)

---

## [1.3.0] - 2026-03-05

### Added — Internationalization (i18n) Module
- **`gateway_agent/i18n/__init__.py`**: New i18n module with 44 translation keys across 8 categories (server, connection, protocol, device, auth, error, cli, status)
- **7 languages supported**: en, ko, ja, zh, de, fr, es
- **`get_translation(key, lang, **kwargs)`**: Main translation function with 3-tier fallback (requested language → English → key)
- **`get_supported_languages()`**: Returns list of supported language codes
- **`get_all_keys()`**: Returns list of all translation keys
- Format parameter support via `str.format()` (e.g., `port`, `client_id`, `job_id`)

---

## [1.2.0] - 2026-02-28

### Changed — iOS App Alignment
- **Package rename**: `swiftquantum-gateway-agent` → `qbridge-gateway`
- **CLI rename**: `gateway-agent` → `qbridge-gateway`
- **Default port**: 8765 → 8090 (matches Q-Bridge iOS QBGatewaySetupView)
- **Default config**: `device_config.yaml` → `config.json`
- **FastAPI title**: `SwiftQuantum Gateway Agent` → `Q-Bridge Gateway Agent`

### Added
- `qbridge-gateway init` subcommand — generates `config.json` template
- `Dockerfile` — builds `qbridge/gateway:latest` image
- `.dockerignore` — standard Python Docker ignore rules
- `config.json` — default JSON config template

---

## [1.1.0] - 2026-02-11

### Added - QEC Delegation Endpoints (v8.1.0)

#### Protocol
- `gateway_agent/protocol.py` — 6 new MessageType enum values: QEC_SIMULATE, QEC_SIMULATE_RESULT, QEC_DECODE_SYNDROME, QEC_DECODE_RESULT, BB_DECODER, BB_DECODER_RESULT

#### QEC REST Endpoints
- `POST /gateway/qec/simulate` — Full QEC simulation with threshold model (surface/color codes, MWPM/Union-Find/Lookup decoders)
- `POST /gateway/qec/decode-syndrome` — Single syndrome measurement decoding
- `POST /gateway/qec/bb-decoder` — BB Code qLDPC decoder with 4 families (bb_72_12_6, bb_90_8_10, bb_144_12_12, bb_288_12_18)

#### WebSocket Message Routing
- QEC_SIMULATE, QEC_DECODE_SYNDROME, BB_DECODER message types added to `handle_message()`

### Modified Files
- `gateway_agent/protocol.py` — QEC MessageType additions
- `gateway_agent/server.py` — QEC endpoint handlers and message routing

---

## [1.0.0] - 2026-02-10

### Added - Initial Release
- **gRPC Device Gateway Agent**: Core gateway agent for quantum backend communication
- **Device Configuration**: YAML-based device configuration (device_config.yaml)
- **Provider Discovery**: Dynamic quantum provider/backend discovery
- **Job Execution**: Submit quantum circuits to backend devices
- **Job Submission Alias**: POST /submit endpoint for simplified job submission
- **Environment Configuration**: .env.example with required settings
- **Python Package**: pyproject.toml with project metadata and dependencies

### Files
- gateway_agent/ - Core agent module
- device_config.yaml - Device configuration
- pyproject.toml - Package configuration
- requirements.txt - Python dependencies
- .env.example - Environment template
- README.md - Project documentation

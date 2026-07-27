# CLAUDE.md — qbridge-gateway

Q-Bridge 경량 게이트웨이 (FastAPI, ECS).

## Coding Rules (ECC 발췌 — Python/FastAPI)

관련 스킬(자동 로드): `fastapi-patterns`, `python-patterns`, `python-testing`, `postgres-patterns`, `redis-patterns`, `database-migrations`, `security-review`

### 스타일
- PEP 8 + 모든 함수 시그니처에 타입 어노테이션. 포맷팅: black + isort, 린트: ruff.
- DTO는 `@dataclass(frozen=True)` 등 불변 구조 우선. 인터페이스는 `typing.Protocol`.

### FastAPI 구조
- 앱 구성은 `create_app()`에. 라우터는 얇게 — 비즈니스 로직은 서비스/CRUD 헬퍼로.
- 요청/수정/응답 스키마 분리. DB 세션·인증은 `Depends` 의존성으로만.
- I/O 하는 엔드포인트는 `async def` + async 클라이언트. async 라우트에서 `requests`·동기 SQLAlchemy 세션·블로킹 I/O 호출 금지.
- 라우트 핸들러 안에서 `SessionLocal()`이나 장수명 클라이언트 생성 금지.

### 스키마/보안
- 응답 모델에 패스워드(해시 포함)·액세스/리프레시 토큰·내부 인증 상태 절대 포함 금지. `response_model` 명시.
- CORS origin은 환경별 분리, 와일드카드+credentials 조합 금지. 브라우저 직접 호출 앱은 `X-App-ID`/`X-App-Client` preflight allow_headers 필요.
- JWT는 만료·발급자·audience·알고리즘 검증. 인증·쓰기 엔드포인트 rate-limit.
- 로그에서 자격증명·쿠키·Authorization 헤더·토큰 마스킹. 정적 분석: `bandit -r`.

### 테스트
- pytest (+ async 테스트 클라이언트). `Depends`에 쓰인 정확한 의존성을 override하고 테스트 후 `app.dependency_overrides` 초기화.

### 배포 (SwiftQuantum 생태계 공통)
- 배포는 로컬에서 `SwiftQuantum-Architecture/scripts/deploy_from_docker.sh`로 ECR+ECS 직접 배포. GitHub Actions 배포 금지.
- ECS 클러스터는 mixed-arch — 푸시 전 TD `runtimePlatform` 확인, ARM64 서비스는 multi-arch 이미지 필요.
- 웹 클라이언트 티어 게이팅은 `*_web_tier`(X-App-Client 기반) — 네이티브 티어 필드로 게이팅 금지.

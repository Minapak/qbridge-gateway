# Gateway Agent 배포 기록 가이드

## 배포 인프라

| 항목 | 값 |
|------|-----|
| 플랫폼 | 로컬 서버 / Docker (독립 실행) |
| 기본 포트 | 8765 |
| 프로토콜 | HTTP REST + WebSocket + gRPC |
| 패키지 | `pip install -e .` (pyproject.toml 기반) |
| CI/CD | 수동 배포 (GitHub Actions 미설정) |
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

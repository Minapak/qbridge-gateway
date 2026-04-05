# TEST GUIDE - gateway-agent

## Overview

Gateway Agent는 다중 양자 하드웨어 프로바이더를 연결하는 게이트웨이 에이전트입니다. 서버, 프로토콜, 디바이스 인터페이스, CLI를 포괄적으로 테스트합니다.

- **Framework**: pytest + pytest-asyncio
- **Test files**: 6 files in `tests/`
- **Test count**: 221 tests

---

## Prerequisites

- Python 3.9+
- Dependencies: `pip install -e ".[test]"` or `pip install -r requirements.txt`
- No external services required

---

## How to Run

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run specific test file
python3 -m pytest tests/test_server.py -v

# Run with coverage
python3 -m pytest tests/ --cov=gateway_agent --cov-report=term-missing
```

---

## Test Structure

| File | Description |
|------|-------------|
| `tests/test_server.py` | Server endpoints: health, circuit execution, QEC, providers |
| `tests/test_device_interface.py` | Backend abstraction, connection lifecycle, capabilities |
| `tests/test_protocol.py` | Message format, serialization, handshake, versioning |
| `tests/test_cli.py` | CLI argument parsing, subcommands, exit codes |
| `tests/test_init.py` | Package imports, version, public API |
| `tests/test_integration.py` | Full request lifecycle, multi-backend distribution |

---

## Test Categories

### 1. Server (`test_server.py`)
- Health check, circuit execution endpoints
- QEC simulation and decoding
- BB decoder, erasure simulation
- Provider listing, message exchange
- **Malformed YAML config**: `dict` 타입 체크 추가로 안정성 확보

### 2. Device Interface (`test_device_interface.py`)
- Backend connect/disconnect/reconnect
- Capability discovery (gates, qubits, connectivity)
- Multi-provider management

### 3. Protocol (`test_protocol.py`)
- Message format validation, binary/JSON serialization
- Handshake sequence, error handling, version negotiation

### 4. CLI (`test_cli.py`)
- Argument parsing, subcommand execution
- Help text, exit code validation

---

## Auth & Rate Limiting Tests (2026-04-06)

### GatewayAuthRateLimitMiddleware Verification

```bash
# Request without token (should return 401)
curl http://localhost:8090/gateway/health
# Expected: 401 Unauthorized

# Request with valid Bearer token
curl -H "Authorization: Bearer $GATEWAY_API_KEY" \
  http://localhost:8090/gateway/health
# Expected: 200 OK

# Rate limit test (send 61 requests in 1 minute)
for i in $(seq 1 61); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer $GATEWAY_API_KEY" \
    http://localhost:8090/gateway/health
done
# Expected: 60x 200, then 429 Too Many Requests

# CORS test (non-swiftquantum origin should be rejected)
curl -H "Origin: https://evil.com" \
  -H "Authorization: Bearer $GATEWAY_API_KEY" \
  http://localhost:8090/gateway/health
# Expected: No Access-Control-Allow-Origin header

# Disallowed method test
curl -X DELETE -H "Authorization: Bearer $GATEWAY_API_KEY" \
  http://localhost:8090/gateway/health
# Expected: 405 Method Not Allowed
```

---

## Important Notes

- **YAML 파싱**: `server.py`의 `_load_config`에서 malformed YAML을 `dict` 타입 체크로 처리
- Async tests use `pytest-asyncio`
- All quantum hardware interactions use mocked backends

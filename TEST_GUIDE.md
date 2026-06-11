# TEST GUIDE - gateway-agent

## Overview

Gateway Agent는 다중 양자 하드웨어 프로바이더를 연결하는 게이트웨이 에이전트입니다. 서버, 프로토콜, 디바이스 인터페이스, CLI를 포괄적으로 테스트합니다.

- **Framework**: pytest + pytest-asyncio
- **Test files**: 6 files in `tests/`
- **Test count**: **221 tests passing** (v1.4.0). When the mocks were replaced with the real numpy statevector engine + real QEC Monte-Carlo, **5 tests that asserted the old mock behaviour were updated to assert the real behaviour** — the suite still ends at 221 passing.

---

## Prerequisites

- Python 3.10+ (CI matrix: 3.10 / 3.11 / 3.12)
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

## Verifying the Real Compute (v1.4.0)

Quick manual checks that the gateway runs genuine physics, not mocks:

### 1. Bell state → reproducible ~50/50 over {00, 11}

```python
from gateway_agent.device_interface import LocalSimulator
sim = LocalSimulator()
circ = {"num_qubits": 2, "gates": [
    {"gate": "h",  "qubits": [0]},
    {"gate": "cx", "qubits": [0, 1]},
]}
r1 = sim.execute(circ, 4000)
r2 = sim.execute(circ, 4000)
assert set(r1.counts) <= {"00", "11"}        # only Bell outcomes
assert r1.counts == r2.counts                  # seeded RNG = deterministic
# e.g. {'00': 1979, '11': 2021} — ~50/50, identical across runs
```

A circuit requesting **>20 qubits** fails validation (the statevector engine
is capped at `MAX_STATEVECTOR_QUBITS = 20`); unsupported gates raise and the
job returns `success: false` with an error — no fabricated counts.

### 2. QEC simulate → deterministic for fixed inputs

```python
from gateway_agent.server import _qec_monte_carlo
a = _qec_monte_carlo("repetition", "mwpm", d=5, p=0.05, shots=2000, num_cycles=3, noise_model="depolarizing")
b = _qec_monte_carlo("repetition", "mwpm", d=5, p=0.05, shots=2000, num_cycles=3, noise_model="depolarizing")
assert a["measured_rate"] == b["measured_rate"]   # seeded numpy RNG → reproducible
```

The reported `logical_error_rate` is the **empirical** failure fraction over
the shots (`method = monte_carlo_repetition_code_seeded`), not a random draw.

### 3. BB decoder → full-name validation (short forms → 400)

```bash
# Valid full family name → 200 with method=analytic_threshold_estimate
curl -s -X POST http://localhost:8090/gateway/qec/bb-decoder \
  -H 'Content-Type: application/json' \
  -d '{"code_family":"bb_144_12_12","decoder":"bp_osd","error_rate":0.001,"rounds":10}'
# logical_error_rate ≈ 1.69342e-07 (per-round p_L ≈ 1.6934e-08 over 10 rounds);
# response.notes states it is NOT a full BP-OSD Monte-Carlo.

# Short / unknown family → 400 Bad Request
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://localhost:8090/gateway/qec/bb-decoder \
  -H 'Content-Type: application/json' -d '{"code_family":"bb144"}'
# Expected: 400
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

## Auth & Rate Limiting Tests

### GatewayAuthRateLimitMiddleware Verification

> Note: `/gateway/health` (and its `/health` alias), `/docs`, `/openapi.json` are
> public paths and never require a token. Use a protected endpoint such as
> `/gateway/backends` to exercise auth. Auth is only enforced when
> `GATEWAY_API_KEY` is set (empty = dev mode, auth disabled).

```bash
# Health is public — always 200, no token needed
curl http://localhost:8090/gateway/health
# Expected: 200 OK

# Protected endpoint without token (should return 401)
curl http://localhost:8090/gateway/backends
# Expected: 401 Unauthorized

# Protected endpoint with valid Bearer token
curl -H "Authorization: Bearer $GATEWAY_API_KEY" \
  http://localhost:8090/gateway/backends
# Expected: 200 OK

# Rate limit test (send 61 requests in 1 minute)
for i in $(seq 1 61); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "Authorization: Bearer $GATEWAY_API_KEY" \
    http://localhost:8090/gateway/backends
done
# Expected: 60x 200, then 429 Too Many Requests

# CORS test (non-swiftquantum origin should be rejected)
curl -H "Origin: https://evil.com" \
  -H "Authorization: Bearer $GATEWAY_API_KEY" \
  http://localhost:8090/gateway/backends
# Expected: No Access-Control-Allow-Origin header

# Disallowed method test (CORS allows GET/POST/OPTIONS only)
curl -X DELETE -H "Authorization: Bearer $GATEWAY_API_KEY" \
  http://localhost:8090/gateway/backends
# Expected: 405 Method Not Allowed
```

---

## Important Notes

- **YAML 파싱**: `server.py`의 `_load_config`에서 malformed YAML을 `dict` 타입 체크로 처리
- Async tests use `pytest-asyncio`
- The built-in `LocalSimulator` is a **real** numpy statevector engine (v1.4.0); QEC simulate/decode run real seeded Monte-Carlo. Only external researcher hardware backends are abstracted behind `DeviceInterface` — there is no mock quantum compute in the simulator path.

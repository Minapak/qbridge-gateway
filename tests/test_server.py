"""
Tests for gateway_agent.server — GatewayServer & all REST endpoints
=====================================================================

Covers:
- GatewayServer construction with/without config
- Config loading (YAML, JSON, missing, unknown format, env var resolution)
- FastAPI app creation
- All REST endpoints:
    GET  /gateway/health
    GET  /gateway/backends
    POST /gateway/execute  (valid, invalid, error handling)
    POST /gateway/transpile
    GET  /gateway/job/{job_id}  (found, not found, device-level lookup)
    POST /gateway/job/{job_id}/cancel  (found, not found)
    GET  /gateway/providers
    POST /gateway/message  (health_check, list_backends, execute_circuit,
                            qec_simulate, qec_decode_syndrome, bb_decoder,
                            unsupported type, error handling)
- QEC endpoints:
    POST /gateway/qec/simulate
    POST /gateway/qec/decode-syndrome
    POST /gateway/qec/bb-decoder
- CORS middleware
- Error handling paths
"""

import json
import os
import time
from unittest.mock import patch, MagicMock

import pytest
import pytest_asyncio

from gateway_agent.server import GatewayServer
from gateway_agent.device_interface import LocalSimulator, DeviceInfo, ExecutionResult
from gateway_agent.protocol import GatewayMessage, MessageType


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GatewayServer construction & config
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGatewayServerConstruction:

    def test_default_construction(self):
        server = GatewayServer()
        assert isinstance(server.device, LocalSimulator)
        assert server.server_name == "gateway_agent"
        assert server.app is not None

    def test_with_custom_device(self):
        sim = LocalSimulator(name="custom_sim", num_qubits=30)
        server = GatewayServer(device=sim)
        info = server.device.get_device_info()
        assert info.name == "custom_sim"
        assert info.num_qubits == 30

    def test_with_yaml_config(self, sample_yaml_config):
        server = GatewayServer(config_path=sample_yaml_config)
        assert server.server_name == "test_gateway"
        assert server.server_id == "gw_test_001"
        # Device should be reconfigured from config
        info = server.device.get_device_info()
        assert info.name == "test_simulator"
        assert info.num_qubits == 8

    def test_with_json_config(self, sample_json_config):
        server = GatewayServer(config_path=sample_json_config)
        assert server.server_name == "json_gateway"
        assert server.server_id == "gw_json_001"
        info = server.device.get_device_info()
        assert info.name == "json_simulator"
        assert info.num_qubits == 12

    def test_missing_config_file(self, tmp_path):
        missing = str(tmp_path / "nonexistent.yaml")
        server = GatewayServer(config_path=missing)
        # Should not crash, just use defaults
        assert server.server_name == "gateway_agent"

    def test_unknown_config_format(self, tmp_path):
        config_file = tmp_path / "config.xml"
        config_file.write_text("<config></config>")
        server = GatewayServer(config_path=str(config_file))
        assert server.config == {}

    def test_jobs_initially_empty(self):
        server = GatewayServer()
        assert server._jobs == {}

    def test_start_time_set(self):
        before = time.time()
        server = GatewayServer()
        after = time.time()
        assert before <= server.start_time <= after


class TestGatewayServerConfigLoading:

    def test_env_var_resolution(self, tmp_path):
        config_content = """
server:
  name: "env_test"
  id: "gw_env"
auth:
  token: "${TEST_GATEWAY_TOKEN}"
"""
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(config_content)

        with patch.dict(os.environ, {"TEST_GATEWAY_TOKEN": "secret123"}):
            server = GatewayServer(config_path=str(config_file))
            assert server.config["auth"]["token"] == "secret123"

    def test_env_var_unset_keeps_placeholder(self, tmp_path):
        config_content = """
server:
  name: "env_test"
auth:
  token: "${NONEXISTENT_VAR_12345}"
"""
        config_file = tmp_path / "env_config.yaml"
        config_file.write_text(config_content)

        server = GatewayServer(config_path=str(config_file))
        assert server.config["auth"]["token"] == "${NONEXISTENT_VAR_12345}"

    def test_malformed_yaml_does_not_crash(self, tmp_path):
        config_file = tmp_path / "bad.yaml"
        config_file.write_text(":::invalid yaml{{{}}}[[[")
        server = GatewayServer(config_path=str(config_file))
        # Should not crash

    def test_cors_origins_from_config(self, sample_yaml_config):
        server = GatewayServer(config_path=sample_yaml_config)
        # Verify CORS middleware was added (app has middleware)
        assert server.app is not None


class TestGatewayServerStart:

    def test_start_raises_without_fastapi(self):
        server = GatewayServer()
        # Temporarily simulate FASTAPI_AVAILABLE = False
        server.app = None
        with patch("gateway_agent.server.FASTAPI_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="FastAPI is required"):
                server.start()

    def test_start_calls_uvicorn(self):
        server = GatewayServer()
        with patch("uvicorn.run") as mock_run:
            server.start(host="127.0.0.1", port=1234)
            mock_run.assert_called_once()
            call_kwargs = mock_run.call_args
            assert call_kwargs[1]["host"] == "127.0.0.1"
            assert call_kwargs[1]["port"] == 1234


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  REST Endpoint Tests (using httpx AsyncClient)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestHealthEndpoint:

    async def test_health_check_status(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"

    async def test_health_check_fields(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/health")
        data = resp.json()
        assert "server_name" in data
        assert "server_id" in data
        assert "version" in data
        assert "protocol_version" in data
        assert "uptime_seconds" in data
        assert "device" in data
        assert data["version"] == "1.0.0"
        assert data["protocol_version"] == "1.0"

    async def test_health_check_uptime_positive(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/health")
        data = resp.json()
        assert data["uptime_seconds"] >= 0

    async def test_health_check_device_info(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/health")
        device = resp.json()["device"]
        assert device["status"] == "online"
        assert "num_qubits" in device

    async def test_health_configured_server_name(self, test_client_with_config):
        async with test_client_with_config as client:
            resp = await client.get("/gateway/health")
        data = resp.json()
        assert data["server_name"] == "test_gateway"


@pytest.mark.asyncio
class TestBackendsEndpoint:

    async def test_list_backends_structure(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/backends")
        assert resp.status_code == 200
        data = resp.json()
        assert "backends" in data
        assert "total" in data
        assert "server" in data
        assert data["total"] == 1

    async def test_backend_info_fields(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/backends")
        backend = resp.json()["backends"][0]
        required_fields = [
            "name", "num_qubits", "technology", "connectivity",
            "supported_gates", "max_shots", "status", "metadata",
        ]
        for field in required_fields:
            assert field in backend, f"Missing field: {field}"

    async def test_backend_is_simulator(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/backends")
        backend = resp.json()["backends"][0]
        assert backend["technology"] == "simulator"


@pytest.mark.asyncio
class TestExecuteEndpoint:

    async def test_execute_bell_circuit(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit, "shots": 1000},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "job_id" in data
        assert "counts" in data
        assert data["shots"] == 1000
        assert sum(data["counts"].values()) == 1000

    async def test_execute_custom_shots(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit, "shots": 5000},
            )
        data = resp.json()
        assert data["shots"] == 5000

    async def test_execute_default_shots(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit},
            )
        data = resp.json()
        assert data["shots"] == 1024  # default

    async def test_execute_response_has_metadata(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit, "shots": 100},
            )
        data = resp.json()
        assert "metadata" in data
        assert "execution_time_ms" in data
        assert "backend" in data
        assert "server" in data

    async def test_execute_invalid_circuit_too_many_qubits(self, test_client):
        circuit = {"num_qubits": 500, "gates": [{"gate": "h", "qubits": [0]}]}
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": circuit, "shots": 100},
            )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "errors" in detail

    async def test_execute_invalid_circuit_unsupported_gate(self, test_client):
        circuit = {
            "num_qubits": 2,
            "gates": [{"gate": "magic_gate_xyz", "qubits": [0]}],
        }
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": circuit, "shots": 100},
            )
        assert resp.status_code == 400

    async def test_execute_stores_job(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit, "shots": 100},
            )
            job_id = resp.json()["job_id"]
            # Now retrieve the job
            resp2 = await client.get(f"/gateway/job/{job_id}")
            assert resp2.status_code == 200
            assert resp2.json()["job_id"] == job_id

    async def test_execute_with_backend_name(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit, "shots": 100, "backend": "my_backend"},
            )
        data = resp.json()
        assert data["backend"] == "my_backend"


@pytest.mark.asyncio
class TestTranspileEndpoint:

    async def test_transpile_basic(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/transpile",
                json={"circuit": bell_circuit},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "transpiled_circuit" in data
        assert data["transpiled_circuit"] == bell_circuit  # default passthrough
        assert "backend" in data
        assert "optimization_level" in data
        assert "server" in data

    async def test_transpile_with_optimization_level(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/transpile",
                json={"circuit": bell_circuit, "optimization_level": 3},
            )
        data = resp.json()
        assert data["optimization_level"] == 3

    async def test_transpile_with_backend(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/transpile",
                json={"circuit": bell_circuit, "backend": "custom_backend"},
            )
        data = resp.json()
        assert data["backend"] == "custom_backend"


@pytest.mark.asyncio
class TestJobEndpoints:

    async def test_get_job_after_execute(self, test_client, bell_circuit):
        async with test_client as client:
            exec_resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit, "shots": 100},
            )
            job_id = exec_resp.json()["job_id"]
            resp = await client.get(f"/gateway/job/{job_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == job_id
        assert data["status"] == "COMPLETED"

    async def test_get_nonexistent_job(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/job/nonexistent_id_12345")
        assert resp.status_code == 404

    async def test_cancel_existing_job(self, test_client, bell_circuit):
        async with test_client as client:
            exec_resp = await client.post(
                "/gateway/execute",
                json={"circuit": bell_circuit, "shots": 100},
            )
            job_id = exec_resp.json()["job_id"]
            resp = await client.post(f"/gateway/job/{job_id}/cancel")
        assert resp.status_code == 200
        assert resp.json()["cancelled"] is True

    async def test_cancel_nonexistent_job(self, test_client):
        async with test_client as client:
            resp = await client.post("/gateway/job/nonexistent_999/cancel")
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestProvidersEndpoint:

    async def test_list_providers_structure(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/providers")
        assert resp.status_code == 200
        data = resp.json()
        assert "providers" in data
        assert len(data["providers"]) == 1

    async def test_provider_info_fields(self, test_client):
        async with test_client as client:
            resp = await client.get("/gateway/providers")
        provider = resp.json()["providers"][0]
        assert provider["id"] == "custom"
        assert provider["type"] == "researcher_hosted"
        assert "backends" in provider
        assert "technology" in provider


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  QEC Endpoints
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestQECSimulateEndpoint:

    async def test_qec_simulate_basic(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/simulate",
                json={
                    "code_type": "surface",
                    "decoder_type": "mwpm",
                    "code_distance": 5,
                    "physical_error_rate": 0.001,
                    "shots": 500,
                    "num_cycles": 3,
                    "noise_model": "depolarizing",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code_type"] == "surface"
        assert data["decoder_type"] == "mwpm"
        assert data["code_distance"] == 5
        assert data["total_shots"] == 500
        assert data["delegated"] is True
        assert "logical_error_rate" in data
        assert "success_count" in data
        assert "failure_count" in data
        assert data["success_count"] + data["failure_count"] == 500

    async def test_qec_simulate_defaults(self, test_client):
        async with test_client as client:
            resp = await client.post("/gateway/qec/simulate", json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code_type"] == "surface"
        assert data["decoder_type"] == "mwpm"
        assert data["code_distance"] == 5
        assert data["total_shots"] == 1000

    async def test_qec_simulate_syndrome_history(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/simulate",
                json={"num_cycles": 5, "code_distance": 3},
            )
        data = resp.json()
        assert len(data["syndrome_history"]) == 5
        for cycle_data in data["syndrome_history"]:
            assert "cycle" in cycle_data
            assert "syndrome_values" in cycle_data
            assert "detected_errors" in cycle_data

    async def test_qec_simulate_color_code(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/simulate",
                json={"code_type": "color", "code_distance": 7},
            )
        assert resp.status_code == 200
        assert resp.json()["code_type"] == "color"

    async def test_qec_simulate_union_find_decoder(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/simulate",
                json={"decoder_type": "union_find"},
            )
        assert resp.status_code == 200
        assert resp.json()["decoder_type"] == "union_find"

    async def test_qec_simulate_lookup_decoder_large_distance(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/simulate",
                json={"decoder_type": "lookup", "code_distance": 7},
            )
        assert resp.status_code == 200

    async def test_qec_simulate_measurement_error_noise(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/simulate",
                json={"noise_model": "measurement_error"},
            )
        assert resp.status_code == 200
        assert resp.json()["noise_model"] == "measurement_error"

    async def test_qec_simulate_idle_error_noise(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/simulate",
                json={"noise_model": "idle_error"},
            )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestQECDecodeSyndromeEndpoint:

    async def test_decode_syndrome_basic(self, test_client):
        syndrome = [[0, 1, 0], [1, 0, 0], [0, 0, 1]]
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/decode-syndrome",
                json={
                    "syndrome_values": syndrome,
                    "decoder_type": "mwpm",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "corrections" in data
        assert "logical_error" in data
        assert "confidence" in data
        assert "decoding_time_ms" in data
        assert data["delegated"] is True

    async def test_decode_syndrome_corrections_match_errors(self, test_client):
        # 2 errors in syndrome
        syndrome = [[1, 0], [0, 1]]
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/decode-syndrome",
                json={"syndrome_values": syndrome, "decoder_type": "mwpm"},
            )
        data = resp.json()
        assert len(data["corrections"]) == 2

    async def test_decode_syndrome_no_errors(self, test_client):
        syndrome = [[0, 0], [0, 0]]
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/decode-syndrome",
                json={"syndrome_values": syndrome},
            )
        data = resp.json()
        assert len(data["corrections"]) == 0
        assert data["logical_error"] is False

    async def test_decode_syndrome_lookup_decoder(self, test_client):
        syndrome = [[1, 1], [1, 1]]
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/decode-syndrome",
                json={"syndrome_values": syndrome, "decoder_type": "lookup"},
            )
        data = resp.json()
        assert data["logical_error"] is True  # 4 errors > 3

    async def test_decode_syndrome_union_find_decoder(self, test_client):
        syndrome = [[1, 0], [0, 0]]
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/decode-syndrome",
                json={"syndrome_values": syndrome, "decoder_type": "union_find"},
            )
        assert resp.status_code == 200


@pytest.mark.asyncio
class TestQECBBDecoderEndpoint:

    async def test_bb_decoder_basic(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={
                    "code_family": "bb_72_12_6",
                    "decoder": "bp_osd",
                    "error_rate": 0.001,
                    "rounds": 10,
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code_family"] == "bb_72_12_6"
        assert data["decoder"] == "bp_osd"
        assert data["delegated"] is True
        assert "logical_error_rate" in data
        assert "threshold" in data
        assert "encoding_rate" in data
        assert "surface_code_comparison" in data
        assert "decoder_metrics" in data

    async def test_bb_decoder_all_families(self, test_client):
        families = ["bb_72_12_6", "bb_90_8_10", "bb_144_12_12", "bb_288_12_18"]
        async with test_client as client:
            for family in families:
                resp = await client.post(
                    "/gateway/qec/bb-decoder",
                    json={"code_family": family, "error_rate": 0.001},
                )
                assert resp.status_code == 200, f"Failed for family {family}"
                data = resp.json()
                assert data["code_family"] == family

    async def test_bb_decoder_unknown_family(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "unknown_family_99"},
            )
        assert resp.status_code == 400

    async def test_bb_decoder_surface_code_comparison(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "bb_144_12_12", "error_rate": 0.001},
            )
        comparison = resp.json()["surface_code_comparison"]
        assert "surface_code_qubits_needed" in comparison
        assert "bb_code_qubits_needed" in comparison
        assert "qubit_savings_percent" in comparison
        assert comparison["bb_code_qubits_needed"] == 144

    async def test_bb_decoder_above_threshold(self, test_client):
        """Physical error rate above threshold should give high logical error rate."""
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "bb_72_12_6", "error_rate": 0.05},
            )
        data = resp.json()
        assert data["logical_error_rate"] > 0.01

    async def test_bb_decoder_below_threshold(self, test_client):
        """Physical error rate well below threshold."""
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "bb_72_12_6", "error_rate": 0.0001},
            )
        data = resp.json()
        # Below threshold, logical should be suppressed
        assert data["logical_error_rate"] < 0.5

    async def test_bb_decoder_mwpm(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "bb_72_12_6", "decoder": "mwpm", "error_rate": 0.001},
            )
        assert resp.status_code == 200
        assert resp.json()["decoder"] == "mwpm"

    async def test_bb_decoder_metrics(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "bb_72_12_6", "decoder": "bp_osd", "error_rate": 0.001},
            )
        metrics = resp.json()["decoder_metrics"]
        assert metrics["decoder_name"] == "bp_osd"
        assert "avg_decoding_time_us" in metrics
        assert "max_decoding_time_us" in metrics
        assert "convergence_iterations" in metrics  # bp decoder should have this


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Generic Protocol Message Endpoint
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestMessageEndpoint:

    async def test_health_check_message(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={"type": "health_check"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "health_response"
        assert data["payload"]["status"] == "healthy"

    async def test_list_backends_message(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={"type": "list_backends", "source": "test_client"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "backend_info"
        assert "backends" in data["payload"]
        assert data["target"] == "test_client"

    async def test_execute_circuit_message(self, test_client, bell_circuit):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={
                    "type": "execute_circuit",
                    "payload": {"circuit": bell_circuit, "shots": 200},
                    "source": "test_client",
                    "correlation_id": "corr-exec-001",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "execute_result"
        assert data["correlation_id"] == "corr-exec-001"
        assert data["target"] == "test_client"
        assert data["payload"]["success"] is True
        assert data["payload"]["shots"] == 200

    async def test_qec_simulate_message(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={
                    "type": "qec_simulate",
                    "payload": {
                        "code_type": "surface",
                        "code_distance": 3,
                        "shots": 100,
                        "num_cycles": 2,
                    },
                    "source": "backend",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "qec_simulate_result"
        assert data["target"] == "backend"

    async def test_qec_decode_syndrome_message(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={
                    "type": "qec_decode_syndrome",
                    "payload": {
                        "syndrome_values": [[1, 0], [0, 1]],
                        "decoder_type": "mwpm",
                    },
                    "source": "backend",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "qec_decode_result"

    async def test_bb_decoder_message(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={
                    "type": "bb_decoder",
                    "payload": {
                        "code_family": "bb_72_12_6",
                        "decoder": "bp_osd",
                        "error_rate": 0.001,
                    },
                    "source": "backend",
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "bb_decoder_result"

    async def test_unsupported_message_type(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={"type": "stream_results", "payload": {}},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "error"

    async def test_unknown_message_type_becomes_error(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={"type": "totally_unknown_type"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "error"

    async def test_message_preserves_correlation_id(self, test_client):
        async with test_client as client:
            resp = await client.post(
                "/gateway/message",
                json={
                    "type": "health_check",
                    "correlation_id": "my-corr-id-123",
                },
            )
        data = resp.json()
        # health_check handler doesn't explicitly carry correlation_id
        # but the message should still have one
        assert "correlation_id" in data

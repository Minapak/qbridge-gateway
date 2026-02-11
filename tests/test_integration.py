"""
Integration tests — SwiftQuantumBackend connectivity
======================================================

These tests verify the gateway agent can handle the full request/response
lifecycle that SwiftQuantumBackend would use when delegating work.

Covers:
- End-to-end circuit execution flow
- End-to-end QEC delegation flow
- End-to-end BB decoder delegation flow
- Protocol message round-trips
- Job lifecycle (execute -> query -> cancel)
- Multiple concurrent-style requests
- Error recovery
- Backend discovery flow
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from gateway_agent.server import GatewayServer
from gateway_agent.device_interface import LocalSimulator
from gateway_agent.protocol import GatewayMessage, MessageType


@pytest.fixture
def integration_server():
    """Server configured for integration testing."""
    sim = LocalSimulator(name="integration_sim", num_qubits=20)
    return GatewayServer(device=sim)


@pytest.fixture
def integration_client(integration_server):
    transport = ASGITransport(app=integration_server.app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  End-to-end circuit execution
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestE2ECircuitExecution:

    async def test_discover_then_execute(self, integration_client):
        """SwiftQuantumBackend flow: discover backends, then execute."""
        async with integration_client as client:
            # Step 1: Discover backends
            backends_resp = await client.get("/gateway/backends")
            assert backends_resp.status_code == 200
            backends = backends_resp.json()["backends"]
            assert len(backends) >= 1
            backend_name = backends[0]["name"]
            num_qubits = backends[0]["num_qubits"]

            # Step 2: Execute a circuit
            circuit = {
                "num_qubits": min(2, num_qubits),
                "gates": [
                    {"gate": "h", "qubits": [0]},
                    {"gate": "cx", "qubits": [0, 1]},
                ],
            }
            exec_resp = await client.post(
                "/gateway/execute",
                json={"circuit": circuit, "shots": 1000, "backend": backend_name},
            )
            assert exec_resp.status_code == 200
            result = exec_resp.json()
            assert result["success"] is True
            assert result["backend"] == backend_name
            assert sum(result["counts"].values()) == 1000

    async def test_execute_then_retrieve_job(self, integration_client):
        """Execute, then query job status - full lifecycle."""
        async with integration_client as client:
            # Execute
            circuit = {
                "num_qubits": 2,
                "gates": [{"gate": "h", "qubits": [0]}],
            }
            exec_resp = await client.post(
                "/gateway/execute",
                json={"circuit": circuit, "shots": 500},
            )
            assert exec_resp.status_code == 200
            job_id = exec_resp.json()["job_id"]

            # Retrieve job
            job_resp = await client.get(f"/gateway/job/{job_id}")
            assert job_resp.status_code == 200
            job_data = job_resp.json()
            assert job_data["job_id"] == job_id
            assert job_data["status"] == "COMPLETED"
            assert job_data["shots"] == 500

    async def test_execute_then_cancel_job(self, integration_client):
        """Execute, then cancel the job."""
        async with integration_client as client:
            circuit = {
                "num_qubits": 2,
                "gates": [{"gate": "h", "qubits": [0]}, {"gate": "cx", "qubits": [0, 1]}],
            }
            exec_resp = await client.post(
                "/gateway/execute",
                json={"circuit": circuit, "shots": 100},
            )
            job_id = exec_resp.json()["job_id"]

            cancel_resp = await client.post(f"/gateway/job/{job_id}/cancel")
            assert cancel_resp.status_code == 200
            assert cancel_resp.json()["cancelled"] is True

    async def test_multiple_executions(self, integration_client):
        """Run several circuits sequentially, verify all produce results."""
        circuits = [
            {  # Bell state
                "num_qubits": 2,
                "gates": [{"gate": "h", "qubits": [0]}, {"gate": "cx", "qubits": [0, 1]}],
            },
            {  # GHZ
                "num_qubits": 3,
                "gates": [
                    {"gate": "h", "qubits": [0]},
                    {"gate": "cx", "qubits": [0, 1]},
                    {"gate": "cx", "qubits": [1, 2]},
                ],
            },
            {  # Superposition
                "num_qubits": 2,
                "gates": [
                    {"gate": "h", "qubits": [0]},
                    {"gate": "h", "qubits": [1]},
                ],
            },
        ]
        async with integration_client as client:
            job_ids = []
            for circuit in circuits:
                resp = await client.post(
                    "/gateway/execute",
                    json={"circuit": circuit, "shots": 200},
                )
                assert resp.status_code == 200
                assert resp.json()["success"] is True
                job_ids.append(resp.json()["job_id"])

            # All jobs should be unique
            assert len(set(job_ids)) == 3

            # All jobs should be retrievable
            for job_id in job_ids:
                job_resp = await client.get(f"/gateway/job/{job_id}")
                assert job_resp.status_code == 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  End-to-end QEC delegation
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestE2EQECDelegation:

    async def test_qec_simulate_full_flow(self, integration_client):
        """SwiftQuantumBackend delegates QEC simulation via protocol message."""
        async with integration_client as client:
            resp = await client.post(
                "/gateway/message",
                json={
                    "type": "qec_simulate",
                    "source": "swiftquantum_backend",
                    "target": "researcher_lab",
                    "correlation_id": "qec-corr-001",
                    "payload": {
                        "code_type": "surface",
                        "decoder_type": "mwpm",
                        "code_distance": 5,
                        "physical_error_rate": 0.001,
                        "shots": 500,
                        "num_cycles": 5,
                    },
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "qec_simulate_result"
        assert data["source"] != ""
        assert data["target"] == "swiftquantum_backend"
        assert data["correlation_id"] == "qec-corr-001"
        payload = data["payload"]
        assert payload["delegated"] is True
        assert payload["total_shots"] == 500

    async def test_qec_decode_then_simulate(self, integration_client):
        """Run a QEC simulation, then decode a syndrome from it."""
        async with integration_client as client:
            # Step 1: Simulate
            sim_resp = await client.post(
                "/gateway/qec/simulate",
                json={
                    "code_type": "surface",
                    "code_distance": 3,
                    "shots": 100,
                    "num_cycles": 2,
                },
            )
            assert sim_resp.status_code == 200
            sim_data = sim_resp.json()

            # Step 2: Take a syndrome from the simulation and decode it
            syndrome = sim_data["syndrome_history"][0]["syndrome_values"]
            decode_resp = await client.post(
                "/gateway/qec/decode-syndrome",
                json={
                    "syndrome_values": syndrome,
                    "decoder_type": "mwpm",
                },
            )
            assert decode_resp.status_code == 200
            decode_data = decode_resp.json()
            assert "corrections" in decode_data
            assert "logical_error" in decode_data

    async def test_bb_decoder_comparison_flow(self, integration_client):
        """Compare BB code families - typical research workflow."""
        families = ["bb_72_12_6", "bb_144_12_12"]
        results = {}

        async with integration_client as client:
            for family in families:
                resp = await client.post(
                    "/gateway/qec/bb-decoder",
                    json={
                        "code_family": family,
                        "decoder": "bp_osd",
                        "error_rate": 0.001,
                        "rounds": 10,
                    },
                )
                assert resp.status_code == 200
                results[family] = resp.json()

        # Larger code family should have better qubit savings
        assert (
            results["bb_144_12_12"]["surface_code_comparison"]["qubit_savings_percent"]
            > 0
        )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Error recovery
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestE2EErrorRecovery:

    async def test_invalid_circuit_does_not_break_server(self, integration_client):
        """After a bad request, subsequent requests should still work."""
        async with integration_client as client:
            # Bad request
            bad_resp = await client.post(
                "/gateway/execute",
                json={
                    "circuit": {"num_qubits": 999, "gates": [{"gate": "h", "qubits": [0]}]},
                    "shots": 100,
                },
            )
            assert bad_resp.status_code == 400

            # Good request should still work
            good_resp = await client.post(
                "/gateway/execute",
                json={
                    "circuit": {"num_qubits": 2, "gates": [{"gate": "h", "qubits": [0]}]},
                    "shots": 100,
                },
            )
            assert good_resp.status_code == 200
            assert good_resp.json()["success"] is True

    async def test_nonexistent_job_then_valid_query(self, integration_client):
        async with integration_client as client:
            # 404 for nonexistent
            resp1 = await client.get("/gateway/job/fake_job")
            assert resp1.status_code == 404

            # Execute and query
            exec_resp = await client.post(
                "/gateway/execute",
                json={
                    "circuit": {"num_qubits": 2, "gates": [{"gate": "h", "qubits": [0]}]},
                    "shots": 50,
                },
            )
            job_id = exec_resp.json()["job_id"]
            resp2 = await client.get(f"/gateway/job/{job_id}")
            assert resp2.status_code == 200

    async def test_invalid_bb_family_then_valid(self, integration_client):
        async with integration_client as client:
            bad_resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "invalid_family"},
            )
            assert bad_resp.status_code == 400

            good_resp = await client.post(
                "/gateway/qec/bb-decoder",
                json={"code_family": "bb_72_12_6", "error_rate": 0.001},
            )
            assert good_resp.status_code == 200


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Health check flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestE2EHealthCheck:

    async def test_health_via_rest(self, integration_client):
        async with integration_client as client:
            resp = await client.get("/gateway/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

    async def test_health_via_protocol(self, integration_client):
        async with integration_client as client:
            resp = await client.post(
                "/gateway/message",
                json={"type": "health_check"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "health_response"
        assert data["payload"]["status"] == "healthy"

    async def test_providers_endpoint(self, integration_client):
        async with integration_client as client:
            resp = await client.get("/gateway/providers")
        assert resp.status_code == 200
        providers = resp.json()["providers"]
        assert len(providers) >= 1
        assert providers[0]["type"] == "researcher_hosted"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Transpile flow
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@pytest.mark.asyncio
class TestE2ETranspile:

    async def test_transpile_and_execute(self, integration_client):
        """Transpile a circuit, then execute it."""
        circuit = {
            "num_qubits": 2,
            "gates": [
                {"gate": "h", "qubits": [0]},
                {"gate": "cx", "qubits": [0, 1]},
            ],
        }
        async with integration_client as client:
            # Transpile
            t_resp = await client.post(
                "/gateway/transpile",
                json={"circuit": circuit, "optimization_level": 2},
            )
            assert t_resp.status_code == 200
            transpiled = t_resp.json()["transpiled_circuit"]

            # Execute transpiled circuit
            e_resp = await client.post(
                "/gateway/execute",
                json={"circuit": transpiled, "shots": 500},
            )
            assert e_resp.status_code == 200
            assert e_resp.json()["success"] is True

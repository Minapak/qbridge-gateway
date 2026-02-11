"""
Tests for gateway_agent.device_interface
=========================================

Covers:
- DeviceInfo dataclass: defaults, custom values, field types
- ExecutionResult dataclass: to_dict, error inclusion/exclusion
- DeviceInterface ABC: validate_circuit, transpile default
- LocalSimulator: construction, device_info, execute (various circuits),
  get_status, get_job, simulation patterns (Bell, GHZ, superposition, ground)
"""

import pytest
from unittest.mock import MagicMock

from gateway_agent.device_interface import (
    DeviceInfo,
    ExecutionResult,
    DeviceInterface,
    LocalSimulator,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DeviceInfo dataclass
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDeviceInfo:

    def test_minimal_construction(self):
        info = DeviceInfo(name="dev", num_qubits=3)
        assert info.name == "dev"
        assert info.num_qubits == 3

    def test_default_technology(self):
        info = DeviceInfo(name="d", num_qubits=1)
        assert info.technology == "custom"

    def test_default_connectivity(self):
        info = DeviceInfo(name="d", num_qubits=1)
        assert info.connectivity == "custom"

    def test_default_supported_gates(self):
        info = DeviceInfo(name="d", num_qubits=1)
        assert "h" in info.supported_gates
        assert "cx" in info.supported_gates

    def test_default_max_shots(self):
        info = DeviceInfo(name="d", num_qubits=1)
        assert info.max_shots == 100000

    def test_default_status(self):
        info = DeviceInfo(name="d", num_qubits=1)
        assert info.status == "online"

    def test_default_metadata(self):
        info = DeviceInfo(name="d", num_qubits=1)
        assert info.metadata == {}

    def test_custom_fields(self):
        info = DeviceInfo(
            name="my_qpu",
            num_qubits=50,
            technology="superconducting",
            connectivity="heavy-hex",
            supported_gates=["h", "cx", "rz"],
            max_shots=50000,
            status="maintenance",
            metadata={"lab": "MIT"},
        )
        assert info.technology == "superconducting"
        assert info.connectivity == "heavy-hex"
        assert info.max_shots == 50000
        assert info.status == "maintenance"
        assert info.metadata["lab"] == "MIT"

    def test_supported_gates_independence(self):
        """Each DeviceInfo should have its own supported_gates list."""
        info1 = DeviceInfo(name="a", num_qubits=1)
        info2 = DeviceInfo(name="b", num_qubits=1)
        info1.supported_gates.append("custom_gate")
        assert "custom_gate" not in info2.supported_gates

    def test_metadata_independence(self):
        """Each DeviceInfo should have its own metadata dict."""
        info1 = DeviceInfo(name="a", num_qubits=1)
        info2 = DeviceInfo(name="b", num_qubits=1)
        info1.metadata["key"] = "val"
        assert "key" not in info2.metadata


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ExecutionResult dataclass
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestExecutionResult:

    def test_successful_result(self, execution_result):
        assert execution_result.success is True
        assert execution_result.error is None
        assert execution_result.job_id == "test_job_001"
        assert execution_result.shots == 1024
        assert sum(execution_result.counts.values()) == 1024

    def test_failed_result(self, failed_execution_result):
        assert failed_execution_result.success is False
        assert failed_execution_result.error == "Circuit validation failed"
        assert failed_execution_result.counts == {}

    def test_to_dict_success(self, execution_result):
        d = execution_result.to_dict()
        assert d["job_id"] == "test_job_001"
        assert d["counts"] == {"00": 500, "11": 524}
        assert d["shots"] == 1024
        assert d["execution_time_ms"] == 12.5
        assert d["success"] is True
        assert "error" not in d  # error excluded when None

    def test_to_dict_failure(self, failed_execution_result):
        d = failed_execution_result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Circuit validation failed"

    def test_to_dict_metadata(self, execution_result):
        d = execution_result.to_dict()
        assert d["metadata"]["simulator"] == "test"

    def test_default_metadata(self):
        result = ExecutionResult(
            job_id="j1", counts={"0": 10}, shots=10,
            execution_time_ms=1.0, success=True,
        )
        assert result.metadata == {}
        d = result.to_dict()
        assert d["metadata"] == {}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DeviceInterface ABC — validate_circuit & transpile
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class ConcreteDevice(DeviceInterface):
    """Concrete implementation for testing the ABC."""

    def __init__(self, num_qubits=5, gates=None):
        self._num_qubits = num_qubits
        self._gates = gates or ["h", "cx", "x", "rz"]

    def get_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name="concrete_test",
            num_qubits=self._num_qubits,
            supported_gates=self._gates,
        )

    def execute(self, circuit, shots, options=None):
        return ExecutionResult(
            job_id="concrete_001", counts={"0" * circuit.get("num_qubits", 1): shots},
            shots=shots, execution_time_ms=1.0, success=True,
        )

    def get_status(self):
        return {"status": "online"}


class TestDeviceInterfaceABC:

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            DeviceInterface()

    def test_concrete_implementation(self):
        dev = ConcreteDevice()
        info = dev.get_device_info()
        assert info.name == "concrete_test"

    def test_validate_circuit_valid(self):
        dev = ConcreteDevice(num_qubits=5)
        circuit = {
            "num_qubits": 3,
            "gates": [
                {"gate": "h", "qubits": [0]},
                {"gate": "cx", "qubits": [0, 1]},
            ],
        }
        errors = dev.validate_circuit(circuit)
        assert errors == []

    def test_validate_circuit_too_many_qubits(self):
        dev = ConcreteDevice(num_qubits=3)
        circuit = {"num_qubits": 10, "gates": []}
        errors = dev.validate_circuit(circuit)
        assert len(errors) == 1
        assert "10 qubits" in errors[0]
        assert "3" in errors[0]

    def test_validate_circuit_unsupported_gate(self):
        dev = ConcreteDevice(num_qubits=5, gates=["h", "x"])
        circuit = {
            "num_qubits": 2,
            "gates": [{"gate": "cx", "qubits": [0, 1]}],
        }
        errors = dev.validate_circuit(circuit)
        assert any("Unsupported gate: cx" in e for e in errors)

    def test_validate_circuit_qubit_out_of_range(self):
        dev = ConcreteDevice(num_qubits=3)
        circuit = {
            "num_qubits": 3,
            "gates": [{"gate": "h", "qubits": [5]}],
        }
        errors = dev.validate_circuit(circuit)
        assert any("Qubit index 5 out of range" in e for e in errors)

    def test_validate_circuit_multiple_errors(self):
        dev = ConcreteDevice(num_qubits=2, gates=["h"])
        circuit = {
            "num_qubits": 5,
            "gates": [
                {"gate": "cx", "qubits": [0, 10]},
                {"gate": "rz", "qubits": [0]},
            ],
        }
        errors = dev.validate_circuit(circuit)
        # Should have: too many qubits, unsupported gate cx, qubit 10 out of range, unsupported gate rz
        assert len(errors) >= 3

    def test_transpile_default_passthrough(self):
        dev = ConcreteDevice()
        circuit = {"num_qubits": 2, "gates": [{"gate": "h", "qubits": [0]}]}
        result = dev.transpile(circuit)
        assert result == circuit

    def test_transpile_with_optimization_level(self):
        dev = ConcreteDevice()
        circuit = {"num_qubits": 1, "gates": []}
        result = dev.transpile(circuit, optimization_level=3)
        assert result == circuit  # default impl ignores optimization level

    def test_validate_empty_circuit(self):
        dev = ConcreteDevice(num_qubits=5)
        circuit = {"num_qubits": 0, "gates": []}
        errors = dev.validate_circuit(circuit)
        assert errors == []


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LocalSimulator
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLocalSimulatorConstruction:

    def test_default_construction(self):
        sim = LocalSimulator()
        assert sim.name == "local_simulator"
        assert sim.num_qubits == 20

    def test_custom_construction(self, local_simulator):
        assert local_simulator.name == "test_sim"
        assert local_simulator.num_qubits == 10

    def test_jobs_initially_empty(self, local_simulator):
        assert local_simulator._jobs == {}


class TestLocalSimulatorDeviceInfo:

    def test_device_info_name(self, local_simulator):
        info = local_simulator.get_device_info()
        assert info.name == "test_sim"

    def test_device_info_num_qubits(self, local_simulator):
        info = local_simulator.get_device_info()
        assert info.num_qubits == 10

    def test_device_info_technology(self, local_simulator):
        info = local_simulator.get_device_info()
        assert info.technology == "simulator"

    def test_device_info_connectivity(self, local_simulator):
        info = local_simulator.get_device_info()
        assert info.connectivity == "full"

    def test_device_info_supported_gates(self, local_simulator):
        info = local_simulator.get_device_info()
        expected_gates = {
            "h", "x", "y", "z", "cx", "cnot", "ccx",
            "rx", "ry", "rz", "s", "sdg", "t", "tdg",
            "swap", "cz", "id", "measure",
        }
        assert set(info.supported_gates) == expected_gates

    def test_device_info_max_shots(self, local_simulator):
        info = local_simulator.get_device_info()
        assert info.max_shots == 1000000

    def test_device_info_status(self, local_simulator):
        info = local_simulator.get_device_info()
        assert info.status == "online"

    def test_device_info_metadata(self, local_simulator):
        info = local_simulator.get_device_info()
        assert info.metadata["type"] == "local_simulator"
        assert info.metadata["version"] == "1.0"


class TestLocalSimulatorExecution:

    def test_execute_bell_circuit(self, local_simulator, bell_circuit):
        result = local_simulator.execute(bell_circuit, shots=10000)
        assert result.success is True
        assert result.error is None
        assert result.shots == 10000
        assert sum(result.counts.values()) == 10000
        # Bell state: only |00> and |11>
        assert set(result.counts.keys()) == {"00", "11"}
        # Roughly 50/50 (within 5%)
        assert abs(result.counts["00"] - 5000) < 600
        assert abs(result.counts["11"] - 5000) < 600

    def test_execute_ghz_circuit(self, local_simulator, ghz_circuit):
        result = local_simulator.execute(ghz_circuit, shots=10000)
        assert result.success is True
        assert sum(result.counts.values()) == 10000
        assert set(result.counts.keys()) == {"000", "111"}

    def test_execute_single_h(self, local_simulator):
        """Single H gate on 2-qubit system: partial superposition."""
        circuit = {
            "num_qubits": 2,
            "gates": [{"gate": "h", "qubits": [0]}],
        }
        result = local_simulator.execute(circuit, shots=10000)
        assert result.success is True
        assert sum(result.counts.values()) == 10000

    def test_execute_full_superposition(self, local_simulator):
        """H on all qubits: uniform distribution."""
        circuit = {
            "num_qubits": 3,
            "gates": [
                {"gate": "h", "qubits": [0]},
                {"gate": "h", "qubits": [1]},
                {"gate": "h", "qubits": [2]},
            ],
        }
        result = local_simulator.execute(circuit, shots=8000)
        assert result.success is True
        assert sum(result.counts.values()) == 8000
        # 2^3 = 8 possible states
        assert len(result.counts) == 8

    def test_execute_ground_state(self, local_simulator):
        """No H or CX gates: should produce ground state only."""
        circuit = {
            "num_qubits": 3,
            "gates": [
                {"gate": "x", "qubits": [0]},
                {"gate": "z", "qubits": [1]},
            ],
        }
        result = local_simulator.execute(circuit, shots=100)
        assert result.success is True
        # No superposition gates -> all |000>
        assert result.counts.get("000") == 100

    def test_execute_generates_job_id(self, local_simulator, bell_circuit):
        result = local_simulator.execute(bell_circuit, shots=100)
        assert result.job_id.startswith("sim_")
        assert len(result.job_id) > 4

    def test_execute_stores_job(self, local_simulator, bell_circuit):
        result = local_simulator.execute(bell_circuit, shots=100)
        stored = local_simulator.get_job(result.job_id)
        assert stored is not None
        assert stored.job_id == result.job_id

    def test_execute_metadata_has_evidence_hash(self, local_simulator, bell_circuit):
        result = local_simulator.execute(bell_circuit, shots=100)
        assert "evidence_hash" in result.metadata
        assert len(result.metadata["evidence_hash"]) == 64  # SHA-256 hex

    def test_execute_metadata_has_simulator_name(self, local_simulator, bell_circuit):
        result = local_simulator.execute(bell_circuit, shots=100)
        assert result.metadata["simulator"] == "test_sim"

    def test_execute_timing(self, local_simulator, bell_circuit):
        result = local_simulator.execute(bell_circuit, shots=100)
        assert result.execution_time_ms >= 0

    def test_execute_invalid_circuit_too_many_qubits(
        self, local_simulator, invalid_circuit_too_many_qubits
    ):
        result = local_simulator.execute(invalid_circuit_too_many_qubits, shots=100)
        assert result.success is False
        assert result.error is not None
        assert "qubits" in result.error.lower()

    def test_execute_invalid_circuit_bad_gate(
        self, local_simulator, invalid_circuit_bad_gate
    ):
        result = local_simulator.execute(invalid_circuit_bad_gate, shots=100)
        assert result.success is False
        assert "unsupported_gate_xyz" in result.error.lower()

    def test_execute_stores_failed_job(
        self, local_simulator, invalid_circuit_too_many_qubits
    ):
        result = local_simulator.execute(invalid_circuit_too_many_qubits, shots=100)
        stored = local_simulator.get_job(result.job_id)
        assert stored is not None
        assert stored.success is False

    def test_multiple_executions_unique_job_ids(self, local_simulator, bell_circuit):
        results = [local_simulator.execute(bell_circuit, shots=10) for _ in range(5)]
        job_ids = [r.job_id for r in results]
        assert len(set(job_ids)) == 5


class TestLocalSimulatorStatus:

    def test_get_status_basic(self, local_simulator):
        status = local_simulator.get_status()
        assert status["status"] == "online"
        assert status["device"] == "test_sim"
        assert status["type"] == "simulator"
        assert status["num_qubits"] == 10
        assert status["jobs_completed"] == 0

    def test_get_status_after_jobs(self, local_simulator, bell_circuit):
        local_simulator.execute(bell_circuit, shots=10)
        local_simulator.execute(bell_circuit, shots=10)
        status = local_simulator.get_status()
        assert status["jobs_completed"] == 2


class TestLocalSimulatorGetJob:

    def test_get_existing_job(self, local_simulator, bell_circuit):
        result = local_simulator.execute(bell_circuit, shots=100)
        job = local_simulator.get_job(result.job_id)
        assert job is not None
        assert job.job_id == result.job_id

    def test_get_nonexistent_job(self, local_simulator):
        job = local_simulator.get_job("nonexistent_job_id")
        assert job is None


class TestLocalSimulatorValidation:

    def test_validate_valid_circuit(self, local_simulator, bell_circuit):
        errors = local_simulator.validate_circuit(bell_circuit)
        assert errors == []

    def test_validate_too_many_qubits(self, local_simulator):
        circuit = {"num_qubits": 100, "gates": []}
        errors = local_simulator.validate_circuit(circuit)
        assert len(errors) == 1

    def test_validate_unsupported_gate(self, local_simulator):
        circuit = {
            "num_qubits": 2,
            "gates": [{"gate": "custom_magic_gate", "qubits": [0]}],
        }
        errors = local_simulator.validate_circuit(circuit)
        assert any("Unsupported gate" in e for e in errors)

    def test_validate_qubit_out_of_range(self, local_simulator):
        circuit = {
            "num_qubits": 10,
            "gates": [{"gate": "h", "qubits": [15]}],
        }
        errors = local_simulator.validate_circuit(circuit)
        assert any("out of range" in e for e in errors)


class TestLocalSimulatorTranspile:

    def test_transpile_passthrough(self, local_simulator, bell_circuit):
        result = local_simulator.transpile(bell_circuit)
        assert result == bell_circuit

    def test_transpile_optimization_levels(self, local_simulator, bell_circuit):
        for level in [0, 1, 2, 3]:
            result = local_simulator.transpile(bell_circuit, optimization_level=level)
            assert result == bell_circuit

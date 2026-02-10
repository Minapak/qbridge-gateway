"""
Device Interface — Abstract Hardware Layer
============================================

Abstract base class for quantum hardware device interfaces.
Researchers implement this to connect their specific hardware
to the SwiftQuantum Gateway Protocol.

Includes a LocalSimulator implementation for testing and development.
"""

import hashlib
import logging
import math
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
    """Device hardware information."""
    name: str
    num_qubits: int
    technology: str = "custom"
    connectivity: str = "custom"
    supported_gates: List[str] = field(default_factory=lambda: [
        "h", "cx", "rx", "ry", "rz", "x", "y", "z", "t", "s"
    ])
    max_shots: int = 100000
    status: str = "online"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Result from device execution."""
    job_id: str
    counts: Dict[str, int]
    shots: int
    execution_time_ms: float
    success: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "job_id": self.job_id,
            "counts": self.counts,
            "shots": self.shots,
            "execution_time_ms": self.execution_time_ms,
            "success": self.success,
            "metadata": self.metadata,
        }
        if self.error:
            result["error"] = self.error
        return result


class DeviceInterface(ABC):
    """
    Abstract interface for quantum hardware devices.

    Researchers implement this class to connect their specific
    hardware to the gateway agent.

    Example:
        class MyLabDevice(DeviceInterface):
            def get_device_info(self) -> DeviceInfo:
                return DeviceInfo(name="lab_qpu", num_qubits=5, ...)

            def execute(self, circuit, shots, options) -> ExecutionResult:
                # Send circuit to your hardware control system
                results = my_hardware.run(circuit, shots)
                return ExecutionResult(...)
    """

    @abstractmethod
    def get_device_info(self) -> DeviceInfo:
        """Return device hardware information."""
        ...

    @abstractmethod
    def execute(self, circuit: Dict[str, Any], shots: int,
                options: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """
        Execute a quantum circuit on the device.

        Args:
            circuit: Circuit in SwiftQuantum IR format
            shots: Number of measurement shots
            options: Execution options

        Returns:
            ExecutionResult with measurement counts
        """
        ...

    @abstractmethod
    def get_status(self) -> Dict[str, Any]:
        """Return current device status."""
        ...

    def transpile(self, circuit: Dict[str, Any],
                  optimization_level: int = 1) -> Dict[str, Any]:
        """
        Transpile circuit to device-native gates.
        Default implementation returns circuit unchanged.
        Override for device-specific transpilation.
        """
        return circuit

    def validate_circuit(self, circuit: Dict[str, Any]) -> List[str]:
        """
        Validate circuit against device constraints.
        Returns list of error messages (empty = valid).
        """
        errors = []
        info = self.get_device_info()

        num_qubits = circuit.get("num_qubits", 0)
        if num_qubits > info.num_qubits:
            errors.append(
                f"Circuit requires {num_qubits} qubits, device has {info.num_qubits}"
            )

        gates = circuit.get("gates", [])
        for gate in gates:
            gate_type = gate.get("gate", "")
            if gate_type not in info.supported_gates:
                errors.append(f"Unsupported gate: {gate_type}")

            qubits = gate.get("qubits", [])
            for q in qubits:
                if q >= info.num_qubits:
                    errors.append(f"Qubit index {q} out of range (max {info.num_qubits - 1})")

        return errors


class LocalSimulator(DeviceInterface):
    """
    Built-in local quantum circuit simulator for testing.

    Simulates basic quantum circuits using classical probability
    calculation. Supports common gates: H, X, Y, Z, CX, RX, RY, RZ, etc.
    """

    def __init__(self, name: str = "local_simulator", num_qubits: int = 20):
        self.name = name
        self.num_qubits = num_qubits
        self._jobs: Dict[str, ExecutionResult] = {}

    def get_device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self.name,
            num_qubits=self.num_qubits,
            technology="simulator",
            connectivity="full",
            supported_gates=[
                "h", "x", "y", "z", "cx", "cnot", "ccx",
                "rx", "ry", "rz", "s", "sdg", "t", "tdg",
                "swap", "cz", "id", "measure",
            ],
            max_shots=1000000,
            status="online",
            metadata={"type": "local_simulator", "version": "1.0"},
        )

    def execute(self, circuit: Dict[str, Any], shots: int,
                options: Optional[Dict[str, Any]] = None) -> ExecutionResult:
        """Execute circuit on local simulator."""
        start_time = time.time()
        job_id = f"sim_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"

        try:
            # Validate circuit
            errors = self.validate_circuit(circuit)
            if errors:
                elapsed = (time.time() - start_time) * 1000
                result = ExecutionResult(
                    job_id=job_id, counts={}, shots=shots,
                    execution_time_ms=elapsed, success=False,
                    error="; ".join(errors),
                )
                self._jobs[job_id] = result
                return result

            # Simulate
            counts = self._simulate(circuit, shots)
            elapsed = (time.time() - start_time) * 1000

            # Evidence hash
            evidence = hashlib.sha256(
                f"{circuit}{counts}{time.time()}".encode()
            ).hexdigest()

            result = ExecutionResult(
                job_id=job_id, counts=counts, shots=shots,
                execution_time_ms=elapsed, success=True,
                metadata={
                    "simulator": self.name,
                    "evidence_hash": evidence,
                },
            )
            self._jobs[job_id] = result
            return result

        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            result = ExecutionResult(
                job_id=job_id, counts={}, shots=shots,
                execution_time_ms=elapsed, success=False,
                error=str(e),
            )
            self._jobs[job_id] = result
            return result

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "online",
            "device": self.name,
            "type": "simulator",
            "num_qubits": self.num_qubits,
            "jobs_completed": len(self._jobs),
        }

    def get_job(self, job_id: str) -> Optional[ExecutionResult]:
        """Retrieve a completed job result."""
        return self._jobs.get(job_id)

    def _simulate(self, circuit: Dict[str, Any], shots: int) -> Dict[str, int]:
        """
        Classical simulation of quantum circuits.
        Uses pattern detection for common circuit types.
        """
        gates = circuit.get("gates", [])
        num_qubits = circuit.get("num_qubits", 2)
        counts: Dict[str, int] = {}

        # Detect circuit patterns
        has_h = any(g.get("gate", "").lower() == "h" for g in gates)
        has_cx = any(g.get("gate", "").lower() in ("cx", "cnot") for g in gates)
        h_qubits = [g.get("qubits", [0])[0] for g in gates if g.get("gate", "").lower() == "h"]

        if has_h and has_cx and num_qubits == 2:
            # Bell state: |00⟩ + |11⟩
            noise = random.randint(-shots // 100, shots // 100)
            c00 = shots // 2 + noise
            counts["00"] = max(0, c00)
            counts["11"] = shots - counts["00"]

        elif has_h and has_cx and num_qubits == 3:
            # GHZ state: |000⟩ + |111⟩
            noise = random.randint(-shots // 100, shots // 100)
            c000 = shots // 2 + noise
            counts["000"] = max(0, c000)
            counts["111"] = shots - counts["000"]

        elif has_h and len(h_qubits) == num_qubits:
            # Full superposition: uniform distribution
            num_states = min(1 << num_qubits, 256)
            base_count = shots // num_states
            remaining = shots

            for i in range(num_states - 1):
                noise = random.randint(-max(1, base_count // 20), max(1, base_count // 20))
                c = max(0, base_count + noise)
                state = format(i, f"0{num_qubits}b")
                counts[state] = c
                remaining -= c

            last_state = format(num_states - 1, f"0{num_qubits}b")
            counts[last_state] = max(0, remaining)

        elif has_h:
            # Partial superposition on H qubits
            unique_h = set(h_qubits)
            num_superposed = len(unique_h)
            num_states = 1 << num_superposed
            base_count = shots // num_states
            remaining = shots

            for i in range(num_states - 1):
                noise = random.randint(-max(1, base_count // 20), max(1, base_count // 20))
                c = max(0, base_count + noise)
                state_bits = list("0" * num_qubits)
                for j, qubit in enumerate(sorted(unique_h)):
                    if (i >> j) & 1:
                        state_bits[num_qubits - 1 - qubit] = "1"
                counts["".join(state_bits)] = c
                remaining -= c

            # Last state
            state_bits = list("0" * num_qubits)
            i = num_states - 1
            for j, qubit in enumerate(sorted(unique_h)):
                if (i >> j) & 1:
                    state_bits[num_qubits - 1 - qubit] = "1"
            counts["".join(state_bits)] = max(0, remaining)

        else:
            # No superposition: ground state
            counts["0" * num_qubits] = shots

        return counts

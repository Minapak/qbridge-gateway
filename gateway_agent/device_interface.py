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
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Maximum qubit count for the dense statevector engine. A complex128
# statevector of n qubits needs 2^n * 16 bytes; 20 qubits ≈ 16 MB.
MAX_STATEVECTOR_QUBITS = 20


def _circuit_seed(circuit: Dict[str, Any], shots: int) -> int:
    """Derive a deterministic 64-bit RNG seed from the circuit + shots.

    Reproducibility contract: the same circuit and shot count always
    produce the same measurement sampling. The seed is a stable hash of
    a canonical JSON encoding, so it does NOT depend on wall-clock time
    or dict ordering.
    """
    import json

    canonical = json.dumps(
        {"circuit": circuit, "shots": shots},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


# ─── Single/Two-qubit gate unitaries (numpy) ───

_INV_SQRT2 = 1.0 / math.sqrt(2.0)


def _gate_angle(gate: Dict[str, Any]) -> float:
    """Extract a rotation angle from a gate dict.

    Accepts `params` (list, OpenQASM/Qiskit style), or scalar `angle` /
    `theta`. Raises ValueError if a rotation gate carries no angle.
    """
    params = gate.get("params")
    if isinstance(params, (list, tuple)) and params:
        return float(params[0])
    for key in ("angle", "theta"):
        if gate.get(key) is not None:
            return float(gate[key])
    raise ValueError(
        f"Rotation gate '{gate.get('gate')}' requires an angle "
        f"(provide 'params': [theta] or 'angle')."
    )


def _single_qubit_unitary(name: str, gate: Dict[str, Any]) -> "np.ndarray":
    """Return the 2x2 unitary for a named single-qubit gate."""
    if name in ("h",):
        return np.array([[_INV_SQRT2, _INV_SQRT2],
                         [_INV_SQRT2, -_INV_SQRT2]], dtype=complex)
    if name in ("x",):
        return np.array([[0, 1], [1, 0]], dtype=complex)
    if name in ("y",):
        return np.array([[0, -1j], [1j, 0]], dtype=complex)
    if name in ("z",):
        return np.array([[1, 0], [0, -1]], dtype=complex)
    if name in ("s",):
        return np.array([[1, 0], [0, 1j]], dtype=complex)
    if name in ("sdg",):
        return np.array([[1, 0], [0, -1j]], dtype=complex)
    if name in ("t",):
        return np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=complex)
    if name in ("tdg",):
        return np.array([[1, 0], [0, np.exp(-1j * math.pi / 4)]], dtype=complex)
    if name in ("id", "i"):
        return np.eye(2, dtype=complex)
    if name in ("rx",):
        t = _gate_angle(gate) / 2.0
        return np.array([[math.cos(t), -1j * math.sin(t)],
                         [-1j * math.sin(t), math.cos(t)]], dtype=complex)
    if name in ("ry",):
        t = _gate_angle(gate) / 2.0
        return np.array([[math.cos(t), -math.sin(t)],
                         [math.sin(t), math.cos(t)]], dtype=complex)
    if name in ("rz",):
        t = _gate_angle(gate) / 2.0
        return np.array([[np.exp(-1j * t), 0],
                         [0, np.exp(1j * t)]], dtype=complex)
    raise ValueError(f"Unsupported single-qubit gate: {name}")


def _apply_single(state: "np.ndarray", u: "np.ndarray",
                  target: int, num_qubits: int) -> "np.ndarray":
    """Apply a 2x2 unitary to `target` of an n-qubit statevector.

    Qubit 0 is the least-significant bit of the basis-state index, matching
    the little-endian bit ordering used when formatting counts.
    """
    state = state.reshape([2] * num_qubits)
    axis = num_qubits - 1 - target  # little-endian: qubit 0 is last axis
    state = np.tensordot(u, state, axes=([1], [axis]))
    state = np.moveaxis(state, 0, axis)
    return state.reshape(-1)


def _apply_controlled(state: "np.ndarray", u: "np.ndarray",
                      control: int, target: int,
                      num_qubits: int) -> "np.ndarray":
    """Apply a controlled single-qubit unitary (control=1 branch)."""
    state = state.reshape([2] * num_qubits)
    c_axis = num_qubits - 1 - control
    t_axis = num_qubits - 1 - target

    idx_one = [slice(None)] * num_qubits
    idx_one[c_axis] = 1
    sub = state[tuple(idx_one)]  # control==1 subspace, (n-1) dims

    # target axis position within the reduced array
    red_axis = t_axis - 1 if t_axis > c_axis else t_axis
    sub = np.tensordot(u, sub, axes=([1], [red_axis]))
    sub = np.moveaxis(sub, 0, red_axis)
    state[tuple(idx_one)] = sub
    return state.reshape(-1)


def _apply_swap(state: "np.ndarray", a: int, b: int,
                num_qubits: int) -> "np.ndarray":
    """Swap two qubits in the statevector."""
    if a == b:
        return state
    state = state.reshape([2] * num_qubits)
    ax_a = num_qubits - 1 - a
    ax_b = num_qubits - 1 - b
    state = np.swapaxes(state, ax_a, ax_b)
    return state.reshape(-1)


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
                "h", "x", "y", "z", "cx", "cnot", "ccx", "toffoli",
                "rx", "ry", "rz", "s", "sdg", "t", "tdg",
                "swap", "cz", "id", "i", "measure", "barrier",
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

    def _statevector(self, circuit: Dict[str, Any]) -> "np.ndarray":
        """Build the final complex statevector by applying real gate
        unitaries to |0...0>.

        Qubit 0 is the least-significant bit of the basis index.
        Unsupported gates raise ValueError (surfaced by the route).
        """
        num_qubits = int(circuit.get("num_qubits", 0))
        if num_qubits <= 0:
            # Trivial 0-qubit circuit: single amplitude.
            return np.array([1.0 + 0j], dtype=complex)
        if num_qubits > MAX_STATEVECTOR_QUBITS:
            raise ValueError(
                f"Circuit requires {num_qubits} qubits; statevector simulator "
                f"is capped at {MAX_STATEVECTOR_QUBITS} (memory limit)."
            )

        state = np.zeros(1 << num_qubits, dtype=complex)
        state[0] = 1.0  # |0...0>

        for gate in circuit.get("gates", []):
            name = str(gate.get("gate", "")).lower()
            qubits = gate.get("qubits", [])

            if name in ("measure", "barrier"):
                # No-op for statevector evolution; sampling handles readout.
                continue

            if name in ("cx", "cnot"):
                if len(qubits) < 2:
                    raise ValueError(f"Gate '{name}' needs 2 qubits, got {qubits}")
                state = _apply_controlled(
                    state, _single_qubit_unitary("x", gate),
                    qubits[0], qubits[1], num_qubits)
            elif name in ("cz",):
                if len(qubits) < 2:
                    raise ValueError(f"Gate '{name}' needs 2 qubits, got {qubits}")
                state = _apply_controlled(
                    state, _single_qubit_unitary("z", gate),
                    qubits[0], qubits[1], num_qubits)
            elif name in ("swap",):
                if len(qubits) < 2:
                    raise ValueError(f"Gate '{name}' needs 2 qubits, got {qubits}")
                state = _apply_swap(state, qubits[0], qubits[1], num_qubits)
            elif name in ("ccx", "toffoli"):
                if len(qubits) < 3:
                    raise ValueError(f"Gate '{name}' needs 3 qubits, got {qubits}")
                # Decompose Toffoli into two nested controls via a temp:
                # apply X on target only when both controls are 1.
                state = self._apply_toffoli(state, qubits, num_qubits)
            else:
                if not qubits:
                    raise ValueError(f"Gate '{name}' needs a target qubit")
                u = _single_qubit_unitary(name, gate)
                state = _apply_single(state, u, qubits[0], num_qubits)

        return state

    def _apply_toffoli(self, state: "np.ndarray", qubits: List[int],
                       num_qubits: int) -> "np.ndarray":
        """Apply CCX by operating on the subspace where both controls=1."""
        c1, c2, t = qubits[0], qubits[1], qubits[2]
        st = state.reshape([2] * num_qubits)
        ax_c1 = num_qubits - 1 - c1
        ax_c2 = num_qubits - 1 - c2
        ax_t = num_qubits - 1 - t
        idx = [slice(None)] * num_qubits
        idx[ax_c1] = 1
        idx[ax_c2] = 1
        sub = st[tuple(idx)]
        # remaining target axis position after fixing two control axes
        removed = sorted([ax_c1, ax_c2])
        red_t = ax_t - sum(1 for r in removed if r < ax_t)
        sub = np.flip(sub, axis=red_t)  # X on target = flip the 0/1 axis
        st[tuple(idx)] = sub
        return st.reshape(-1)

    def _simulate(self, circuit: Dict[str, Any], shots: int) -> Dict[str, int]:
        """Real statevector simulation with seeded Born-rule sampling.

        Builds the exact final statevector, computes |amplitude|^2
        probabilities, and samples `shots` outcomes with a numpy RNG seeded
        deterministically from a hash of the circuit (reproducible: same
        circuit + shots -> same counts). Unsupported gates raise.
        """
        num_qubits = int(circuit.get("num_qubits", 0))
        state = self._statevector(circuit)

        probs = np.abs(state) ** 2
        total = probs.sum()
        if total <= 0:
            raise ValueError("Statevector has zero norm; cannot sample.")
        probs = probs / total

        rng = np.random.default_rng(_circuit_seed(circuit, shots))
        num_states = probs.shape[0]
        samples = rng.choice(num_states, size=int(shots), p=probs)
        idx, freqs = np.unique(samples, return_counts=True)

        width = max(num_qubits, 1)
        counts: Dict[str, int] = {}
        for state_idx, freq in zip(idx.tolist(), freqs.tolist()):
            bitstring = format(state_idx, f"0{width}b")
            counts[bitstring] = int(freq)
        return counts

    def transpile(self, circuit: Dict[str, Any],
                  optimization_level: int = 1) -> Dict[str, Any]:
        """Real (minimal) transpile pass.

        Performs a genuine pass over the circuit: decomposes a small set of
        composite gates into the native basis {h,x,y,z,s,t,rx,ry,rz,cx,cz,
        swap}, then computes real gate-count and depth metrics from the
        rewritten circuit (not an identity no-op). The returned circuit is
        functionally equivalent to the input.
        """
        gates_in = circuit.get("gates", [])
        num_qubits = int(circuit.get("num_qubits", 0))

        # Composite-gate decomposition into the native basis.
        decomposed: List[Dict[str, Any]] = []
        for gate in gates_in:
            name = str(gate.get("gate", "")).lower()
            qubits = list(gate.get("qubits", []))
            if name in ("cnot",):
                decomposed.append({"gate": "cx", "qubits": qubits})
            elif name in ("swap",):
                # SWAP(a,b) = CX(a,b) CX(b,a) CX(a,b)
                if len(qubits) >= 2:
                    a, b = qubits[0], qubits[1]
                    decomposed.append({"gate": "cx", "qubits": [a, b]})
                    decomposed.append({"gate": "cx", "qubits": [b, a]})
                    decomposed.append({"gate": "cx", "qubits": [a, b]})
                else:
                    decomposed.append({"gate": "swap", "qubits": qubits})
            elif name in ("tdg",):
                decomposed.append({"gate": "rz", "qubits": qubits,
                                   "params": [-math.pi / 4]})
            elif name in ("sdg",):
                decomposed.append({"gate": "rz", "qubits": qubits,
                                   "params": [-math.pi / 2]})
            else:
                decomposed.append(dict(gate))

        # Real depth analysis: greedy layering by qubit occupancy.
        depth = 0
        frontier: Dict[int, int] = {}
        for gate in decomposed:
            qs = gate.get("qubits", []) or [0]
            layer = max((frontier.get(q, 0) for q in qs), default=0) + 1
            for q in qs:
                frontier[q] = layer
            depth = max(depth, layer)

        single_q = sum(1 for g in decomposed if len(g.get("qubits", [])) == 1)
        two_q = sum(1 for g in decomposed if len(g.get("qubits", [])) >= 2)

        transpiled = {
            "num_qubits": num_qubits,
            "gates": decomposed,
            "metadata": {
                "transpiled": True,
                "optimization_level": optimization_level,
                "gate_count": len(decomposed),
                "single_qubit_gates": single_q,
                "two_qubit_gates": two_q,
                "depth": depth,
                "basis_gates": ["h", "x", "y", "z", "s", "t",
                                "rx", "ry", "rz", "cx", "cz"],
            },
        }
        # Preserve any extra top-level keys from the input circuit.
        for key, value in circuit.items():
            if key not in transpiled:
                transpiled[key] = value
        return transpiled

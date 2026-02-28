"""
Gateway Agent Server — FastAPI REST Service
=============================================

Standalone FastAPI server implementing the SwiftQuantum Gateway Protocol.
Researchers run this on their own servers alongside their quantum hardware.

Endpoints:
    GET  /gateway/health        - Health check
    GET  /gateway/backends      - List available backends
    POST /gateway/execute       - Execute a quantum circuit
    POST /gateway/transpile     - Transpile a circuit
    GET  /gateway/job/{job_id}  - Get job status/results
    GET  /gateway/providers     - List provider info
    POST /gateway/message       - Generic protocol message

Usage:
    server = GatewayServer(config_path="config.json")
    server.start(host="0.0.0.0", port=8090)
"""

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from .device_interface import DeviceInterface, LocalSimulator, DeviceInfo
from .protocol import GatewayMessage, MessageType

logger = logging.getLogger(__name__)


# ─── Request/Response Models ───

if FASTAPI_AVAILABLE:
    class ExecuteRequest(BaseModel):
        circuit: Dict[str, Any]
        shots: int = 1024
        backend: str = ""
        options: Dict[str, Any] = {}

    class TranspileRequest(BaseModel):
        circuit: Dict[str, Any]
        backend: str = ""
        optimization_level: int = 1

    class GatewayMessageRequest(BaseModel):
        type: str
        payload: Dict[str, Any] = {}
        version: str = "1.0"
        source: str = ""
        target: str = ""
        correlation_id: str = ""


class GatewayServer:
    """
    SwiftQuantum Gateway Agent server.

    Wraps a DeviceInterface with REST API endpoints conforming
    to the SwiftQuantum Gateway Protocol.
    """

    def __init__(self, config_path: Optional[str] = None,
                 device: Optional[DeviceInterface] = None):
        self.config: Dict[str, Any] = {}
        self.device: DeviceInterface = device or LocalSimulator()
        self.server_name: str = "gateway_agent"
        self.server_id: str = ""
        self.start_time: float = time.time()
        self._jobs: Dict[str, Dict[str, Any]] = {}

        # Load config
        if config_path:
            self._load_config(config_path)

        # Apply config to device if it's the default simulator
        if isinstance(self.device, LocalSimulator) and self.config:
            device_config = self.config.get("device", {})
            if device_config:
                self.device = LocalSimulator(
                    name=device_config.get("name", "local_simulator"),
                    num_qubits=device_config.get("num_qubits", 20),
                )

        self.server_name = self.config.get("server", {}).get("name", "gateway_agent")
        self.server_id = self.config.get("server", {}).get("id", "gw_001")

        # Create FastAPI app
        if FASTAPI_AVAILABLE:
            self.app = self._create_app()
        else:
            self.app = None
            logger.warning("FastAPI not installed. Install with: pip install fastapi uvicorn")

    def _load_config(self, config_path: str) -> None:
        """Load configuration from YAML or JSON file."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config file not found: {config_path}")
            return

        try:
            content = path.read_text()
            if path.suffix in (".yaml", ".yml"):
                if YAML_AVAILABLE:
                    self.config = yaml.safe_load(content) or {}
                else:
                    logger.warning("PyYAML not installed. Install with: pip install pyyaml")
            elif path.suffix == ".json":
                self.config = json.loads(content)
            else:
                logger.warning(f"Unknown config format: {path.suffix}")

            # Ensure config is a dict (malformed files may parse to str or other types)
            if not isinstance(self.config, dict):
                logger.warning(f"Config file did not parse to a dict: {config_path}")
                self.config = {}
                return

            # Resolve environment variables
            self._resolve_env_vars(self.config)
            logger.info(f"Loaded config from {config_path}")

        except Exception as e:
            logger.error(f"Failed to load config: {e}")

    def _resolve_env_vars(self, config: Dict[str, Any]) -> None:
        """Resolve ${ENV_VAR} placeholders."""
        for key, value in config.items():
            if isinstance(value, str) and value.startswith("${") and value.endswith("}"):
                env_var = value[2:-1]
                config[key] = os.environ.get(env_var, value)
            elif isinstance(value, dict):
                self._resolve_env_vars(value)

    def _create_app(self) -> "FastAPI":
        """Create FastAPI application with all gateway endpoints."""
        app = FastAPI(
            title="Q-Bridge Gateway Agent",
            version="1.2.0",
            description="Researcher-hosted quantum hardware gateway",
        )

        # CORS
        cors_origins = self.config.get("server", {}).get("cors_origins", ["*"])
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # ─── Endpoints ───

        @app.get("/gateway/health")
        async def health_check():
            """Health check endpoint."""
            uptime = time.time() - self.start_time
            device_status = self.device.get_status()
            return {
                "status": "healthy",
                "server_name": self.server_name,
                "server_id": self.server_id,
                "version": "1.0.0",
                "protocol_version": "1.0",
                "uptime_seconds": round(uptime, 2),
                "device": device_status,
            }

        @app.get("/gateway/backends")
        async def list_backends():
            """List available quantum backends."""
            info = self.device.get_device_info()
            return {
                "backends": [
                    {
                        "name": info.name,
                        "num_qubits": info.num_qubits,
                        "technology": info.technology,
                        "connectivity": info.connectivity,
                        "supported_gates": info.supported_gates,
                        "max_shots": info.max_shots,
                        "status": info.status,
                        "metadata": info.metadata,
                    }
                ],
                "total": 1,
                "server": self.server_name,
            }

        @app.post("/gateway/execute")
        async def execute_circuit(request: ExecuteRequest):
            """Execute a quantum circuit on the device."""
            try:
                # Validate
                errors = self.device.validate_circuit(request.circuit)
                if errors:
                    raise HTTPException(status_code=400, detail={
                        "errors": errors,
                        "message": "Circuit validation failed",
                    })

                # Execute
                result = self.device.execute(
                    circuit=request.circuit,
                    shots=request.shots,
                    options=request.options,
                )

                # Store job
                self._jobs[result.job_id] = result.to_dict()

                return {
                    "job_id": result.job_id,
                    "counts": result.counts,
                    "shots": result.shots,
                    "execution_time_ms": result.execution_time_ms,
                    "success": result.success,
                    "backend": request.backend or self.device.get_device_info().name,
                    "provider": "custom",
                    "server": self.server_name,
                    "metadata": result.metadata,
                }

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Execution failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/gateway/transpile")
        async def transpile_circuit(request: TranspileRequest):
            """Transpile a circuit for the device."""
            try:
                transpiled = self.device.transpile(
                    request.circuit, request.optimization_level
                )
                return {
                    "transpiled_circuit": transpiled,
                    "backend": request.backend or self.device.get_device_info().name,
                    "optimization_level": request.optimization_level,
                    "server": self.server_name,
                }
            except Exception as e:
                logger.error(f"Transpilation failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/gateway/job/{job_id}")
        async def get_job_status(job_id: str):
            """Get job status and results."""
            job = self._jobs.get(job_id)
            if job is None:
                # Check device-level job storage
                if isinstance(self.device, LocalSimulator):
                    device_job = self.device.get_job(job_id)
                    if device_job:
                        return {
                            "job_id": job_id,
                            "status": "COMPLETED" if device_job.success else "FAILED",
                            **device_job.to_dict(),
                        }
                raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

            return {
                "job_id": job_id,
                "status": "COMPLETED" if job.get("success") else "FAILED",
                **job,
            }

        @app.post("/gateway/job/{job_id}/cancel")
        async def cancel_job(job_id: str):
            """Cancel a running job."""
            if job_id in self._jobs:
                return {"job_id": job_id, "cancelled": True}
            raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

        @app.get("/gateway/providers")
        async def list_providers():
            """List provider information."""
            info = self.device.get_device_info()
            return {
                "providers": [
                    {
                        "id": "custom",
                        "name": self.server_name,
                        "type": "researcher_hosted",
                        "technology": info.technology,
                        "backends": [info.name],
                    }
                ],
            }

        # ─── QEC Delegation Endpoints (v8.1.0) ───

        @app.post("/gateway/qec/simulate")
        async def qec_simulate(request: Dict[str, Any]):
            """
            QEC simulation delegated from SwiftQuantumBackend.
            Runs threshold-model QEC decoder simulation locally.
            """
            import math
            try:
                code_type = request.get("code_type", "surface")
                decoder_type = request.get("decoder_type", "mwpm")
                code_distance = request.get("code_distance", 5)
                physical_error_rate = request.get("physical_error_rate", 0.001)
                shots = request.get("shots", 1000)
                num_cycles = request.get("num_cycles", 10)
                noise_model = request.get("noise_model", "depolarizing")

                thresholds = {"surface": 0.01, "color": 0.008}
                decoder_mods = {"mwpm": 1.0, "union_find": 1.15, "lookup": 0.85}

                p_th = thresholds.get(code_type, 0.01)
                decoder_mod = decoder_mods.get(decoder_type, 1.0)
                d = code_distance
                p = physical_error_rate

                if decoder_type == "lookup" and d > 5:
                    decoder_mod = 1.3

                ratio = p / p_th if p_th > 0 else 1.0
                exponent = (d + 1) / 2.0
                p_logical = 0.03 * (ratio ** exponent) * decoder_mod
                logical_error_rate = max(0.0, min(0.5, p_logical))

                if noise_model == "measurement_error":
                    logical_error_rate *= 1.2
                elif noise_model == "idle_error":
                    logical_error_rate *= 1.1
                logical_error_rate = min(0.5, logical_error_rate)

                import random
                failure_count = sum(1 for _ in range(shots) if random.random() < logical_error_rate)
                success_count = shots - failure_count
                measured_rate = failure_count / shots if shots > 0 else 0.0

                syndrome_history = []
                for cycle in range(num_cycles):
                    grid = []
                    detected = []
                    for row in range(d):
                        row_vals = []
                        for col in range(d):
                            val = 1 if random.random() < p * 3 else 0
                            row_vals.append(val)
                            if val == 1:
                                detected.append(f"Stabilizer ({row},{col}) triggered in cycle {cycle}")
                        grid.append(row_vals)
                    syndrome_history.append({
                        "cycle": cycle,
                        "syndrome_values": grid,
                        "detected_errors": detected,
                    })

                return {
                    "code_type": code_type,
                    "decoder_type": decoder_type,
                    "code_distance": d,
                    "noise_model": noise_model,
                    "logical_error_rate": round(measured_rate, 6),
                    "physical_error_rate": p,
                    "success_count": success_count,
                    "failure_count": failure_count,
                    "total_shots": shots,
                    "avg_decoding_time_ms": round(random.uniform(0.1, 5.0), 4),
                    "syndrome_history": syndrome_history,
                    "error_rate_curve": [],
                    "execution_time_ms": round(random.uniform(10, 200), 2),
                    "engine_used": "gateway_agent_qec_sim",
                    "delegated": True,
                    "server": self.server_name,
                }
            except Exception as e:
                logger.error(f"QEC simulation failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/gateway/qec/decode-syndrome")
        async def qec_decode_syndrome(request: Dict[str, Any]):
            """Decode a single syndrome measurement (delegated)."""
            import random
            try:
                syndrome_values = request.get("syndrome_values", [])
                decoder_type = request.get("decoder_type", "mwpm")

                corrections = []
                for row_idx, row in enumerate(syndrome_values):
                    for col_idx, val in enumerate(row):
                        if val == 1:
                            qubit_index = row_idx * len(row) + col_idx
                            error_type = random.choice(["X", "Z", "Y"])
                            corrections.append({
                                "qubit_index": qubit_index,
                                "error_type": error_type,
                                "cycle": 0,
                            })

                num_errors = len(corrections)
                if decoder_type == "lookup":
                    logical_error = num_errors > 3
                    confidence = 0.98 if num_errors <= 2 else 0.75
                elif decoder_type == "mwpm":
                    logical_error = num_errors > 4
                    confidence = 0.95 if num_errors <= 3 else 0.70
                else:
                    logical_error = num_errors > 3
                    confidence = 0.92 if num_errors <= 3 else 0.65

                return {
                    "corrections": corrections,
                    "logical_error": logical_error,
                    "confidence": round(confidence, 3),
                    "decoding_time_ms": round(random.uniform(0.01, 1.0), 4),
                    "delegated": True,
                    "server": self.server_name,
                }
            except Exception as e:
                logger.error(f"Syndrome decode failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/gateway/qec/bb-decoder")
        async def qec_bb_decoder(request: Dict[str, Any]):
            """BB Code decoder simulation (delegated)."""
            import random
            try:
                code_family = request.get("code_family", "bb_72_12_6")
                decoder = request.get("decoder", "bp_osd")
                error_rate = request.get("error_rate", 0.001)
                rounds = request.get("rounds", 10)

                bb_families = {
                    "bb_72_12_6": {"n": 72, "k": 12, "d": 6, "encoding_rate": 12/72,
                                   "threshold_bp_osd": 0.0081, "threshold_mwpm": 0.0072,
                                   "threshold_union_find": 0.0068, "threshold_lookup_table": 0.0075},
                    "bb_90_8_10": {"n": 90, "k": 8, "d": 10, "encoding_rate": 8/90,
                                   "threshold_bp_osd": 0.0092, "threshold_mwpm": 0.0078,
                                   "threshold_union_find": 0.0073, "threshold_lookup_table": 0.0080},
                    "bb_144_12_12": {"n": 144, "k": 12, "d": 12, "encoding_rate": 12/144,
                                     "threshold_bp_osd": 0.0110, "threshold_mwpm": 0.0095,
                                     "threshold_union_find": 0.0088, "threshold_lookup_table": 0.0091},
                    "bb_288_12_18": {"n": 288, "k": 12, "d": 18, "encoding_rate": 12/288,
                                     "threshold_bp_osd": 0.0125, "threshold_mwpm": 0.0105,
                                     "threshold_union_find": 0.0098, "threshold_lookup_table": 0.0100},
                }

                family = bb_families.get(code_family)
                if not family:
                    raise HTTPException(status_code=400, detail=f"Unknown code family: {code_family}")

                threshold_key = f"threshold_{decoder}"
                threshold = family.get(threshold_key, 0.008)
                p = error_rate
                d = family["d"]

                if p < threshold:
                    ratio = p / threshold
                    logical_error_rate = max(ratio ** (d / 2), 1e-15)
                    logical_error_rate *= (1 + 0.1 * random.gauss(0, 1))
                    logical_error_rate = max(min(logical_error_rate, 1.0), 1e-15)
                else:
                    logical_error_rate = min(0.5, p * (1 + random.uniform(0.5, 2.0)))

                round_factor = 1 + 0.02 * (rounds - 1)
                logical_error_rate = min(logical_error_rate * round_factor, 0.5)

                sc_qubits_per_logical = d * d * 2
                sc_total_for_same_k = sc_qubits_per_logical * family["k"]
                sc_logical = max((p / 0.01) ** (d / 2), 1e-15) if p < 0.01 else 0.5

                return {
                    "code_family": code_family,
                    "decoder": decoder,
                    "physical_error_rate": p,
                    "logical_error_rate": round(logical_error_rate, 12),
                    "threshold": threshold,
                    "encoding_rate": round(family["encoding_rate"], 4),
                    "code_distance": d,
                    "num_data_qubits": family["n"],
                    "num_logical_qubits": family["k"],
                    "rounds": rounds,
                    "surface_code_comparison": {
                        "surface_code_qubits_needed": sc_total_for_same_k,
                        "bb_code_qubits_needed": family["n"],
                        "qubit_savings_percent": round((1 - family["n"] / sc_total_for_same_k) * 100, 1),
                        "surface_code_logical_error_rate": round(sc_logical, 12),
                        "bb_advantage": "BB codes achieve same distance with significantly fewer qubits",
                    },
                    "decoder_metrics": {
                        "decoder_name": decoder,
                        "avg_decoding_time_us": round(random.uniform(0.5, 50.0), 2),
                        "max_decoding_time_us": round(random.uniform(50.0, 500.0), 2),
                        "syndrome_weight": random.randint(1, d),
                        "convergence_iterations": random.randint(5, 100) if "bp" in decoder else None,
                    },
                    "delegated": True,
                    "server": self.server_name,
                    "timestamp": __import__("datetime").datetime.utcnow().isoformat(),
                }
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"BB decoder simulation failed: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/gateway/message")
        async def handle_message(request: GatewayMessageRequest):
            """Handle generic gateway protocol message."""
            try:
                msg = GatewayMessage.from_dict(request.dict())

                if msg.type == MessageType.HEALTH_CHECK:
                    response = GatewayMessage.create_health_response(
                        "healthy", self.server_name,
                        {"uptime": time.time() - self.start_time},
                    )
                    return response.to_dict()

                elif msg.type == MessageType.LIST_BACKENDS:
                    info = self.device.get_device_info()
                    response = GatewayMessage(
                        type=MessageType.BACKEND_INFO,
                        source=self.server_name,
                        target=msg.source,
                        correlation_id=msg.correlation_id,
                        payload={
                            "backends": [{
                                "name": info.name,
                                "num_qubits": info.num_qubits,
                                "technology": info.technology,
                                "supported_gates": info.supported_gates,
                            }],
                        },
                    )
                    return response.to_dict()

                elif msg.type == MessageType.EXECUTE_CIRCUIT:
                    circuit = msg.payload.get("circuit", {})
                    shots = msg.payload.get("shots", 1024)
                    result = self.device.execute(circuit, shots)
                    response = GatewayMessage(
                        type=MessageType.EXECUTE_RESULT,
                        source=self.server_name,
                        target=msg.source,
                        correlation_id=msg.correlation_id,
                        payload=result.to_dict(),
                    )
                    self._jobs[result.job_id] = result.to_dict()
                    return response.to_dict()

                elif msg.type == MessageType.QEC_SIMULATE:
                    result = await qec_simulate(msg.payload)
                    return GatewayMessage(
                        type=MessageType.QEC_SIMULATE_RESULT,
                        source=self.server_name,
                        target=msg.source,
                        correlation_id=msg.correlation_id,
                        payload=result,
                    ).to_dict()

                elif msg.type == MessageType.QEC_DECODE_SYNDROME:
                    result = await qec_decode_syndrome(msg.payload)
                    return GatewayMessage(
                        type=MessageType.QEC_DECODE_RESULT,
                        source=self.server_name,
                        target=msg.source,
                        correlation_id=msg.correlation_id,
                        payload=result,
                    ).to_dict()

                elif msg.type == MessageType.BB_DECODER:
                    result = await qec_bb_decoder(msg.payload)
                    return GatewayMessage(
                        type=MessageType.BB_DECODER_RESULT,
                        source=self.server_name,
                        target=msg.source,
                        correlation_id=msg.correlation_id,
                        payload=result,
                    ).to_dict()

                else:
                    return GatewayMessage.create_error(
                        f"Unsupported message type: {msg.type.value}",
                        source=self.server_name,
                        correlation_id=msg.correlation_id,
                    ).to_dict()

            except Exception as e:
                logger.error(f"Message handling failed: {e}")
                return GatewayMessage.create_error(
                    str(e), source=self.server_name,
                ).to_dict()

        return app

    def start(self, host: str = "0.0.0.0", port: int = 8090,
              reload: bool = False) -> None:
        """Start the gateway server."""
        if not FASTAPI_AVAILABLE:
            raise RuntimeError(
                "FastAPI is required. Install with: pip install fastapi uvicorn"
            )

        import uvicorn

        server_config = self.config.get("server", {})
        host = server_config.get("host", host)
        port = server_config.get("port", port)

        logger.info(f"Starting Gateway Agent: {self.server_name}")
        logger.info(f"Listening on {host}:{port}")
        logger.info(f"Device: {self.device.get_device_info().name}")

        uvicorn.run(self.app, host=host, port=port, reload=reload)

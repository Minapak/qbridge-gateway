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
    server = GatewayServer(config_path="device_config.yaml")
    server.start(host="0.0.0.0", port=8765)
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
            title="SwiftQuantum Gateway Agent",
            version="1.0.0",
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

    def start(self, host: str = "0.0.0.0", port: int = 8765,
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

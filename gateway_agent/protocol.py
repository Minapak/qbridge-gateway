"""
SwiftQuantum Gateway Protocol
===============================

Standardized message envelope and message types for communication
between SwiftQuantum services and researcher-hosted quantum hardware.

Protocol Version: 1.0
Transport: REST (HTTP/JSON) or WebSocket

Message Envelope:
    {
        "type": "execute_circuit",
        "version": "1.0",
        "timestamp": "2025-01-01T00:00:00Z",
        "source": "swiftquantum_backend",
        "target": "researcher_lab",
        "payload": { ... },
        "correlation_id": "uuid"
    }
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
import uuid


class MessageType(Enum):
    """Gateway protocol message types."""

    # Circuit operations
    EXECUTE_CIRCUIT = "execute_circuit"
    EXECUTE_RESULT = "execute_result"
    TRANSPILE = "transpile"
    TRANSPILE_RESULT = "transpile_result"

    # Job management
    JOB_STATUS = "job_status"
    JOB_STATUS_RESPONSE = "job_status_response"
    JOB_CANCEL = "job_cancel"
    JOB_CANCEL_RESPONSE = "job_cancel_response"

    # Backend discovery
    LIST_BACKENDS = "list_backends"
    BACKEND_INFO = "backend_info"

    # Health & registration
    HEALTH_CHECK = "health_check"
    HEALTH_RESPONSE = "health_response"
    REGISTER = "register"
    REGISTER_RESPONSE = "register_response"

    # Error
    ERROR = "error"

    # Streaming
    STREAM_RESULTS = "stream_results"
    STREAM_CHUNK = "stream_chunk"


@dataclass
class GatewayMessage:
    """
    Standard gateway protocol message envelope.

    All communication between SwiftQuantum services and gateway agents
    uses this standardized envelope format.
    """
    type: MessageType
    payload: Dict[str, Any] = field(default_factory=dict)
    version: str = "1.0"
    timestamp: str = ""
    source: str = ""
    target: str = ""
    correlation_id: str = ""
    error: Optional[str] = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.correlation_id:
            self.correlation_id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "type": self.type.value,
            "version": self.version,
            "timestamp": self.timestamp,
            "source": self.source,
            "target": self.target,
            "payload": self.payload,
            "correlation_id": self.correlation_id,
        }
        if self.error:
            result["error"] = self.error
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GatewayMessage":
        """Deserialize from dictionary."""
        msg_type = data.get("type", "error")

        # Find matching MessageType
        try:
            message_type = MessageType(msg_type)
        except ValueError:
            message_type = MessageType.ERROR

        return cls(
            type=message_type,
            payload=data.get("payload", {}),
            version=data.get("version", "1.0"),
            timestamp=data.get("timestamp", ""),
            source=data.get("source", ""),
            target=data.get("target", ""),
            correlation_id=data.get("correlation_id", ""),
            error=data.get("error"),
        )

    @classmethod
    def create_error(cls, error_message: str, source: str = "",
                     correlation_id: str = "") -> "GatewayMessage":
        """Create an error message."""
        return cls(
            type=MessageType.ERROR,
            payload={"error_message": error_message},
            source=source,
            correlation_id=correlation_id or str(uuid.uuid4()),
            error=error_message,
        )

    @classmethod
    def create_health_response(cls, status: str, server_name: str,
                                details: Optional[Dict[str, Any]] = None) -> "GatewayMessage":
        """Create a health check response."""
        return cls(
            type=MessageType.HEALTH_RESPONSE,
            source=server_name,
            payload={
                "status": status,
                "server_name": server_name,
                "version": "1.0.0",
                **(details or {}),
            },
        )

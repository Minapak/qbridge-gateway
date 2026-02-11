"""
Tests for gateway_agent.protocol — GatewayMessage & MessageType
================================================================

Covers:
- MessageType enum values and membership
- GatewayMessage construction, auto-populated fields
- Serialization (to_dict) and deserialization (from_dict)
- Round-trip serialization fidelity
- Factory methods: create_error, create_health_response
- Edge cases: unknown type, missing fields, empty payload
"""

import uuid
from datetime import datetime, timezone

import pytest

from gateway_agent.protocol import GatewayMessage, MessageType


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MessageType enum
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestMessageType:
    """Tests for the MessageType enumeration."""

    def test_circuit_operations_exist(self):
        assert MessageType.EXECUTE_CIRCUIT.value == "execute_circuit"
        assert MessageType.EXECUTE_RESULT.value == "execute_result"
        assert MessageType.TRANSPILE.value == "transpile"
        assert MessageType.TRANSPILE_RESULT.value == "transpile_result"

    def test_job_management_types_exist(self):
        assert MessageType.JOB_STATUS.value == "job_status"
        assert MessageType.JOB_STATUS_RESPONSE.value == "job_status_response"
        assert MessageType.JOB_CANCEL.value == "job_cancel"
        assert MessageType.JOB_CANCEL_RESPONSE.value == "job_cancel_response"

    def test_backend_discovery_types_exist(self):
        assert MessageType.LIST_BACKENDS.value == "list_backends"
        assert MessageType.BACKEND_INFO.value == "backend_info"

    def test_health_and_registration_types_exist(self):
        assert MessageType.HEALTH_CHECK.value == "health_check"
        assert MessageType.HEALTH_RESPONSE.value == "health_response"
        assert MessageType.REGISTER.value == "register"
        assert MessageType.REGISTER_RESPONSE.value == "register_response"

    def test_error_type_exists(self):
        assert MessageType.ERROR.value == "error"

    def test_streaming_types_exist(self):
        assert MessageType.STREAM_RESULTS.value == "stream_results"
        assert MessageType.STREAM_CHUNK.value == "stream_chunk"

    def test_qec_delegation_types_exist(self):
        assert MessageType.QEC_SIMULATE.value == "qec_simulate"
        assert MessageType.QEC_SIMULATE_RESULT.value == "qec_simulate_result"
        assert MessageType.QEC_DECODE_SYNDROME.value == "qec_decode_syndrome"
        assert MessageType.QEC_DECODE_RESULT.value == "qec_decode_result"
        assert MessageType.BB_DECODER.value == "bb_decoder"
        assert MessageType.BB_DECODER_RESULT.value == "bb_decoder_result"

    def test_total_enum_members(self):
        """Ensure we have the expected number of message types."""
        assert len(MessageType) == 23

    def test_enum_from_value(self):
        assert MessageType("execute_circuit") == MessageType.EXECUTE_CIRCUIT
        assert MessageType("error") == MessageType.ERROR
        assert MessageType("qec_simulate") == MessageType.QEC_SIMULATE

    def test_invalid_value_raises_error(self):
        with pytest.raises(ValueError):
            MessageType("nonexistent_type")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GatewayMessage construction
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGatewayMessageConstruction:
    """Tests for GatewayMessage initialization and auto-fields."""

    def test_minimal_construction(self):
        msg = GatewayMessage(type=MessageType.HEALTH_CHECK)
        assert msg.type == MessageType.HEALTH_CHECK
        assert msg.payload == {}
        assert msg.version == "1.0"
        assert msg.source == ""
        assert msg.target == ""
        assert msg.error is None

    def test_auto_timestamp(self):
        msg = GatewayMessage(type=MessageType.HEALTH_CHECK)
        assert msg.timestamp != ""
        # Should be a valid ISO format timestamp
        parsed = datetime.fromisoformat(msg.timestamp)
        assert parsed.tzinfo is not None  # timezone-aware

    def test_auto_correlation_id(self):
        msg = GatewayMessage(type=MessageType.HEALTH_CHECK)
        assert msg.correlation_id != ""
        # Should be a valid UUID
        uuid.UUID(msg.correlation_id)  # raises if invalid

    def test_explicit_timestamp_not_overridden(self):
        ts = "2025-01-01T00:00:00+00:00"
        msg = GatewayMessage(type=MessageType.HEALTH_CHECK, timestamp=ts)
        assert msg.timestamp == ts

    def test_explicit_correlation_id_not_overridden(self):
        cid = "my-custom-correlation-id"
        msg = GatewayMessage(type=MessageType.HEALTH_CHECK, correlation_id=cid)
        assert msg.correlation_id == cid

    def test_full_construction(self):
        msg = GatewayMessage(
            type=MessageType.EXECUTE_CIRCUIT,
            payload={"circuit": {}, "shots": 1024},
            version="1.0",
            timestamp="2025-06-01T12:00:00+00:00",
            source="client",
            target="server",
            correlation_id="abc-123",
            error=None,
        )
        assert msg.type == MessageType.EXECUTE_CIRCUIT
        assert msg.payload["shots"] == 1024
        assert msg.source == "client"
        assert msg.target == "server"
        assert msg.correlation_id == "abc-123"

    def test_with_error_field(self):
        msg = GatewayMessage(
            type=MessageType.ERROR,
            error="Something went wrong",
        )
        assert msg.error == "Something went wrong"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Serialization: to_dict
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGatewayMessageToDict:
    """Tests for GatewayMessage.to_dict() serialization."""

    def test_to_dict_keys(self, sample_gateway_message):
        d = sample_gateway_message.to_dict()
        expected_keys = {
            "type", "version", "timestamp", "source",
            "target", "payload", "correlation_id",
        }
        assert expected_keys.issubset(d.keys())

    def test_type_is_string_value(self, sample_gateway_message):
        d = sample_gateway_message.to_dict()
        assert d["type"] == "execute_circuit"
        assert isinstance(d["type"], str)

    def test_payload_preserved(self, sample_gateway_message):
        d = sample_gateway_message.to_dict()
        assert d["payload"]["shots"] == 512

    def test_error_omitted_when_none(self):
        msg = GatewayMessage(type=MessageType.HEALTH_CHECK)
        d = msg.to_dict()
        assert "error" not in d

    def test_error_included_when_set(self):
        msg = GatewayMessage(type=MessageType.ERROR, error="fail")
        d = msg.to_dict()
        assert d["error"] == "fail"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Deserialization: from_dict
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGatewayMessageFromDict:
    """Tests for GatewayMessage.from_dict() deserialization."""

    def test_from_dict_valid(self, sample_message_dict):
        msg = GatewayMessage.from_dict(sample_message_dict)
        assert msg.type == MessageType.EXECUTE_CIRCUIT
        assert msg.version == "1.0"
        assert msg.source == "test_client"
        assert msg.target == "gateway_agent"
        assert msg.correlation_id == "test-corr-001"
        assert msg.payload["shots"] == 100

    def test_from_dict_unknown_type_becomes_error(self):
        data = {"type": "totally_unknown_type", "payload": {}}
        msg = GatewayMessage.from_dict(data)
        assert msg.type == MessageType.ERROR

    def test_from_dict_missing_type_becomes_error(self):
        data = {"payload": {"key": "value"}}
        msg = GatewayMessage.from_dict(data)
        assert msg.type == MessageType.ERROR

    def test_from_dict_empty_dict(self):
        msg = GatewayMessage.from_dict({})
        assert msg.type == MessageType.ERROR
        assert msg.payload == {}

    def test_from_dict_preserves_error_field(self):
        data = {"type": "error", "error": "something broke", "payload": {}}
        msg = GatewayMessage.from_dict(data)
        assert msg.error == "something broke"

    def test_from_dict_default_version(self):
        data = {"type": "health_check"}
        msg = GatewayMessage.from_dict(data)
        assert msg.version == "1.0"

    def test_from_dict_all_qec_types(self):
        for qec_type in ["qec_simulate", "qec_simulate_result",
                          "qec_decode_syndrome", "qec_decode_result",
                          "bb_decoder", "bb_decoder_result"]:
            data = {"type": qec_type, "payload": {"test": True}}
            msg = GatewayMessage.from_dict(data)
            assert msg.type.value == qec_type


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Round-trip serialization
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGatewayMessageRoundTrip:
    """Verify to_dict -> from_dict round-trip fidelity."""

    def test_round_trip_execute(self, sample_gateway_message):
        d = sample_gateway_message.to_dict()
        reconstructed = GatewayMessage.from_dict(d)
        assert reconstructed.type == sample_gateway_message.type
        assert reconstructed.payload == sample_gateway_message.payload
        assert reconstructed.source == sample_gateway_message.source
        assert reconstructed.target == sample_gateway_message.target
        assert reconstructed.correlation_id == sample_gateway_message.correlation_id

    def test_round_trip_error_message(self):
        original = GatewayMessage(
            type=MessageType.ERROR,
            error="test error",
            payload={"detail": "more info"},
        )
        d = original.to_dict()
        reconstructed = GatewayMessage.from_dict(d)
        assert reconstructed.type == MessageType.ERROR
        assert reconstructed.error == "test error"
        assert reconstructed.payload["detail"] == "more info"

    def test_round_trip_all_types(self):
        """Every MessageType should survive a round-trip."""
        for mt in MessageType:
            original = GatewayMessage(type=mt, payload={"mt": mt.value})
            d = original.to_dict()
            reconstructed = GatewayMessage.from_dict(d)
            assert reconstructed.type == mt
            assert reconstructed.payload["mt"] == mt.value


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Factory methods
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestGatewayMessageFactories:
    """Tests for create_error and create_health_response."""

    def test_create_error_basic(self):
        msg = GatewayMessage.create_error("something failed")
        assert msg.type == MessageType.ERROR
        assert msg.error == "something failed"
        assert msg.payload["error_message"] == "something failed"
        assert msg.correlation_id != ""

    def test_create_error_with_source(self):
        msg = GatewayMessage.create_error("fail", source="test_server")
        assert msg.source == "test_server"

    def test_create_error_with_correlation_id(self):
        msg = GatewayMessage.create_error("fail", correlation_id="corr-999")
        assert msg.correlation_id == "corr-999"

    def test_create_health_response_basic(self):
        msg = GatewayMessage.create_health_response("healthy", "my_server")
        assert msg.type == MessageType.HEALTH_RESPONSE
        assert msg.source == "my_server"
        assert msg.payload["status"] == "healthy"
        assert msg.payload["server_name"] == "my_server"
        assert msg.payload["version"] == "1.0.0"

    def test_create_health_response_with_details(self):
        details = {"uptime": 3600, "load": 0.5}
        msg = GatewayMessage.create_health_response("healthy", "srv", details)
        assert msg.payload["uptime"] == 3600
        assert msg.payload["load"] == 0.5

    def test_create_health_response_none_details(self):
        msg = GatewayMessage.create_health_response("degraded", "srv", None)
        assert msg.payload["status"] == "degraded"

    def test_create_error_serializes_correctly(self):
        msg = GatewayMessage.create_error("oops", source="s")
        d = msg.to_dict()
        assert d["type"] == "error"
        assert d["error"] == "oops"
        assert d["source"] == "s"

"""Unit coverage for isolated A2A/A2UI development protocol observability."""

from __future__ import annotations

import io
import json
import logging

from agent_nebula_platform.protocols.a2a.extensions.a2ui.observability import (
    summarize_a2ui_message_metadata,
    summarize_a2ui_parts,
)
from agent_nebula_platform.protocols.a2a.observability import A2AProtocolTraceEvent
from agent_nebula_platform.protocols.a2a.observability.redaction import redact_protocol_value
from agent_nebula_platform.protocols.a2a.observability.tracer import (
    LoggingA2AProtocolTracer,
    NoOpA2AProtocolTracer,
    create_protocol_tracer_from_environment,
)


def test_trace_is_disabled_by_default(monkeypatch) -> None:
    """Keep protocol tracing opt-in so production behavior is unchanged."""

    monkeypatch.delenv("ANU_A2A_PROTOCOL_TRACE", raising=False)
    assert isinstance(create_protocol_tracer_from_environment(), NoOpA2AProtocolTracer)


def test_trace_payload_switch_is_independent(monkeypatch) -> None:
    """Require a second explicit switch before normalized payloads are attached."""

    monkeypatch.setenv("ANU_A2A_PROTOCOL_TRACE", "true")
    monkeypatch.delenv("ANU_A2A_PROTOCOL_TRACE_PAYLOADS", raising=False)
    tracer = create_protocol_tracer_from_environment()
    assert isinstance(tracer, LoggingA2AProtocolTracer)
    assert tracer.include_payloads is False



def test_logging_tracer_owns_single_console_sink() -> None:
    """Keep enabled client traces independent from application logging setup."""

    logger = logging.getLogger("agent_nebula_platform.protocols.a2a.trace")
    previous_level = logger.level
    previous_propagate = logger.propagate
    previous_handlers = list(logger.handlers)
    try:
        logger.handlers.clear()
        logger.setLevel(logging.NOTSET)
        logger.propagate = True

        LoggingA2AProtocolTracer()
        LoggingA2AProtocolTracer()

        assert logger.level == logging.INFO
        assert logger.propagate is False
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0], logging.StreamHandler)
    finally:
        logger.handlers[:] = previous_handlers
        logger.setLevel(previous_level)
        logger.propagate = previous_propagate


def test_logging_tracer_emits_without_parent_or_root_handler() -> None:
    """Prove a client-only process can emit traces through the owned sink."""

    logger = logging.getLogger("agent_nebula_platform.protocols.a2a.trace")
    parent = logging.getLogger("agent_nebula_platform")
    root = logging.getLogger()
    previous_logger_handlers = list(logger.handlers)
    previous_parent_handlers = list(parent.handlers)
    previous_root_handlers = list(root.handlers)
    try:
        logger.handlers.clear()
        parent.handlers.clear()
        root.handlers.clear()

        tracer = LoggingA2AProtocolTracer()
        stream = io.StringIO()
        logger.handlers[0].setStream(stream)
        tracer.emit(A2AProtocolTraceEvent("request.send", "client->remote", {"messageId": "m-1"}))

        assert 'A2A_PROTOCOL_TRACE' in stream.getvalue()
        assert '"event":"request.send"' in stream.getvalue()
    finally:
        logger.handlers[:] = previous_logger_handlers
        parent.handlers[:] = previous_parent_handlers
        root.handlers[:] = previous_root_handlers


def test_redaction_removes_security_material_recursively() -> None:
    """Prevent protocol diagnostics from becoming a credential disclosure path."""

    value = {
        "Authorization": "Bearer token",
        "metadata": {"api_key": "secret", "safe": "visible"},
        "items": [{"dpop": "proof"}],
    }
    assert redact_protocol_value(value) == {
        "Authorization": "<redacted>",
        "metadata": {"api_key": "<redacted>", "safe": "visible"},
        "items": [{"dpop": "<redacted>"}],
    }


def test_a2ui_observer_summarizes_capabilities_and_datapart() -> None:
    """Expose A2UI negotiation and message shape without owning protocol behavior."""

    metadata = {
        "a2uiRendererCapabilities": {
            "v1.0": {"supportedCatalogIds": ["https://example.test/basic.json"]}
        }
    }
    document = {
        "parts": [
            {
                "metadata": {"mimeType": "application/a2ui+json"},
                "data": [
                    {
                        "version": "v1.0",
                        "createSurface": {
                            "surfaceId": "surface-1",
                            "catalogId": "https://example.test/basic.json",
                            "components": [{"id": "root", "component": "Text"}],
                        },
                    }
                ],
            }
        ]
    }
    assert summarize_a2ui_message_metadata(metadata) == metadata
    assert summarize_a2ui_parts(document) == (
        {
            "mimeType": "application/a2ui+json",
            "messages": [
                {
                    "version": "v1.0",
                    "messageType": "createSurface",
                    "surfaceId": "surface-1",
                    "catalogId": "https://example.test/basic.json",
                    "componentCount": 1,
                }
            ],
        },
    )


def test_logging_tracer_emits_single_redacted_json_event() -> None:
    """Keep trace output machine-readable while enforcing redaction at the sink."""

    logger = logging.getLogger("agent_nebula_platform.protocols.a2a.trace")
    previous_handlers = list(logger.handlers)
    try:
        logger.handlers.clear()
        tracer = LoggingA2AProtocolTracer(include_payloads=True)
        stream = io.StringIO()
        logger.handlers[0].setStream(stream)
        tracer.emit(
            A2AProtocolTraceEvent(
                "request.send",
                "client->remote",
                {"request": {"authorization": "Bearer token", "message_id": "m-1"}},
            )
        )
        records = [line for line in stream.getvalue().splitlines() if "A2A_PROTOCOL_TRACE" in line]
        assert len(records) == 1
        payload = json.loads(records[0].split("A2A_PROTOCOL_TRACE ", 1)[1])
        assert payload["request"]["authorization"] == "<redacted>"
        assert payload["request"]["message_id"] == "m-1"
    finally:
        logger.handlers[:] = previous_handlers

class _FailingProtocolTracer:
    """Test double proving diagnostic sinks cannot affect protocol behavior."""

    @property
    def include_payloads(self) -> bool:
        """Simulate a tracer failure before payload inspection."""

        raise RuntimeError("trace configuration failure")

    def emit(self, event: A2AProtocolTraceEvent) -> None:
        """Simulate a failing trace sink."""

        del event
        raise RuntimeError("trace sink failure")


def test_result_mapping_survives_broken_protocol_tracer() -> None:
    """Keep valid A2A response mapping independent from observability failures."""

    from agent_nebula_platform.protocols.a2a.server.result_mapper import A2AResultMapper

    message = A2AResultMapper(protocol_tracer=_FailingProtocolTracer()).map(
        {"message": "still delivered"}
    )

    assert message is not None

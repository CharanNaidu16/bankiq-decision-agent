"""API routes: the streaming investigate endpoint and a health check.

``POST /api/investigate`` runs the five-agent pipeline and streams progress to
the client as Server-Sent Events. Each event has a named ``event`` type so the
frontend can route it without sniffing payload shape:

- ``agent_progress`` — an :class:`AgentProgressEvent`.
- ``report``         — the terminal :class:`FinalReport`.
- ``done``           — a sentinel signaling stream completion.
- ``error``          — an unexpected stream-level error (should be rare; agent
  failures are handled inside the pipeline and surface as degraded reports).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from app.config import get_settings
from app.constants import (
    SSE_EVENT_AGENT_PROGRESS,
    SSE_EVENT_DONE,
    SSE_EVENT_ERROR,
    SSE_EVENT_REPORT,
)
from app.core.logging import get_logger
from app.models.email import SendReportRequest
from app.models.events import AgentProgressEvent
from app.models.investigation import FinalReport, InvestigationRequest
from app.pipeline.investigation_pipeline import InvestigationPipeline
from app.services.dataset_repository import DatasetRepository
from app.services.email_service import EmailError, EmailService
from app.services.llm_client import GroqLlmClient

_logger = get_logger("api")

router = APIRouter(prefix="/api", tags=["investigation"])

# Shared, read-only singletons constructed once at import time. The repository
# caches dataset frames in memory; the LLM client holds a pooled HTTP client.
_dataset_repository = DatasetRepository()
_llm_client = GroqLlmClient()
_email_service = EmailService()


@router.get("/health")
async def health() -> dict[str, object]:
    """Report service readiness.

    Returns:
        A mapping describing service status, the configured model, whether the
        LLM is configured, and whether all datasets are present on disk.
    """
    settings = get_settings()
    return {
        "status": "ok",
        "model": settings.groq_model,
        "llm_configured": settings.is_llm_configured,
        "datasets_loaded": _dataset_repository.all_datasets_present(),
    }


@router.post("/send-report")
async def send_report(send_request: SendReportRequest) -> dict[str, object]:
    """Email a generated report to a recipient via the configured SMTP server.

    The server holds the sending credential, so the caller only supplies the
    recipient address and the report body — no per-user authentication.

    Args:
        send_request: The validated recipient, subject, and report body.

    Returns:
        A small confirmation payload.

    Raises:
        HTTPException: 503 if email is not configured on the server, or 502 if
            the message could not be delivered.
    """
    if not _email_service.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Email sending is not configured on the server.",
        )
    _logger.info(
        "Report email requested for %d recipient(s), %d cc",
        len(send_request.recipients),
        len(send_request.cc),
    )
    try:
        await _email_service.send_report(
            recipients=send_request.recipients,
            cc=send_request.cc,
            subject=send_request.subject,
            body=send_request.body,
        )
    except EmailError as error:
        raise HTTPException(
            status_code=502, detail=f"Could not send the email: {error}"
        ) from error
    return {
        "status": "sent",
        "recipients": send_request.recipients,
        "cc": send_request.cc,
    }


@router.post("/investigate")
async def investigate(
    investigation_request: InvestigationRequest, request: Request
) -> EventSourceResponse:
    """Run an investigation and stream agent progress + report over SSE.

    Args:
        investigation_request: The validated request carrying the question.
        request: The Starlette request, used to detect client disconnects.

    Returns:
        An :class:`EventSourceResponse` streaming named SSE events.
    """
    pipeline = InvestigationPipeline(_llm_client, _dataset_repository)
    _logger.info("Investigation requested: %r", investigation_request.question)

    async def event_generator() -> AsyncIterator[dict[str, str]]:
        """Yield SSE-formatted dictionaries for each pipeline output.

        Yields:
            Dicts with ``event`` and JSON ``data`` keys for ``sse-starlette``.
        """
        try:
            async for item in pipeline.run(investigation_request.question):
                if await request.is_disconnected():
                    _logger.info("Client disconnected; aborting investigation stream.")
                    return
                if isinstance(item, AgentProgressEvent):
                    yield {
                        "event": SSE_EVENT_AGENT_PROGRESS,
                        "data": item.model_dump_json(),
                    }
                elif isinstance(item, FinalReport):
                    yield {"event": SSE_EVENT_REPORT, "data": item.model_dump_json()}
            yield {"event": SSE_EVENT_DONE, "data": "{}"}
        except Exception as error:
            _logger.exception("Unexpected stream-level error: %s", error)
            yield {
                "event": SSE_EVENT_ERROR,
                "data": f'{{"message": "Investigation stream failed: {error}"}}',
            }

    return EventSourceResponse(event_generator())

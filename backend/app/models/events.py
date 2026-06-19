"""SSE payload models: agent progress events and status enums.

These are the only models serialized directly onto the Server-Sent Events
stream alongside the final report. The frontend mirrors them in
``frontend/src/types/investigation.ts``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class AgentStatus(StrEnum):
    """Lifecycle status of a single agent within the pipeline."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AgentProgressEvent(BaseModel):
    """A progress update emitted when an agent starts, completes, or fails.

    Attributes:
        agent_name: Stable agent identifier (see ``constants.ORDERED_AGENT_NAMES``).
        display_name: Human-friendly agent label for the UI.
        status: Current lifecycle status of the agent.
        message: Short, user-facing description of what just happened.
        step_index: Zero-based position of this agent in the pipeline.
        total_steps: Total number of agents in the pipeline.
        elapsed_ms: Wall-clock time the agent took, populated on completion/failure.
    """

    agent_name: str
    display_name: str
    status: AgentStatus
    message: str
    step_index: int = Field(ge=0)
    total_steps: int = Field(gt=0)
    elapsed_ms: float | None = Field(default=None, ge=0.0)

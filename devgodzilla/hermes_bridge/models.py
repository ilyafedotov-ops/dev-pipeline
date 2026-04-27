from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolPayload(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)


class ToolResult(BaseModel):
    ok: bool = True
    tool: str
    data: Any


class ToolErrorBody(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ToolErrorEnvelope(BaseModel):
    ok: bool = False
    tool: str
    error: ToolErrorBody


class SubmitFeedbackRequest(BaseModel):
    action: Literal["retry", "approve", "reject", "clarify_create", "clarify_answer"]
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    key: str | None = None
    answer: str | None = None
    answered_by: str | None = None


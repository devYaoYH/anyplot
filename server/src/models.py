"""Pydantic models for request/response handling."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class VisualizeRequest(BaseModel):
    """Request model for the /visualize endpoint."""

    data: list[dict[str, Any]] = Field(
        ..., description="Array of data rows as JSON objects"
    )
    prompt: str = Field(
        ..., description="Natural language description of desired visualization"
    )
    viz_mode: Literal["matplotlib", "altair"] = Field(
        default="matplotlib",
        description="Visualization mode: 'matplotlib' for static images, 'altair' for interactive Vega-Lite",
    )
    epsilon: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Privacy budget per query (lower = more private)",
    )
    total_budget: float = Field(
        default=10.0,
        ge=1.0,
        le=100.0,
        description="Total privacy budget for the session",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional Anthropic API key (uses server default if not provided)",
    )


class VisualizeResponse(BaseModel):
    """Response model for the /visualize endpoint."""

    image: str | None = Field(default=None, description="Base64-encoded PNG image (for matplotlib mode)")
    vega_spec: dict | None = Field(default=None, description="Vega-Lite JSON spec (for altair mode)")
    viz_type: Literal["image", "vega_lite"] = Field(
        default="image",
        description="Type of visualization output"
    )
    code: str = Field(..., description="Generated Python code that produced the visualization")


class ReplayRequest(BaseModel):
    """Request model for the /visualize/replay endpoint."""

    data: list[dict[str, Any]] = Field(
        ..., description="Array of data rows as JSON objects (new data to visualize)"
    )
    code: str = Field(
        ..., description="Previously generated visualization code to replay"
    )
    original_prompt: str = Field(
        ..., description="Original user prompt (used if code needs fixing)"
    )
    total_budget: float = Field(
        default=10.0,
        ge=1.0,
        le=100.0,
        description="Total privacy budget for the session",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional Anthropic API key (uses server default if not provided)",
    )


class ContinueRequest(BaseModel):
    """Request model for the /visualize/continue endpoint."""

    data: list[dict[str, Any]] = Field(
        ..., description="Array of data rows as JSON objects"
    )
    prompt: str = Field(
        ..., description="User's adjustment request"
    )
    previous_messages: list[dict[str, Any]] = Field(
        ..., description="Previous conversation messages from agent result"
    )
    previous_tool_calls: list[dict[str, Any]] = Field(
        default_factory=list, description="Previous tool calls from agent result"
    )
    total_budget: float = Field(
        default=10.0,
        ge=1.0,
        le=100.0,
        description="Total privacy budget for the session",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional Anthropic API key (uses server default if not provided)",
    )


class HealthResponse(BaseModel):
    """Response model for the /health endpoint."""

    status: str = Field(default="ok", description="Service health status")


class ConfigStatusResponse(BaseModel):
    """Response model for the /config/status endpoint."""

    api_key_configured: bool = Field(
        ..., description="Whether an API key is configured on the server"
    )


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str = Field(..., description="Error message")


class ConvertRequest(BaseModel):
    """Request model for the /visualize/convert endpoint."""

    data: list[dict[str, Any]] = Field(
        ..., description="Array of data rows as JSON objects"
    )
    current_code: str = Field(
        ..., description="Current visualization code to convert"
    )
    target_mode: Literal["matplotlib", "altair"] = Field(
        ..., description="Target visualization mode to convert to"
    )
    original_prompt: str = Field(
        ..., description="Original user prompt for context"
    )
    total_budget: float = Field(
        default=10.0,
        ge=1.0,
        le=100.0,
        description="Total privacy budget for the session",
    )
    api_key: str | None = Field(
        default=None,
        description="Optional Anthropic API key (uses server default if not provided)",
    )


class CreateSessionRequest(BaseModel):
    """Request model for creating a new session."""

    name: str | None = Field(
        default=None,
        description="Optional session name. Defaults to timestamp-based name.",
    )


class UpdateSessionRequest(BaseModel):
    """Request model for updating a session."""

    name: str | None = Field(default=None, description="New session name")
    raw_data: list[dict[str, Any]] | None = Field(
        default=None, description="Updated raw data"
    )
    sql_query: str | None = Field(default=None, description="Updated SQL query")
    log_snapshots: list[dict[str, Any]] | None = Field(
        default=None, description="Updated log snapshots"
    )
    matplotlib_result: dict[str, Any] | None = Field(
        default=None, description="Updated matplotlib visualization result"
    )
    altair_result: dict[str, Any] | None = Field(
        default=None, description="Updated altair visualization result"
    )

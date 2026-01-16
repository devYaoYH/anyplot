"""FastAPI application for Sanctum visualization server.

This module provides the HTTP API for the visualization service.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sanctum_mcp import MCPServer

from .agent import Agent, AgentConfig, AgentError
from .models import (
    ConfigStatusResponse,
    ErrorResponse,
    HealthResponse,
    VisualizeRequest,
    VisualizeResponse,
)
from .sandbox import Sandbox, SandboxConfig, validate_code


def get_server_api_key() -> str | None:
    """Get the API key from server environment."""
    return os.environ.get("ANTHROPIC_API_KEY")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="Sanctum Visualization API",
    description="Privacy-preserving data visualization using LLM agents",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.get("/config/status", response_model=ConfigStatusResponse)
async def config_status():
    """Check if the server has an API key configured."""
    api_key = get_server_api_key()
    return ConfigStatusResponse(api_key_configured=api_key is not None and len(api_key) > 0)


@app.post(
    "/visualize",
    response_model=VisualizeResponse,
    responses={400: {"model": ErrorResponse}, 500: {"model": ErrorResponse}},
)
async def visualize(request: VisualizeRequest):
    """Generate a visualization from data and prompt.

    This endpoint:
    1. Creates an MCP server with the provided data
    2. Uses Claude to generate visualization code via MCP tools
    3. Executes the code in a secure sandbox
    4. Returns the generated image and code
    """
    # Determine which API key to use
    api_key = request.api_key or get_server_api_key()

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="No API key provided. Please configure an API key in settings or set ANTHROPIC_API_KEY on the server.",
        )

    session_id = str(uuid.uuid4())[:8]

    try:
        # Convert data to DataFrame
        df = pd.DataFrame(request.data)

        if df.empty:
            raise HTTPException(status_code=400, detail="Data cannot be empty")

        # Create MCP server for this session
        mcp_server = MCPServer(
            df=df,
            session_id=session_id,
            total_budget=request.total_budget,
        )

        # Create agent with the determined API key
        config = AgentConfig()
        agent = Agent(
            mcp_server=mcp_server,
            config=config,
            api_key=api_key,
        )

        # Generate visualization code
        result = agent.generate_visualization_code(request.prompt)

        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to generate visualization code: {result.error}",
            )

        # Execute code in sandbox with retry loop
        sandbox = Sandbox(SandboxConfig(timeout_seconds=30))
        column_mapping = mcp_server.get_column_mapping()

        current_code = result.code
        current_result = result
        last_error = None

        for attempt in range(config.max_execution_retries + 1):
            # Validate the generated code
            is_valid, validation_error = validate_code(current_code)
            if not is_valid:
                if attempt < config.max_execution_retries:
                    # Treat validation failure as an execution error for refinement
                    current_result = agent.refine_code(
                        current_result,
                        f"Code validation failed: {validation_error}",
                    )
                    if not current_result.success:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Failed to refine code after validation error: {current_result.error}",
                        )
                    current_code = current_result.code
                    continue
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Generated code failed validation after {config.max_execution_retries} retries: {validation_error}",
                    )

            # Execute the code
            sandbox_result = sandbox.execute(
                code=current_code,
                data=request.data,
                column_mapping=column_mapping,
            )

            if sandbox_result.success:
                # Success! Return the result
                return VisualizeResponse(
                    image=sandbox_result.image_base64,
                    code=current_code,
                )

            # Execution failed - try to refine if we have retries left
            last_error = f"{sandbox_result.error}"
            if sandbox_result.stderr:
                last_error += f" | Stderr: {sandbox_result.stderr}"

            if attempt < config.max_execution_retries:
                current_result = agent.refine_code(
                    current_result,
                    sandbox_result.error,
                    sandbox_result.stderr,
                )
                if not current_result.success:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Failed to refine code after execution error: {current_result.error}",
                    )
                current_code = current_result.code

        # All retries exhausted
        raise HTTPException(
            status_code=400,
            detail=f"Visualization execution failed after {config.max_execution_retries} retries. Last error: {last_error}",
        )

    except HTTPException:
        raise
    except AgentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


def format_sse_event(event: str, data: dict) -> str:
    """Format a Server-Sent Event message."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def visualize_stream_generator(request: VisualizeRequest) -> AsyncGenerator[str, None]:
    """Generate SSE events for visualization progress.

    Events:
    - status: Progress updates (generating, validating, executing, retrying)
    - result: Final success result with image and code
    - error: Error message if visualization fails
    """
    api_key = request.api_key or get_server_api_key()

    if not api_key:
        yield format_sse_event("error", {"message": "No API key provided"})
        return

    session_id = str(uuid.uuid4())[:8]

    try:
        yield format_sse_event("status", {"stage": "initializing", "message": "Setting up visualization session"})

        df = pd.DataFrame(request.data)
        if df.empty:
            yield format_sse_event("error", {"message": "Data cannot be empty"})
            return

        mcp_server = MCPServer(
            df=df,
            session_id=session_id,
            total_budget=request.total_budget,
        )

        config = AgentConfig()
        agent = Agent(
            mcp_server=mcp_server,
            config=config,
            api_key=api_key,
        )

        yield format_sse_event("status", {"stage": "generating", "message": "Generating visualization code"})

        result = agent.generate_visualization_code(request.prompt)

        if not result.success:
            yield format_sse_event("error", {"message": f"Failed to generate code: {result.error}"})
            return

        sandbox = Sandbox(SandboxConfig(timeout_seconds=30))
        column_mapping = mcp_server.get_column_mapping()

        current_code = result.code
        current_result = result
        last_error = None

        for attempt in range(config.max_execution_retries + 1):
            yield format_sse_event("status", {
                "stage": "validating",
                "message": f"Validating code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            is_valid, validation_error = validate_code(current_code)
            if not is_valid:
                if attempt < config.max_execution_retries:
                    yield format_sse_event("status", {
                        "stage": "retrying",
                        "message": f"Code validation failed, refining: {validation_error}",
                        "attempt": attempt + 1,
                    })
                    current_result = agent.refine_code(
                        current_result,
                        f"Code validation failed: {validation_error}",
                    )
                    if not current_result.success:
                        yield format_sse_event("error", {"message": f"Failed to refine code: {current_result.error}"})
                        return
                    current_code = current_result.code
                    continue
                else:
                    yield format_sse_event("error", {
                        "message": f"Code validation failed after {config.max_execution_retries} retries: {validation_error}"
                    })
                    return

            yield format_sse_event("status", {
                "stage": "executing",
                "message": f"Executing visualization code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            sandbox_result = sandbox.execute(
                code=current_code,
                data=request.data,
                column_mapping=column_mapping,
            )

            if sandbox_result.success:
                yield format_sse_event("result", {
                    "image": sandbox_result.image_base64,
                    "code": current_code,
                })
                return

            last_error = f"{sandbox_result.error}"
            if sandbox_result.stderr:
                last_error += f" | Stderr: {sandbox_result.stderr}"

            if attempt < config.max_execution_retries:
                yield format_sse_event("status", {
                    "stage": "retrying",
                    "message": f"Execution failed, refining code: {sandbox_result.error}",
                    "attempt": attempt + 1,
                })
                current_result = agent.refine_code(
                    current_result,
                    sandbox_result.error,
                    sandbox_result.stderr,
                )
                if not current_result.success:
                    yield format_sse_event("error", {"message": f"Failed to refine code: {current_result.error}"})
                    return
                current_code = current_result.code

        yield format_sse_event("error", {
            "message": f"Visualization failed after {config.max_execution_retries} retries. Last error: {last_error}"
        })

    except AgentError as e:
        yield format_sse_event("error", {"message": str(e)})
    except Exception as e:
        yield format_sse_event("error", {"message": f"Internal error: {str(e)}"})


@app.post("/visualize/stream")
async def visualize_stream(request: VisualizeRequest):
    """Stream visualization progress using Server-Sent Events.

    This endpoint streams progress updates while generating the visualization,
    which is useful for long-running requests with retries.

    Events:
    - status: {"stage": "...", "message": "...", "attempt": N}
    - result: {"image": "base64...", "code": "..."}
    - error: {"message": "..."}
    """
    return StreamingResponse(
        visualize_stream_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# For running with uvicorn directly
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

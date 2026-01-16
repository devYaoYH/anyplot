"""FastAPI application for Sanctum visualization server.

This module provides the HTTP API for the visualization service.
"""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager

import uvicorn
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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
        agent = Agent(
            mcp_server=mcp_server,
            config=AgentConfig(),
            api_key=api_key,
        )

        # Generate visualization code
        result = agent.generate_visualization_code(request.prompt)

        if not result.success:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to generate visualization code: {result.error}",
            )

        # Validate the generated code
        is_valid, validation_error = validate_code(result.code)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Generated code failed validation: {validation_error}",
            )

        # Execute code in sandbox
        sandbox = Sandbox(SandboxConfig(timeout_seconds=30))

        # Get column mapping for the sandbox
        column_mapping = mcp_server.get_column_mapping()

        # Execute the code
        sandbox_result = sandbox.execute(
            code=result.code,
            data=request.data,
            column_mapping=column_mapping,
        )

        if not sandbox_result.success:
            raise HTTPException(
                status_code=400,
                detail=f"Visualization execution failed: {sandbox_result.error}. Stderr: {sandbox_result.stderr}",
            )

        return VisualizeResponse(
            image=sandbox_result.image_base64,
            code=result.code,
        )

    except HTTPException:
        raise
    except AgentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


# For running with uvicorn directly
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

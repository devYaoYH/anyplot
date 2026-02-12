"""FastAPI application for AnyPlot visualization server.

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

from .agent import (
    Agent,
    AgentConfig,
    AgentError,
    AgentResult,
    MATPLOTLIB_SYSTEM_PROMPT,
    ALTAIR_SYSTEM_PROMPT,
    CONVERT_TO_ALTAIR_PROMPT,
    CONVERT_TO_MATPLOTLIB_PROMPT,
)
from .models import (
    ConfigStatusResponse,
    ContinueRequest,
    ConvertRequest,
    CreateSessionRequest,
    ErrorResponse,
    HealthResponse,
    ReplayRequest,
    UpdateSessionRequest,
    VisualizeRequest,
    VisualizeResponse,
)
from .sandbox import Sandbox, SandboxConfig, validate_code
from .session_store import (
    get_session_store,
    SessionData,
    SessionMetadata,
    LogSnapshotModel,
    VisualizationResultModel,
)


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
    title="AnyPlot Visualization API",
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

        # Get schema context for prompt augmentation
        schema_context = mcp_server.get_schema_with_original_names()

        # Generate visualization code with schema context
        result = agent.generate_visualization_code(request.prompt, schema_context)

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


def _serialize_agent_log(result) -> dict:
    """Serialize agent result logs for the frontend.

    Converts tool calls and messages to a JSON-serializable format.
    """
    serialized_messages = []
    for msg in result.messages:
        if isinstance(msg.get("content"), list):
            # Handle structured content (tool use blocks, etc.)
            content_items = []
            for item in msg["content"]:
                if hasattr(item, "type"):
                    # Anthropic content block
                    if item.type == "text":
                        content_items.append({"type": "text", "text": item.text})
                    elif item.type == "tool_use":
                        content_items.append({
                            "type": "tool_use",
                            "id": item.id,
                            "name": item.name,
                            "input": item.input,
                        })
                elif isinstance(item, dict):
                    content_items.append(item)
                else:
                    content_items.append(str(item))
            serialized_messages.append({
                "role": msg["role"],
                "content": content_items,
            })
        else:
            serialized_messages.append({
                "role": msg["role"],
                "content": msg.get("content"),
            })

    return {
        "tool_calls": result.tool_calls,
        "messages": serialized_messages,
    }


def _generate_with_system_prompt(agent: Agent, prompt: str, schema_context, system_prompt: str):
    """Generate visualization code with a custom system prompt.

    Args:
        agent: The Agent instance
        prompt: User's visualization prompt
        schema_context: Schema context for column mapping
        system_prompt: Custom system prompt to use

    Returns:
        AgentResult with generated code
    """

    tools = agent._build_anthropic_tools()
    augmented_prompt = agent._augment_prompt_with_schema(prompt, schema_context)
    messages = [{"role": "user", "content": augmented_prompt}]
    tool_calls_made = []
    num_iterations = 0

    while num_iterations < agent.config.max_tool_calls:
        num_iterations += 1
        try:
            response = agent._client.messages.create(
                model=agent.config.model,
                max_tokens=agent.config.max_tokens,
                temperature=agent.config.temperature,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
        except Exception as e:
            return AgentResult(
                success=False,
                error=f"API error: {str(e)}",
                tool_calls=tool_calls_made,
                messages=messages,
            )

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = agent.mcp_server.call_tool(block.name, block.input)
                    tool_calls_made.append({
                        "tool": block.name,
                        "input": block.input,
                        "result": result.data if result.success else result.error,
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(result.data) if result.success else f"Error: {result.error}",
                    })
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
        else:
            messages.append({"role": "assistant", "content": response.content})
            code = agent._extract_code(response)
            if code:
                return AgentResult(
                    success=True,
                    code=code,
                    tool_calls=tool_calls_made,
                    messages=messages,
                )
            else:
                text_response = agent._extract_text(response)
                return AgentResult(
                    success=False,
                    error=f"No code block found. Response: {text_response[:500] if text_response else 'Empty'}",
                    tool_calls=tool_calls_made,
                    messages=messages,
                )

    return AgentResult(
        success=False,
        error=f"Max tool calls ({agent.config.max_tool_calls}) exceeded",
        tool_calls=tool_calls_made,
        messages=messages,
    )


async def visualize_stream_generator(request: VisualizeRequest) -> AsyncGenerator[str, None]:
    """Generate SSE events for visualization progress.

    Events:
    - status: Progress updates (generating, validating, executing, retrying)
    - result: Final success result with image/vega_spec and code
    - error: Error message if visualization fails
    """
    api_key = request.api_key or get_server_api_key()

    if not api_key:
        yield format_sse_event("error", {"message": "No API key provided"})
        return

    session_id = str(uuid.uuid4())[:8]
    viz_mode = request.viz_mode

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

        # Get schema context for prompt augmentation
        schema_context = mcp_server.get_schema_with_original_names()

        # Select system prompt based on viz_mode
        system_prompt = ALTAIR_SYSTEM_PROMPT if viz_mode == "altair" else MATPLOTLIB_SYSTEM_PROMPT

        yield format_sse_event("status", {"stage": "generating", "message": f"Generating {'interactive' if viz_mode == 'altair' else 'static'} visualization code"})

        result = _generate_with_system_prompt(agent, request.prompt, schema_context, system_prompt)

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
                viz_mode=viz_mode,
            )

            if sandbox_result.success:
                # Serialize agent logs for the frontend
                agent_log = _serialize_agent_log(current_result)
                result_data = {
                    "code": current_code,
                    "agent_log": agent_log,
                    "viz_type": sandbox_result.viz_type,
                }
                if sandbox_result.viz_type == "vega_lite":
                    result_data["vega_spec"] = sandbox_result.vega_spec
                else:
                    result_data["image"] = sandbox_result.image_base64
                yield format_sse_event("result", result_data)
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


REPLAY_FIX_SYSTEM_PROMPT = """You are a data visualization assistant helping to adapt existing visualization code to work with new data.

IMPORTANT CONSTRAINTS:
1. You cannot see raw data rows - only aggregate statistics via the provided tools.
2. You can use the following tools:
   - get_schema: Get the masked column names and their data types
   - query_stat: Get a differentially private aggregate statistic (mean, max, min, count, sum)
   - get_histogram: Get a differentially private histogram for a column

3. COLUMN NAME MAPPING:
   - The user's message includes a "Column Mapping" section that shows how their column names map to masked IDs
   - Use the MASKED names when calling tools like query_stat and get_histogram
   - In your generated code, use the ORIGINAL column names (the user's names), NOT the masked names

4. Your task is to fix the provided visualization code so it works with the new data structure.
   - First, use get_schema to understand the available columns in the new data
   - Compare with the original code to identify mismatches
   - Adapt the code to work with the available columns
   - The code will have access to a DataFrame called `df` with the ORIGINAL column names

5. Your generated code should:
   - Use matplotlib.pyplot (already imported as plt)
   - Work with a DataFrame called `df` using ORIGINAL column names
   - Create clear, informative visualizations with proper labels
   - NOT call plt.show() - the system will save the figure automatically

OUTPUT FORMAT:
After analyzing the schema and understanding the issue, output your fixed Python code in a code block:
```python
# Your fixed visualization code here
```

Only include the visualization code, not data loading or saving."""


async def replay_stream_generator(request: ReplayRequest) -> AsyncGenerator[str, None]:
    """Generate SSE events for replay with optional code fixing.

    Events:
    - status: Progress updates
    - result: Final success result with image, code, and agent_log
    - error: Error message if replay fails
    """
    api_key = request.api_key or get_server_api_key()

    if not api_key:
        yield format_sse_event("error", {"message": "No API key provided"})
        return

    session_id = str(uuid.uuid4())[:8]

    try:
        yield format_sse_event("status", {"stage": "initializing", "message": "Setting up replay session"})

        df = pd.DataFrame(request.data)
        if df.empty:
            yield format_sse_event("error", {"message": "Data cannot be empty"})
            return

        # Create MCP server for this session (needed for column mapping and potential fixes)
        mcp_server = MCPServer(
            df=df,
            session_id=session_id,
            total_budget=request.total_budget,
        )
        column_mapping = mcp_server.get_column_mapping()

        # First, try to execute the code directly
        yield format_sse_event("status", {"stage": "executing", "message": "Executing saved code on new data"})

        sandbox = Sandbox(SandboxConfig(timeout_seconds=30))

        # Validate the code first
        is_valid, validation_error = validate_code(request.code)
        if not is_valid:
            yield format_sse_event("status", {
                "stage": "retrying",
                "message": f"Code validation failed: {validation_error}. Launching agent to fix...",
            })
        else:
            # Try to execute directly
            sandbox_result = sandbox.execute(
                code=request.code,
                data=request.data,
                column_mapping=column_mapping,
            )

            if sandbox_result.success:
                # Direct execution succeeded - no agent needed
                yield format_sse_event("result", {
                    "image": sandbox_result.image_base64,
                    "code": request.code,
                    "agent_log": None,
                    "was_fixed": False,
                })
                return

            # Execution failed - need to fix with agent
            yield format_sse_event("status", {
                "stage": "retrying",
                "message": f"Execution failed: {sandbox_result.error}. Launching agent to fix...",
            })
            validation_error = f"{sandbox_result.error}"
            if sandbox_result.stderr:
                validation_error += f"\nStderr: {sandbox_result.stderr}"

        # Launch agent to fix the code
        yield format_sse_event("status", {"stage": "generating", "message": "Agent analyzing new data structure"})

        config = AgentConfig()
        agent = Agent(
            mcp_server=mcp_server,
            config=config,
            api_key=api_key,
        )

        # Get schema context for prompt augmentation
        schema_context = mcp_server.get_schema_with_original_names()

        # Build the fix prompt
        fix_prompt = f"""The following visualization code failed to execute on new data:

```python
{request.code}
```

Error encountered:
{validation_error}

Original visualization request: "{request.original_prompt}"

Please analyze the new data structure using the available tools and fix the code to work with the current data.
The visualization should still accomplish the original goal: {request.original_prompt}"""

        # Use the replay fix system prompt
        agent._client = agent._client  # Keep client
        original_generate = agent.generate_visualization_code

        def generate_with_fix_prompt(prompt: str, schema_ctx=None):
            """Generate with the fix system prompt."""
            tools = agent._build_anthropic_tools()
            augmented_prompt = agent._augment_prompt_with_schema(prompt, schema_ctx)
            messages = [{"role": "user", "content": augmented_prompt}]
            tool_calls_made = []
            num_iterations = 0

            while num_iterations < agent.config.max_tool_calls:
                num_iterations += 1
                try:
                    response = agent._client.messages.create(
                        model=agent.config.model,
                        max_tokens=agent.config.max_tokens,
                        temperature=agent.config.temperature,
                        system=REPLAY_FIX_SYSTEM_PROMPT,
                        tools=tools,
                        messages=messages,
                    )
                except Exception as e:
                    return AgentResult(
                        success=False,
                        error=f"API error: {str(e)}",
                        tool_calls=tool_calls_made,
                        messages=messages,
                    )

                if response.stop_reason == "tool_use":
                    tool_results = []
                    for block in response.content:
                        if block.type == "tool_use":
                            result = agent.mcp_server.call_tool(block.name, block.input)
                            tool_calls_made.append({
                                "tool": block.name,
                                "input": block.input,
                                "result": result.data if result.success else result.error,
                            })
                            tool_results.append({
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result.data) if result.success else f"Error: {result.error}",
                            })
                    messages.append({"role": "assistant", "content": response.content})
                    messages.append({"role": "user", "content": tool_results})
                else:
                    messages.append({"role": "assistant", "content": response.content})
                    code = agent._extract_code(response)
                    if code:
                        return AgentResult(
                            success=True,
                            code=code,
                            tool_calls=tool_calls_made,
                            messages=messages,
                        )
                    else:
                        text_response = agent._extract_text(response)
                        return AgentResult(
                            success=False,
                            error=f"No code block found. Response: {text_response[:500] if text_response else 'Empty'}",
                            tool_calls=tool_calls_made,
                            messages=messages,
                        )

            return AgentResult(
                success=False,
                error=f"Max tool calls ({agent.config.max_tool_calls}) exceeded",
                tool_calls=tool_calls_made,
                messages=messages,
            )

        result = generate_with_fix_prompt(fix_prompt, schema_context)

        if not result.success:
            yield format_sse_event("error", {"message": f"Failed to fix code: {result.error}"})
            return

        # Execute the fixed code with retry loop
        current_code = result.code
        current_result = result
        last_error = None

        for attempt in range(config.max_execution_retries + 1):
            yield format_sse_event("status", {
                "stage": "validating",
                "message": f"Validating fixed code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            is_valid, validation_error = validate_code(current_code)
            if not is_valid:
                if attempt < config.max_execution_retries:
                    yield format_sse_event("status", {
                        "stage": "retrying",
                        "message": f"Validation failed, refining: {validation_error}",
                        "attempt": attempt + 1,
                    })
                    current_result = agent.refine_code(
                        current_result,
                        f"Code validation failed: {validation_error}",
                    )
                    if not current_result.success:
                        yield format_sse_event("error", {"message": f"Failed to refine: {current_result.error}"})
                        return
                    current_code = current_result.code
                    continue
                else:
                    yield format_sse_event("error", {
                        "message": f"Validation failed after {config.max_execution_retries} retries: {validation_error}"
                    })
                    return

            yield format_sse_event("status", {
                "stage": "executing",
                "message": f"Executing fixed code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            sandbox_result = sandbox.execute(
                code=current_code,
                data=request.data,
                column_mapping=column_mapping,
            )

            if sandbox_result.success:
                agent_log = _serialize_agent_log(current_result)
                yield format_sse_event("result", {
                    "image": sandbox_result.image_base64,
                    "code": current_code,
                    "agent_log": agent_log,
                    "was_fixed": True,
                })
                return

            last_error = f"{sandbox_result.error}"
            if sandbox_result.stderr:
                last_error += f" | Stderr: {sandbox_result.stderr}"

            if attempt < config.max_execution_retries:
                yield format_sse_event("status", {
                    "stage": "retrying",
                    "message": f"Execution failed, refining: {sandbox_result.error}",
                    "attempt": attempt + 1,
                })
                current_result = agent.refine_code(
                    current_result,
                    sandbox_result.error,
                    sandbox_result.stderr,
                )
                if not current_result.success:
                    yield format_sse_event("error", {"message": f"Failed to refine: {current_result.error}"})
                    return
                current_code = current_result.code

        yield format_sse_event("error", {
            "message": f"Replay failed after {config.max_execution_retries} retries. Last error: {last_error}"
        })

    except AgentError as e:
        yield format_sse_event("error", {"message": str(e)})
    except Exception as e:
        yield format_sse_event("error", {"message": f"Internal error: {str(e)}"})


@app.post("/visualize/replay")
async def visualize_replay(request: ReplayRequest):
    """Replay saved visualization code on new data with automatic fixing.

    This endpoint:
    1. First tries to execute the provided code directly on new data
    2. If execution fails, launches an agent to fix the code
    3. The agent only sees data through privacy-preserving MCP tools

    Events:
    - status: {"stage": "...", "message": "...", "attempt": N}
    - result: {"image": "base64...", "code": "...", "agent_log": {...}, "was_fixed": bool}
    - error: {"message": "..."}
    """
    return StreamingResponse(
        replay_stream_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def continue_stream_generator(request: ContinueRequest) -> AsyncGenerator[str, None]:
    """Generate SSE events for continuing a visualization conversation.

    Events:
    - status: Progress updates
    - result: Final success result with image, code, and agent_log
    - error: Error message if continuation fails
    """
    api_key = request.api_key or get_server_api_key()

    if not api_key:
        yield format_sse_event("error", {"message": "No API key provided"})
        return

    session_id = str(uuid.uuid4())[:8]

    try:
        yield format_sse_event("status", {"stage": "initializing", "message": "Continuing conversation"})

        df = pd.DataFrame(request.data)
        if df.empty:
            yield format_sse_event("error", {"message": "Data cannot be empty"})
            return

        # Create MCP server for this session
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

        # Get schema context for prompt augmentation
        schema_context = mcp_server.get_schema_with_original_names()

        yield format_sse_event("status", {"stage": "generating", "message": "Processing adjustment request"})

        # Reconstruct previous result from request
        previous_result = AgentResult(
            success=True,
            code=None,  # Not needed for continuation
            tool_calls=request.previous_tool_calls,
            messages=request.previous_messages,
        )

        # Continue the conversation
        result = agent.continue_conversation(previous_result, request.prompt, schema_context)

        if not result.success:
            yield format_sse_event("error", {"message": f"Failed to generate adjusted code: {result.error}"})
            return

        # Execute the adjusted code with retry loop
        sandbox = Sandbox(SandboxConfig(timeout_seconds=30))
        column_mapping = mcp_server.get_column_mapping()

        current_code = result.code
        current_result = result
        last_error = None

        for attempt in range(config.max_execution_retries + 1):
            yield format_sse_event("status", {
                "stage": "validating",
                "message": f"Validating adjusted code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            is_valid, validation_error = validate_code(current_code)
            if not is_valid:
                if attempt < config.max_execution_retries:
                    yield format_sse_event("status", {
                        "stage": "retrying",
                        "message": f"Validation failed, refining: {validation_error}",
                        "attempt": attempt + 1,
                    })
                    current_result = agent.refine_code(
                        current_result,
                        f"Code validation failed: {validation_error}",
                    )
                    if not current_result.success:
                        yield format_sse_event("error", {"message": f"Failed to refine: {current_result.error}"})
                        return
                    current_code = current_result.code
                    continue
                else:
                    yield format_sse_event("error", {
                        "message": f"Validation failed after {config.max_execution_retries} retries: {validation_error}"
                    })
                    return

            yield format_sse_event("status", {
                "stage": "executing",
                "message": f"Executing adjusted code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            sandbox_result = sandbox.execute(
                code=current_code,
                data=request.data,
                column_mapping=column_mapping,
            )

            if sandbox_result.success:
                agent_log = _serialize_agent_log(current_result)
                yield format_sse_event("result", {
                    "image": sandbox_result.image_base64,
                    "code": current_code,
                    "agent_log": agent_log,
                })
                return

            last_error = f"{sandbox_result.error}"
            if sandbox_result.stderr:
                last_error += f" | Stderr: {sandbox_result.stderr}"

            if attempt < config.max_execution_retries:
                yield format_sse_event("status", {
                    "stage": "retrying",
                    "message": f"Execution failed, refining: {sandbox_result.error}",
                    "attempt": attempt + 1,
                })
                current_result = agent.refine_code(
                    current_result,
                    sandbox_result.error,
                    sandbox_result.stderr,
                )
                if not current_result.success:
                    yield format_sse_event("error", {"message": f"Failed to refine: {current_result.error}"})
                    return
                current_code = current_result.code

        yield format_sse_event("error", {
            "message": f"Continuation failed after {config.max_execution_retries} retries. Last error: {last_error}"
        })

    except AgentError as e:
        yield format_sse_event("error", {"message": str(e)})
    except Exception as e:
        yield format_sse_event("error", {"message": f"Internal error: {str(e)}"})


@app.post("/visualize/continue")
async def visualize_continue(request: ContinueRequest):
    """Continue a visualization conversation with an adjustment request.

    This endpoint continues from a previous conversation, allowing users
    to make adjustments to their visualization without starting over.

    Events:
    - status: {"stage": "...", "message": "...", "attempt": N}
    - result: {"image": "base64...", "code": "...", "agent_log": {...}}
    - error: {"message": "..."}
    """
    return StreamingResponse(
        continue_stream_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


async def convert_stream_generator(request: ConvertRequest) -> AsyncGenerator[str, None]:
    """Generate SSE events for converting visualization between modes.

    Events:
    - status: Progress updates
    - result: Final success result with converted visualization
    - error: Error message if conversion fails
    """
    api_key = request.api_key or get_server_api_key()

    if not api_key:
        yield format_sse_event("error", {"message": "No API key provided"})
        return

    session_id = str(uuid.uuid4())[:8]
    target_mode = request.target_mode

    try:
        yield format_sse_event("status", {"stage": "initializing", "message": "Setting up conversion session"})

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

        # Get schema context for prompt augmentation
        schema_context = mcp_server.get_schema_with_original_names()

        # Select conversion prompt based on target mode
        if target_mode == "altair":
            system_prompt = CONVERT_TO_ALTAIR_PROMPT
            mode_label = "interactive Altair"
        else:
            system_prompt = CONVERT_TO_MATPLOTLIB_PROMPT
            mode_label = "static matplotlib"

        yield format_sse_event("status", {"stage": "generating", "message": f"Converting to {mode_label}"})

        # Build conversion prompt with the original code
        conversion_prompt = f"""Convert the following visualization code to {mode_label}:

Original prompt: "{request.original_prompt}"

Current code:
```python
{request.current_code}
```

Please create an equivalent visualization using {'Altair' if target_mode == 'altair' else 'matplotlib'}."""

        result = _generate_with_system_prompt(agent, conversion_prompt, schema_context, system_prompt)

        if not result.success:
            yield format_sse_event("error", {"message": f"Failed to convert code: {result.error}"})
            return

        sandbox = Sandbox(SandboxConfig(timeout_seconds=30))
        column_mapping = mcp_server.get_column_mapping()

        current_code = result.code
        current_result = result
        last_error = None

        for attempt in range(config.max_execution_retries + 1):
            yield format_sse_event("status", {
                "stage": "validating",
                "message": f"Validating converted code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            is_valid, validation_error = validate_code(current_code)
            if not is_valid:
                if attempt < config.max_execution_retries:
                    yield format_sse_event("status", {
                        "stage": "retrying",
                        "message": f"Validation failed, refining: {validation_error}",
                        "attempt": attempt + 1,
                    })
                    current_result = agent.refine_code(
                        current_result,
                        f"Code validation failed: {validation_error}",
                    )
                    if not current_result.success:
                        yield format_sse_event("error", {"message": f"Failed to refine: {current_result.error}"})
                        return
                    current_code = current_result.code
                    continue
                else:
                    yield format_sse_event("error", {
                        "message": f"Validation failed after {config.max_execution_retries} retries: {validation_error}"
                    })
                    return

            yield format_sse_event("status", {
                "stage": "executing",
                "message": f"Executing converted code (attempt {attempt + 1}/{config.max_execution_retries + 1})",
                "attempt": attempt + 1,
            })

            sandbox_result = sandbox.execute(
                code=current_code,
                data=request.data,
                column_mapping=column_mapping,
                viz_mode=target_mode,
            )

            if sandbox_result.success:
                agent_log = _serialize_agent_log(current_result)
                result_data = {
                    "code": current_code,
                    "agent_log": agent_log,
                    "viz_type": sandbox_result.viz_type,
                }
                if sandbox_result.viz_type == "vega_lite":
                    result_data["vega_spec"] = sandbox_result.vega_spec
                else:
                    result_data["image"] = sandbox_result.image_base64
                yield format_sse_event("result", result_data)
                return

            last_error = f"{sandbox_result.error}"
            if sandbox_result.stderr:
                last_error += f" | Stderr: {sandbox_result.stderr}"

            if attempt < config.max_execution_retries:
                yield format_sse_event("status", {
                    "stage": "retrying",
                    "message": f"Execution failed, refining: {sandbox_result.error}",
                    "attempt": attempt + 1,
                })
                current_result = agent.refine_code(
                    current_result,
                    sandbox_result.error,
                    sandbox_result.stderr,
                )
                if not current_result.success:
                    yield format_sse_event("error", {"message": f"Failed to refine: {current_result.error}"})
                    return
                current_code = current_result.code

        yield format_sse_event("error", {
            "message": f"Conversion failed after {config.max_execution_retries} retries. Last error: {last_error}"
        })

    except AgentError as e:
        yield format_sse_event("error", {"message": str(e)})
    except Exception as e:
        yield format_sse_event("error", {"message": f"Internal error: {str(e)}"})


@app.post("/visualize/convert")
async def visualize_convert(request: ConvertRequest):
    """Convert a visualization between matplotlib and Altair modes.

    This endpoint converts existing visualization code from one mode to another:
    - matplotlib → altair: Convert static chart to interactive
    - altair → matplotlib: Convert interactive chart to static

    Events:
    - status: {"stage": "...", "message": "...", "attempt": N}
    - result: {"image": "base64...", "code": "...", "agent_log": {...}, "viz_type": "..."}
      or {"vega_spec": {...}, "code": "...", "agent_log": {...}, "viz_type": "vega_lite"}
    - error: {"message": "..."}
    """
    return StreamingResponse(
        convert_stream_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Session Management Endpoints
# ============================================================================


@app.post("/sessions", response_model=SessionData)
async def create_session(request: CreateSessionRequest | None = None):
    """Create a new session.

    Args:
        request: Optional request with session name.

    Returns:
        The created session data.
    """
    store = get_session_store()
    name = request.name if request else None
    return store.create_session(name=name)


@app.get("/sessions", response_model=list[SessionMetadata])
async def list_sessions(limit: int = 50, offset: int = 0):
    """List all sessions, most recently updated first.

    Args:
        limit: Maximum number of sessions to return.
        offset: Number of sessions to skip.

    Returns:
        List of session metadata.
    """
    store = get_session_store()
    return store.list_sessions(limit=limit, offset=offset)


@app.get("/sessions/{session_id}", response_model=SessionData)
async def get_session(session_id: str):
    """Get a session by ID.

    Args:
        session_id: The session ID.

    Returns:
        The session data.

    Raises:
        HTTPException: If session not found.
    """
    store = get_session_store()
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@app.put("/sessions/{session_id}", response_model=SessionData)
async def update_session(session_id: str, request: UpdateSessionRequest):
    """Update a session.

    Args:
        session_id: The session ID.
        request: Fields to update.

    Returns:
        The updated session data.

    Raises:
        HTTPException: If session not found.
    """
    store = get_session_store()

    # Build updates dict from non-None fields
    updates = {}
    if request.name is not None:
        updates["name"] = request.name
    if request.raw_data is not None:
        updates["raw_data"] = request.raw_data
    if request.sql_query is not None:
        updates["sql_query"] = request.sql_query
    if request.log_snapshots is not None:
        updates["log_snapshots"] = request.log_snapshots
    if request.matplotlib_result is not None:
        updates["matplotlib_result"] = request.matplotlib_result
    if request.altair_result is not None:
        updates["altair_result"] = request.altair_result

    session = store.update_session(session_id, **updates)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return session


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a session.

    Args:
        session_id: The session ID.

    Returns:
        Success message.

    Raises:
        HTTPException: If session not found.
    """
    store = get_session_store()
    deleted = store.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"message": f"Session {session_id} deleted"}


# For running with uvicorn directly
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

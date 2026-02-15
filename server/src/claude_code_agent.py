"""Claude Code Agent SDK wrapper for subscription-based authentication.

This module provides a ClaudeCodeAgent that uses the Claude Agent SDK
(claude-agent-sdk) to make LLM calls using the local Claude Code CLI's
authentication. This allows users with a Claude Code subscription to use
the app without a separate API key.

All public methods on ClaudeCodeAgent are async because the Agent SDK
spawns the claude CLI as a subprocess, which requires the main event loop.
"""

from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    query,
    tool,
    create_sdk_mcp_server,
)

from .agent import AgentConfig, AgentResult


def build_sdk_mcp_server(mcp_server: Any):
    """Create an SDK MCP server wrapping the sanctum MCP server tools.

    Args:
        mcp_server: The sanctum MCPServer instance.

    Returns:
        McpSdkServerConfig for use with ClaudeAgentOptions.
    """

    @tool(
        "get_schema",
        "Get the masked schema of the dataset. Returns column names (hashed) and their data types.",
        {},
    )
    async def get_schema(args: dict[str, Any]) -> dict[str, Any]:
        result = mcp_server.call_tool("get_schema", args)
        content = str(result.data) if result.success else f"Error: {result.error}"
        return {"content": [{"type": "text", "text": content}]}

    @tool(
        "query_stat",
        "Get a differentially private aggregate statistic for a column.",
        {
            "column": str,
            "statistic": str,
        },
    )
    async def query_stat(args: dict[str, Any]) -> dict[str, Any]:
        result = mcp_server.call_tool("query_stat", args)
        content = str(result.data) if result.success else f"Error: {result.error}"
        return {"content": [{"type": "text", "text": content}]}

    @tool(
        "get_histogram",
        "Get a differentially private histogram for a numeric column.",
        {
            "column": str,
            "num_bins": int,
        },
    )
    async def get_histogram(args: dict[str, Any]) -> dict[str, Any]:
        result = mcp_server.call_tool("get_histogram", args)
        content = str(result.data) if result.success else f"Error: {result.error}"
        return {"content": [{"type": "text", "text": content}]}

    return create_sdk_mcp_server(
        name="sanctum",
        tools=[get_schema, query_stat, get_histogram],
    )


def _extract_code_from_text(text: str) -> str | None:
    """Extract Python code from a text response containing code blocks."""
    code_pattern = r"```python\s*(.*?)\s*```"
    matches = re.findall(code_pattern, text, re.DOTALL)
    if matches:
        return matches[-1].strip()
    return None


def _build_agent_options(
    system_prompt: str,
    mcp_server: Any,
    config: AgentConfig,
) -> ClaudeAgentOptions:
    """Build ClaudeAgentOptions with sanctum MCP tools.

    Args:
        system_prompt: The system prompt to use.
        mcp_server: The sanctum MCPServer instance.
        config: Agent configuration.

    Returns:
        ClaudeAgentOptions configured for visualization generation.
    """
    sdk_server = build_sdk_mcp_server(mcp_server)

    # Build a clean env that strips CLAUDECODE to prevent the CLI from
    # refusing to start when the server is launched from within a Claude Code session.
    clean_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        model=config.model,
        max_turns=config.max_tool_calls,
        permission_mode="bypassPermissions",
        mcp_servers={"sanctum": sdk_server},
        allowed_tools=[
            "mcp__sanctum__get_schema",
            "mcp__sanctum__query_stat",
            "mcp__sanctum__get_histogram",
        ],
        env=clean_env,
    )


async def _as_stream(prompt: str) -> AsyncIterator[dict[str, Any]]:
    """Wrap a string prompt as an async generator.

    The Agent SDK's transport synchronization for in-process MCP servers
    only activates when the prompt is an AsyncIterable (triggering the
    stream_input() code path). Passing a plain string causes the transport
    to close before MCP tool responses can be written back, resulting in
    "ProcessTransport is not ready for writing". Wrapping the prompt as
    an async generator avoids this race condition.
    """
    yield {
        "type": "user",
        "message": {
            "role": "user",
            "content": prompt,
        },
    }


async def _run_query(prompt: str, options: ClaudeAgentOptions) -> AgentResult:
    """Run a query through the Claude Agent SDK and extract results.

    Args:
        prompt: The user prompt.
        options: ClaudeAgentOptions for the query.

    Returns:
        AgentResult with generated code or error.
    """
    tool_calls_made: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    result_text: str | None = None

    try:
        async for message in query(prompt=_as_stream(prompt), options=options):
            if isinstance(message, AssistantMessage):
                content_items = []
                for block in message.content:
                    if isinstance(block, TextBlock):
                        content_items.append({"type": "text", "text": block.text})
                    elif isinstance(block, ToolUseBlock):
                        content_items.append({
                            "type": "tool_use",
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        })
                        tool_calls_made.append({
                            "tool": block.name,
                            "input": block.input,
                            "result": None,
                        })
                    elif isinstance(block, ToolResultBlock):
                        content_text = block.content if isinstance(block.content, str) else str(block.content)
                        # Update the last matching tool call with its result
                        if block.tool_use_id:
                            for tc in reversed(tool_calls_made):
                                if tc["result"] is None:
                                    tc["result"] = content_text
                                    break
                        content_items.append({
                            "type": "tool_result",
                            "tool_use_id": block.tool_use_id,
                            "content": content_text,
                        })
                if content_items:
                    messages.append({"role": "assistant", "content": content_items})

            elif isinstance(message, ResultMessage):
                result_text = message.result
                if message.is_error:
                    return AgentResult(
                        success=False,
                        error=f"Agent SDK error: {result_text}",
                        tool_calls=tool_calls_made,
                        messages=messages,
                    )

    except BaseException as e:
        # Unwrap ExceptionGroup/TaskGroup errors to surface the actual cause
        error_msg = str(e)
        if isinstance(e, BaseExceptionGroup):
            sub_errors = [str(exc) for exc in e.exceptions]
            error_msg = "; ".join(sub_errors)
        return AgentResult(
            success=False,
            error=f"Agent SDK error: {error_msg}",
            tool_calls=tool_calls_made,
            messages=messages,
        )

    if result_text:
        code = _extract_code_from_text(result_text)
        if code:
            return AgentResult(
                success=True,
                code=code,
                tool_calls=tool_calls_made,
                messages=messages,
            )

    # Try to extract code from assistant messages
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            for item in msg.get("content", []):
                if isinstance(item, dict) and item.get("type") == "text":
                    code = _extract_code_from_text(item["text"])
                    if code:
                        return AgentResult(
                            success=True,
                            code=code,
                            tool_calls=tool_calls_made,
                            messages=messages,
                        )

    return AgentResult(
        success=False,
        error=f"No code block found in response. Result: {result_text[:500] if result_text else 'Empty'}",
        tool_calls=tool_calls_made,
        messages=messages,
    )


class ClaudeCodeAgent:
    """Agent that uses the Claude Agent SDK for subscription-based auth.

    This agent provides async equivalents of the standard Agent class methods.
    All methods are async because the Agent SDK spawns the claude CLI as a
    subprocess, which requires the main event loop.
    """

    def __init__(
        self,
        mcp_server: Any,
        config: AgentConfig | None = None,
    ):
        self.config = config or AgentConfig()
        self.mcp_server = mcp_server

    def _augment_prompt_with_schema(
        self,
        prompt: str,
        schema_context: list[dict[str, str]] | None,
    ) -> str:
        """Augment user prompt with column mapping context."""
        if not schema_context:
            return prompt

        mapping_lines = []
        for col in schema_context:
            original = col.get("original_name", "unknown")
            masked = col.get("masked_name", "unknown")
            dtype = col.get("dtype", "unknown")
            mapping_lines.append(f'  - "{original}" → {masked} (type: {dtype})')

        column_mapping_text = "\n".join(mapping_lines)

        return f"""{prompt}

---
COLUMN MAPPING (use masked names for tool calls, original names in generated code):
{column_mapping_text}
---"""

    async def generate_visualization_code(
        self,
        prompt: str,
        schema_context: list[dict[str, str]] | None = None,
        system_prompt: str | None = None,
    ) -> AgentResult:
        """Generate visualization code based on user prompt.

        Args:
            prompt: User's description of the desired visualization.
            schema_context: Optional column mapping context.
            system_prompt: Optional custom system prompt override.

        Returns:
            AgentResult with generated code or error.
        """
        from .agent import MATPLOTLIB_SYSTEM_PROMPT

        augmented_prompt = self._augment_prompt_with_schema(prompt, schema_context)
        options = _build_agent_options(
            system_prompt=system_prompt or MATPLOTLIB_SYSTEM_PROMPT,
            mcp_server=self.mcp_server,
            config=self.config,
        )

        return await _run_query(augmented_prompt, options)

    async def refine_code(
        self,
        previous_result: AgentResult,
        execution_error: str,
        stderr: str | None = None,
    ) -> AgentResult:
        """Refine code based on execution errors.

        Since the Agent SDK manages its own sessions, we include the previous
        code and error context in a fresh prompt.

        Args:
            previous_result: The previous AgentResult containing code.
            execution_error: The error message from code execution.
            stderr: Optional stderr output from execution.

        Returns:
            AgentResult with refined code or error.
        """
        from .agent import MATPLOTLIB_SYSTEM_PROMPT

        error_details = f"Error: {execution_error}"
        if stderr:
            error_details += f"\nStderr: {stderr}"

        prompt = f"""The following visualization code failed to execute:

```python
{previous_result.code}
```

{error_details}

Please fix the code. The DataFrame is called `df` with original (unmasked) column names.
Use matplotlib.pyplot (imported as plt). Do not call plt.show().

Provide corrected code in a ```python code block."""

        options = _build_agent_options(
            system_prompt=MATPLOTLIB_SYSTEM_PROMPT,
            mcp_server=self.mcp_server,
            config=self.config,
        )

        result = await _run_query(prompt, options)
        # Merge tool call logs
        result.tool_calls = previous_result.tool_calls + result.tool_calls
        return result

    async def continue_conversation(
        self,
        previous_result: AgentResult,
        adjustment_prompt: str,
        schema_context: list[dict[str, str]] | None = None,
    ) -> AgentResult:
        """Continue a conversation with a user adjustment request.

        Since the Agent SDK manages its own sessions, we include the previous
        code context in a fresh prompt.

        Args:
            previous_result: The previous AgentResult containing code.
            adjustment_prompt: User's request for adjustment.
            schema_context: Optional schema context for column mapping.

        Returns:
            AgentResult with adjusted code or error.
        """
        from .agent import MATPLOTLIB_SYSTEM_PROMPT

        augmented_prompt = self._augment_prompt_with_schema(adjustment_prompt, schema_context)

        prompt = f"""Here is the current visualization code:

```python
{previous_result.code}
```

The user wants to adjust it:

{augmented_prompt}

Please modify the code. You can use the MCP tools for additional data info.
The DataFrame is called `df` with original (unmasked) column names.
Use matplotlib.pyplot (imported as plt). Do not call plt.show().

Provide updated code in a ```python code block."""

        options = _build_agent_options(
            system_prompt=MATPLOTLIB_SYSTEM_PROMPT,
            mcp_server=self.mcp_server,
            config=self.config,
        )

        result = await _run_query(prompt, options)
        # Merge tool call logs
        result.tool_calls = previous_result.tool_calls + result.tool_calls
        return result

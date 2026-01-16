"""Agent orchestration module for Sanctum.

This module wraps the Claude SDK and manages the interaction between
the LLM and the MCP tools for privacy-preserving data visualization.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import anthropic
from pydantic import BaseModel


@dataclass
class AgentConfig:
    """Configuration for the visualization agent."""

    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 4096
    temperature: float = 0.0
    max_tool_calls: int = 10
    max_execution_retries: int = 3


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class NoCodeGeneratedError(AgentError):
    """Raised when agent fails to generate visualization code."""

    pass


SYSTEM_PROMPT = """You are a data visualization assistant. You help users create visualizations from datasets while preserving data privacy.

IMPORTANT CONSTRAINTS:
1. You cannot see raw data rows - only aggregate statistics via the provided tools.
2. You can use the following tools:
   - get_schema: Get the masked column names and their data types
   - query_stat: Get a differentially private aggregate statistic (mean, max, min, count, sum)
   - get_histogram: Get a differentially private histogram for a column

3. When generating visualizations:
   - First call get_schema to understand the data structure
   - Use query_stat or get_histogram to gather statistics needed for visualization
   - Generate Python code using matplotlib that creates the visualization
   - The code will have access to a DataFrame called `df` with the ORIGINAL column names (not masked)

4. Your generated code should:
   - Use matplotlib.pyplot (already imported as plt)
   - Work with a DataFrame called `df` that contains the real data
   - Create clear, informative visualizations
   - NOT call plt.show() - the system will save the figure automatically

5. When interpreting masked column names:
   - Use the dtype to understand what kind of data the column contains
   - Use query_stat to understand the data distribution before plotting

OUTPUT FORMAT:
After gathering information, output your Python code in a code block like this:
```python
# Your visualization code here
```

Only include the visualization code, not data loading or saving."""


@dataclass
class AgentResult:
    """Result from agent code generation."""

    success: bool
    code: str | None = None
    error: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)


class Agent:
    """Agent that generates visualization code using Claude and MCP tools.

    The agent uses the Claude API to interpret user requests and generate
    matplotlib code for data visualization. It uses MCP tools to gather
    privacy-preserving statistics about the data.
    """

    def __init__(
        self,
        mcp_server: Any,  # MCPServer type from mcp package
        config: AgentConfig | None = None,
        api_key: str | None = None,
    ):
        """Initialize the agent.

        Args:
            mcp_server: The MCP server instance for tool calls
            config: Optional agent configuration
            api_key: Optional API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.config = config or AgentConfig()
        self.mcp_server = mcp_server
        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

    def generate_visualization_code(self, prompt: str) -> AgentResult:
        """Generate visualization code based on user prompt.

        Args:
            prompt: User's description of the desired visualization

        Returns:
            AgentResult with generated code or error
        """
        # Build tools from MCP server
        tools = self._build_anthropic_tools()

        # Start conversation
        messages = [{"role": "user", "content": prompt}]

        tool_calls_made = []
        num_iterations = 0

        while num_iterations < self.config.max_tool_calls:
            num_iterations += 1

            try:
                response = self._client.messages.create(
                    model=self.config.model,
                    max_tokens=self.config.max_tokens,
                    temperature=self.config.temperature,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                )
            except anthropic.APIError as e:
                return AgentResult(
                    success=False,
                    error=f"API error: {str(e)}",
                    tool_calls=tool_calls_made,
                    messages=messages,
                )

            # Check if we need to process tool calls
            if response.stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

                        # Call the MCP server
                        result = self.mcp_server.call_tool(tool_name, tool_input)

                        tool_calls_made.append(
                            {
                                "tool": tool_name,
                                "input": tool_input,
                                "result": result.data if result.success else result.error,
                            }
                        )

                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": str(result.data) if result.success else f"Error: {result.error}",
                            }
                        )

                # Add assistant response and tool results to messages
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Response complete, extract code
                # Add the final assistant response to messages
                messages.append({"role": "assistant", "content": response.content})

                code = self._extract_code(response)
                if code:
                    return AgentResult(
                        success=True,
                        code=code,
                        tool_calls=tool_calls_made,
                        messages=messages,
                    )
                else:
                    # Try to get any text response
                    text_response = self._extract_text(response)
                    return AgentResult(
                        success=False,
                        error=f"No code block found in response. Response: {text_response[:500] if text_response else 'Empty'}",
                        tool_calls=tool_calls_made,
                        messages=messages,
                    )

        return AgentResult(
            success=False,
            error=f"Max tool calls ({self.config.max_tool_calls}) exceeded",
            tool_calls=tool_calls_made,
            messages=messages,
        )

    def _build_anthropic_tools(self) -> list[dict[str, Any]]:
        """Convert MCP tool definitions to Anthropic format."""
        mcp_tools = self.mcp_server.get_tools()
        anthropic_tools = []

        for tool in mcp_tools:
            anthropic_tools.append(
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["input_schema"],
                }
            )

        return anthropic_tools

    def _extract_code(self, response: anthropic.types.Message) -> str | None:
        """Extract Python code from the response."""
        for block in response.content:
            if block.type == "text":
                # Look for code blocks
                code_pattern = r"```python\s*(.*?)\s*```"
                matches = re.findall(code_pattern, block.text, re.DOTALL)
                if matches:
                    return matches[-1].strip()  # Return the last code block

        return None

    def _extract_text(self, response: anthropic.types.Message) -> str | None:
        """Extract text content from the response."""
        texts = []
        for block in response.content:
            if block.type == "text":
                texts.append(block.text)
        return "\n".join(texts) if texts else None

    def refine_code(
        self,
        previous_result: AgentResult,
        execution_error: str,
        stderr: str | None = None,
    ) -> AgentResult:
        """Refine code based on execution errors.

        This method continues the conversation from a previous result,
        providing the execution error to the agent so it can fix the code.

        Args:
            previous_result: The previous AgentResult containing messages and code
            execution_error: The error message from code execution
            stderr: Optional stderr output from execution

        Returns:
            AgentResult with refined code or error
        """
        # Build the error feedback message
        error_feedback = f"""The code you generated failed to execute with the following error:

Error: {execution_error}
"""
        if stderr:
            error_feedback += f"""
Stderr output:
{stderr}
"""
        error_feedback += """
Please analyze the error and provide corrected Python code that will successfully create the visualization.
Remember:
- The DataFrame is called `df` and has the original (unmasked) column names
- Use matplotlib.pyplot (imported as plt)
- Do not call plt.show() - the figure will be saved automatically

Provide the corrected code in a ```python code block."""

        # Continue from previous messages
        messages = list(previous_result.messages)  # Copy to avoid mutation
        messages.append({"role": "user", "content": error_feedback})

        tool_calls_made = list(previous_result.tool_calls)  # Copy previous tool calls

        try:
            response = self._client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=SYSTEM_PROMPT,
                tools=self._build_anthropic_tools(),
                messages=messages,
            )
        except anthropic.APIError as e:
            return AgentResult(
                success=False,
                error=f"API error during refinement: {str(e)}",
                tool_calls=tool_calls_made,
                messages=messages,
            )

        # Add the assistant's response to messages
        messages.append({"role": "assistant", "content": response.content})

        # Extract the refined code
        code = self._extract_code(response)
        if code:
            return AgentResult(
                success=True,
                code=code,
                tool_calls=tool_calls_made,
                messages=messages,
            )
        else:
            text_response = self._extract_text(response)
            return AgentResult(
                success=False,
                error=f"No code block found in refinement response. Response: {text_response[:500] if text_response else 'Empty'}",
                tool_calls=tool_calls_made,
                messages=messages,
            )

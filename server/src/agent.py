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


MATPLOTLIB_SYSTEM_PROMPT = """You are a data visualization assistant. You help users create visualizations from datasets while preserving data privacy.

IMPORTANT CONSTRAINTS:
1. You cannot see raw data rows - only aggregate statistics via the provided tools.
2. You can use the following tools:
   - get_schema: Get the masked column names and their data types
   - query_stat: Get a differentially private aggregate statistic (mean, max, min, count, sum)
   - get_histogram: Get a differentially private histogram for a column

3. COLUMN NAME MAPPING:
   - The user's message includes a "Column Mapping" section that shows how their column names map to masked IDs
   - When the user refers to a column (e.g., "sales"), find its corresponding masked name (e.g., "col_abc123") in the mapping
   - Use the MASKED names when calling tools like query_stat and get_histogram
   - In your generated code, use the ORIGINAL column names (the user's names), NOT the masked names

4. When generating visualizations:
   - Use the column mapping to understand which masked column corresponds to which user concept
   - Use query_stat or get_histogram with the MASKED column names to gather statistics
   - Generate Python code using matplotlib that creates the visualization
   - The code will have access to a DataFrame called `df` with the ORIGINAL column names

5. Your generated code should:
   - Use matplotlib.pyplot (already imported as plt)
   - Work with a DataFrame called `df` using ORIGINAL column names (e.g., df['sales'], NOT df['col_abc123'])
   - Create clear, informative visualizations with proper labels using the original column names
   - NOT call plt.show() - the system will save the figure automatically

OUTPUT FORMAT:
After gathering information, output your Python code in a code block like this:
```python
# Your visualization code here
```

Only include the visualization code, not data loading or saving."""

# Alias for backwards compatibility
SYSTEM_PROMPT = MATPLOTLIB_SYSTEM_PROMPT

ALTAIR_SYSTEM_PROMPT = """You are a data visualization assistant. You help users create interactive visualizations from datasets while preserving data privacy.

IMPORTANT CONSTRAINTS:
1. You cannot see raw data rows - only aggregate statistics via the provided tools.
2. You can use the following tools:
   - get_schema: Get the masked column names and their data types
   - query_stat: Get a differentially private aggregate statistic (mean, max, min, count, sum)
   - get_histogram: Get a differentially private histogram for a column

3. COLUMN NAME MAPPING:
   - The user's message includes a "Column Mapping" section that shows how their column names map to masked IDs
   - When the user refers to a column (e.g., "sales"), find its corresponding masked name (e.g., "col_abc123") in the mapping
   - Use the MASKED names when calling tools like query_stat and get_histogram
   - In your generated code, use the ORIGINAL column names (the user's names), NOT the masked names

4. When generating visualizations:
   - Use the column mapping to understand which masked column corresponds to which user concept
   - Use query_stat or get_histogram with the MASKED column names to gather statistics
   - Generate Python code using Altair to create INTERACTIVE visualizations
   - The code will have access to a DataFrame called `df` with the ORIGINAL column names

5. Your generated code should:
   - Use Altair (already imported as alt) to create interactive charts
   - Work with a DataFrame called `df` using ORIGINAL column names
   - Use alt.Chart(df) to create charts
   - Add interactive features like tooltips, zoom, pan, and brush selection where appropriate
   - Call save_chart(chart) at the end to save the Vega-Lite spec
   - Create clear, informative visualizations with proper labels

6. Altair best practices:
   - Use .interactive() for pan/zoom on scatter plots and line charts
   - Use .add_params() with alt.selection_interval() for brush selection
   - Add tooltips with tooltip=[...] parameter for hover information
   - Use alt.condition() for selection-based highlighting

OUTPUT FORMAT:
After gathering information, output your Python code in a code block like this:
```python
# Your Altair visualization code here
chart = alt.Chart(df).mark_...
save_chart(chart)
```

Only include the visualization code, not data loading. Always call save_chart(chart) at the end."""

CONVERT_TO_ALTAIR_PROMPT = """You are converting a matplotlib visualization to an interactive Altair visualization.

The original matplotlib code is provided below. Your task is to:
1. Analyze the matplotlib code to understand what visualization it creates
2. Create an equivalent Altair visualization with interactive features
3. Add appropriate interactivity (tooltips, zoom, pan, brush selection) based on the chart type

IMPORTANT:
- The DataFrame `df` is already loaded with the ORIGINAL column names
- Altair is imported as `alt`
- You must call save_chart(chart) at the end to save the Vega-Lite spec
- Preserve the visual intent of the original chart (colors, labels, etc.)

OUTPUT FORMAT:
Output your Altair code in a code block:
```python
# Your Altair visualization code here
chart = alt.Chart(df).mark_...
save_chart(chart)
```"""

CONVERT_TO_MATPLOTLIB_PROMPT = """You are converting an Altair visualization to a static matplotlib visualization.

The original Altair code is provided below. Your task is to:
1. Analyze the Altair code to understand what visualization it creates
2. Create an equivalent matplotlib visualization
3. Preserve the visual intent (chart type, colors, labels, etc.)

IMPORTANT:
- The DataFrame `df` is already loaded with the ORIGINAL column names
- matplotlib.pyplot is imported as plt
- Do NOT call plt.show() - the system will save the figure automatically
- Create clear, properly labeled visualizations

OUTPUT FORMAT:
Output your matplotlib code in a code block:
```python
# Your matplotlib visualization code here
plt.figure(figsize=(10, 6))
...
```"""


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

    def generate_visualization_code(
        self,
        prompt: str,
        schema_context: list[dict[str, str]] | None = None,
    ) -> AgentResult:
        """Generate visualization code based on user prompt.

        Args:
            prompt: User's description of the desired visualization
            schema_context: Optional list of column info dicts with original_name,
                          masked_name, and dtype for augmenting the prompt

        Returns:
            AgentResult with generated code or error
        """
        # Build tools from MCP server
        tools = self._build_anthropic_tools()

        # Augment prompt with column mapping if provided
        augmented_prompt = self._augment_prompt_with_schema(prompt, schema_context)

        # Start conversation
        messages = [{"role": "user", "content": augmented_prompt}]

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

    def _augment_prompt_with_schema(
        self,
        prompt: str,
        schema_context: list[dict[str, str]] | None,
    ) -> str:
        """Augment user prompt with column mapping context.

        Args:
            prompt: Original user prompt
            schema_context: List of dicts with original_name, masked_name, dtype

        Returns:
            Augmented prompt with column mapping information
        """
        if not schema_context:
            return prompt

        # Build column mapping section
        mapping_lines = []
        for col in schema_context:
            original = col.get("original_name", "unknown")
            masked = col.get("masked_name", "unknown")
            dtype = col.get("dtype", "unknown")
            mapping_lines.append(f"  - \"{original}\" → {masked} (type: {dtype})")

        column_mapping_text = "\n".join(mapping_lines)

        augmented = f"""{prompt}

---
COLUMN MAPPING (use masked names for tool calls, original names in generated code):
{column_mapping_text}
---"""

        return augmented

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

    def continue_conversation(
        self,
        previous_result: AgentResult,
        adjustment_prompt: str,
        schema_context: list[dict[str, str]] | None = None,
    ) -> AgentResult:
        """Continue a conversation with a user adjustment request.

        This method continues the conversation from a previous result,
        allowing the user to request modifications to the visualization.

        Args:
            previous_result: The previous AgentResult containing messages and code
            adjustment_prompt: User's request for adjustment
            schema_context: Optional schema context for column mapping

        Returns:
            AgentResult with adjusted code or error
        """
        # Augment the adjustment prompt with schema context if provided
        augmented_prompt = self._augment_prompt_with_schema(adjustment_prompt, schema_context)

        # Build the continuation message
        continuation_message = f"""The user wants to adjust the visualization:

{augmented_prompt}

Please modify the code to implement this change. You can use the MCP tools if you need additional information about the data.

Remember:
- The DataFrame is called `df` and has the original (unmasked) column names
- Use matplotlib.pyplot (imported as plt)
- Do not call plt.show() - the figure will be saved automatically

Provide the updated code in a ```python code block."""

        # Continue from previous messages
        messages = list(previous_result.messages)  # Copy to avoid mutation
        messages.append({"role": "user", "content": continuation_message})

        tool_calls_made = list(previous_result.tool_calls)  # Copy previous tool calls
        tools = self._build_anthropic_tools()

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
                    error=f"API error during continuation: {str(e)}",
                    tool_calls=tool_calls_made,
                    messages=messages,
                )

            # Check if we need to process tool calls
            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        tool_name = block.name
                        tool_input = block.input

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

                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

            else:
                # Response complete, extract code
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
                    text_response = self._extract_text(response)
                    return AgentResult(
                        success=False,
                        error=f"No code block found in continuation response. Response: {text_response[:500] if text_response else 'Empty'}",
                        tool_calls=tool_calls_made,
                        messages=messages,
                    )

        return AgentResult(
            success=False,
            error=f"Max tool calls ({self.config.max_tool_calls}) exceeded during continuation",
            tool_calls=tool_calls_made,
            messages=messages,
        )

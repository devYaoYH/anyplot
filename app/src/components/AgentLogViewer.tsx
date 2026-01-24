/**
 * Component for viewing agent logs with nested turns.
 */

import { useState } from 'react';
import type { AgentLog, ToolCallLog, MessageLog } from '../lib/api';

interface AgentLogViewerProps {
  log: AgentLog;
}

interface TurnViewerProps {
  turnNumber: number;
  message: MessageLog;
  toolCalls: ToolCallLog[];
}

function TurnViewer({ turnNumber, message, toolCalls }: TurnViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const getContentPreview = (content: unknown): string => {
    if (typeof content === 'string') {
      return content.slice(0, 100) + (content.length > 100 ? '...' : '');
    }
    if (Array.isArray(content)) {
      const textItems = content.filter(
        (item): item is { type: string; text?: string } =>
          typeof item === 'object' && item !== null && 'type' in item
      );
      const textContent = textItems
        .filter((item) => item.type === 'text' && item.text)
        .map((item) => item.text)
        .join(' ');
      if (textContent) {
        return textContent.slice(0, 100) + (textContent.length > 100 ? '...' : '');
      }
      const toolUseCount = textItems.filter((item) => item.type === 'tool_use').length;
      if (toolUseCount > 0) {
        return `[${toolUseCount} tool call${toolUseCount > 1 ? 's' : ''}]`;
      }
    }
    return '[Complex content]';
  };

  return (
    <div className="border border-gray-100 rounded overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-2 py-1.5 flex items-center gap-2 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <svg
          className={`w-3 h-3 text-gray-400 transition-transform ${
            isExpanded ? 'rotate-90' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        <span className="text-xs font-medium text-gray-600">
          Turn {turnNumber}
        </span>
        <span
          className={`px-1.5 py-0.5 text-xs rounded ${
            message.role === 'user'
              ? 'bg-blue-100 text-blue-700'
              : 'bg-green-100 text-green-700'
          }`}
        >
          {message.role}
        </span>
        {toolCalls.length > 0 && (
          <span className="px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
            {toolCalls.length} tool{toolCalls.length > 1 ? 's' : ''}
          </span>
        )}
      </button>
      {isExpanded && (
        <div className="p-2 space-y-2 bg-white">
          <div>
            <div className="text-xs font-medium text-gray-500 mb-1">Content:</div>
            <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto whitespace-pre-wrap break-words max-h-40 overflow-y-auto">
              {typeof message.content === 'string'
                ? message.content
                : JSON.stringify(message.content, null, 2)}
            </pre>
          </div>
          {toolCalls.length > 0 && (
            <div>
              <div className="text-xs font-medium text-gray-500 mb-1">Tool Calls:</div>
              <div className="space-y-1">
                {toolCalls.map((call, idx) => (
                  <ToolCallViewer key={idx} call={call} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {!isExpanded && (
        <div className="px-2 py-1 text-xs text-gray-500 truncate">
          {getContentPreview(message.content)}
        </div>
      )}
    </div>
  );
}

interface ToolCallViewerProps {
  call: ToolCallLog;
}

function ToolCallViewer({ call }: ToolCallViewerProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="border border-purple-100 rounded overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-2 py-1 flex items-center gap-2 bg-purple-50 hover:bg-purple-100 transition-colors text-left"
      >
        <svg
          className={`w-2.5 h-2.5 text-purple-400 transition-transform ${
            isExpanded ? 'rotate-90' : ''
          }`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M9 5l7 7-7 7"
          />
        </svg>
        <code className="text-xs font-medium text-purple-700">{call.tool}</code>
      </button>
      {isExpanded && (
        <div className="p-2 space-y-2 bg-white text-xs">
          <div>
            <div className="font-medium text-gray-500 mb-1">Input:</div>
            <pre className="bg-gray-50 p-1.5 rounded overflow-x-auto whitespace-pre-wrap break-words">
              {JSON.stringify(call.input, null, 2)}
            </pre>
          </div>
          <div>
            <div className="font-medium text-gray-500 mb-1">Result:</div>
            <pre className="bg-gray-50 p-1.5 rounded overflow-x-auto whitespace-pre-wrap break-words max-h-32 overflow-y-auto">
              {typeof call.result === 'string'
                ? call.result
                : JSON.stringify(call.result, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}

export function AgentLogViewer({ log }: AgentLogViewerProps) {
  // Group messages into turns (user message followed by assistant response)
  const turns: { message: MessageLog; toolCalls: ToolCallLog[] }[] = [];
  let currentToolCallIndex = 0;

  for (const message of log.messages) {
    const turnToolCalls: ToolCallLog[] = [];

    // If this is an assistant message, find associated tool calls
    if (message.role === 'assistant' && Array.isArray(message.content)) {
      const toolUseBlocks = message.content.filter(
        (item): item is { type: string; name: string } =>
          typeof item === 'object' &&
          item !== null &&
          'type' in item &&
          item.type === 'tool_use'
      );

      // Match tool calls from the log
      for (const block of toolUseBlocks) {
        if (currentToolCallIndex < log.tool_calls.length) {
          const toolCall = log.tool_calls[currentToolCallIndex];
          if (toolCall.tool === block.name) {
            turnToolCalls.push(toolCall);
            currentToolCallIndex++;
          }
        }
      }
    }

    turns.push({ message, toolCalls: turnToolCalls });
  }

  if (turns.length === 0) {
    return (
      <div className="text-xs text-gray-500 italic">No agent messages recorded</div>
    );
  }

  return (
    <div className="space-y-1">
      {turns.map((turn, idx) => (
        <TurnViewer
          key={idx}
          turnNumber={idx + 1}
          message={turn.message}
          toolCalls={turn.toolCalls}
        />
      ))}
    </div>
  );
}

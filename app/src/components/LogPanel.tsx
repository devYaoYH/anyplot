/**
 * Log panel component for displaying visualization history.
 */

import { CollapsibleSection } from './CollapsibleSection';
import { AgentLogViewer } from './AgentLogViewer';
import type { AgentLog } from '../lib/api';

export interface LogSnapshot {
  id: string;
  timestamp: Date;
  sqlQuery: string;
  userPrompt: string;
  agentLog: AgentLog | null;
  finalCode: string | null;
  success: boolean;
  error: string | null;
}

interface LogPanelProps {
  snapshots: LogSnapshot[];
  onClearHistory: () => void;
}

interface SnapshotViewerProps {
  snapshot: LogSnapshot;
  index: number;
  onExport: () => void;
}

function SnapshotViewer({ snapshot, index, onExport }: SnapshotViewerProps) {
  const formatTime = (date: Date): string => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <div className="px-3 py-2 bg-gray-50 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-gray-700">
            #{index + 1}
          </span>
          <span className="text-xs text-gray-500">
            {formatTime(snapshot.timestamp)}
          </span>
          <span
            className={`px-1.5 py-0.5 text-xs rounded ${
              snapshot.success
                ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700'
            }`}
          >
            {snapshot.success ? 'Success' : 'Failed'}
          </span>
        </div>
        <button
          onClick={onExport}
          className="p-1 text-gray-400 hover:text-gray-600 transition-colors"
          title="Export as JSON"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
            />
          </svg>
        </button>
      </div>
      <div className="p-2 space-y-2">
        <CollapsibleSection title="SQL Query">
          <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto whitespace-pre-wrap break-words">
            {snapshot.sqlQuery}
          </pre>
        </CollapsibleSection>

        <CollapsibleSection title="User Prompt">
          <p className="text-sm text-gray-700 whitespace-pre-wrap">
            {snapshot.userPrompt}
          </p>
        </CollapsibleSection>

        {snapshot.agentLog && (
          <CollapsibleSection
            title="Agent Log"
            badge={snapshot.agentLog.tool_calls.length}
          >
            <AgentLogViewer log={snapshot.agentLog} />
          </CollapsibleSection>
        )}

        {snapshot.finalCode && (
          <CollapsibleSection title="Final Code">
            <pre className="text-xs bg-gray-50 p-2 rounded overflow-x-auto whitespace-pre-wrap break-words max-h-60 overflow-y-auto">
              {snapshot.finalCode}
            </pre>
          </CollapsibleSection>
        )}

        {snapshot.error && (
          <CollapsibleSection title="Error">
            <p className="text-sm text-red-600">{snapshot.error}</p>
          </CollapsibleSection>
        )}
      </div>
    </div>
  );
}

export function LogPanel({ snapshots, onClearHistory }: LogPanelProps) {
  const handleExportSnapshot = (snapshot: LogSnapshot) => {
    const exportData = {
      id: snapshot.id,
      timestamp: snapshot.timestamp.toISOString(),
      sqlQuery: snapshot.sqlQuery,
      userPrompt: snapshot.userPrompt,
      agentLog: snapshot.agentLog,
      finalCode: snapshot.finalCode,
      success: snapshot.success,
      error: snapshot.error,
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sanctum-log-${snapshot.id}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportAll = () => {
    const exportData = snapshots.map((snapshot) => ({
      id: snapshot.id,
      timestamp: snapshot.timestamp.toISOString(),
      sqlQuery: snapshot.sqlQuery,
      userPrompt: snapshot.userPrompt,
      agentLog: snapshot.agentLog,
      finalCode: snapshot.finalCode,
      success: snapshot.success,
      error: snapshot.error,
    }));

    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sanctum-logs-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-white rounded-lg shadow h-full flex flex-col">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-sm font-medium text-gray-900">History</h2>
        <div className="flex items-center gap-2">
          {snapshots.length > 0 && (
            <>
              <button
                onClick={handleExportAll}
                className="text-xs text-blue-600 hover:text-blue-800 transition-colors"
                title="Export all logs"
              >
                Export All
              </button>
              <button
                onClick={onClearHistory}
                className="text-xs text-red-600 hover:text-red-800 transition-colors"
              >
                Clear
              </button>
            </>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto p-3">
        {snapshots.length === 0 ? (
          <div className="text-center py-8">
            <svg
              className="w-12 h-12 mx-auto text-gray-300 mb-3"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
            <p className="text-sm text-gray-500">No visualization history yet</p>
            <p className="text-xs text-gray-400 mt-1">
              Generate a visualization to see logs here
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {[...snapshots].reverse().map((snapshot, idx) => (
              <SnapshotViewer
                key={snapshot.id}
                snapshot={snapshot}
                index={snapshots.length - 1 - idx}
                onExport={() => handleExportSnapshot(snapshot)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

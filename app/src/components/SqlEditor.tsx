/**
 * SQL query editor component using CodeMirror.
 */

import CodeMirror from '@uiw/react-codemirror';
import { sql } from '@codemirror/lang-sql';

interface SqlEditorProps {
  value: string;
  onChange: (value: string) => void;
  onRun: () => void;
  disabled?: boolean;
}

export function SqlEditor({ value, onChange, onRun, disabled = false }: SqlEditorProps) {
  const handleKeyDown = (event: React.KeyboardEvent) => {
    // Run query on Ctrl/Cmd + Enter
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault();
      onRun();
    }
  };

  return (
    <div className="space-y-2" onKeyDown={handleKeyDown}>
      <div className="flex justify-between items-center">
        <label className="text-sm font-medium text-gray-700">SQL Query</label>
        <span className="text-xs text-gray-500">Ctrl+Enter to run</span>
      </div>
      <CodeMirror
        value={value}
        height="120px"
        extensions={[sql()]}
        onChange={onChange}
        editable={!disabled}
        className="border rounded-md overflow-hidden"
        basicSetup={{
          lineNumbers: true,
          highlightActiveLineGutter: true,
          foldGutter: false,
        }}
      />
      <button
        onClick={onRun}
        disabled={disabled || !value.trim()}
        className={`
          px-4 py-2 rounded-md text-white font-medium
          transition-colors duration-200
          ${
            disabled || !value.trim()
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700'
          }
        `}
      >
        Run Query
      </button>
    </div>
  );
}

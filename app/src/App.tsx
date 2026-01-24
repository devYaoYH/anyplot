/**
 * Main application component for Sanctum.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Layout } from './components/Layout';
import { DataUploader } from './components/DataUploader';
import { SqlEditor } from './components/SqlEditor';
import { DataGrid } from './components/DataGrid';
import { VisualizationPanel } from './components/VisualizationPanel';
import { LogPanel, type LogSnapshot } from './components/LogPanel';
import { useSqlite } from './hooks/useSqlite';
import { useVisualize } from './hooks/useVisualize';

function App() {
  const [rawData, setRawData] = useState<Record<string, unknown>[]>([]);
  const [sqlQuery, setSqlQuery] = useState('SELECT * FROM data LIMIT 100');
  const [queryResult, setQueryResult] = useState<{
    columns: string[];
    values: unknown[][];
  } | null>(null);
  const [logSnapshots, setLogSnapshots] = useState<LogSnapshot[]>([]);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  const {
    isReady: sqliteReady,
    error: sqliteError,
    loadData,
    runQuery,
    clearDatabase,
  } = useSqlite();

  const {
    isLoading: visualizeLoading,
    error: visualizeError,
    result: visualizeResult,
    progress: visualizeProgress,
    generateVisualization,
    cancelVisualization,
    clearResult,
  } = useVisualize();

  const handleDataLoaded = useCallback(
    (data: Record<string, unknown>[]) => {
      setRawData(data);
      loadData(data);
      setQueryResult(null);
      clearResult();
      // Auto-run the default query
      const result = runQuery('SELECT * FROM data LIMIT 100');
      if (result) {
        setQueryResult(result);
      }
    },
    [loadData, runQuery, clearResult]
  );

  const handleRunQuery = useCallback(() => {
    const result = runQuery(sqlQuery);
    if (result) {
      setQueryResult(result);
    }
  }, [runQuery, sqlQuery]);

  const sqlQueryRef = useRef(sqlQuery);
  sqlQueryRef.current = sqlQuery;

  const handleVisualize = useCallback(
    (prompt: string) => {
      // Get current query result data as JSON
      if (!queryResult || queryResult.values.length === 0) {
        return;
      }

      // Convert query result to array of objects
      const data = queryResult.values.map((row) => {
        const obj: Record<string, unknown> = {};
        queryResult.columns.forEach((col, idx) => {
          obj[col] = row[idx];
        });
        return obj;
      });

      // Store the prompt for snapshot creation
      setPendingPrompt(prompt);
      generateVisualization(data, prompt);
    },
    [queryResult, generateVisualization]
  );

  // Create a snapshot when visualization completes or errors
  useEffect(() => {
    if (pendingPrompt && (visualizeResult || visualizeError) && !visualizeLoading) {
      const snapshot: LogSnapshot = {
        id: crypto.randomUUID().slice(0, 8),
        timestamp: new Date(),
        sqlQuery: sqlQueryRef.current,
        userPrompt: pendingPrompt,
        agentLog: visualizeResult?.agentLog || null,
        finalCode: visualizeResult?.code || null,
        success: !!visualizeResult && !visualizeError,
        error: visualizeError,
      };
      setLogSnapshots((prev) => [...prev, snapshot]);
      setPendingPrompt(null);
    }
  }, [visualizeResult, visualizeError, visualizeLoading, pendingPrompt]);

  const handleClear = useCallback(() => {
    setRawData([]);
    setQueryResult(null);
    clearDatabase();
    clearResult();
    setSqlQuery('SELECT * FROM data LIMIT 100');
  }, [clearDatabase, clearResult]);

  const handleClearHistory = useCallback(() => {
    setLogSnapshots([]);
  }, []);

  const hasData = rawData.length > 0;
  const hasQueryResult = queryResult && queryResult.values.length > 0;

  return (
    <Layout
      rightPanel={
        <LogPanel
          snapshots={logSnapshots}
          onClearHistory={handleClearHistory}
        />
      }
    >
      <div className="space-y-6">
        {/* Data Upload Section */}
        <section className="bg-white rounded-lg shadow p-6">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-lg font-medium text-gray-900">Data Source</h2>
            {hasData && (
              <button
                onClick={handleClear}
                className="text-sm text-red-600 hover:text-red-800"
              >
                Clear Data
              </button>
            )}
          </div>
          {!hasData ? (
            <DataUploader
              onDataLoaded={handleDataLoaded}
              onError={(err) => console.error(err)}
            />
          ) : (
            <div className="text-sm text-gray-600">
              Loaded {rawData.length} rows with {Object.keys(rawData[0]).length} columns
            </div>
          )}
        </section>

        {/* SQL Editor Section */}
        {hasData && (
          <section className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Query Data
            </h2>
            {!sqliteReady ? (
              <div className="text-gray-500">Initializing SQLite...</div>
            ) : (
              <>
                {sqliteError && (
                  <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                    {sqliteError}
                  </div>
                )}
                <SqlEditor
                  value={sqlQuery}
                  onChange={setSqlQuery}
                  onRun={handleRunQuery}
                  disabled={!sqliteReady}
                />
              </>
            )}
          </section>
        )}

        {/* Query Results Section */}
        {hasData && queryResult && (
          <section className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Query Results
            </h2>
            <DataGrid columns={queryResult.columns} data={queryResult.values} />
          </section>
        )}

        {/* Visualization Section */}
        {hasQueryResult && (
          <section className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Visualize
            </h2>
            <VisualizationPanel
              onVisualize={handleVisualize}
              onCancel={cancelVisualization}
              isLoading={visualizeLoading}
              imageBase64={visualizeResult?.image || null}
              code={visualizeResult?.code || null}
              error={visualizeError}
              progress={visualizeProgress}
              disabled={!hasQueryResult}
            />
          </section>
        )}
      </div>
    </Layout>
  );
}

export default App;

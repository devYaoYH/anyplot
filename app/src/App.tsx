/**
 * Main application component for Sanctum.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Layout } from './components/Layout';
import { DataUploader } from './components/DataUploader';
import { SqlEditor } from './components/SqlEditor';
import { DataGrid } from './components/DataGrid';
import { VisualizationPanel } from './components/VisualizationPanel';
import { InteractiveDashboard } from './components/InteractiveDashboard';
import { LogPanel, type LogSnapshot } from './components/LogPanel';
import { SessionSelector } from './components/SessionSelector';
import { useSqlite } from './hooks/useSqlite';
import { useVisualize } from './hooks/useVisualize';
import { useSession } from './hooks/useSession';
import { useDashboard } from './hooks/useDashboard';
import type { LogSnapshot as ApiLogSnapshot } from './lib/api';

function App() {
  const [rawData, setRawData] = useState<Record<string, unknown>[]>([]);
  const [sqlQuery, setSqlQuery] = useState('SELECT * FROM data LIMIT 100');
  const [queryResult, setQueryResult] = useState<{
    columns: string[];
    values: unknown[][];
  } | null>(null);
  const [logSnapshots, setLogSnapshots] = useState<LogSnapshot[]>([]);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);
  const [pendingReplay, setPendingReplay] = useState<{ code: string; prompt: string } | null>(null);
  const [pendingContinue, setPendingContinue] = useState<string | null>(null);
  const [currentSnapshotId, setCurrentSnapshotId] = useState<string | null>(null);
  const [isRestoringSession, setIsRestoringSession] = useState(false);

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
    matplotlibResult,
    altairResult,
    progress: visualizeProgress,
    hasActiveSession,
    generateVisualization,
    continueVisualization,
    replayVisualization,
    convertVisualization,
    cancelVisualization,
    clearResult,
    clearSession,
    restoreResults,
  } = useVisualize();

  const {
    currentSession,
    sessions,
    isLoading: sessionLoading,
    createNewSession,
    loadSession,
    saveSession,
    deleteCurrentSession,
  } = useSession();

  const {
    charts: dashboardCharts,
    filters: dashboardFilters,
    allFilterableFields,
    addChartsFromSpec,
    isCompositeSpec,
    countChartsInSpec,
    removeChart: removeChartFromDashboard,
    updateLayout: updateDashboardLayout,
    addFilter: addDashboardFilter,
    removeFilter: removeDashboardFilter,
    updateFilter: updateDashboardFilter,
    clearFilters: clearDashboardFilters,
    getFilteredSpec,
    getApplicableFiltersForChart,
    clearDashboard,
  } = useDashboard();

  const sqlQueryRef = useRef(sqlQuery);
  sqlQueryRef.current = sqlQuery;

  // Convert API LogSnapshot to UI LogSnapshot format
  const apiToUiSnapshot = (snap: ApiLogSnapshot): LogSnapshot => ({
    id: snap.id,
    timestamp: new Date(snap.timestamp),
    sqlQuery: snap.sql_query,
    userPrompt: snap.user_prompt,
    agentLog: snap.agent_log,
    finalCode: snap.final_code,
    success: snap.success,
    error: snap.error,
  });

  // Convert UI LogSnapshot to API LogSnapshot format
  const uiToApiSnapshot = (snap: LogSnapshot): ApiLogSnapshot => ({
    id: snap.id,
    timestamp: snap.timestamp.toISOString(),
    sql_query: snap.sqlQuery,
    user_prompt: snap.userPrompt,
    agent_log: snap.agentLog,
    final_code: snap.finalCode,
    success: snap.success,
    error: snap.error,
  });

  // Restore session when loaded
  useEffect(() => {
    if (currentSession && sqliteReady && !isRestoringSession) {
      setIsRestoringSession(true);

      // Restore raw data
      if (currentSession.raw_data.length > 0) {
        setRawData(currentSession.raw_data);
        loadData(currentSession.raw_data);

        // Restore SQL query
        setSqlQuery(currentSession.sql_query);

        // Run the query to populate results
        setTimeout(() => {
          const result = runQuery(currentSession.sql_query);
          if (result) {
            setQueryResult(result);
          }
        }, 100);
      }

      // Restore log snapshots
      if (currentSession.log_snapshots.length > 0) {
        setLogSnapshots(currentSession.log_snapshots.map(apiToUiSnapshot));
      }

      // Restore visualization results
      if (currentSession.matplotlib_result || currentSession.altair_result) {
        restoreResults(
          currentSession.matplotlib_result,
          currentSession.altair_result
        );
      }

      setIsRestoringSession(false);
    }
  }, [currentSession?.id, sqliteReady, restoreResults]);

  // Save session when state changes (debounced via saveSession)
  const saveCurrentState = useCallback(() => {
    if (isRestoringSession || !currentSession) return;

    saveSession({
      raw_data: rawData,
      sql_query: sqlQuery,
      log_snapshots: logSnapshots.map(uiToApiSnapshot),
      matplotlib_result: matplotlibResult ? {
        image: matplotlibResult.image,
        vega_spec: matplotlibResult.vegaSpec,
        viz_type: matplotlibResult.vizType,
        code: matplotlibResult.code,
      } : null,
      altair_result: altairResult ? {
        image: altairResult.image,
        vega_spec: altairResult.vegaSpec,
        viz_type: altairResult.vizType,
        code: altairResult.code,
      } : null,
    });
  }, [rawData, sqlQuery, logSnapshots, matplotlibResult, altairResult, currentSession, isRestoringSession, saveSession]);

  // Auto-save when state changes
  useEffect(() => {
    if (!isRestoringSession && currentSession) {
      saveCurrentState();
    }
  }, [rawData, sqlQuery, logSnapshots, matplotlibResult, altairResult]);

  const handleDataLoaded = useCallback(
    async (data: Record<string, unknown>[]) => {
      // Create a new session if none exists
      if (!currentSession) {
        await createNewSession();
      }

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
    [loadData, runQuery, clearResult, currentSession, createNewSession]
  );

  const handleRunQuery = useCallback(() => {
    const result = runQuery(sqlQuery);
    if (result) {
      setQueryResult(result);
      // Clear session when running new query - new visualizations should start fresh
      clearSession();
      setCurrentSnapshotId(null);
    }
  }, [runQuery, sqlQuery, clearSession]);

  const getQueryData = useCallback(() => {
    if (!queryResult || queryResult.values.length === 0) {
      return null;
    }
    return queryResult.values.map((row) => {
      const obj: Record<string, unknown> = {};
      queryResult.columns.forEach((col, idx) => {
        obj[col] = row[idx];
      });
      return obj;
    });
  }, [queryResult]);

  const handleVisualize = useCallback(
    (prompt: string, vizMode: 'matplotlib' | 'altair' = 'matplotlib') => {
      const data = getQueryData();
      if (!data) return;

      // Store the prompt for snapshot creation
      setPendingPrompt(prompt);
      setCurrentSnapshotId(null); // New visualization, new snapshot
      generateVisualization(data, prompt, vizMode);
    },
    [getQueryData, generateVisualization]
  );

  const handleContinue = useCallback(
    (prompt: string) => {
      const data = getQueryData();
      if (!data) return;

      // Store the continue prompt for snapshot update
      setPendingContinue(prompt);
      continueVisualization(data, prompt);
    },
    [getQueryData, continueVisualization]
  );

  const handleNewVisualization = useCallback(() => {
    clearSession();
    clearResult();
    setCurrentSnapshotId(null);
  }, [clearSession, clearResult]);

  const handleConvert = useCallback(
    (targetMode: 'matplotlib' | 'altair') => {
      const data = getQueryData();
      if (!data) return;

      // Get the current code to convert from
      const sourceResult = targetMode === 'altair' ? matplotlibResult : altairResult;
      if (!sourceResult?.code) return;

      // Use the original prompt if available, otherwise use a generic description
      const originalPrompt = pendingPrompt || 'visualization';

      convertVisualization(data, sourceResult.code, originalPrompt, targetMode);
    },
    [getQueryData, matplotlibResult, altairResult, convertVisualization, pendingPrompt]
  );

  const handleAddToDashboard = useCallback(
    (vegaSpec: object, code: string, splitCharts: boolean) => {
      addChartsFromSpec(vegaSpec, code, splitCharts);
    },
    [addChartsFromSpec]
  );

  // Create or update snapshot when visualization completes or errors
  useEffect(() => {
    const hasPending = pendingPrompt || pendingReplay || pendingContinue;
    if (hasPending && (visualizeResult || visualizeError) && !visualizeLoading) {
      const isReplay = !!pendingReplay;
      const isContinue = !!pendingContinue;

      if (isContinue && currentSnapshotId) {
        // Update existing snapshot with continuation
        setLogSnapshots((prev) =>
          prev.map((snapshot) => {
            if (snapshot.id !== currentSnapshotId) return snapshot;

            // Append the continue prompt to userPrompt
            const updatedPrompt = `${snapshot.userPrompt}\n\n[Adjustment] ${pendingContinue}`;

            return {
              ...snapshot,
              userPrompt: updatedPrompt,
              agentLog: visualizeResult?.agentLog || snapshot.agentLog,
              finalCode: visualizeResult?.code || snapshot.finalCode,
              success: !!visualizeResult && !visualizeError,
              error: visualizeError,
            };
          })
        );
      } else {
        // Create new snapshot
        const promptText = pendingReplay?.prompt || pendingPrompt || '';
        const displayPrompt = isReplay
          ? `[Replay${visualizeResult?.wasFixed ? ' - Fixed' : ''}] ${promptText}`
          : promptText;

        const newId = crypto.randomUUID().slice(0, 8);
        const snapshot: LogSnapshot = {
          id: newId,
          timestamp: new Date(),
          sqlQuery: sqlQueryRef.current,
          userPrompt: displayPrompt,
          agentLog: visualizeResult?.agentLog || null,
          finalCode: visualizeResult?.code || null,
          success: !!visualizeResult && !visualizeError,
          error: visualizeError,
        };
        setLogSnapshots((prev) => [...prev, snapshot]);
        setCurrentSnapshotId(newId);
      }

      setPendingPrompt(null);
      setPendingReplay(null);
      setPendingContinue(null);
    }
  }, [visualizeResult, visualizeError, visualizeLoading, pendingPrompt, pendingReplay, pendingContinue, currentSnapshotId]);

  const handleReplay = useCallback(
    (code: string, originalPrompt: string) => {
      const data = getQueryData();
      if (!data) return;

      // Store the replay info for snapshot creation
      setPendingReplay({ code, prompt: originalPrompt });
      setCurrentSnapshotId(null); // Replay creates new snapshot
      replayVisualization(data, code, originalPrompt);
    },
    [getQueryData, replayVisualization]
  );

  const handleClear = useCallback(() => {
    setRawData([]);
    setQueryResult(null);
    clearDatabase();
    clearResult();
    setSqlQuery('SELECT * FROM data LIMIT 100');
    setLogSnapshots([]);
  }, [clearDatabase, clearResult]);

  const handleClearHistory = useCallback(() => {
    setLogSnapshots([]);
  }, []);

  const handleCreateSession = useCallback(async (name?: string) => {
    await createNewSession(name);
    // Clear current state for new session
    handleClear();
  }, [createNewSession, handleClear]);

  const handleLoadSession = useCallback(async (sessionId: string) => {
    // Clear current state before loading
    setRawData([]);
    setQueryResult(null);
    clearDatabase();
    clearResult();
    setLogSnapshots([]);
    setSqlQuery('SELECT * FROM data LIMIT 100');

    await loadSession(sessionId);
  }, [loadSession, clearDatabase, clearResult]);

  const handleDeleteSession = useCallback(async () => {
    await deleteCurrentSession();
    handleClear();
  }, [deleteCurrentSession, handleClear]);

  const hasData = rawData.length > 0;
  const hasQueryResult = queryResult && queryResult.values.length > 0;

  return (
    <Layout
      rightPanel={
        <LogPanel
          snapshots={logSnapshots}
          onClearHistory={handleClearHistory}
          onReplay={handleReplay}
          canReplay={!!hasQueryResult}
          isLoading={visualizeLoading}
        />
      }
      headerExtra={
        <SessionSelector
          currentSession={currentSession}
          sessions={sessions}
          isLoading={sessionLoading}
          onCreateSession={handleCreateSession}
          onLoadSession={handleLoadSession}
          onDeleteSession={handleDeleteSession}
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
              onContinue={handleContinue}
              onConvert={handleConvert}
              onNewVisualization={handleNewVisualization}
              onCancel={cancelVisualization}
              onAddToDashboard={handleAddToDashboard}
              isCompositeSpec={isCompositeSpec}
              countChartsInSpec={countChartsInSpec}
              dashboardChartCount={dashboardCharts.length}
              dashboardContent={
                <InteractiveDashboard
                  charts={dashboardCharts}
                  filters={dashboardFilters}
                  allFilterableFields={allFilterableFields}
                  onUpdateLayout={updateDashboardLayout}
                  onRemoveChart={removeChartFromDashboard}
                  onAddFilter={addDashboardFilter}
                  onRemoveFilter={removeDashboardFilter}
                  onUpdateFilter={updateDashboardFilter}
                  onClearFilters={clearDashboardFilters}
                  getFilteredSpec={getFilteredSpec}
                  getApplicableFiltersForChart={getApplicableFiltersForChart}
                  onClearDashboard={clearDashboard}
                />
              }
              isLoading={visualizeLoading}
              result={visualizeResult}
              matplotlibResult={matplotlibResult}
              altairResult={altairResult}
              error={visualizeError}
              progress={visualizeProgress}
              hasActiveSession={hasActiveSession}
              disabled={!hasQueryResult}
            />
          </section>
        )}
      </div>
    </Layout>
  );
}

export default App;

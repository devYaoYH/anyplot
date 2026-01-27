/**
 * Interactive multi-chart dashboard with grid layout and filters.
 */

import { useMemo, useCallback, useRef, useState, useEffect } from 'react';
import GridLayout from 'react-grid-layout';
import type { Layout } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import 'react-resizable/css/styles.css';
import { DashboardChart } from './DashboardChart';
import { FilterBar } from './FilterBar';
import type { DashboardChart as DashboardChartType, DashboardFilter } from '../types/dashboard';

interface InteractiveDashboardProps {
  charts: DashboardChartType[];
  filters: DashboardFilter[];
  allFilterableFields: string[];
  onUpdateLayout: (layouts: Layout[]) => void;
  onRemoveChart: (id: string) => void;
  onAddFilter: (filter: Omit<DashboardFilter, 'id'>) => void;
  onRemoveFilter: (id: string) => void;
  onUpdateFilter: (id: string, updates: Partial<Omit<DashboardFilter, 'id'>>) => void;
  onClearFilters: () => void;
  getFilteredSpec: (chart: DashboardChartType) => object;
  getApplicableFiltersForChart: (chart: DashboardChartType) => DashboardFilter[];
  onClearDashboard: () => void;
}

const GRID_CONFIG = {
  cols: 12,
  rowHeight: 100,
  margin: [16, 16] as [number, number],
};

export function InteractiveDashboard({
  charts,
  filters,
  allFilterableFields,
  onUpdateLayout,
  onRemoveChart,
  onAddFilter,
  onRemoveFilter,
  onUpdateFilter,
  onClearFilters,
  getFilteredSpec,
  getApplicableFiltersForChart,
  onClearDashboard,
}: InteractiveDashboardProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(1200);

  // Track container width for responsive layout
  useEffect(() => {
    const updateWidth = () => {
      if (containerRef.current) {
        setContainerWidth(containerRef.current.offsetWidth);
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  // Calculate cell dimensions based on layout
  const getCellDimensions = useCallback(
    (layout: Layout) => {
      const colWidth = (containerWidth - GRID_CONFIG.margin[0] * (GRID_CONFIG.cols + 1)) / GRID_CONFIG.cols;
      return {
        width: layout.w * colWidth + (layout.w - 1) * GRID_CONFIG.margin[0],
        height: layout.h * GRID_CONFIG.rowHeight + (layout.h - 1) * GRID_CONFIG.margin[1],
      };
    },
    [containerWidth]
  );

  // Generate layout from charts
  const layout = useMemo(
    () => charts.map((chart) => chart.layout),
    [charts]
  );

  const handleLayoutChange = useCallback(
    (newLayout: Layout[]) => {
      onUpdateLayout(newLayout);
    },
    [onUpdateLayout]
  );

  if (charts.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-gray-500">
        <svg
          className="w-16 h-16 mb-4 text-gray-300"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M4 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1V5zM14 5a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zM4 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1H5a1 1 0 01-1-1v-4zM14 15a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z"
          />
        </svg>
        <p className="text-lg font-medium mb-2">No charts in dashboard</p>
        <p className="text-sm">
          Add charts from the "Single Chart" view using the "Add to Dashboard" button.
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="space-y-4">
      {/* Filter bar */}
      <FilterBar
        filters={filters}
        allFilterableFields={allFilterableFields}
        charts={charts}
        onAddFilter={onAddFilter}
        onRemoveFilter={onRemoveFilter}
        onUpdateFilter={onUpdateFilter}
        onClearFilters={onClearFilters}
      />

      {/* Dashboard header */}
      <div className="flex items-center justify-between">
        <span className="text-sm text-gray-600">
          {charts.length} chart{charts.length > 1 ? 's' : ''} in dashboard
        </span>
        <button
          onClick={onClearDashboard}
          className="text-sm text-red-600 hover:text-red-800"
        >
          Clear Dashboard
        </button>
      </div>

      {/* Grid layout */}
      <GridLayout
        className="dashboard-grid"
        layout={layout}
        cols={GRID_CONFIG.cols}
        rowHeight={GRID_CONFIG.rowHeight}
        width={containerWidth}
        margin={GRID_CONFIG.margin}
        onLayoutChange={handleLayoutChange}
        draggableHandle=".drag-handle"
        useCSSTransforms={true}
        compactType="vertical"
        preventCollision={false}
      >
        {charts.map((chart) => {
          const cellDimensions = getCellDimensions(chart.layout);
          return (
            <div key={chart.id}>
              <DashboardChart
                chart={chart}
                filteredSpec={getFilteredSpec(chart)}
                applicableFilters={getApplicableFiltersForChart(chart)}
                onRemove={() => onRemoveChart(chart.id)}
                containerWidth={cellDimensions.width}
                containerHeight={cellDimensions.height}
              />
            </div>
          );
        })}
      </GridLayout>
    </div>
  );
}

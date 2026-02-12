/**
 * Individual chart component for the dashboard grid.
 */

import { useState, useMemo } from 'react';
import { VegaChart } from './VegaChart';
import { CodeViewerModal } from './CodeViewerModal';
import type { DashboardChart as DashboardChartType, DashboardFilter } from '../types/dashboard';

interface DashboardChartProps {
  chart: DashboardChartType;
  filteredSpec: object;
  applicableFilters: DashboardFilter[];
  onRemove: () => void;
  containerWidth: number;
  containerHeight: number;
}

export function DashboardChart({
  chart,
  filteredSpec,
  applicableFilters,
  onRemove,
  containerWidth,
  containerHeight,
}: DashboardChartProps) {
  const [showCodeModal, setShowCodeModal] = useState(false);

  // Calculate chart dimensions with padding for header and actions
  const chartDimensions = useMemo(() => {
    const headerHeight = 40;
    const actionsHeight = 36;
    const padding = 16;
    return {
      width: Math.max(containerWidth - padding, 200),
      height: Math.max(containerHeight - headerHeight - actionsHeight - padding, 150),
    };
  }, [containerWidth, containerHeight]);

  // Apply dimensions to the spec
  const sizedSpec = useMemo(() => {
    return {
      ...filteredSpec,
      width: chartDimensions.width - 50,
      height: chartDimensions.height - 50,
      autosize: { type: 'fit', contains: 'padding' },
    };
  }, [filteredSpec, chartDimensions]);

  const hasActiveFilters = applicableFilters.length > 0;

  return (
    <>
      <div className="h-full flex flex-col bg-white rounded-lg border border-gray-200 shadow-sm overflow-hidden">
        {/* Header with drag handle */}
        <div className="flex items-center justify-between px-3 py-2 bg-gray-50 border-b border-gray-200 cursor-move drag-handle">
          <div className="flex items-center gap-2 min-w-0">
            {/* Drag indicator */}
            <svg
              className="w-4 h-4 text-gray-400 flex-shrink-0"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <circle cx="8" cy="6" r="1.5" />
              <circle cx="16" cy="6" r="1.5" />
              <circle cx="8" cy="12" r="1.5" />
              <circle cx="16" cy="12" r="1.5" />
              <circle cx="8" cy="18" r="1.5" />
              <circle cx="16" cy="18" r="1.5" />
            </svg>
            <span className="text-sm font-medium text-gray-700 truncate">
              {chart.title}
            </span>
            {hasActiveFilters && (
              <span
                className="flex-shrink-0 px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded"
                title={`${applicableFilters.length} filter(s) applied`}
              >
                {applicableFilters.length} filter{applicableFilters.length > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>

        {/* Chart content */}
        <div className="flex-1 overflow-hidden p-2">
          <VegaChart
            spec={sizedSpec}
            width={chartDimensions.width}
            height={chartDimensions.height}
          />
        </div>

        {/* Action bar */}
        <div className="flex items-center justify-end gap-2 px-3 py-1.5 bg-gray-50 border-t border-gray-200">
          <button
            onClick={() => setShowCodeModal(true)}
            className="px-2 py-1 text-xs text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded transition-colors"
          >
            Show Code
          </button>
          <button
            onClick={onRemove}
            className="px-2 py-1 text-xs text-red-600 hover:text-red-800 hover:bg-red-50 rounded transition-colors"
          >
            Remove
          </button>
        </div>
      </div>

      <CodeViewerModal
        isOpen={showCodeModal}
        onClose={() => setShowCodeModal(false)}
        code={chart.code}
        title={chart.title ? `Code: ${chart.title}` : 'Chart Code'}
      />
    </>
  );
}

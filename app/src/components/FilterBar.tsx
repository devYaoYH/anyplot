/**
 * Filter bar component for global dashboard filters.
 */

import { useState, useMemo } from 'react';
import type { DashboardFilter, FilterOperator } from '../types/dashboard';
import type { DashboardChart } from '../types/dashboard';
import { inferFieldInfo } from '../lib/vegaFilters';

interface FilterBarProps {
  filters: DashboardFilter[];
  allFilterableFields: string[];
  charts: DashboardChart[];
  onAddFilter: (filter: Omit<DashboardFilter, 'id'>) => void;
  onRemoveFilter: (id: string) => void;
  onUpdateFilter: (id: string, updates: Partial<Omit<DashboardFilter, 'id'>>) => void;
  onClearFilters: () => void;
}

const OPERATORS: { value: FilterOperator; label: string }[] = [
  { value: 'equals', label: '=' },
  { value: 'contains', label: 'contains' },
  { value: 'gt', label: '>' },
  { value: 'lt', label: '<' },
  { value: 'in', label: 'in' },
];

export function FilterBar({
  filters,
  allFilterableFields,
  charts,
  onAddFilter,
  onRemoveFilter,
  onClearFilters,
}: FilterBarProps) {
  const [selectedField, setSelectedField] = useState<string>('');
  const [selectedOperator, setSelectedOperator] = useState<FilterOperator>('equals');
  const [filterValue, setFilterValue] = useState<string>('');
  const [isExpanded, setIsExpanded] = useState(false);

  // Get field info from any chart that has this field
  const fieldInfo = useMemo(() => {
    if (!selectedField) return null;
    const chartWithField = charts.find((c) =>
      c.filterableFields.includes(selectedField)
    );
    if (!chartWithField) return null;
    return inferFieldInfo(chartWithField.vegaSpec, selectedField);
  }, [selectedField, charts]);

  // Get available operators based on field type
  const availableOperators = useMemo(() => {
    if (!fieldInfo) return OPERATORS;
    switch (fieldInfo.type) {
      case 'numeric':
        return OPERATORS.filter((op) =>
          ['equals', 'gt', 'lt'].includes(op.value)
        );
      case 'categorical':
        return OPERATORS.filter((op) =>
          ['equals', 'in'].includes(op.value)
        );
      default:
        return OPERATORS;
    }
  }, [fieldInfo]);

  const handleAddFilter = () => {
    if (!selectedField || !filterValue) return;

    let parsedValue: unknown = filterValue;

    // Parse value based on operator
    if (selectedOperator === 'in') {
      parsedValue = filterValue.split(',').map((v) => v.trim());
    } else if (fieldInfo?.type === 'numeric') {
      parsedValue = parseFloat(filterValue);
      if (isNaN(parsedValue as number)) return;
    }

    onAddFilter({
      field: selectedField,
      operator: selectedOperator,
      value: parsedValue,
    });

    // Reset form
    setFilterValue('');
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleAddFilter();
    }
  };

  const formatFilterValue = (filter: DashboardFilter): string => {
    if (Array.isArray(filter.value)) {
      return filter.value.join(', ');
    }
    return String(filter.value);
  };

  const getOperatorSymbol = (op: FilterOperator): string => {
    const found = OPERATORS.find((o) => o.value === op);
    return found?.label || op;
  };

  if (allFilterableFields.length === 0) {
    return null;
  }

  return (
    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="flex items-center gap-2 text-sm font-medium text-gray-700 hover:text-gray-900"
        >
          <svg
            className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
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
          Global Filters
          {filters.length > 0 && (
            <span className="ml-1 px-1.5 py-0.5 text-xs bg-purple-100 text-purple-700 rounded">
              {filters.length}
            </span>
          )}
        </button>
        {filters.length > 0 && (
          <button
            onClick={onClearFilters}
            className="text-xs text-red-600 hover:text-red-800"
          >
            Clear all
          </button>
        )}
      </div>

      {/* Active filters */}
      {filters.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {filters.map((filter) => (
            <div
              key={filter.id}
              className="inline-flex items-center gap-1 px-2 py-1 bg-purple-100 text-purple-800 rounded text-sm"
            >
              <span className="font-medium">{filter.field}</span>
              <span className="text-purple-600">{getOperatorSymbol(filter.operator)}</span>
              <span>{formatFilterValue(filter)}</span>
              <button
                onClick={() => onRemoveFilter(filter.id)}
                className="ml-1 text-purple-600 hover:text-purple-800"
                aria-label="Remove filter"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add filter form */}
      {isExpanded && (
        <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-200">
          {/* Field selector */}
          <select
            value={selectedField}
            onChange={(e) => {
              setSelectedField(e.target.value);
              setSelectedOperator('equals');
              setFilterValue('');
            }}
            className="px-2 py-1.5 text-sm border border-gray-300 rounded bg-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <option value="">Select field...</option>
            {allFilterableFields.map((field) => (
              <option key={field} value={field}>
                {field}
              </option>
            ))}
          </select>

          {/* Operator selector */}
          <select
            value={selectedOperator}
            onChange={(e) => setSelectedOperator(e.target.value as FilterOperator)}
            disabled={!selectedField}
            className="px-2 py-1.5 text-sm border border-gray-300 rounded bg-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:bg-gray-100 disabled:text-gray-400"
          >
            {availableOperators.map((op) => (
              <option key={op.value} value={op.value}>
                {op.label}
              </option>
            ))}
          </select>

          {/* Value input */}
          {fieldInfo?.type === 'categorical' && fieldInfo.uniqueValues ? (
            <select
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
              disabled={!selectedField}
              className="px-2 py-1.5 text-sm border border-gray-300 rounded bg-white focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:bg-gray-100 min-w-[120px]"
            >
              <option value="">Select value...</option>
              {fieldInfo.uniqueValues.map((val) => (
                <option key={String(val)} value={String(val)}>
                  {String(val)}
                </option>
              ))}
            </select>
          ) : (
            <input
              type={fieldInfo?.type === 'numeric' ? 'number' : 'text'}
              value={filterValue}
              onChange={(e) => setFilterValue(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder={
                selectedOperator === 'in'
                  ? 'value1, value2, ...'
                  : 'Enter value...'
              }
              disabled={!selectedField}
              className="px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-purple-500 disabled:bg-gray-100 min-w-[120px]"
            />
          )}

          {/* Add button */}
          <button
            onClick={handleAddFilter}
            disabled={!selectedField || !filterValue}
            className="px-3 py-1.5 text-sm bg-purple-600 text-white rounded hover:bg-purple-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            Add Filter
          </button>
        </div>
      )}
    </div>
  );
}

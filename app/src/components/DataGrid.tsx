/**
 * Data grid component for displaying query results.
 */

interface DataGridProps {
  columns: string[];
  data: unknown[][];
  maxRows?: number;
}

export function DataGrid({ columns, data, maxRows = 100 }: DataGridProps) {
  const displayData = data.slice(0, maxRows);
  const hasMore = data.length > maxRows;

  if (columns.length === 0) {
    return (
      <div className="text-gray-500 text-center py-8">
        No data to display. Run a query to see results.
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="text-sm text-gray-600">
        {data.length} row{data.length !== 1 ? 's' : ''}
        {hasMore && ` (showing first ${maxRows})`}
      </div>
      <div className="overflow-auto max-h-96 border rounded-md">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50 sticky top-0">
            <tr>
              {columns.map((col, idx) => (
                <th
                  key={idx}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {displayData.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-gray-50">
                {row.map((cell, cellIdx) => (
                  <td
                    key={cellIdx}
                    className="px-4 py-2 text-sm text-gray-900 whitespace-nowrap"
                  >
                    {formatCell(cell)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) {
    return 'NULL';
  }
  if (typeof value === 'number') {
    return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  }
  return String(value);
}

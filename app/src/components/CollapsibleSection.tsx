/**
 * Collapsible section component with expand/collapse functionality.
 */

import { useState, type ReactNode } from 'react';

interface CollapsibleSectionProps {
  title: string;
  children: ReactNode;
  defaultExpanded?: boolean;
  badge?: string | number;
}

export function CollapsibleSection({
  title,
  children,
  defaultExpanded = false,
  badge,
}: CollapsibleSectionProps) {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);

  return (
    <div className="border border-gray-200 rounded-md overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full px-3 py-2 flex items-center justify-between bg-gray-50 hover:bg-gray-100 transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <svg
            className={`w-4 h-4 text-gray-500 transition-transform ${
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
          <span className="text-sm font-medium text-gray-700">{title}</span>
        </div>
        {badge !== undefined && (
          <span className="px-2 py-0.5 text-xs bg-gray-200 text-gray-600 rounded-full">
            {badge}
          </span>
        )}
      </button>
      {isExpanded && (
        <div className="p-3 bg-white border-t border-gray-200">
          {children}
        </div>
      )}
    </div>
  );
}

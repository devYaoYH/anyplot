/**
 * Main layout component for the application.
 */

import type { ReactNode } from 'react';
import { Settings } from './Settings';

interface LayoutProps {
  children: ReactNode;
  rightPanel?: ReactNode;
  onApiKeyChange?: () => void;
}

export function Layout({ children, rightPanel, onApiKeyChange }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm">
        <div className="max-w-[1600px] mx-auto px-4 py-4 flex justify-between items-start">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">
              Sanctum
            </h1>
            <p className="text-sm text-gray-500">
              Privacy-preserving data visualization
            </p>
          </div>
          <Settings onApiKeyChange={onApiKeyChange} />
        </div>
      </header>
      <main className="max-w-[1600px] mx-auto px-4 py-6">
        <div className={`flex gap-6 ${rightPanel ? '' : ''}`}>
          <div className={rightPanel ? 'flex-1 min-w-0' : 'w-full'}>
            {children}
          </div>
          {rightPanel && (
            <div className="w-80 flex-shrink-0">
              <div className="sticky top-6 max-h-[calc(100vh-6rem)] overflow-hidden">
                {rightPanel}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

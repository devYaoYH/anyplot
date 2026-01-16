/**
 * CSV file upload component using react-dropzone.
 */

import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import Papa from 'papaparse';

interface DataUploaderProps {
  onDataLoaded: (data: Record<string, unknown>[]) => void;
  onError: (error: string) => void;
}

export function DataUploader({ onDataLoaded, onError }: DataUploaderProps) {
  const onDrop = useCallback(
    (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      if (!file.name.endsWith('.csv')) {
        onError('Please upload a CSV file');
        return;
      }

      Papa.parse(file, {
        header: true,
        dynamicTyping: true,
        skipEmptyLines: true,
        complete: (results) => {
          if (results.errors.length > 0) {
            onError(`CSV parsing error: ${results.errors[0].message}`);
            return;
          }
          onDataLoaded(results.data as Record<string, unknown>[]);
        },
        error: (error) => {
          onError(`Failed to parse CSV: ${error.message}`);
        },
      });
    },
    [onDataLoaded, onError]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'text/csv': ['.csv'],
    },
    multiple: false,
  });

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-lg p-8 text-center cursor-pointer
        transition-colors duration-200
        ${
          isDragActive
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }
      `}
    >
      <input {...getInputProps()} />
      <div className="text-gray-600">
        {isDragActive ? (
          <p>Drop the CSV file here...</p>
        ) : (
          <>
            <p className="mb-2">Drag and drop a CSV file here</p>
            <p className="text-sm text-gray-500">or click to select a file</p>
          </>
        )}
      </div>
    </div>
  );
}

/**
 * Hook for managing SQLite WASM database.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import initSqlJs from 'sql.js';
import type { Database, SqlJsStatic } from 'sql.js';

export interface QueryResult {
  columns: string[];
  values: unknown[][];
}

export interface UseSqliteReturn {
  isReady: boolean;
  error: string | null;
  loadData: (data: Record<string, unknown>[]) => void;
  runQuery: (sql: string) => QueryResult | null;
  getTableInfo: () => { name: string; columns: string[] }[];
  clearDatabase: () => void;
}

export function useSqlite(): UseSqliteReturn {
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const sqlRef = useRef<SqlJsStatic | null>(null);
  const dbRef = useRef<Database | null>(null);

  // Initialize SQL.js
  useEffect(() => {
    const initDb = async () => {
      try {
        const SQL = await initSqlJs({
          locateFile: (file: string) => `https://sql.js.org/dist/${file}`,
        });
        sqlRef.current = SQL;
        dbRef.current = new SQL.Database();
        setIsReady(true);
      } catch (err) {
        setError(`Failed to initialize SQLite: ${err}`);
      }
    };

    initDb();

    return () => {
      if (dbRef.current) {
        dbRef.current.close();
      }
    };
  }, []);

  const loadData = useCallback((data: Record<string, unknown>[]) => {
    if (!dbRef.current || data.length === 0) return;

    try {
      // Get column names from first row
      const columns = Object.keys(data[0]);

      // Drop existing table
      dbRef.current.run('DROP TABLE IF EXISTS data');

      // Create table with appropriate types
      const columnDefs = columns.map((col) => {
        const value = data[0][col];
        let type = 'TEXT';
        if (typeof value === 'number') {
          type = Number.isInteger(value) ? 'INTEGER' : 'REAL';
        }
        return `"${col}" ${type}`;
      });

      dbRef.current.run(`CREATE TABLE data (${columnDefs.join(', ')})`);

      // Insert data
      const placeholders = columns.map(() => '?').join(', ');
      const stmt = dbRef.current.prepare(`INSERT INTO data VALUES (${placeholders})`);

      for (const row of data) {
        const values = columns.map((col) => row[col] as string | number | null);
        stmt.run(values);
      }

      stmt.free();
      setError(null);
    } catch (err) {
      setError(`Failed to load data: ${err}`);
    }
  }, []);

  const runQuery = useCallback((sql: string): QueryResult | null => {
    if (!dbRef.current) return null;

    try {
      const result = dbRef.current.exec(sql);
      if (result.length === 0) {
        return { columns: [], values: [] };
      }
      setError(null);
      return {
        columns: result[0].columns,
        values: result[0].values,
      };
    } catch (err) {
      setError(`Query error: ${err}`);
      return null;
    }
  }, []);

  const getTableInfo = useCallback((): { name: string; columns: string[] }[] => {
    if (!dbRef.current) return [];

    try {
      const tables = dbRef.current.exec(
        "SELECT name FROM sqlite_master WHERE type='table'"
      );

      if (tables.length === 0) return [];

      return tables[0].values.map((row: unknown[]) => {
        const tableName = row[0] as string;
        const columnsResult = dbRef.current!.exec(
          `PRAGMA table_info("${tableName}")`
        );
        const columns =
          columnsResult.length > 0
            ? columnsResult[0].values.map((col: unknown[]) => col[1] as string)
            : [];
        return { name: tableName, columns };
      });
    } catch {
      return [];
    }
  }, []);

  const clearDatabase = useCallback(() => {
    if (!dbRef.current || !sqlRef.current) return;

    dbRef.current.close();
    dbRef.current = new sqlRef.current.Database();
    setError(null);
  }, []);

  return {
    isReady,
    error,
    loadData,
    runQuery,
    getTableInfo,
    clearDatabase,
  };
}

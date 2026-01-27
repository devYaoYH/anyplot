"""SQLite-based session store for persisting user sessions.

Stores:
- Session metadata (id, name, timestamps)
- Uploaded data
- SQL queries
- Visualization history (log snapshots)
- Visualization results (images, vega specs, code)
"""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class LogSnapshotModel(BaseModel):
    """Model for a visualization log snapshot."""

    id: str
    timestamp: str
    sql_query: str
    user_prompt: str
    agent_log: dict | None = None
    final_code: str | None = None
    success: bool
    error: str | None = None


class VisualizationResultModel(BaseModel):
    """Model for a visualization result."""

    image: str | None = None
    vega_spec: dict | None = None
    viz_type: str = "image"
    code: str | None = None


class SessionData(BaseModel):
    """Complete session data for save/load operations."""

    id: str
    name: str
    created_at: str
    updated_at: str
    raw_data: list[dict[str, Any]] = Field(default_factory=list)
    sql_query: str = "SELECT * FROM data LIMIT 100"
    log_snapshots: list[LogSnapshotModel] = Field(default_factory=list)
    matplotlib_result: VisualizationResultModel | None = None
    altair_result: VisualizationResultModel | None = None


class SessionMetadata(BaseModel):
    """Session metadata for listing sessions."""

    id: str
    name: str
    created_at: str
    updated_at: str
    row_count: int
    snapshot_count: int


class SessionStore:
    """SQLite-based session store."""

    def __init__(self, db_path: Path | str | None = None):
        """Initialize the session store.

        Args:
            db_path: Path to the SQLite database file.
                    Defaults to ~/.sanctum/sessions.db
        """
        if db_path is None:
            db_path = Path.home() / ".sanctum" / "sessions.db"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with automatic cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize the database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    raw_data TEXT NOT NULL DEFAULT '[]',
                    sql_query TEXT NOT NULL DEFAULT 'SELECT * FROM data LIMIT 100',
                    log_snapshots TEXT NOT NULL DEFAULT '[]',
                    matplotlib_result TEXT,
                    altair_result TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated_at
                ON sessions(updated_at DESC)
            """)

    def create_session(self, name: str | None = None) -> SessionData:
        """Create a new session.

        Args:
            name: Optional session name. Defaults to timestamp-based name.

        Returns:
            The created session data.
        """
        session_id = str(uuid.uuid4())[:8]
        now = datetime.utcnow().isoformat()
        if name is None:
            name = f"Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}"

        session = SessionData(
            id=session_id,
            name=name,
            created_at=now,
            updated_at=now,
        )

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO sessions (id, name, created_at, updated_at, raw_data, sql_query, log_snapshots)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.id,
                    session.name,
                    session.created_at,
                    session.updated_at,
                    json.dumps(session.raw_data),
                    session.sql_query,
                    json.dumps([]),
                ),
            )

        return session

    def get_session(self, session_id: str) -> SessionData | None:
        """Get a session by ID.

        Args:
            session_id: The session ID.

        Returns:
            The session data, or None if not found.
        """
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_session(row)

    def _row_to_session(self, row: sqlite3.Row) -> SessionData:
        """Convert a database row to a SessionData object."""
        log_snapshots_raw = json.loads(row["log_snapshots"])
        log_snapshots = [LogSnapshotModel(**snap) for snap in log_snapshots_raw]

        matplotlib_result = None
        if row["matplotlib_result"]:
            matplotlib_result = VisualizationResultModel(**json.loads(row["matplotlib_result"]))

        altair_result = None
        if row["altair_result"]:
            altair_result = VisualizationResultModel(**json.loads(row["altair_result"]))

        return SessionData(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            raw_data=json.loads(row["raw_data"]),
            sql_query=row["sql_query"],
            log_snapshots=log_snapshots,
            matplotlib_result=matplotlib_result,
            altair_result=altair_result,
        )

    def update_session(self, session_id: str, **updates) -> SessionData | None:
        """Update a session.

        Args:
            session_id: The session ID.
            **updates: Fields to update (raw_data, sql_query, log_snapshots,
                      matplotlib_result, altair_result, name)

        Returns:
            The updated session data, or None if not found.
        """
        session = self.get_session(session_id)
        if session is None:
            return None

        now = datetime.utcnow().isoformat()
        set_clauses = ["updated_at = ?"]
        params = [now]

        if "raw_data" in updates:
            set_clauses.append("raw_data = ?")
            params.append(json.dumps(updates["raw_data"]))

        if "sql_query" in updates:
            set_clauses.append("sql_query = ?")
            params.append(updates["sql_query"])

        if "log_snapshots" in updates:
            set_clauses.append("log_snapshots = ?")
            snapshots = [
                snap.model_dump() if isinstance(snap, LogSnapshotModel) else snap
                for snap in updates["log_snapshots"]
            ]
            params.append(json.dumps(snapshots))

        if "matplotlib_result" in updates:
            set_clauses.append("matplotlib_result = ?")
            result = updates["matplotlib_result"]
            if result is not None:
                if isinstance(result, VisualizationResultModel):
                    result = result.model_dump()
                params.append(json.dumps(result))
            else:
                params.append(None)

        if "altair_result" in updates:
            set_clauses.append("altair_result = ?")
            result = updates["altair_result"]
            if result is not None:
                if isinstance(result, VisualizationResultModel):
                    result = result.model_dump()
                params.append(json.dumps(result))
            else:
                params.append(None)

        if "name" in updates:
            set_clauses.append("name = ?")
            params.append(updates["name"])

        params.append(session_id)

        with self._get_connection() as conn:
            conn.execute(
                f"UPDATE sessions SET {', '.join(set_clauses)} WHERE id = ?",
                params,
            )

        return self.get_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session.

        Args:
            session_id: The session ID.

        Returns:
            True if deleted, False if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM sessions WHERE id = ?",
                (session_id,),
            )
            return cursor.rowcount > 0

    def list_sessions(self, limit: int = 50, offset: int = 0) -> list[SessionMetadata]:
        """List all sessions, most recently updated first.

        Args:
            limit: Maximum number of sessions to return.
            offset: Number of sessions to skip.

        Returns:
            List of session metadata.
        """
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, name, created_at, updated_at, raw_data, log_snapshots
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()

        sessions = []
        for row in rows:
            raw_data = json.loads(row["raw_data"])
            log_snapshots = json.loads(row["log_snapshots"])
            sessions.append(
                SessionMetadata(
                    id=row["id"],
                    name=row["name"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    row_count=len(raw_data),
                    snapshot_count=len(log_snapshots),
                )
            )
        return sessions


# Global session store instance
_session_store: SessionStore | None = None


def get_session_store() -> SessionStore:
    """Get the global session store instance."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store

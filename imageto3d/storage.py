"""SQLite-backed task store for the Web UI (survives server restarts)."""

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

ACTIVE_STATUSES = ("queued", "running")

_COLUMNS = (
    "status",
    "subdivision_level",
    "file_format",
    "created_at",
    "updated_at",
    "image_count",
    "image_info",
    "output_url",
    "local_path",
    "draft",
    "seed",
    "error",
)


class TaskStore:
    """Thread-safe SQLite storage for conversion tasks."""

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self._db_path), check_same_thread=False, timeout=15.0
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._create_tables()
        self._migrate()

    def _create_tables(self) -> None:
        with self._lock:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    subdivision_level TEXT,
                    file_format TEXT,
                    created_at REAL NOT NULL,
                    updated_at REAL,
                    image_count INTEGER DEFAULT 1,
                    image_info TEXT,
                    output_url TEXT,
                    local_path TEXT,
                    draft INTEGER DEFAULT 0,
                    seed INTEGER,
                    error TEXT
                )
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )
            self._conn.commit()

    def _migrate(self) -> None:
        """Add any missing columns to databases created by older versions."""
        with self._lock:
            existing = {
                row["name"]
                for row in self._conn.execute("PRAGMA table_info(tasks)").fetchall()
            }
            for column in _COLUMNS:
                if column not in existing:
                    self._conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} TEXT")
            self._conn.commit()

    @staticmethod
    def _serialize(task: Dict[str, Any]) -> Dict[str, Any]:
        data = dict(task)
        if isinstance(data.get("image_info"), (dict, list)):
            data["image_info"] = json.dumps(data["image_info"], ensure_ascii=False)
        return data

    @staticmethod
    def _deserialize(row: sqlite3.Row) -> Dict[str, Any]:
        task = dict(row)
        if task.get("image_info"):
            try:
                task["image_info"] = json.loads(task["image_info"])
            except ValueError:
                task["image_info"] = []
        return task

    def upsert(self, task: Dict[str, Any]) -> None:
        data = self._serialize(task)
        with self._lock:
            self._conn.execute(
                f"""
                INSERT INTO tasks ({", ".join(["id"] + list(_COLUMNS))})
                VALUES ({", ".join(["?"] * (len(_COLUMNS) + 1))})
                ON CONFLICT(id) DO UPDATE SET
                    {", ".join(f"{c} = excluded.{c}" for c in _COLUMNS)}
                """,
                [data.get("id")] + [data.get(c) for c in _COLUMNS],
            )
            self._conn.commit()

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return self._deserialize(row) if row else None

    def list(
        self,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        page = max(1, int(page))
        page_size = max(1, min(int(page_size), 100))

        where = ""
        params: List[Any] = []
        if status and status != "all":
            where = "WHERE status = ?"
            params.append(status)

        with self._lock:
            total = self._conn.execute(
                f"SELECT COUNT(*) FROM tasks {where}", params
            ).fetchone()[0]
            rows = self._conn.execute(
                f"SELECT * FROM tasks {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params + [page_size, (page - 1) * page_size],
            ).fetchall()

        return {
            "tasks": [self._deserialize(r) for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def list_unfinished(self) -> List[Dict[str, Any]]:
        with self._lock:
            placeholders = ", ".join("?" for _ in ACTIVE_STATUSES)
            rows = self._conn.execute(
                f"SELECT * FROM tasks WHERE status IN ({placeholders})",
                list(ACTIVE_STATUSES),
            ).fetchall()
        return [self._deserialize(r) for r in rows]

    def update(self, task_id: str, **fields: Any) -> None:
        allowed = {k: v for k, v in fields.items() if k in _COLUMNS}
        if not allowed:
            return
        data = self._serialize(allowed)
        assignments = ", ".join(f"{k} = ?" for k in data)
        with self._lock:
            self._conn.execute(
                f"UPDATE tasks SET {assignments} WHERE id = ?",
                list(data.values()) + [task_id],
            )
            self._conn.commit()

    def delete(self, task_id: str) -> bool:
        with self._lock:
            cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            self._conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.ProgrammingError:
                pass  # already closed

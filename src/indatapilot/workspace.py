from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
from datetime import datetime, timezone
import json
import sqlite3
import threading
import uuid

from .catalog import Catalog

WORKSPACE_FILE = "workspace.sqlite"
CATALOG_FILE = "catalog.jsonl"
META_FILE = "meta.json"


class Workspace:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / WORKSPACE_FILE
        self.catalog_path = self.root / CATALOG_FILE
        self.meta_path = self.root / META_FILE
        self._db: sqlite3.Connection | None = None
        self._query_lock = threading.Lock()

    @classmethod
    def create(cls, root: Path, name: str | None = None) -> "Workspace":
        ws = cls(root)
        if not ws.meta_path.exists():
            meta = {
                "id": str(uuid.uuid4()),
                "name": name or ws.root.name,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            ws.meta_path.write_text(json.dumps(meta, indent=2))
            ws.catalog.append({
                "event": "workspace_created",
                "workspace": meta["id"],
                "name": meta["name"],
            })
        return ws

    @classmethod
    def exists(cls, root: Path) -> bool:
        return (Path(root) / META_FILE).exists()

    @property
    def query_lock(self) -> threading.Lock:
        return self._query_lock

    def __enter__(self) -> "Workspace":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    @property
    def meta(self) -> dict:
        return json.loads(self.meta_path.read_text())

    @property
    def catalog(self) -> Catalog:
        return Catalog(self.catalog_path)

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._db.row_factory = sqlite3.Row
            self._db.execute("PRAGMA journal_mode = WAL")
            self._db.execute("PRAGMA synchronous = NORMAL")
            self._db.execute("PRAGMA foreign_keys = ON")
        return self._db

    @contextmanager
    def write_lock(self):
        """Lock cross-processo para operações que escrevem no SQLite.

        Usa flock em <db>.lock. Em plataformas sem fcntl (Windows), é no-op.
        Não serializa threads no mesmo processo; use ws.query_lock para isso.
        """
        lock_path = self.db_path.with_suffix(".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("w") as f:
            try:
                import fcntl
            except ImportError:
                yield
                return
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

from __future__ import annotations
from pathlib import Path
from datetime import datetime, timezone
from typing import Iterator
import json

try:
    import fcntl
    _FCNTL = True
except ImportError:
    _FCNTL = False


class Catalog:
    def __init__(self, path: Path):
        self.path = Path(path)

    def append(self, event: dict) -> None:
        event = {"ts": datetime.now(timezone.utc).isoformat(), **event}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(event, ensure_ascii=False) + "\n"
        with self.path.open("a", encoding="utf-8") as f:
            if _FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(line); f.flush()
            finally:
                if _FCNTL:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def __iter__(self) -> Iterator[dict]:
        if not self.path.exists():
            return
        yield from _read_file(self.path)

    def iter_all(self) -> Iterator[dict]:
        parent = self.path.parent
        archives = sorted(parent.glob(f"{self.path.stem}-*.jsonl"))
        for a in archives:
            yield from _read_file(a)
        yield from self.__iter__()

    def tables(self) -> dict[str, dict]:
        state: dict[str, dict] = {}
        for ev in self:
            e = ev.get("event")
            if e == "state_snapshot":
                state = {k: dict(v) for k, v in ev.get("tables", {}).items()}
            elif e == "table_registered":
                state[ev["table"]] = ev
            elif e == "table_dropped":
                state.pop(ev["table"], None)
        return state

    def views(self) -> dict[str, dict]:
        state: dict[str, dict] = {}
        for ev in self:
            e = ev.get("event")
            if e == "state_snapshot":
                state = {k: dict(v) for k, v in ev.get("views", {}).items()}
            elif e == "view_created":
                state[ev["name"]] = ev
            elif e == "view_dropped":
                state.pop(ev["name"], None)
        return state

    def rotate(self, max_bytes: int = 10_000_000) -> Path | None:
        if not self.path.exists() or self.path.stat().st_size < max_bytes:
            return None
        snap_tables = {k: dict(v) for k, v in self.tables().items()}
        snap_views = {k: dict(v) for k, v in self.views().items()}
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        archive = self.path.with_name(f"{self.path.stem}-{ts}.jsonl")
        self.path.rename(archive)
        self.append({
            "event": "state_snapshot",
            "tables": snap_tables,
            "views": snap_views,
        })
        return archive


def _read_file(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue

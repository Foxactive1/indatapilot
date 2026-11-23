from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import csv
import json
import re
import threading
import time
import uuid

from .sqlutil import strip_literals
from .workspace import Workspace

FORBIDDEN = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "ATTACH", "DETACH", "VACUUM", "REINDEX", "PRAGMA", "REPLACE",
    "TRUNCATE", "GRANT", "REVOKE",
)

DEFAULT_LIMIT = 1000
DEFAULT_TIMEOUT_S = 30
DEFAULT_EXPORT_LIMIT = 1_000_000


@dataclass
class QueryResult:
    sql: str
    original_sql: str
    rows: int
    columns: list[str] = field(default_factory=list)
    data: list[dict] = field(default_factory=list)
    latency_ms: int = 0
    status: str = "ok"
    error: str | None = None


def _validate(sql: str) -> str | None:
    stripped = sql.strip().rstrip(";")
    if not stripped:
        return "SQL vazio"
    scan = strip_literals(stripped).upper()
    if not re.match(r"^\s*(SELECT|WITH)\b", scan):
        return "somente SELECT/WITH são permitidos"
    for word in FORBIDDEN:
        if re.search(rf"\b{word}\b", scan):
            return f"palavra proibida: {word}"
    return None


def _enforce_limit(sql: str, limit: int) -> str:
    body = sql.strip().rstrip(";")
    return f"SELECT * FROM (\n{body}\n) LIMIT {limit}"


def _sync_temp_views(ws: Workspace) -> None:
    existing = {
        r[0] for r in ws.db.execute(
            "SELECT name FROM sqlite_temp_master WHERE type='view'"
        ).fetchall()
    }
    for name in existing:
        ws.db.execute(f'DROP VIEW IF EXISTS temp."{name}"')
    for name, info in ws.catalog.views().items():
        ws.db.execute(f'CREATE TEMP VIEW "{name}" AS {info["sql"]}')


def execute(ws, sql, *, limit=DEFAULT_LIMIT, timeout_s=DEFAULT_TIMEOUT_S):
    run_id = str(uuid.uuid4())
    started = time.time()

    err = _validate(sql)
    if err:
        latency = int((time.time() - started) * 1000)
        _log(ws, run_id, sql, sql, 0, "rejected", err, latency)
        return QueryResult(sql=sql, original_sql=sql, rows=0,
                           latency_ms=latency, status="rejected", error=err)

    safe_sql = _enforce_limit(sql, limit)
    columns: list[str] = []
    data: list[dict] = []
    status, error = "ok", None

    with ws.query_lock:
        _sync_temp_views(ws)
        timer = threading.Timer(timeout_s, ws.db.interrupt)
        timer.daemon = True
        timer.start()
        try:
            cur = ws.db.execute(safe_sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            data = [dict(row) for row in cur.fetchall()] if columns else []
        except Exception as e:
            status, error = "error", str(e)[:500]
        finally:
            timer.cancel()

    latency = int((time.time() - started) * 1000)
    _log(ws, run_id, sql, safe_sql, len(data), status, error, latency)
    return QueryResult(sql=safe_sql, original_sql=sql, rows=len(data),
                       columns=columns, data=data, latency_ms=latency,
                       status=status, error=error)


def export_query(ws, sql, output, *, limit=DEFAULT_EXPORT_LIMIT, timeout_s=300):
    err = _validate(sql)
    if err:
        raise ValueError(err)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    ext = output.suffix.lower()
    if ext not in (".csv", ".jsonl", ".json", ".parquet", ".pq"):
        raise ValueError(f"formato de saída não suportado: {ext}")

    safe_sql = _enforce_limit(sql, limit) if limit > 0 else sql.strip().rstrip(";")
    run_id = str(uuid.uuid4())
    started = time.time()
    status, error = "ok", None
    written = 0

    with ws.query_lock:
        _sync_temp_views(ws)
        timer = threading.Timer(timeout_s, ws.db.interrupt)
        timer.daemon = True
        timer.start()
        try:
            written = _stream_to(
                ws.db, safe_sql, output, ext,
                metadata={"indatapilot_sql": sql, "indatapilot_run_id": run_id},
            )
        except Exception as e:
            status, error = "error", str(e)[:500]
        finally:
            timer.cancel()

    latency = int((time.time() - started) * 1000)
    ws.catalog.append({
        "event": "query_executed",
        "workspace": ws.meta["id"],
        "run_id": run_id,
        "sql": safe_sql,
        "original_sql": sql,
        "rows": written,
        "status": status,
        "error": error,
        "latency_ms": latency,
        "export_to": str(output),
    })

    if error:
        raise RuntimeError(error)
    return written


def _stream_to(db, sql, output, ext, metadata):
    cur = db.execute(sql)
    columns = [d[0] for d in cur.description]

    if ext == ".csv":
        with output.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(columns)
            n = 0
            for row in cur:
                w.writerow(tuple(row))
                n += 1
        return n

    if ext == ".jsonl":
        with output.open("w", encoding="utf-8") as f:
            n = 0
            for row in cur:
                d = dict(zip(columns, row))
                f.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
                n += 1
        return n

    if ext == ".json":
        rows = [dict(zip(columns, row)) for row in cur]
        output.write_text(
            json.dumps(rows, ensure_ascii=False, default=str, indent=2),
            encoding="utf-8",
        )
        return len(rows)

    if ext in (".parquet", ".pq"):
        import pyarrow as pa
        import pyarrow.parquet as pq
        import pandas as pd

        meta_bytes = {k.encode(): v.encode() for k, v in metadata.items()}
        writer = None
        n = 0
        try:
            while True:
                rows = cur.fetchmany(100_000)
                if not rows:
                    break
                df = pd.DataFrame(
                    [dict(zip(columns, r)) for r in rows], columns=columns,
                )
                t = pa.Table.from_pandas(df, preserve_index=False)
                if writer is None:
                    base_meta = t.schema.metadata or {}
                    schema = t.schema.with_metadata({**base_meta, **meta_bytes})
                    writer = pq.ParquetWriter(output, schema)
                writer.write_table(t)
                n += len(rows)
        finally:
            if writer is not None:
                writer.close()
        if writer is None:
            pd.DataFrame(columns=columns).to_parquet(output, index=False)
        return n

    raise ValueError(f"extensão não suportada: {ext}")


def _log(ws, run_id, original_sql, executed_sql, rows, status, error, latency_ms):
    ws.catalog.append({
        "event": "query_executed",
        "workspace": ws.meta["id"],
        "run_id": run_id,
        "sql": executed_sql,
        "original_sql": original_sql,
        "rows": rows,
        "status": status,
        "error": error,
        "latency_ms": latency_ms,
    })

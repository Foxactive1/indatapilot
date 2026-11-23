from __future__ import annotations
from pathlib import Path
import pandas as pd
from ..sqlutil import quote_identifier, sanitize_table_name
from ..workspace import Workspace
from .base import TableInfo


def _require(mod: str, feature: str) -> None:
    try:
        __import__(mod)
    except ImportError as e:
        raise RuntimeError(
            f"Recurso {feature} requer '{mod}'. "
            f"Instale com `pip install {mod}` (ou `pkg install python-{mod}`)."
        ) from e
def import_file(ws, path, table=None, *, if_exists="replace"):
    path = Path(path)
    if not path.exists(): raise FileNotFoundError(path)
    table = sanitize_table_name(table or path.stem)
    ext = path.suffix.lower()
    if ext == ".csv": df = pd.read_csv(path)
    elif ext in (".parquet", ".pq"): df = pd.read_parquet(path)
    elif ext == ".json": df = pd.read_json(path)
    elif ext == ".jsonl": df = pd.read_json(path, lines=True)
    elif ext in (".xlsx", ".xls"): df = pd.read_excel(path)
    else: raise ValueError(f"Formato não suportado: {ext}")
    if df.shape[1] == 0: raise ValueError(f"Arquivo sem colunas: {path}")
    with ws.write_lock(), ws.db: df.to_sql(table, ws.db, if_exists=if_exists, index=False)
    info = _describe(ws, table, source=f"file:{ext}", mode="materialized")
    ws.catalog.append({"event":"table_registered","workspace":ws.meta["id"],
        "table":info.table,"source":info.source,"mode":info.mode,
        "rows":info.rows,"columns":info.columns})
    return info
def _describe(ws, table, source, mode):
    ident = quote_identifier(table)
    cols = ws.db.execute(f"PRAGMA table_info({ident})").fetchall()
    rows = ws.db.execute(f"SELECT COUNT(*) FROM {ident}").fetchone()[0]
    return TableInfo(table=table, source=source, mode=mode, rows=rows,
                     columns=[{"name": c[1], "type": c[2]} for c in cols])

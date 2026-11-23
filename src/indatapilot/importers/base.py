# src/indatapilot/importers/base.py
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class TableInfo:
    table: str
    source: str
    mode: str
    rows: int
    columns: list[dict]
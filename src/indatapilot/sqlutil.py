from __future__ import annotations
import re
_IDENT_RE = re.compile(r"[^a-zA-Z0-9_]")
def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'
def sanitize_table_name(name: str) -> str:
    c = re.sub(r"_+", "_", _IDENT_RE.sub("_", name).strip("_").lower()) or "tabela"
    return ("_" + c if c[0].isdigit() else c)[:64]
def strip_literals(sql: str) -> str:
    out, i, n = [], 0, len(sql)
    while i < n:
        c = sql[i]
        if c in ("'", '"'):
            q = c; i += 1
            while i < n:
                if sql[i] == q:
                    if i + 1 < n and sql[i + 1] == q: i += 2; continue
                    i += 1; break
                i += 1
        elif c == "`":
            i += 1
            while i < n and sql[i] != "`": i += 1
            i += 1
        elif c == "[":
            i += 1
            while i < n and sql[i] != "]": i += 1
            i += 1
        elif sql[i:i+2] == "--":
            while i < n and sql[i] != "\n": i += 1
        elif sql[i:i+2] == "/*":
            i += 2
            while i < n and sql[i:i+2] != "*/": i += 1
            i += 2
        else:
            out.append(c); i += 1
    return "".join(out)

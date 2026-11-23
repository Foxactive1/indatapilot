import pandas as pd

from indatapilot.executor import execute
from indatapilot.importers.files import import_file


def _seed(ws, tmp_path):
    csv = tmp_path / "t.csv"
    pd.DataFrame({"x": [1, 2, 3]}).to_csv(csv, index=False)
    import_file(ws, csv)


def _add_view(ws, name, sql):
    ws.catalog.append({
        "event": "view_created",
        "workspace": ws.meta["id"],
        "name": name,
        "sql": sql,
    })


def test_view_query(ws, tmp_path):
    _seed(ws, tmp_path)
    _add_view(ws, "v", "SELECT x FROM t WHERE x > 1")
    res = execute(ws, "SELECT * FROM v")
    assert res.status == "ok"
    assert sorted(r["x"] for r in res.data) == [2, 3]


def test_view_nested(ws, tmp_path):
    _seed(ws, tmp_path)
    _add_view(ws, "v1", "SELECT x FROM t WHERE x > 1")
    _add_view(ws, "v2", "SELECT SUM(x) AS s FROM v1")
    res = execute(ws, "SELECT * FROM v2")
    assert res.status == "ok"
    assert res.data[0]["s"] == 5


def test_view_drop(ws, tmp_path):
    _seed(ws, tmp_path)
    _add_view(ws, "v", "SELECT * FROM t")
    assert execute(ws, "SELECT COUNT(*) AS n FROM v").status == "ok"
    ws.catalog.append({"event": "view_dropped",
                       "workspace": ws.meta["id"], "name": "v"})
    res = execute(ws, "SELECT * FROM v")
    assert res.status == "error"
    assert "no such table" in (res.error or "").lower()

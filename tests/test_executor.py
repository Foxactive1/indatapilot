# tests/test_executor.py
import pandas as pd
from indatapilot.executor import execute
from indatapilot.importers.files import import_file


def _seed(ws, tmp_path):
    csv = tmp_path / "t.csv"
    pd.DataFrame({"x": [1, 2, 3]}).to_csv(csv, index=False)
    import_file(ws, csv)


def test_select_ok(ws, tmp_path):
    _seed(ws, tmp_path)
    res = execute(ws, "SELECT SUM(x) AS total FROM t")
    assert res.status == "ok"
    assert res.data[0]["total"] == 6


def test_rejects_delete(ws):
    res = execute(ws, "DELETE FROM t")
    assert res.status == "rejected"


def test_rejects_insert(ws):
    res = execute(ws, "INSERT INTO t VALUES (4)")
    assert res.status == "rejected"


def test_rejects_create(ws):
    res = execute(ws, "CREATE TABLE x AS SELECT 1")
    assert res.status == "rejected"


def test_auto_limit(ws, tmp_path):
    _seed(ws, tmp_path)
    res = execute(ws, "SELECT * FROM t")
    assert "LIMIT" in res.sql.upper()


def test_query_is_logged(ws, tmp_path):
    _seed(ws, tmp_path)
    execute(ws, "SELECT 1")
    events = [e for e in ws.catalog if e.get("event") == "query_executed"]
    assert len(events) == 1
    assert events[0]["status"] == "ok"

# tests/test_executor.py — adições

def test_literal_with_forbidden_word_is_allowed(ws, tmp_path):
    _seed(ws, tmp_path)
    res = execute(ws, "SELECT 'DROP TABLE' AS tag FROM t")
    assert res.status == "ok"


def test_comment_with_forbidden_word_is_allowed(ws, tmp_path):
    _seed(ws, tmp_path)
    res = execute(ws, "SELECT x FROM t -- DELETE later\n")
    assert res.status == "ok"


def test_limit_is_wrapped_outside_subquery(ws, tmp_path):
    _seed(ws, tmp_path)
    res = execute(ws, "SELECT * FROM (SELECT * FROM t LIMIT 5)", limit=2)
    assert res.rows == 2
    assert "LIMIT 2" in res.sql
    assert res.original_sql == "SELECT * FROM (SELECT * FROM t LIMIT 5)"


def test_simple_select_works_under_wrap(ws):
    res = execute(ws, "SELECT 1 AS one", limit=5)
    assert res.status == "ok"
    assert res.data == [{"one": 1}]

def test_literal_with_forbidden_word_is_allowed(ws, tmp_path):
    _seed(ws, tmp_path)
    res = execute(ws, "SELECT 'DROP TABLE' AS tag FROM t")
    assert res.status == "ok"


def test_comment_with_forbidden_word_is_allowed(ws, tmp_path):
    _seed(ws, tmp_path)
    res = execute(ws, "SELECT x FROM t -- DELETE later\n")
    assert res.status == "ok"

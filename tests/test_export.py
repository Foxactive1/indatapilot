import json
import pandas as pd
import pytest

from indatapilot.executor import export_query
from indatapilot.importers.files import import_file


@pytest.fixture
def ws_seeded(ws, tmp_path):
    csv = tmp_path / "t.csv"
    pd.DataFrame({"x": [1, 2, 3]}).to_csv(csv, index=False)
    import_file(ws, csv)
    return ws


def test_export_csv(ws_seeded, tmp_path):
    out = tmp_path / "out.csv"
    assert export_query(ws_seeded, "SELECT * FROM t", out) == 3
    assert pd.read_csv(out)["x"].tolist() == [1, 2, 3]


def test_export_jsonl(ws_seeded, tmp_path):
    out = tmp_path / "out.jsonl"
    assert export_query(ws_seeded, "SELECT * FROM t", out) == 3
    lines = out.read_text().strip().split("\n")
    assert len(lines) == 3
    assert [json.loads(l)["x"] for l in lines] == [1, 2, 3]


def test_export_parquet(ws_seeded, tmp_path):
    pytest.importorskip("pyarrow")
    out = tmp_path / "out.parquet"
    assert export_query(ws_seeded, "SELECT * FROM t", out) == 3
    assert sorted(pd.read_parquet(out)["x"].tolist()) == [1, 2, 3]


def test_export_respects_limit(ws_seeded, tmp_path):
    out = tmp_path / "out.csv"
    assert export_query(ws_seeded, "SELECT * FROM t", out, limit=2) == 2


def test_export_rejects_delete(ws_seeded, tmp_path):
    out = tmp_path / "out.csv"
    with pytest.raises(ValueError):
        export_query(ws_seeded, "DELETE FROM t", out)
    assert not out.exists()


def test_export_unsupported_ext(ws_seeded, tmp_path):
    with pytest.raises(ValueError):
        export_query(ws_seeded, "SELECT * FROM t", tmp_path / "out.xyz")


def test_export_is_logged(ws_seeded, tmp_path):
    export_query(ws_seeded, "SELECT * FROM t", tmp_path / "out.csv")
    events = [e for e in ws_seeded.catalog
              if e.get("event") == "query_executed" and e.get("export_to")]
    assert len(events) == 1
    assert events[0]["rows"] == 3 and events[0]["status"] == "ok"

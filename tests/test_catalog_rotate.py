import pandas as pd
import pytest

from indatapilot.importers.files import import_file


def _seed(ws, tmp_path, name="a", n=2):
    csv = tmp_path / f"{name}.csv"
    pd.DataFrame({"v": list(range(n))}).to_csv(csv, index=False)
    import_file(ws, csv, table=name)


def test_rotate_no_op_below_threshold(ws):
    assert ws.catalog.rotate(max_bytes=10_000_000) is None


def test_rotate_archives_and_snapshots(ws, tmp_path):
    _seed(ws, tmp_path, "a")
    _seed(ws, tmp_path, "b")
    archived = ws.catalog.rotate(max_bytes=1)
    assert archived is not None and archived.exists()
    assert ws.catalog.path.exists()
    events = list(ws.catalog)
    assert events[0]["event"] == "state_snapshot"
    tables = ws.catalog.tables()
    assert set(tables.keys()) == {"a", "b"}
    assert tables["a"]["rows"] == 2


def test_tables_survive_multiple_rotations(ws, tmp_path):
    _seed(ws, tmp_path, "a")
    ws.catalog.rotate(max_bytes=1)
    _seed(ws, tmp_path, "b")
    ws.catalog.rotate(max_bytes=1)
    _seed(ws, tmp_path, "c")
    tables = ws.catalog.tables()
    assert set(tables.keys()) == {"a", "b", "c"}


def test_views_survive_rotation(ws, tmp_path):
    _seed(ws, tmp_path, "t")
    ws.catalog.append({
        "event": "view_created",
        "workspace": ws.meta["id"],
        "name": "v1",
        "sql": "SELECT * FROM t",
    })
    ws.catalog.rotate(max_bytes=1)
    assert "v1" in ws.catalog.views()
    assert ws.catalog.views()["v1"]["sql"] == "SELECT * FROM t"


def test_iter_all_spans_archives(ws, tmp_path):
    _seed(ws, tmp_path, "a")
    ws.catalog.rotate(max_bytes=1)
    _seed(ws, tmp_path, "b")
    kinds = [e.get("event") for e in ws.catalog.iter_all()]
    assert "workspace_created" in kinds
    assert "state_snapshot" in kinds
    assert kinds.count("table_registered") >= 2


def test_iter_skips_corrupt_lines(ws, tmp_path):
    _seed(ws, tmp_path, "a")
    with ws.catalog.path.open("a") as f:
        f.write("{not json\n")
    events = list(ws.catalog)
    assert any(e.get("event") == "table_registered" for e in events)


def test_state_snapshot_preserves_table_metadata(ws, tmp_path):
    _seed(ws, tmp_path, "a", n=5)
    ws.catalog.rotate(max_bytes=1)
    info = ws.catalog.tables()["a"]
    assert info["rows"] == 5
    assert info["source"] == "file:.csv"
    assert {c["name"] for c in info["columns"]} == {"v"}

# tests/test_catalog.py
import pandas as pd
from indatapilot.importers.files import import_file


def test_tables_state(ws, tmp_path):
    csv = tmp_path / "a.csv"
    pd.DataFrame({"v": [1, 2]}).to_csv(csv, index=False)
    import_file(ws, csv)
    assert "a" in ws.catalog.tables()
    assert ws.catalog.tables()["a"]["rows"] == 2

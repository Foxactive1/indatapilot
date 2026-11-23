# tests/test_importers.py
import pandas as pd
from indatapilot.importers.files import import_file


def test_import_csv(ws, tmp_path):
    csv = tmp_path / "vendas.csv"
    pd.DataFrame({"regiao": ["Sul", "Norte"], "valor": [100, 200]}).to_csv(csv, index=False)
    info = import_file(ws, csv)
    assert info.table == "vendas"
    assert info.rows == 2
    assert {c["name"] for c in info.columns} == {"regiao", "valor"}


def test_import_parquet(ws, tmp_path):
    import pytest
    pytest.importorskip("pyarrow")
    p = tmp_path / "dados.parquet"
    pd.DataFrame({"a": [1, 2, 3]}).to_parquet(p)
    info = import_file(ws, p)
    assert info.rows == 3


def test_import_unsupported(ws, tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("nada")
    try:
        import_file(ws, f)
        assert False, "deveria falhar"
    except ValueError:
        pass

# tests/test_importers.py — adições

def test_invalid_table_name_is_sanitized(ws, tmp_path):
    csv = tmp_path / "x.csv"
    pd.DataFrame({"a": [1]}).to_csv(csv, index=False)
    info = import_file(ws, csv, table='my table"; DROP TABLE y; --')
    assert info.table == "my_table_drop_table_y"


def test_empty_csv_raises(ws, tmp_path):
    csv = tmp_path / "empty.csv"
    csv.write_text("")
    try:
        import_file(ws, csv)
        assert False, "deveria falhar"
    except ValueError:
        pass

def test_invalid_table_name_is_sanitized(ws, tmp_path):
    csv = tmp_path / "x.csv"
    pd.DataFrame({"a": [1]}).to_csv(csv, index=False)
    info = import_file(ws, csv, table='my table"; DROP TABLE y; --')
    assert info.table == "my_table_drop_table_y"


def test_empty_csv_raises(ws, tmp_path):
    csv = tmp_path / "empty.csv"
    csv.write_text("")
    try:
        import_file(ws, csv)
        assert False, "deveria falhar"
    except ValueError:
        pass

def test_invalid_table_name_is_sanitized(ws, tmp_path):
    csv = tmp_path / "x.csv"; pd.DataFrame({"a": [1]}).to_csv(csv, index=False)
    info = import_file(ws, csv, table='my table"; DROP TABLE y; --')
    assert info.table == "my_table_drop_table_y"

def test_empty_csv_raises(ws, tmp_path):
    csv = tmp_path / "empty.csv"; csv.write_text("")
    try: import_file(ws, csv); assert False
    except ValueError: pass

def test_invalid_table_name_is_sanitized(ws, tmp_path):
    csv = tmp_path / "x.csv"; pd.DataFrame({"a": [1]}).to_csv(csv, index=False)
    info = import_file(ws, csv, table='my table"; DROP TABLE y; --')
    assert info.table == "my_table_drop_table_y"

def test_empty_csv_raises(ws, tmp_path):
    csv = tmp_path / "empty.csv"; csv.write_text("")
    try: import_file(ws, csv); assert False
    except ValueError: pass

def test_invalid_table_name_is_sanitized(ws, tmp_path):
    csv = tmp_path / "x.csv"; pd.DataFrame({"a": [1]}).to_csv(csv, index=False)
    info = import_file(ws, csv, table='my table"; DROP TABLE y; --')
    assert info.table == "my_table_drop_table_y"

def test_empty_csv_raises(ws, tmp_path):
    csv = tmp_path / "empty.csv"; csv.write_text("")
    try: import_file(ws, csv); assert False
    except ValueError: pass

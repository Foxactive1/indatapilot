import pandas as pd
import pytest

from indatapilot.importers.files import import_file


def test_write_lock_context(ws):
    with ws.write_lock():
        pass
    # arquivo de lock foi criado
    assert ws.db_path.with_suffix(".lock").exists()


def test_write_lock_sequential_imports(ws, tmp_path):
    for i in range(3):
        csv = tmp_path / f"t{i}.csv"
        pd.DataFrame({"x": [i]}).to_csv(csv, index=False)
        import_file(ws, csv)
    assert len(ws.catalog.tables()) == 3


def test_write_lock_releases_on_error(ws, tmp_path):
    csv = tmp_path / "bad.csv"
    csv.write_text("")  # sem colunas
    with pytest.raises(ValueError):
        import_file(ws, csv)
    # lock liberado: outro import funciona
    csv2 = tmp_path / "ok.csv"
    pd.DataFrame({"a": [1]}).to_csv(csv2, index=False)
    info = import_file(ws, csv2)
    assert info.rows == 1


def test_import_after_export(ws, tmp_path):
    # regressão: export não segura write_lock, import funciona depois
    from indatapilot.executor import export_query
    csv = tmp_path / "a.csv"
    pd.DataFrame({"x": [1, 2]}).to_csv(csv, index=False)
    import_file(ws, csv)
    export_query(ws, "SELECT * FROM a", tmp_path / "out.csv")
    # importa de novo depois do export
    info = import_file(ws, csv)
    assert info.rows == 2

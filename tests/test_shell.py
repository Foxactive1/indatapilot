from io import StringIO
import pandas as pd
from rich.console import Console

from indatapilot.importers.files import import_file
from indatapilot.shell import run_shell


def _seed(ws, tmp_path):
    csv = tmp_path / "t.csv"
    pd.DataFrame({"x": [1, 2, 3]}).to_csv(csv, index=False)
    import_file(ws, csv)


def _run(ws, inputs):
    buf = StringIO()
    con = Console(file=buf, force_terminal=False, width=120)
    it = iter(inputs)
    def fake_input(prompt=""):
        try:
            return next(it)
        except StopIteration:
            raise EOFError
    con.input = fake_input
    run_shell(ws, con)
    return buf.getvalue()


def test_shell_quit(ws):
    assert "até logo" in _run(ws, [".quit"])


def test_shell_eof(ws):
    assert "até logo" in _run(ws, [])


def test_shell_query(ws, tmp_path):
    _seed(ws, tmp_path)
    out = _run(ws, ["SELECT * FROM t;", ".quit"])
    assert "ok" in out and "3" in out


def test_shell_meta_tables(ws, tmp_path):
    _seed(ws, tmp_path)
    out = _run(ws, [".tables", ".quit"])
    assert "t" in out and "linhas" in out


def test_shell_multiline(ws, tmp_path):
    _seed(ws, tmp_path)
    out = _run(ws, ["SELECT x", "FROM t;", ".quit"])
    assert "ok" in out

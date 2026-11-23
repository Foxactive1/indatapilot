from __future__ import annotations
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from .executor import execute, export_query, DEFAULT_LIMIT, DEFAULT_EXPORT_LIMIT
from .workspace import Workspace

HELP = """\
[bold]Comandos[/]
  [cyan].help[/]                       esta ajuda
  [cyan].tables[/]                     lista tabelas
  [cyan].views[/]                      lista views
  [cyan].schema <tabela>[/]            DDL + colunas
  [cyan].limit <n>[/]                  cap de linhas por SELECT (0 = sem cap)
  [cyan].export <arquivo> <sql>[/]     exporta SQL para .csv/.jsonl/.json/.parquet
  [cyan].catalog[/]                    últimas 10 entradas do catálogo
  [cyan].clear[/]                      limpa a tela
  [cyan].quit[/]                       sai (ou Ctrl+D)

[bold]SQL[/]
  Qualquer SELECT/WITH. Termine com [cyan];[/] ou linha em branco.
  Ctrl+C durante digitação limpa o buffer; durante query, cancela.
"""


def _banner(ws: Workspace) -> Panel:
    meta = ws.meta
    return Panel.fit(
        f"[bold]{escape(str(meta['name']))}[/]  [dim]{ws.root}[/]\n"
        f"tabelas: [cyan]{len(ws.catalog.tables())}[/] | "
        f"views: [cyan]{len(ws.catalog.views())}[/]",
        title="InDataPilot shell", border_style="blue",
    )


def _run_meta(ws, console, cmd, args, state) -> bool:
    if cmd in (".quit", ".exit", ".q"):
        return False
    if cmd == ".help":
        console.print(HELP); return True
    if cmd == ".clear":
        console.clear(); return True
    if cmd == ".tables":
        st = ws.catalog.tables()
        if not st:
            console.print("[dim]nenhuma tabela[/dim]"); return True
        t = Table()
        t.add_column("tabela"); t.add_column("linhas"); t.add_column("origem")
        for tbl, info in st.items():
            t.add_row(tbl, str(info["rows"]), info["source"])
        console.print(t); return True
    if cmd == ".views":
        vs = ws.catalog.views()
        if not vs:
            console.print("[dim]nenhuma view[/dim]"); return True
        t = Table()
        t.add_column("nome"); t.add_column("sql")
        for n, i in vs.items():
            s = i["sql"]
            t.add_row(n, s if len(s) <= 70 else s[:67] + "...")
        console.print(t); return True
    if cmd == ".schema":
        if not args:
            console.print("[red]uso: .schema <tabela>[/red]"); return True
        row = ws.db.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (args[0],),
        ).fetchone()
        if not row:
            console.print(f"[red]tabela '{escape(args[0])}' não encontrada[/red]")
            return True
        console.print(Syntax(row[0], "sql", theme="monokai")); return True
    if cmd == ".limit":
        if not args or not args[0].lstrip("-").isdigit():
            console.print(f"[yellow]limite atual: {state['limit']}[/yellow]")
            return True
        state["limit"] = max(0, int(args[0]))
        console.print(f"[green]limite: {state['limit']}[/green]"); return True
    if cmd == ".catalog":
        for ev in list(ws.catalog)[-10:]:
            console.print(escape(str(ev)))
        return True
    if cmd == ".export":
        if len(args) < 2:
            console.print("[red]uso: .export <arquivo> <sql>[/red]"); return True
        path = Path(args[0])
        sql = " ".join(args[1:]).rstrip(";").strip()
        try:
            n = export_query(ws, sql, path, limit=DEFAULT_EXPORT_LIMIT)
            console.print(f"[green]{n} linhas → {path}[/green]")
        except Exception as e:
            console.print(f"[red]{escape(str(e))}[/red]")
        return True
    console.print(f"[red]comando desconhecido: {escape(cmd)}[/red] (use .help)")
    return True


def _run_sql(ws, console, sql, limit):
    try:
        res = execute(ws, sql, limit=limit if limit > 0 else 10**9)
    except Exception as e:
        console.print(f"[red]erro: {escape(str(e))}[/red]"); return
    color = "green" if res.status == "ok" else "red"
    console.print(
        f"[{color}]{res.status}[/] — {res.rows} linhas em {res.latency_ms}ms"
    )
    if res.error:
        console.print(f"[red]{escape(res.error)}[/red]"); return
    if not res.columns:
        return
    t = Table()
    for c in res.columns:
        t.add_column(c, overflow="fold")
    for row in res.data[:50]:
        t.add_row(*[str(row.get(c, "")) for c in res.columns])
    if res.rows > 50:
        console.print(f"[dim](mostrando 50 de {res.rows})[/dim]")
    console.print(t)


def run_shell(ws: Workspace, console: Console | None = None) -> None:
    console = console or Console()
    state = {"limit": DEFAULT_LIMIT}
    console.print(_banner(ws))
    console.print("[dim]Digite .help para comandos. Ctrl+D para sair.[/dim]\n")

    hist = ws.root / ".shell_history"
    _has_rl = False
    try:
        import readline  # noqa: F401
        _has_rl = True
        try:
            readline.read_history_file(hist)
        except FileNotFoundError:
            pass
        readline.set_history_length(1000)
    except ImportError:
        pass

    buf: list[str] = []
    try:
        while True:
            prompt = "[bold cyan]sql>[/] " if buf else "[bold cyan]ws>[/]  "
            try:
                line = console.input(prompt)
            except EOFError:
                console.print(); break
            except KeyboardInterrupt:
                if buf:
                    buf.clear()
                    console.print("[yellow]buffer limpo[/yellow]")
                else:
                    console.print(); break
                continue

            stripped = line.strip()

            if not buf and stripped.startswith("."):
                parts = stripped.split(maxsplit=1)
                cmd = parts[0].lower()
                args = parts[1].split() if len(parts) > 1 else []
                if not _run_meta(ws, console, cmd, args, state):
                    break
                continue

            if not buf and not stripped:
                continue

            buf.append(line)
            joined = "\n".join(buf)
            if joined.rstrip().endswith(";"):
                sql = joined.strip().rstrip(";").strip()
                buf.clear()
                if sql:
                    _run_sql(ws, console, sql, state["limit"])
    finally:
        if _has_rl:
            try:
                readline.write_history_file(hist)
            except Exception:
                pass
        console.print("[dim]até logo[/dim]")

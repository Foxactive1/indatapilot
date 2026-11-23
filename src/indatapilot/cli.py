from __future__ import annotations
from pathlib import Path
import json
import typer
from rich.console import Console
from rich.markup import escape
from rich.table import Table

from .workspace import Workspace
from .importers.files import import_file
from .executor import (
    execute, export_query, _validate,
    DEFAULT_LIMIT, DEFAULT_EXPORT_LIMIT,
)
from .sqlutil import sanitize_table_name
from .shell import run_shell

app = typer.Typer(help="InDataPilot — workspace universal de dados")
view_app = typer.Typer(help="Gerenciar views")
app.add_typer(view_app, name="view")
console = Console()

WORKSPACES_ROOT = Path("data/workspaces")


def _ws(name: str, require: bool = True) -> Workspace:
    root = WORKSPACES_ROOT / name
    if require and not Workspace.exists(root):
        raise FileNotFoundError(
            f"Workspace '{name}' não existe. Rode `init {name}` primeiro."
        )
    return Workspace.create(root)


def _abort(msg: str) -> None:
    console.print(f"[red]{msg}[/red]")
    raise typer.Exit(1)


@app.command()
def init(name: str):
    try:
        ws = _ws(name, require=False)
    except Exception as e:
        _abort(f"Erro ao criar workspace: {e}")
    console.print(f"[green]Workspace '{name}' criado em {ws.root}[/green]")


@app.command("import")
def import_cmd(name: str, path: Path, table: str = typer.Option(None)):
    try:
        with _ws(name) as ws:
            target = sanitize_table_name(table or path.stem)
            if target in ws.catalog.views():
                _abort(f"'{target}' é uma view; use --table com outro nome")
            info = import_file(ws, path, table)
    except typer.Exit:
        raise
    except Exception as e:
        _abort(f"Erro ao importar: {e}")
    console.print(f"[green]{info.rows} linhas importadas em '{info.table}'[/green]")
    t = Table(title=info.table)
    t.add_column("coluna"); t.add_column("tipo")
    for c in info.columns:
        t.add_row(c["name"], c["type"])
    console.print(t)


@app.command()
def tables(name: str):
    try:
        with _ws(name) as ws:
            state = ws.catalog.tables()
    except Exception as e:
        _abort(f"Erro: {e}")
    t = Table(title=f"Tabelas em '{name}'")
    t.add_column("tabela"); t.add_column("linhas"); t.add_column("origem")
    for tbl, info in state.items():
        t.add_row(tbl, str(info["rows"]), info["source"])
    console.print(t)


@app.command()
def query(name: str, sql: str,
          limit: int = typer.Option(DEFAULT_LIMIT, min=1, max=100_000)):
    try:
        with _ws(name) as ws:
            res = execute(ws, sql, limit=limit)
    except Exception as e:
        _abort(f"Erro: {e}")
    color = "green" if res.status == "ok" else "red"
    console.print(f"[{color}]{res.status}[/] — {res.rows} linhas em {res.latency_ms}ms")
    if res.error:
        _abort(res.error)
    if res.sql != res.original_sql:
        console.print(f"[dim]SQL executado: {res.sql}[/dim]")
    if res.columns:
        t = Table()
        for c in res.columns:
            t.add_column(c)
        for row in res.data[:50]:
            t.add_row(*[str(row.get(c, "")) for c in res.columns])
        if res.rows > 50:
            console.print(f"[dim](mostrando 50 de {res.rows})[/dim]")
        console.print(t)


@app.command()
def shell(name: str):
    """REPL interativo do workspace."""
    try:
        with _ws(name) as ws:
            run_shell(ws, console)
    except Exception as e:
        _abort(f"Erro: {e}")


@app.command()
def catalog(name: str):
    try:
        with _ws(name) as ws:
            events = list(ws.catalog)
    except Exception as e:
        _abort(f"Erro: {e}")
    for ev in events:
        console.print(json.dumps(ev, ensure_ascii=False))


@app.command()
def export(
    name: str,
    sql: str | None = typer.Argument(None, help="SQL (ou use --table)"),
    output: Path = typer.Option(..., "--output", "-o", help="Arquivo de saída"),
    table: str | None = typer.Option(None, "--table", "-t", help="Atalho: exporta tabela"),
    limit: int = typer.Option(DEFAULT_EXPORT_LIMIT, "--limit", "-l",
                              help="Máximo de linhas (0 = sem cap)"),
):
    if table and sql:
        _abort("use --table OU SQL, não ambos")
    if table:
        sql = f'SELECT * FROM "{sanitize_table_name(table)}"'
    if not sql:
        _abort("informe SQL ou --table")
    try:
        with _ws(name) as ws:
            n = export_query(ws, sql, output, limit=limit)
    except Exception as e:
        _abort(f"Erro: {e}")
    console.print(f"[green]{n} linhas exportadas para {output}[/green]")


@view_app.command("create")
def view_create(name: str, view_name: str, sql: str):
    view_name = sanitize_table_name(view_name)
    err = _validate(sql)
    if err:
        _abort(err)
    try:
        with _ws(name) as ws:
            if view_name in ws.catalog.tables():
                _abort(f"'{view_name}' já existe como tabela")
            ws.catalog.append({
                "event": "view_created",
                "workspace": ws.meta["id"],
                "name": view_name,
                "sql": sql.strip().rstrip(";"),
            })
    except typer.Exit:
        raise
    except Exception as e:
        _abort(f"Erro: {e}")
    console.print(f"[green]View '{view_name}' criada[/green]")


@view_app.command("list")
def view_list(name: str):
    try:
        with _ws(name) as ws:
            views = ws.catalog.views()
    except Exception as e:
        _abort(f"Erro: {e}")
    t = Table(title=f"Views em '{name}'")
    t.add_column("nome"); t.add_column("sql")
    for vn, info in views.items():
        s = info["sql"]
        t.add_row(vn, s if len(s) <= 80 else s[:77] + "...")
    console.print(t)


@view_app.command("drop")
def view_drop(name: str, view_name: str):
    try:
        with _ws(name) as ws:
            if view_name not in ws.catalog.views():
                _abort(f"View '{view_name}' não existe")
            ws.catalog.append({
                "event": "view_dropped",
                "workspace": ws.meta["id"],
                "name": view_name,
            })
    except typer.Exit:
        raise
    except Exception as e:
        _abort(f"Erro: {e}")
    console.print(f"[green]View '{view_name}' removida[/green]")


@app.command()
def stats(name: str):
    """Estatísticas agregadas do workspace."""
    from collections import Counter
    from .workspace import Workspace as _W

    try:
        with _ws(name) as ws:
            meta = ws.meta
            events = list(ws.catalog.iter_all())
            tables = ws.catalog.tables()
            views = ws.catalog.views()
            archives = sorted(
                ws.catalog.path.parent.glob(f"{ws.catalog.path.stem}-*.jsonl")
            )
    except Exception as e:
        _abort(f"Erro: {e}")

    qs = [e for e in events if e.get("event") == "query_executed"]
    ok = [e for e in qs if e.get("status") == "ok"]
    rej = [e for e in qs if e.get("status") == "rejected"]
    err = [e for e in qs if e.get("status") == "error"]
    lats = sorted(e.get("latency_ms", 0) for e in ok if "latency_ms" in e)

    def pct(vs, p):
        if not vs:
            return 0
        i = int(len(vs) * p / 100)
        return vs[min(i, len(vs) - 1)]

    total_rows = sum(i.get("rows", 0) for i in tables.values())

    console.print(
        f"[bold]{meta.get('name', name)}[/]  "
        f"[dim]{meta.get('created_at', '?')}[/dim]"
    )
    console.print(
        f"Tabelas: [cyan]{len(tables)}[/] ({total_rows:,} linhas) | "
        f"Views: [cyan]{len(views)}[/]"
    )
    console.print(
        f"Queries: [cyan]{len(qs)}[/] "
        f"({len(ok)} ok, {len(rej)} rejected, {len(err)} error)"
    )
    if lats:
        console.print(
            f"Latência (ok): p50=[cyan]{pct(lats, 50)}ms[/] "
            f"p95=[cyan]{pct(lats, 95)}ms[/] "
            f"p99=[cyan]{pct(lats, 99)}ms[/]"
        )
    if archives:
        total_mb = sum(a.stat().st_size for a in archives) / 1_000_000
        console.print(
            f"Rotacionados: [cyan]{len(archives)}[/] arquivo(s) "
            f"({total_mb:.1f} MB)"
        )

    if tables:
        t = Table(title="Tabelas por tamanho")
        t.add_column("tabela"); t.add_column("linhas", justify="right")
        for tn, info in sorted(
            tables.items(), key=lambda kv: -kv[1].get("rows", 0)
        )[:5]:
            t.add_row(tn, f"{info.get('rows', 0):,}")
        console.print(t)

    if qs:
        top = Counter(
            (e.get("original_sql") or e.get("sql") or "")[:80] for e in qs
        ).most_common(5)
        t = Table(title="Queries mais frequentes")
        t.add_column("n", justify="right"); t.add_column("sql")
        for sql, n in top:
            t.add_row(str(n), escape(sql))
        console.print(t)

    if rej:
        top = Counter(
            (e.get("original_sql") or e.get("sql") or "")[:80] for e in rej
        ).most_common(5)
        t = Table(title="Rejeições")
        t.add_column("n", justify="right"); t.add_column("sql")
        for sql, n in top:
            t.add_row(str(n), escape(sql))
        console.print(t)


@app.command()
def rotate(
    name: str,
    max_mb: int = typer.Option(
        10, "--max-mb", "-m", min=1,
        help="Rotaciona se catalog.jsonl exceder N MB",
    ),
):
    """Arquiva o catálogo atual em catalog-<ts>.jsonl e recomeça com snapshot."""
    try:
        with _ws(name) as ws:
            with ws.write_lock():
                archived = ws.catalog.rotate(max_mb * 1_000_000)
    except Exception as e:
        _abort(f"Erro: {e}")
    if archived:
        console.print(f"[green]Catálogo rotacionado → {archived.name}[/green]")
    else:
        console.print(
            f"[dim]Catálogo abaixo do limite ({max_mb} MB); nada a fazer[/dim]"
        )

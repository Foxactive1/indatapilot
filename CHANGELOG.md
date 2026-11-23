# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
Versionamento: [SemVer](https://semver.org/lang/pt-BR/).

## [0.2.0] — 2026-11-23

### Added
- `indatapilot export` — exporta resultado de SQL ou tabela inteira para
  `.csv`, `.jsonl`, `.json`, `.parquet`. Streaming (não materializa tudo em
  memória); Parquet leva `indatapilot_sql` e `indatapilot_run_id` no header.
  `--limit 0` desliga o cap default de 1M linhas.
- `indatapilot view create|list|drop` — views nomeadas persistidas no
  catálogo, resolvidas via `TEMP VIEW` sincronizada antes de cada query.
  Suporta views aninhadas.
- `indatapilot shell <ws>` — REPL com multi-linha (`;` termina), meta-comandos
  (`.tables`, `.views`, `.schema`, `.limit`, `.export`, `.catalog`, `.clear`,
  `.help`, `.quit`), histórico persistente em `.shell_history`.
- `indatapilot stats <ws>` — contagens de tabelas/views/queries, p50/p95/p99
  de latência, top queries, top rejeições, tamanho do catálogo rotacionado.
- `indatapilot rotate <ws> --max-mb N` — arquiva `catalog.jsonl` em
  `catalog-<ts>.jsonl` e recomeça com `state_snapshot` que preserva tabelas
  e views. Estado derivado sobrevive a múltiplas rotações.
- `Workspace.write_lock()` — `flock` cross-processo em `workspace.sqlite.lock`
  para operações de escrita. `import` em processos paralelos serializa em vez
  de dar `SQLITE_BUSY`.
- `Workspace` como context manager (`with Workspace.create(...) as ws:`);
  `Workspace.exists(root)` para checar sem criar.
- `pyproject.toml`: extras `.[xlsx]`, `.[parquet]`, `.[all]`, `.[kuzu]`.
- `sqlutil.py`: `quote_identifier`, `sanitize_table_name`, `strip_literals`.
- Testes: 45 total (era 4), cobrindo export, views, shell, rotate, write_lock,
  regressões dos bugs abaixo.

### Changed
- `import_file` só exige `openpyxl` (XLSX) ou `pyarrow` (Parquet) no formato
  correspondente; mensagem de erro orienta instalação. CSV/JSON/JSONL
  funcionam sempre.
- `import_file` aceita `--table` sanitizado; colisão com nome de view é
  rejeitada no CLI.
- `QueryResult` carrega `original_sql` e `sql` (executado); ambos vão para o
  catálogo. Export também loga `query_executed` com `export_to`.
- `run.sh` só exporta `LD_PRELOAD` se a `libpython3.14.so` existir.
- `execute` serializa `Connection.interrupt` por workspace via `query_lock`,
  evitando que timeout de uma query mate outra concorrente.
- `catalog.__iter__` ignora linhas JSON corrompidas em vez de falhar.
- CLI: `_ws(require=True)` por padrão (exceto `init`); `--limit` configurável
  em `query` e `export`; aviso explícito `(mostrando 50 de N)`.

### Fixed
- Validação SQL dava falso positivo em strings e comentários:
  `SELECT 'DROP TABLE'` era rejeitado. `strip_literals` remove strings,
  identificadores quotados e comentários antes da varredura de palavras
  proibidas. DML/DDL continua bloqueado.
- `LIMIT` não era enforçado em subqueries (`SELECT * FROM (... LIMIT 5)`
  passava sem cap externo). Wrap incondicional `SELECT * FROM (...) LIMIT N`,
  com `\n` antes do `)` para não colidir com comentário de linha.
- Injeção via `--table` no CLI: nome era interpolado direto em
  `PRAGMA table_info("{table}")`. Agora `sanitize_table_name` + `quote_identifier`
  centralizados.
- `workspace.py` reescrito: o patch anterior embaralhou a ordem da classe e
  derrubou `Workspace.create`. Reescrita íntegra, com `query_lock`,
  `write_lock`, `exists` e context manager.
- `pyproject.toml` listava `kuzu` implicitamente via `run.sh` mas não nas
  deps. Agora é extra opcional `.[kuzu]` documentado.

### Known limitations
- Validação SQL é heurística (regex + strip de literais), não parser. Suficiente
  para o escopo atual; `sqlglot` fica como caminho de migração se o conjunto
  de queries crescer ou aparecer falso positivo legítimo.
- Timeout de query é advisory (`Connection.interrupt`); scans patológicos em C
  podem não abortar imediatamente. Alternativa futura: subprocesso + `SIGKILL`.
- `write_lock` usa `flock`; no Windows sem `fcntl` vira no-op.
- Sem autenticação/multi-tenant além de `data/workspaces/<name>` no filesystem.

## [0.1.0] — baseline

- Workspace SQLite + catálogo JSONL append-only.
- `import` de CSV/Parquet/JSON/JSONL/XLSX via pandas.
- `query` com validação (somente `SELECT`/`WITH`), auto-`LIMIT`, timeout.
- CLI Typer com `init`, `import`, `tables`, `query`, `catalog`.

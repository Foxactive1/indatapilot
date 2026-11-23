
cd ~/indatapilot && cat > README.md <<'README_EOF'
# InDataPilot

**Workspace universal de dados em um único diretório.** Importa planilhas,
consulta com SQL, exporta resultado em CSV/Parquet/JSON, tudo versionado em
um catálogo append-only auditável.

Pensado para rodar em **Termux (Android)** e Linux. Sem servidor, sem
dependência de nuvem, sem banco externo — só um diretório com SQLite e um
`catalog.jsonl`.

```

┌──────────┐      ┌──────────────┐      ┌──────────┐
│  arquivo │ ───► │  workspace   │ ───► │  saída   │
│  .csv    │      │  .sqlite     │      │  .parquet│
│  .xlsx   │      │  catalog.jsonl      │  .csv    │
│  .parquet│      │  meta.json   │      │  .jsonl  │
└──────────┘      └──────────────┘      └──────────┘
▲
│ SQL (SELECT/WITH)

```

---

## Status

**`v0.2.0`** — funcional, 45 testes verdes. Escopo intencionalmente restrito:
analista solo, arquivos locais, SQLite como motor.

O que **existe** hoje:

- Import: CSV, JSON, JSONL, XLSX, Parquet
- Query: apenas `SELECT`/`WITH` (validação), `LIMIT` automático, timeout
- Export: CSV, JSONL, JSON, Parquet (streaming)
- Views nomeadas, persistidas no catálogo
- REPL interativo (`indatapilot shell`)
- Estatísticas (`stats`) e rotação do catálogo (`rotate`)
- Catálogo append-only — toda operação fica registrada

O que **não existe** (por design, ver [Limitações](#limitações)):

- Escrita via SQL (`INSERT`, `UPDATE`, `DELETE` bloqueados)
- Autenticação / multi-tenant além de diretórios
- Servidor HTTP / UI web
- Concorrência de escrita além de `flock` cross-processo

---

## Instalação

### Termux (Android)

O `pandas` precisa vir do `pkg` (compilar via `pip` no Android raramente
funciona). O venv é criado com `--system-site-packages` para herdá-lo.

```bash
pkg install python python-pandas
# opcionais, por formato:
pkg install python-pyarrow       # .parquet
pkg install python-openpyxl      # .xlsx (ou pip install openpyxl)

cd ~/indatapilot
python -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -e ".[dev]"
```

Se o Python do Termux não exportar símbolos que extensões C esperam, use
./run.sh em vez de python — ele ajusta LD_PRELOAD da libpython.

Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,xlsx,parquet]"
```

.[xlsx] e .[parquet] são opcionais — sem eles, os formatos correspondentes
só reclamam quando você tentar importar/exportar. CSV/JSON/JSONL funcionam
sempre.

Verificar

```bash
indatapilot --help
python -m pytest -q          # 45 passed
```

---

Início rápido

```bash
# 1. criar workspace
indatapilot init vendas

# 2. importar
indatapilot import vendas ~/vendas.csv

# 3. consultar
indatapilot query vendas "SELECT regiao, SUM(valor) AS total FROM vendas GROUP BY regiao"

# 4. exportar
indatapilot export vendas "SELECT * FROM vendas WHERE regiao='Sul'" -o sul.parquet

# 5. ver auditoria
indatapilot catalog vendas
```

Cada workspace é um diretório em data/workspaces/<nome>/:

```
data/workspaces/vendas/
├── workspace.sqlite      dados e schema
├── catalog.jsonl         log append-only de tudo
├── catalog-*.jsonl       arquivos rotacionados (quando rotate dispara)
├── meta.json             id, nome, created_at
└── .shell_history        histórico do REPL (se usar `shell`)
```

---

Comandos

init <nome>

Cria um workspace. Idempotente — chamar de novo em workspace existente
não faz nada.

```bash
indatapilot init vendas
```

import <nome> <arquivo> [--table <nome>]

Importa CSV, JSON, JSONL, XLSX ou Parquet para uma tabela. O nome da tabela
é derivado do arquivo (sanitizado) ou passado em --table. Reimportar
substitui (DROP+CREATE+INSERT).

```bash
indatapilot import vendas dados.csv                      # tabela "dados"
indatapilot import vendas dados.csv --table vendas_2024  # nome explícito
```

tables <nome>

Lista tabelas, contagem de linhas e origem.

```bash
indatapilot tables vendas
```

query <nome> <sql> [--limit N]

Executa SELECT/WITH. Limite default: 1000 linhas. --limit ajusta.

Toda query passa por:

· validação (só SELECT/WITH; INSERT, DROP, PRAGMA etc. rejeitados)
· LIMIT externo forçado (mesmo que a SQL tenha LIMIT interno em subquery)
· timeout de 30s
· log no catálogo (status, latência, linhas)

```bash
indatapilot query vendas "SELECT COUNT(*) AS n FROM vendas"
indatapilot query vendas "SELECT * FROM vendas ORDER BY valor DESC" --limit 20
```

export <nome> <sql> -o <arquivo>

Exporta para .csv, .jsonl, .json, .parquet. Streaming — não carrega
tudo em memória. Cap default de 1M linhas (--limit 0 desliga).

Também aceita --table como atalho:

```bash
indatapilot export vendas "SELECT * FROM vendas WHERE valor > 100" -o grandes.csv
indatapilot export vendas --table vendas -o tudo.parquet --limit 0
```

Arquivos Parquet carregam metadados indatapilot_sql e indatapilot_run_id
no header — rastreabilidade sem depender do catálogo.

view create|list|drop

Views nomeadas, persistidas no catálogo, resolvidas via TEMP VIEW
sincronizada antes de cada query. Suportam aninhamento.

```bash
indatapilot view create vendas receita_sul \
  "SELECT regiao, SUM(valor) AS total FROM vendas WHERE regiao='Sul' GROUP BY regiao"
indatapilot view list vendas
indatapilot query vendas "SELECT * FROM receita_sul"
indatapilot view drop vendas receita_sul
```

A validação de SELECT/WITH acontece na criação da view, não no uso.

shell <nome>

REPL interativo. SQL termina em ; (multi-linha funciona). Comandos de
meta começam com ..

```
ws>  SELECT regiao, SUM(valor) AS total
sql> FROM vendas GROUP BY regiao;
ok — 3 linhas em 2ms
┌────────┬───────┐
│ regiao │ total │
...
```

Meta-comandos:

Comando Função
.tables lista tabelas
.views lista views
.schema <tabela> DDL da tabela
.limit <n> cap por SELECT (0 = sem cap)
.export <arq> <sql> exporta direto do REPL
.catalog últimas 10 entradas
.clear limpa tela
.help ajuda
.quit / Ctrl+D sai

Ctrl+C durante digitação limpa o buffer; durante query, cancela. Histórico
persiste em .shell_history no workspace.

stats <nome>

```
vendas  2026-11-20T10:00:00+00:00
Tabelas: 3 (12,450 linhas) | Views: 2
Queries: 142 (135 ok, 5 rejected, 2 error)
Latência (ok): p50=12ms p95=340ms p99=1210ms
Rotacionados: 1 arquivo(s) (2.1 MB)
```

rotate <nome> [--max-mb N]

Arquiva catalog.jsonl em catalog-<ts>.jsonl e recomeça com um evento
state_snapshot que preserva tabelas e views. Roda automaticamente antes
de qualquer import se o catálogo passar de --max-mb (default 10 MB).

```bash
indatapilot rotate vendas --max-mb 10
```

catalog <nome>

Despeja todos os eventos do catálogo (incluindo rotacionados) em JSON.
Útil para auditoria bruta ou exportação para outro sistema.

---

Arquitetura (curta)

· SQLite (workspace.sqlite) — dados materializados. WAL ligado,
  synchronous=NORMAL. Cada import é DROP+CREATE+INSERT em transação.
· Catálogo (catalog.jsonl) — append-only, um evento JSON por linha.
  Toda operação (workspace_created, table_registered, view_created,
  query_executed, state_snapshot) é registrada. flock em cada append.
· Views — guardadas no catálogo, materializadas como TEMP VIEW na
  conexão antes de cada execute/export. DROP remove no próximo sync.
· Concorrência — query_lock (threading) para Connection.interrupt;
  write_lock (flock em workspace.sqlite.lock) para escrita
  cross-processo.

---

Limitações

Conscientes e documentadas — não são bugs:

· Sem escrita via SQL. INSERT/UPDATE/DELETE/DDL bloqueados. Para
  modificar dados: reimportar o arquivo (--table com o mesmo nome substitui).
· Validação heurística. strip_literals + regex, não parser SQL. Falsos
  positivos são possíveis (reporte!). A migração para sqlglot está no roadmap
  se o conjunto de queries crescer.
· Timeout advisory. Connection.interrupt não aborta scans patológicos
  em C imediatamente. Alternativa futura: subprocesso com SIGKILL.
· write_lock no-op em Windows (sem fcntl).
· Sem autenticação. Isolamento entre workspaces é por diretório em
  data/workspaces/.

---

Desenvolvimento

```bash
pip install -e ".[dev,xlsx,parquet]"
pytest -q          # 45 testes
pytest -v          # verboso
pytest tests/test_executor.py -k limit   # filtro
```

Estrutura:

```
src/indatapilot/
├── workspace.py       Workspace (SQLite, locks, meta)
├── catalog.py         Catalog (append-only, rotate, tables/views)
├── executor.py        execute, export_query, validação, LIMIT
├── shell.py           REPL
├── cli.py             Typer commands
├── sqlutil.py         quote_identifier, sanitize_table_name, strip_literals
└── importers/
    ├── base.py        TableInfo
    └── files.py       import_file (CSV/JSON/JSONL/XLSX/Parquet)
```

---

Roadmap

Versão Item
v0.3 import_url (HTTP direto via fsspec)
v0.3 import_sqlite (consolidar outros DBs)
v0.4 serve (FastAPI + HTMX, UI web)
quando doer validação via sqlglot
quando doer query em subprocesso com SIGKILL

---

Licença


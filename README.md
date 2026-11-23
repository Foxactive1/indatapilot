<div align="center">

# 🧭 InDataPilot

**Workspace universal de dados em um único diretório.**

Importe planilhas, consulte com SQL, exporte em CSV/Parquet/JSON — tudo versionado em um catálogo *append-only* auditável.

![versão](https://img.shields.io/badge/vers%C3%A3o-0.2.0-blue)
![testes](https://img.shields.io/badge/testes-45%20passando-brightgreen)
![plataformas](https://img.shields.io/badge/plataformas-Termux%20%7C%20Linux%20%7C%20macOS-lightgrey)
![motor](https://img.shields.io/badge/motor-SQLite-003B57)

</div>

---

## 📖 Sobre

O InDataPilot foi pensado para rodar em **Termux (Android)** e Linux, sem servidor, sem dependência de nuvem e sem banco externo. Um workspace é apenas um diretório com um banco SQLite e um `catalog.jsonl`.

```text
┌───────────┐      ┌──────────────────────┐      ┌────────────┐
│  arquivo  │      │      workspace       │      │   saída    │
│  .csv     │ ───► │  workspace.sqlite    │ ───► │  .parquet  │
│  .xlsx    │      │  catalog.jsonl       │      │  .csv      │
│  .parquet │      │  meta.json           │      │  .jsonl    │
└───────────┘      └──────────────────────┘      └────────────┘
                              ▲
                              │ SQL (SELECT / WITH)
```

## ✨ Funcionalidades

- **Import:** CSV, JSON, JSONL, XLSX e Parquet
- **Query segura:** apenas `SELECT`/`WITH`, `LIMIT` automático e timeout
- **Export em streaming:** CSV, JSONL, JSON e Parquet
- **Views nomeadas** persistidas no catálogo
- **REPL interativo** (`indatapilot shell`)
- **Estatísticas** (`stats`) e **rotação do catálogo** (`rotate`)
- **Auditoria completa:** toda operação fica registrada no catálogo

## 🚦 Status

**`v0.2.0`** — funcional, com 45 testes passando. O escopo é intencionalmente restrito: analista solo, arquivos locais, SQLite como motor.

O que **não existe**, por design (veja [Limitações](#-limitações)):

- Escrita via SQL (`INSERT`, `UPDATE`, `DELETE` são bloqueados)
- Autenticação / multi-tenant além de diretórios
- Servidor HTTP / UI web
- Concorrência de escrita além de `flock` entre processos

---

## 📦 Instalação

### Termux (Android)

O `pandas` precisa vir do `pkg` (compilar via `pip` no Android raramente funciona). O venv é criado com `--system-site-packages` para herdá-lo.

```bash
pkg install python python-pandas

# opcionais, por formato:
pkg install python-pyarrow       # .parquet
pkg install python-openpyxl      # .xlsx (ou: pip install openpyxl)

cd ~/indatapilot
python -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -e ".[dev]"
```

> 💡 Se o Python do Termux não exportar símbolos que extensões C esperam, use `./run.sh` em vez de `python` — ele ajusta o `LD_PRELOAD` da libpython.

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,xlsx,parquet]"
```

Os extras `[xlsx]` e `[parquet]` são opcionais: sem eles, os formatos correspondentes só reclamam quando você tentar importar/exportar. CSV, JSON e JSONL funcionam sempre.

### Verificar a instalação

```bash
indatapilot --help
python -m pytest -q          # 45 passed
```

---

## 🚀 Início rápido

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

Cada workspace é um diretório em `data/workspaces/<nome>/`:

```text
data/workspaces/vendas/
├── workspace.sqlite     # dados e schema
├── catalog.jsonl        # log append-only de tudo
├── catalog-*.jsonl      # arquivos rotacionados (quando rotate dispara)
├── meta.json            # id, nome, created_at
└── .shell_history       # histórico do REPL (se usar `shell`)
```

---

## 🛠️ Comandos

| Comando | Descrição |
|---|---|
| [`init`](#init) | Cria um workspace |
| [`import`](#import) | Importa um arquivo para uma tabela |
| [`tables`](#tables) | Lista tabelas, linhas e origem |
| [`query`](#query) | Executa `SELECT`/`WITH` |
| [`export`](#export) | Exporta o resultado de uma query |
| [`view`](#view) | Gerencia views nomeadas |
| [`shell`](#shell) | REPL interativo |
| [`stats`](#stats) | Estatísticas do workspace |
| [`rotate`](#rotate) | Rotaciona o catálogo |
| [`catalog`](#catalog) | Despeja todos os eventos em JSON |

### `init`

```bash
indatapilot init <nome>
```

Cria um workspace. É idempotente: chamar de novo em um workspace existente não faz nada.

### `import`

```bash
indatapilot import <nome> <arquivo> [--table <nome>]
```

Importa CSV, JSON, JSONL, XLSX ou Parquet para uma tabela. O nome da tabela é derivado do arquivo (sanitizado) ou passado em `--table`. **Reimportar substitui** a tabela (`DROP` + `CREATE` + `INSERT`).

```bash
indatapilot import vendas dados.csv                       # tabela "dados"
indatapilot import vendas dados.csv --table vendas_2024   # nome explícito
```

### `tables`

```bash
indatapilot tables <nome>
```

Lista tabelas, contagem de linhas e origem.

### `query`

```bash
indatapilot query <nome> <sql> [--limit N]
```

Executa `SELECT`/`WITH`. Limite padrão: **1000 linhas** (ajuste com `--limit`).

Toda query passa por:

- validação (só `SELECT`/`WITH`; `INSERT`, `DROP`, `PRAGMA` etc. são rejeitados)
- `LIMIT` externo forçado (mesmo que a SQL tenha `LIMIT` interno em subquery)
- timeout de 30 s
- registro no catálogo (status, latência, linhas)

```bash
indatapilot query vendas "SELECT COUNT(*) AS n FROM vendas"
indatapilot query vendas "SELECT * FROM vendas ORDER BY valor DESC" --limit 20
```

### `export`

```bash
indatapilot export <nome> <sql> -o <arquivo>
```

Exporta para `.csv`, `.jsonl`, `.json` ou `.parquet`, em streaming (sem carregar tudo em memória). Cap padrão de 1M linhas (`--limit 0` desliga). Também aceita `--table` como atalho:

```bash
indatapilot export vendas "SELECT * FROM vendas WHERE valor > 100" -o grandes.csv
indatapilot export vendas --table vendas -o tudo.parquet --limit 0
```

> Arquivos Parquet carregam os metadados `indatapilot_sql` e `indatapilot_run_id` no header — rastreabilidade sem depender do catálogo.

### `view`

```bash
indatapilot view create|list|drop <nome> [...]
```

Views nomeadas, persistidas no catálogo e resolvidas via `TEMP VIEW`, sincronizada antes de cada query. Suportam aninhamento.

```bash
indatapilot view create vendas receita_sul \
  "SELECT regiao, SUM(valor) AS total FROM vendas WHERE regiao='Sul' GROUP BY regiao"
indatapilot view list vendas
indatapilot query vendas "SELECT * FROM receita_sul"
indatapilot view drop vendas receita_sul
```

A validação de `SELECT`/`WITH` acontece na **criação** da view, não no uso.

### `shell`

```bash
indatapilot shell <nome>
```

REPL interativo. A SQL termina em `;` (multilinha funciona). Meta-comandos começam com `.`.

```text
ws>  SELECT regiao, SUM(valor) AS total
sql> FROM vendas GROUP BY regiao;
ok — 3 linhas em 2ms
┌────────┬───────┐
│ regiao │ total │
...
```

| Meta-comando | Função |
|---|---|
| `.tables` | lista tabelas |
| `.views` | lista views |
| `.schema <tabela>` | DDL da tabela |
| `.limit <n>` | cap por `SELECT` (`0` = sem cap) |
| `.export <arq> <sql>` | exporta direto do REPL |
| `.catalog` | últimas 10 entradas |
| `.clear` | limpa a tela |
| `.help` | ajuda |
| `.quit` / `Ctrl+D` | sai |

`Ctrl+C` durante a digitação limpa o buffer; durante uma query, cancela. O histórico persiste em `.shell_history` no workspace.

### `stats`

```bash
indatapilot stats <nome>
```

```text
vendas  2026-11-20T10:00:00+00:00
Tabelas: 3 (12,450 linhas) | Views: 2
Queries: 142 (135 ok, 5 rejected, 2 error)
Latência (ok): p50=12ms p95=340ms p99=1210ms
Rotacionados: 1 arquivo(s) (2.1 MB)
```

### `rotate`

```bash
indatapilot rotate <nome> [--max-mb N]
```

Arquiva `catalog.jsonl` em `catalog-<ts>.jsonl` e recomeça com um evento `state_snapshot` que preserva tabelas e views. Roda automaticamente antes de qualquer `import` se o catálogo passar de `--max-mb` (padrão: 10 MB).

### `catalog`

```bash
indatapilot catalog <nome>
```

Despeja todos os eventos do catálogo (incluindo os rotacionados) em JSON. Útil para auditoria bruta ou exportação para outro sistema.

---

## 🏗️ Arquitetura

- **SQLite** (`workspace.sqlite`) — dados materializados, com WAL ligado e `synchronous=NORMAL`. Cada import é `DROP` + `CREATE` + `INSERT` em transação.
- **Catálogo** (`catalog.jsonl`) — *append-only*, um evento JSON por linha. Toda operação (`workspace_created`, `table_registered`, `view_created`, `query_executed`, `state_snapshot`) é registrada, com `flock` em cada append.
- **Views** — guardadas no catálogo e materializadas como `TEMP VIEW` na conexão antes de cada execute/export. O `DROP` é aplicado no próximo sync.
- **Concorrência** — `query_lock` (threading) para `Connection.interrupt`; `write_lock` (`flock` em `workspace.sqlite.lock`) para escrita entre processos.

## ⚠️ Limitações

Conscientes e documentadas — não são bugs:

- **Sem escrita via SQL.** `INSERT`/`UPDATE`/`DELETE`/DDL são bloqueados. Para modificar dados, reimporte o arquivo (`--table` com o mesmo nome substitui).
- **Validação heurística.** Usa `strip_literals` + regex, não um parser SQL. Falsos positivos são possíveis — por favor, reporte! A migração para `sqlglot` está no roadmap.
- **Timeout advisory.** `Connection.interrupt` não aborta imediatamente scans patológicos em C. Alternativa futura: subprocesso com `SIGKILL`.
- **`write_lock` é no-op no Windows** (sem `fcntl`).
- **Sem autenticação.** O isolamento entre workspaces é por diretório em `data/workspaces/`.

---

## 🧪 Desenvolvimento

```bash
pip install -e ".[dev,xlsx,parquet]"
pytest -q                                  # 45 testes
pytest -v                                  # verboso
pytest tests/test_executor.py -k limit     # filtro
```

Estrutura do projeto:

```text
src/indatapilot/
├── workspace.py       # Workspace (SQLite, locks, meta)
├── catalog.py         # Catalog (append-only, rotate, tables/views)
├── executor.py        # execute, export_query, validação, LIMIT
├── shell.py           # REPL
├── cli.py             # comandos Typer
├── sqlutil.py         # quote_identifier, sanitize_table_name, strip_literals
└── importers/
    ├── base.py        # TableInfo
    └── files.py       # import_file (CSV/JSON/JSONL/XLSX/Parquet)
```

## 🗺️ Roadmap

| Versão | Item |
|---|---|
| v0.3 | `import_url` (HTTP direto via fsspec) |
| v0.3 | `import_sqlite` (consolidar outros bancos) |
| v0.4 | `serve` (FastAPI + HTMX, UI web) |
| quando doer | validação via `sqlglot` |
| quando doer | query em subprocesso com `SIGKILL` |

## 🤝 Contribuindo

Issues e pull requests são bem-vindos. Encontrou um falso positivo na validação de SQL? Abra uma issue com a query que foi rejeitada.

## 📄 Licença

_Defina aqui a licença do projeto (ex.: MIT) e adicione o arquivo `LICENSE` na raiz do repositório._

---

<div align="center">

Feito por **[Dione Castro Alves](https://github.com/Foxactive1)** · [InNovaIdeia](mailto:innovaideia2023@gmail.com)

</div>

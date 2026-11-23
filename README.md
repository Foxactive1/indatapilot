# InDataPilot

Workspace universal de dados em SQLite + catálogo JSONL append-only.

## Instalação (Termux)
pkg install python-pandas python-pyarrow
python -m venv .venv --system-site-packages
source .venv/bin/activate
pip install -e ".[dev]"

## Uso rápido
indatapilot init w1
indatapilot import w1 dados.csv
indatapilot query w1 "SELECT * FROM dados LIMIT 5"
indatapilot export w1 "SELECT * FROM dados" -o saida.parquet
indatapilot shell w1

## Comandos
init, import, tables, query, export, view, shell, stats, rotate, catalog

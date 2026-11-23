#!/data/data/com.termux/files/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"; source .venv/bin/activate
PYTHON_PREFIX="$(python -c 'import sys; print(sys.prefix)')"
LIBPYTHON="$PYTHON_PREFIX/lib/libpython3.14.so"
[ -f "$LIBPYTHON" ] || LIBPYTHON="${PREFIX:-}/lib/libpython3.14.so"
if [ -f "$LIBPYTHON" ]; then
    export LD_PRELOAD="$LIBPYTHON${LD_PRELOAD:+:$LD_PRELOAD}"
else
    echo "run.sh: libpython3.14.so ausente; sem LD_PRELOAD" >&2
fi
exec python "$@"

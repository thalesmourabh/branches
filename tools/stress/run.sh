#!/usr/bin/env bash
# Roda os stress tests nos tres builds e arquiva o resultado.
#
# Os tres builds sao o MESMO commit (534605904df); a unica variavel entre eles
# e GIL / free-threaded / free-threaded+TSan. Rodar nos tres e o que separa
# "bug de free-threading" de "ja estava assim".
#
#   ~/src/cpython        com GIL, pydebug          -> controle
#   ~/src/cpython-ft     free-threaded, pydebug    -> onde o bug aparece
#   ~/src/cpython-tsan   free-threaded, pydebug, TSan -> onde ele e explicado
#
# Uso: bash run.sh [nome-do-teste ...]      (default: todos)
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"
RUNS="$HERE/runs"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$RUNS/$STAMP"
mkdir -p "$OUT"

SYMBOLIZER=/usr/lib/llvm-21/bin/llvm-symbolizer

TESTS=("$@")
if [ ${#TESTS[@]} -eq 0 ]; then
  TESTS=(test_zoneinfo.py test_decimal.py test_hashlib.py)
fi

run_one() {
  local build="$1" label="$2" test="$3"
  local py="$build/python"
  [ -x "$py" ] || { echo "SEM BUILD: $py"; return; }

  local log="$OUT/$label.$(basename "$test" .py).log"

  if [ "$label" = "tsan" ]; then
    # Mesmas opcoes do CI deles (.github/workflows/reusable-san.yml), mais o
    # caminho do symbolizer, que no Ubuntu nao fica no PATH.
    TSAN_OPTIONS="suppressions=$build/Tools/tsan/suppressions_free_threading.txt handle_segv=0 external_symbolizer_path=$SYMBOLIZER" \
      "$py" "$HERE/$test" -v > "$log" 2>&1
  else
    "$py" "$HERE/$test" -v > "$log" 2>&1
  fi

  local rc=$?
  local races
  races=$(grep -c 'WARNING: ThreadSanitizer' "$log" 2>/dev/null || echo 0)
  printf '%-6s %-20s exit=%-3s tsan_warnings=%s\n' "$label" "$test" "$rc" "$races"
}

echo "=== $STAMP ==="
for t in "${TESTS[@]}"; do
  run_one ~/src/cpython      gil  "$t"
  run_one ~/src/cpython-ft   ft   "$t"
  run_one ~/src/cpython-tsan tsan "$t"
  echo
done

echo "logs em $OUT"

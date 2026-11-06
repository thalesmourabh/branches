#!/usr/bin/env bash
# S3.3 — TERCEIRO baseline: a suite inteira sob ThreadSanitizer.
#
# Por que um terceiro. O baseline da S0 foi capturado no build com GIL, e la os
# 62 testes test_free_threading.* ficam todos SKIPADOS -- ele nao valida nada
# de free-threading. O TSan, por sua vez, muda o que falha e o que estoura
# timeout. Sao tres baselines distintos e nenhum substitui o outro:
#
#   1. GIL             -> baselines/cpython-main-pydebug-testsuite.md   (S0, feito)
#   2. free-threaded   -> este script, alvo "ft"
#   3. free-threaded + TSan -> este script, alvo "tsan"
#
# Sem isto nao ha como distinguir "eu quebrei" de "ja estava quebrado".
#
# Uso: bash baseline-tsan.sh ft|tsan
set -u

TARGET="${1:-tsan}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../../baselines"
mkdir -p "$OUT"

case "$TARGET" in
  ft)   BUILD=~/src/cpython-ft ;;
  tsan) BUILD=~/src/cpython-tsan ;;
  *)    echo "uso: $0 ft|tsan"; exit 2 ;;
esac

cd "$BUILD" || exit 1
LOG="$OUT/cpython-main-$TARGET-testsuite.raw.log"

echo "build:  $BUILD"
echo "commit: $(git rev-parse HEAD)"
echo "log:    $LOG"

if [ "$TARGET" = "tsan" ]; then
  # Iguais ao CI deles, mais o symbolizer.
  export TSAN_OPTIONS="suppressions=$BUILD/Tools/tsan/suppressions_free_threading.txt handle_segv=0 external_symbolizer_path=/usr/lib/llvm-21/bin/llvm-symbolizer"
  # --tsan seleciona o subconjunto que eles consideram utilizavel sob TSan.
  ARGS="--tsan -j4 -W --timeout=600 --slowest"
else
  ARGS="-j10 -W --timeout=600 --slowest"
fi

START=$(date -u +%s)
# shellcheck disable=SC2086
./python -m test $ARGS > "$LOG" 2>&1
RC=$?
END=$(date -u +%s)

echo "exit=$RC  duracao=$(( (END - START) / 60 ))min"
echo
echo "=== resumo ==="
grep -E '^(Total tests|Total test files|Result|== Tests)' "$LOG" | tail -10
echo
echo "=== avisos do TSan ==="
grep -c 'WARNING: ThreadSanitizer' "$LOG"
echo
echo "=== quais testes geraram aviso do TSan ==="
grep -B40 'WARNING: ThreadSanitizer' "$LOG" | grep -oE '^0:[0-9:]+ load avg: [0-9.]+ \[[ 0-9/]+\] [a-z_.]+' | awk '{print $NF}' | sort -u | head -40

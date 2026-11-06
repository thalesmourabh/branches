#!/usr/bin/env bash
# S3.5 — loop continuo para transformar crash de uma-ocorrencia em repro.
#
# Os dois crashes do baseline (mimalloc em test_generators, refcount em
# test_str) apareceram UMA vez cada, na suite completa sob carga, e nao
# reproduziram isolados: 0/5. Sem taxa de reproducao eles nao viram issue --
# relatar crash que nao se sabe provocar e pedir a label
# AI-needs-explanation.
#
# Este loop usa os proprios knobs do regrtest em vez de um laco meu:
#   -F / --forever        roda em loop ate dar erro (ja implica --failfast)
#   --parallel-threads=N  roda N copias de cada teste ao mesmo tempo
#   -j N                  processos em paralelo, para reproduzir a carga
#
# Uso: bash hunt-loop.sh <gil|ft|tsan> <teste> [minutos] [parallel-threads]
set -u

LABEL="${1:?uso: hunt-loop.sh <gil|ft|tsan> <teste> [minutos] [threads]}"
TEST="${2:?falta o teste, ex: test_free_threading.test_generators}"
MINUTES="${3:-20}"
PTHREADS="${4:-4}"

case "$LABEL" in
  gil)  BUILD=~/src/cpython ;;
  ft)   BUILD=~/src/cpython-ft ;;
  tsan) BUILD=~/src/cpython-tsan ;;
  *)    echo "label invalido: $LABEL"; exit 2 ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/runs/hunt-$(date -u +%Y%m%dT%H%M%SZ)-$LABEL-${TEST##*.}"
mkdir -p "$OUT"
LOG="$OUT/run.log"

cd "$BUILD" || exit 1

if [ "$LABEL" = "tsan" ]; then
  export TSAN_OPTIONS="suppressions=$BUILD/Tools/tsan/suppressions_free_threading.txt handle_segv=0 external_symbolizer_path=/usr/lib/llvm-21/bin/llvm-symbolizer"
fi

{
  echo "build:   $BUILD"
  echo "commit:  $(git rev-parse HEAD)"
  echo "teste:   $TEST"
  echo "limite:  ${MINUTES}min"
  echo "threads: $PTHREADS   j: 10"
  echo "inicio:  $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
} | tee "$LOG"

START=$(date -u +%s)
timeout "${MINUTES}m" ./python -m test "$TEST" \
    -F --parallel-threads="$PTHREADS" -j10 -W >> "$LOG" 2>&1
RC=$?
END=$(date -u +%s)
ELAPSED=$(( END - START ))

{
  echo
  echo "fim:     $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "exit:    $RC"
  echo "duracao: ${ELAPSED}s"
} | tee -a "$LOG" > /dev/null

# 124 = o timeout estourou, ou seja rodou o tempo todo sem erro.
if [ "$RC" -eq 124 ]; then
  echo "LIMPO  $LABEL $TEST  -- ${ELAPSED}s sem erro"
  echo "veredito: LIMPO, timeout atingido sem erro" >> "$LOG"
else
  ITER=$(grep -cE '^0:[0-9]{2}:[0-9]{2} load avg' "$LOG" 2>/dev/null || echo "?")
  echo "CRASH  $LABEL $TEST  -- apos ${ELAPSED}s, ~${ITER} execucoes"
  echo "veredito: ERRO em ${ELAPSED}s, ~${ITER} execucoes" >> "$LOG"
  echo "--- trecho relevante ---"
  grep -E -A12 'assertion|Assertion|Fatal Python error|WARNING: ThreadSanitizer' "$LOG" | head -30
fi

echo "log: $LOG"

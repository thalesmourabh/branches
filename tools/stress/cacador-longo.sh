#!/usr/bin/env bash
# Cacador de longa duracao para corrida rara.
#
# POR QUE ESTE SCRIPT EXISTE, e nao mais um loop de 4 minutos:
#
# A assertion do mimalloc (arena-abandon.c:162) foi observada DUAS vezes em
# ~1h de execucao pesada, e depois 0 vezes em 12 tentativas deliberadas de
# 4 min cada (48 min no total). Ou seja: trial curto e SUBDIMENSIONADO para
# uma corrida nesta frequencia. Com ~1 ocorrencia por ~30 min de carga, um
# trial de 4 min tem chance baixa de pegar, e uma sequencia de trials limpos
# nao e evidencia de ausencia.
#
# Este script acumula tempo e conta ocorrencias num arquivo de tally que
# sobrevive entre execucoes, para que a taxa saia de horas e nao de minutos.
# E so com taxa que a coisa vira issue, e so com taxa o bisect tem oraculo.
#
# Uso: bash cacador-longo.sh <gil|ft|tsan> <teste> [horas] [threads]
set -u

LABEL="${1:?uso: cacador-longo.sh <gil|ft|tsan> <teste> [horas] [threads]}"
TEST="${2:?falta o teste}"
HORAS="${3:-1}"
PTHREADS="${4:-4}"

case "$LABEL" in
  gil)  BUILD=$HOME/src/cpython ;;
  ft)   BUILD=$HOME/src/cpython-ft ;;
  tsan) BUILD=$HOME/src/cpython-tsan ;;
  *)    echo "label invalido"; exit 2 ;;
esac

HERE="$(cd "$(dirname "$0")" && pwd)"
RUNS="$HERE/runs/cacador"
mkdir -p "$RUNS"
TALLY="$RUNS/tally-$LABEL-${TEST##*.}.tsv"
[ -f "$TALLY" ] || printf 'inicio_utc\tduracao_s\tveredito\tdetalhe\n' > "$TALLY"

cd "$BUILD" || exit 1
if [ "$LABEL" = "tsan" ]; then
  export TSAN_OPTIONS="suppressions=$BUILD/Tools/tsan/suppressions_free_threading.txt handle_segv=0 external_symbolizer_path=/usr/lib/llvm-21/bin/llvm-symbolizer"
fi

FIM=$(( $(date +%s) + $(printf '%.0f' "$(echo "$HORAS * 3600" | bc -l)") ))
RODADA=0
ACHOU=0

echo "cacador: $LABEL / $TEST / ${HORAS}h / threads=$PTHREADS"
echo "tally:   $TALLY"

while [ "$(date +%s)" -lt "$FIM" ]; do
  RODADA=$((RODADA + 1))
  T0=$(date -u +%s)
  INICIO=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # -F roda em loop ate dar erro. Fatias de 10 min: longas o bastante para a
  # corrida acontecer, curtas o bastante para nao perder tudo se travar.
  OUT=$(timeout 600s ./python -m test "$TEST" -F --parallel-threads="$PTHREADS" -j10 -W 2>&1)
  T1=$(date -u +%s)
  DUR=$((T1 - T0))

  if printf '%s' "$OUT" | grep -q 'mimalloc: assertion failed'; then
    ACHOU=$((ACHOU + 1))
    DET=$(printf '%s' "$OUT" | grep -oE 'at "[^"]+":[0-9]+, [a-z_]+' | head -1)
    printf '%s\t%s\tMIMALLOC\t%s\n' "$INICIO" "$DUR" "$DET" >> "$TALLY"
    printf '%s' "$OUT" > "$RUNS/hit-$INICIO-$LABEL-mimalloc.log"
    echo "  rodada $RODADA: MIMALLOC apos ${DUR}s -> $DET"
  elif printf '%s' "$OUT" | grep -qE 'Assertion .* failed|Fatal Python error'; then
    ACHOU=$((ACHOU + 1))
    DET=$(printf '%s' "$OUT" | grep -oE 'Assertion `[^'"'"']+'"'"' failed' | head -1)
    printf '%s\t%s\tOUTRO\t%s\n' "$INICIO" "$DUR" "$DET" >> "$TALLY"
    printf '%s' "$OUT" > "$RUNS/hit-$INICIO-$LABEL-outro.log"
    echo "  rodada $RODADA: OUTRO CRASH apos ${DUR}s -> $DET"
  else
    printf '%s\t%s\tlimpo\t-\n' "$INICIO" "$DUR" >> "$TALLY"
    echo "  rodada $RODADA: limpo (${DUR}s)"
  fi
done

TOTAL=$(awk -F'\t' 'NR>1 {s+=$2} END {print s+0}' "$TALLY")
HITS=$(awk -F'\t' 'NR>1 && $3!="limpo" {n++} END {print n+0}' "$TALLY")
echo
echo "=== acumulado em $TALLY ==="
echo "tempo total: $((TOTAL / 60)) min"
echo "ocorrencias: $HITS"
if [ "$HITS" -gt 0 ]; then
  echo "taxa:        1 a cada $((TOTAL / HITS / 60)) min de carga"
fi

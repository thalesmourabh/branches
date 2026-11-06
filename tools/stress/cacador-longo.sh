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
# O alvo pode ser o nome de um teste ou a palavra SUITE.
#
# SUITE existe porque as duas observacoes vieram dai, nao de repeticao de um
# teste so: a primeira aconteceu DURANTE a suite completa, e a segunda foi a
# primeira execucao de teste unico logo DEPOIS da suite completa terminar.
# Repeticao de teste unico desde entao: 0 em ~26 min. A hipotese e que o
# gatilho precisa da variedade da suite -- muitos padroes de alocacao e muitas
# threads em arquivos diferentes -- e nao de repetir um caso. Nao esta provado;
# com n=2 nao da para afirmar. Mas a suite custa 7 min no build FT, entao
# testar a hipotese e barato.
#
# Uso: bash cacador-longo.sh <gil|ft|tsan> <teste|SUITE> [horas] [threads]
set -u

LABEL="${1:?uso: cacador-longo.sh <gil|ft|tsan> <teste|SUITE> [horas] [threads]}"
TEST="${2:?falta o alvo: nome do teste ou SUITE}"
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
[ -f "$TALLY" ] || printf 'inicio_utc\tduracao_s\tveredito\tfatia_completa\tdetalhe\n' > "$TALLY"

# Duracao da fatia. SUITE usa fatia maior porque uma passada leva 7 min no FT
# e 17 no TSan; fatia curta cortaria passada no meio.
if [ "$TEST" = "SUITE" ]; then FATIA=1800; else FATIA=600; fi

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
  #
  # Em SUITE nao vai --parallel-threads: a observacao 1 nao tinha, e com a
  # suite inteira isso multiplicaria o tempo de cada passada sem necessidade.
  # Fatia maior (20 min) porque uma passada da suite leva 7 min no FT e 17 no
  # TSan -- fatia de 10 min cortaria a passada no meio.
  if [ "$TEST" = "SUITE" ]; then
    # -x test_perf_profiler e OBRIGATORIO aqui, e a primeira versao deste
    # script errou por nao ter: -F implica --failfast, e test_perf_profiler
    # falha por limitacao do ambiente (o perf do kernel do WSL nao aceita a
    # flag -j que o CPython passa para `perf inject`). Resultado: toda passada
    # parava nele em ~250s, bem antes de a suite terminar os 7 min. Foram 9
    # passadas truncadas no mesmo ponto, zero passadas completas, e o script
    # reportou "0 ocorrencias em 37 min" como se tivesse testado algo.
    #
    # test_free_threading.test_generators NAO entra na exclusao: o crash dele
    # e justamente o que se procura, e parar nele e o comportamento correto.
    OUT=$(timeout "${FATIA}s" ./python -m test -F -j10 -W --timeout=600 -x test_perf_profiler 2>&1)
  else
    OUT=$(timeout "${FATIA}s" ./python -m test "$TEST" -F --parallel-threads="$PTHREADS" -j10 -W 2>&1)
  fi
  T1=$(date -u +%s)
  DUR=$((T1 - T0))

  # Sempre guarda o rabo da saida. Sem isto nao ha como saber POR QUE uma
  # passada acabou, e passada truncada contada como tempo de caca foi
  # exatamente o erro que invalidou os primeiros 37 min (ver hunts/005).
  printf '%s' "$OUT" | tail -40 > "$RUNS/ultima-$LABEL-$RODADA.log"

  # Uma fatia so conta como caca de verdade se rodou o tempo todo. Se saiu
  # antes, --failfast parou em alguma falha, e o tempo nao foi gasto cacando.
  if [ "$DUR" -ge "$((FATIA - 5))" ]; then
    COMPLETA=sim
  else
    COMPLETA=NAO
  fi
  QUEBROU=$(printf '%s' "$OUT" | grep -oE '^[0-9]+ tests? failed:' -A2 | tail -1 | tr -s ' ' | cut -c1-60)
  [ -n "$QUEBROU" ] || QUEBROU='-'

  if printf '%s' "$OUT" | grep -q 'mimalloc: assertion failed'; then
    ACHOU=$((ACHOU + 1))
    DET=$(printf '%s' "$OUT" | grep -oE 'at "[^"]+":[0-9]+, [a-z_]+' | head -1)
    printf '%s\t%s\tMIMALLOC\t%s\t%s\n' "$INICIO" "$DUR" "$COMPLETA" "$DET" >> "$TALLY"
    printf '%s' "$OUT" > "$RUNS/hit-$INICIO-$LABEL-mimalloc.log"
    echo "  rodada $RODADA: MIMALLOC apos ${DUR}s -> $DET"
  elif printf '%s' "$OUT" | grep -qE 'Assertion .* failed|Fatal Python error'; then
    ACHOU=$((ACHOU + 1))
    DET=$(printf '%s' "$OUT" | grep -oE 'Assertion `[^'"'"']+'"'"' failed' | head -1)
    printf '%s\t%s\tOUTRO\t%s\t%s\n' "$INICIO" "$DUR" "$COMPLETA" "$DET" >> "$TALLY"
    printf '%s' "$OUT" > "$RUNS/hit-$INICIO-$LABEL-outro.log"
    echo "  rodada $RODADA: OUTRO CRASH apos ${DUR}s -> $DET"
  elif [ "$COMPLETA" = "NAO" ]; then
    # Nao e caca limpa: e fatia truncada. Nao soma como tempo de caca.
    printf '%s\t%s\tTRUNCADA\tNAO\t%s\n' "$INICIO" "$DUR" "$QUEBROU" >> "$TALLY"
    echo "  rodada $RODADA: TRUNCADA em ${DUR}s (parou em: $QUEBROU) -- nao conta"
  else
    printf '%s\t%s\tlimpo\tsim\t-\n' "$INICIO" "$DUR" >> "$TALLY"
    echo "  rodada $RODADA: limpo (${DUR}s)"
  fi
done

# Tempo de caca conta SO fatia completa e fatia que terminou em achado. Fatia
# truncada por falha alheia nao e tempo cacando.
TOTAL=$(awk -F'\t' 'NR>1 && $3!="TRUNCADA" {s+=$2} END {print s+0}' "$TALLY")
TRUNC=$(awk -F'\t' 'NR>1 && $3=="TRUNCADA" {s+=$2} END {print s+0}' "$TALLY")
HITS=$(awk -F'\t' 'NR>1 && ($3=="MIMALLOC" || $3=="OUTRO") {n++} END {print n+0}' "$TALLY")
echo
echo "=== acumulado em $TALLY ==="
echo "tempo cacando:  $((TOTAL / 60)) min"
echo "tempo perdido:  $((TRUNC / 60)) min em fatia truncada (nao conta)"
echo "ocorrencias:    $HITS"
if [ "$HITS" -gt 0 ]; then
  echo "taxa:           1 a cada $((TOTAL / HITS / 60)) min"
else
  echo "taxa:           desconhecida -- 0 em $((TOTAL / 60)) min nao e ausencia,"
  echo "                e so limite inferior do que esta medicao alcanca"
fi

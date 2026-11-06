#!/usr/bin/env bash
# Bisect de um commit: o bump do mimalloc 2.1.2 -> 2.5.2 introduziu a assertion
# de arena-abandon.c:162?
#
# Constroi os DOIS commits adjacentes. Entre eles a unica diferenca e o bump,
# entao nao ha confusao com outras mudancas:
#
#   aff7a2e23bd^  mimalloc 2.1.2   (esperado: limpo)
#   aff7a2e23bd   mimalloc 2.5.2   (esperado: assertion)
#
# Por que nao `git revert` do bump sobre o main atual: tentei, da conflito --
# pycore_mimalloc.h foi mexido depois do bump. E arvore sintetica que ninguem
# distribui vale menos como prova que dois commits reais adjacentes.
#
# O oraculo (como provocar o crash) e parametro, porque depende de qual se
# mostrou confiavel na medicao:
#   suite  -> ./python -m test <teste> -F --parallel-threads=N -j10
#   script -> ./python <repro.py>
#
# Uso: bash bisect-mimalloc.sh <suite|script> <alvo> [segundos] [threads]
set -u

MODO="${1:?uso: bisect-mimalloc.sh <suite|script> <alvo> [segundos] [threads]}"
ALVO="${2:?alvo: nome do teste, ou caminho do script}"
LIMITE="${3:-240}"
PTHREADS="${4:-4}"

BUMP=aff7a2e23bd6ed68fa15c1ceda94a2fdd7f8cf7f
MI='mimalloc: assertion failed'

constroi_e_testa() {
  local ref="$1" rotulo="$2"
  local dst="$HOME/src/cpython-bisect-$rotulo"

  echo "=============== $rotulo  ($ref) ==============="
  cd "$HOME/src/cpython" || return 1
  if [ ! -d "$dst" ]; then
    git worktree add --detach "$dst" "$ref" > /dev/null 2>&1 || { echo "worktree falhou"; return 1; }
  fi

  cd "$dst" || return 1
  echo "HEAD:     $(git rev-parse --short HEAD)"
  echo "mimalloc: $(grep -oE 'MI_MALLOC_VERSION +[0-9]+' Include/internal/mimalloc/mimalloc.h | head -1)"

  if [ ! -x ./python ]; then
    ./configure --with-pydebug --disable-gil > configure.log 2>&1
    make -j10 > build.log 2>&1
    if [ ! -x ./python ]; then
      echo "BUILD FALHOU"; grep -E 'error:' build.log | head -3; return 1
    fi
  fi
  echo "build:    ok  ($(./python -c 'import sys; print(sys.version.split()[0])' 2>/dev/null))"

  local out
  if [ "$MODO" = "suite" ]; then
    out=$(timeout "${LIMITE}s" ./python -m test "$ALVO" -F --parallel-threads="$PTHREADS" -j10 -W 2>&1)
  else
    out=$(timeout "${LIMITE}s" ./python "$ALVO" 2>&1)
  fi

  if printf '%s' "$out" | grep -q "$MI"; then
    echo "VEREDITO: ASSERTION DO MIMALLOC"
    printf '%s' "$out" | grep -A3 "$MI" | head -5
  else
    echo "VEREDITO: limpo em ${LIMITE}s"
  fi
  echo
}

constroi_e_testa "${BUMP}^" "antes"
constroi_e_testa "$BUMP"    "depois"

echo "Limpo nos dois = o oraculo nao e forte o bastante; aumentar limite ou threads."
echo "Sujo nos dois  = nao e o bump; a regressao e mais antiga."
echo "Limpo/sujo     = o bump introduziu."

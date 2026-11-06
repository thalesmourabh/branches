#!/usr/bin/env bash
# Ultima combinacao: copias no mesmo processo (como --parallel-threads=4) MAIS
# sobrecarga de processos (como -j10). Juntos dao ~80 threads em 10 nucleos,
# que e o que o regrtest cria.
#
# Resultados anteriores, todos 0:
#   300 tentativas, 1 copia, 1 processo
#   1440 tentativas, 1 copia, 24 processos
#   800 execucoes, 4 copias, 1 processo
set -u
cd ~ || exit 1
rm -f ~/s3/inproc-*.log

for i in $(seq 1 10); do
  ~/src/cpython-ft/python ~/s3/gi-inprocesso.py 40 4 > ~/s3/inproc-"$i".log 2>&1 &
done
wait
echo "10 processos x 4 copias terminaram"
echo

soma() { grep -h "$1" ~/s3/inproc-*.log | grep -oE ':[[:space:]]*[0-9]+' | tr -d ': ' | awk '{s+=$1} END {print s+0}'; }

echo "execucoes do metodo somadas: $(soma 'execucoes do metodo')"
echo "frames vazio (0 != 1):       $(soma 'frames vazio')"
echo "frames > 1:                  $(soma 'frames > 1')"
echo "menor nº de voltas:          $(grep -h 'menor' ~/s3/inproc-*.log | grep -oE '[0-9]+' | sort -n | head -1)"
echo
if grep -qh 'CASOS COM' ~/s3/inproc-*.log; then
  echo "--- casos capturados (len, voltas, nao_none) ---"
  grep -h -A6 'CASOS COM' ~/s3/inproc-*.log | grep -E '^\s+\(' | head -10
  grep -h '>>>' ~/s3/inproc-*.log | sort -u
else
  echo "nenhum caso de frames vazio"
fi

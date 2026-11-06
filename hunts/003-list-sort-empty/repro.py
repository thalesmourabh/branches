"""
gh-126559 — outra thread observa a lista vazia durante list.sort()

Reduzido do MRE do grupo de pesquisa na issue: tirei o aninhamento de threads
e o caso __str__, que nao muda o mecanismo. Mantive a Barrier, que e o que
sincroniza as duas threads na janela certa.

Mecanismo: listsort() troca ob_item por uma lista vazia enquanto ordena, para
detectar mutacao durante o sort. Com GIL isso e invisivel na maioria dos casos;
sem GIL outra thread le len()==0.

    ~/src/cpython-ft/python repro.py
"""

import sys
from threading import Barrier, Thread

TENTATIVAS = 200


def le_tamanho(barreira, lista, saida):
    barreira.wait()
    saida[0] = len(lista)


def ordena(barreira, lista):
    barreira.wait()
    lista.sort()


def uma_tentativa():
    lista = [1, 2, 3] * 100          # 300 elementos, len esperado = 300
    barreira = Barrier(2)
    saida = [None]

    threads = [
        Thread(target=le_tamanho, args=(barreira, lista, saida)),
        Thread(target=ordena, args=(barreira, lista)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    return saida[0]


vistos = {}
for _ in range(TENTATIVAS):
    n = uma_tentativa()
    vistos[n] = vistos.get(n, 0) + 1

print(f"gil_enabled={sys._is_gil_enabled()}")
print(f"tentativas={TENTATIVAS}")
for valor in sorted(vistos, key=lambda v: (v is None, v)):
    print(f"  len() observado = {valor!r:>6}  em {vistos[valor]} tentativas")

anomalias = vistos.get(0, 0)
print(f"RESULTADO: {'REPRODUZ' if anomalias else 'NAO_REPRODUZ'} (len()==0 em {anomalias})")

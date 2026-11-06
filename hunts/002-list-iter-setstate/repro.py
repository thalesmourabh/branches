"""
gh-129139 — list iterator __setstate__() divergente entre GIL e free-threaded

Nao e race: e divergencia deterministica de semantica entre os dois builds.
Nao precisa de thread nenhuma, o que torna a comparacao limpa.

Esperado (build com GIL):        [] -- iterador exaurido continua exaurido
Observado (build free-threaded): [1] -- __setstate__(0) ressuscita o iterador

    ~/src/cpython/python    repro.py   # GIL
    ~/src/cpython-ft/python repro.py   # free-threaded
"""

import sys

it = iter([1])
primeiro = list(it)          # exaure o iterador

it.__setstate__(0)           # tenta rebobinar para o indice 0
segundo = list(it)

gil = sys._is_gil_enabled()
print(f"gil_enabled={gil}")
print(f"list(it) apos exaurir      = {primeiro}")
print(f"list(it) apos __setstate__ = {segundo}")

# O build com GIL devolve [], o free-threaded devolve [1].
esperado = []
print("DIVERGE" if segundo != esperado else "IGUAL_AO_GIL")

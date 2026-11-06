"""
gh-129139 — extensao: quais iteradores divergem entre GIL e free-threaded
em __setstate__ depois de exauridos.

A issue relata apenas o iterador de lista. Isto varre todos os tipos de
iterador da stdlib que expoem __setstate__, para saber o alcance real.

Protocolo por tipo:
  1. cria o iterador sobre uma sequencia de 1 elemento
  2. exaure com list(it)
  3. chama it.__setstate__(0) -- tenta rebobinar
  4. list(it) de novo

Correto (comportamento do build com GIL): passo 4 devolve [] -- iterador
exaurido permanece exaurido.

    ~/src/cpython/python    repro_matriz.py
    ~/src/cpython-ft/python repro_matriz.py
"""

import sys


class ComGetitem:
    """Dispara o iterador generico de sequencia de Objects/iterobject.c."""

    def __init__(self, dados):
        self._dados = dados

    def __getitem__(self, i):
        return self._dados[i]


CASOS = [
    ("list",         lambda: iter([1])),
    ("list reverso", lambda: reversed([1])),
    ("tuple",        lambda: iter((1,))),
    ("str",          lambda: iter("a")),
    ("bytes",        lambda: iter(b"a")),
    ("bytearray",    lambda: iter(bytearray(b"a"))),
    ("range",        lambda: iter(range(1))),
    ("seq genérico", lambda: iter(ComGetitem([1]))),
]

gil = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True
print(f"gil_enabled={gil}")
print(f"{sys.version.splitlines()[0]}")
print()
print(f"{'tipo':<16} {'tem __setstate__':<17} {'exaure':<8} {'após setstate(0)':<18} veredito")
print("-" * 74)

for nome, fabrica in CASOS:
    it = fabrica()

    if not hasattr(it, "__setstate__"):
        print(f"{nome:<16} {'nao':<17} {'-':<8} {'-':<18} n/a")
        continue

    primeiro = list(it)
    try:
        it.__setstate__(0)
    except Exception as exc:
        print(f"{nome:<16} {'sim':<17} {str(primeiro):<8} {'erro: ' + type(exc).__name__:<18} n/a")
        continue
    segundo = list(it)

    veredito = "RESSUSCITA" if segundo else "ok"
    print(f"{nome:<16} {'sim':<17} {str(primeiro):<8} {str(segundo):<18} {veredito}")

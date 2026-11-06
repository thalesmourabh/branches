"""Adiciona o teste de regressao da gh-160978 e o blurb.

Dois testes, de proposito, porque cobrem caminhos diferentes:

  - o deterministico, via metaclasse com __set_name__, falha nos DOIS builds e
    portanto protege a correcao tambem no CI com GIL;
  - o concorrente, que e o sintoma original da issue e so falha no
    free-threaded.

Sem o primeiro, o CI com GIL nao pegaria uma regressao deste fix.

Uso: python aplicar-teste.py <caminho-da-arvore>
"""
import io
import os
import sys

arvore = sys.argv[1]
p = f"{arvore}/Lib/test/test_ctypes/test_arrays.py"
s = io.open(p, encoding="utf-8").read()

if "gh-160978" in s:
    print("teste ja aplicado, nada a fazer")
    raise SystemExit

# ---- imports: o arquivo nao importa threading nem ThreadPoolExecutor ----
antigo_imp = """import ctypes
import sys
import unittest
"""
novo_imp = """import ctypes
import sys
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
"""
assert s.count(antigo_imp) == 1, "ancora de import nao unica"
s = s.replace(antigo_imp, novo_imp)

# SHORT_TIMEOUT entra na linha de from test.support que ja existe
antigo_sup = ("from test.support import bigmemtest, _2G, threading_helper, "
              "Py_GIL_DISABLED")
novo_sup = ("from test.support import (bigmemtest, _2G, threading_helper,\n"
            "                          Py_GIL_DISABLED, SHORT_TIMEOUT)")
assert s.count(antigo_sup) == 1, "ancora de test.support nao unica"
s = s.replace(antigo_sup, novo_sup)

# ---- a classe de teste, antes do guard de main ----
teste = '''
class ArrayTypeCacheTest(unittest.TestCase):
    # gh-160978: the array type cache could hand out distinct type objects for
    # the same (item type, length) pair when the array type was created from
    # more than one thread at a time.

    def test_concurrent_creation_with_set_name(self):
        # Creating the array type runs Python code -- ``__set_name__`` here --
        # which lets a second thread reach the cache before the first one has
        # stored its type. Without the fix this fails on the default build as
        # well, so it guards the fix even where threads cannot interleave
        # freely.
        barrier = threading.Barrier(2)

        class Meta(type(c_int)):
            def __set_name__(cls, owner, name):
                barrier.wait(timeout=SHORT_TIMEOUT)

        class Item(c_int, metaclass=Meta):
            pass

        with ThreadPoolExecutor(2) as pool:
            first, second = pool.map(lambda _: Item * 100, range(2))

        self.assertIs(first, second)
        # Raises TypeError if the two types are distinct.
        first.from_param(second())

    @threading_helper.requires_working_threading()
    def test_concurrent_creation_returns_identical_types(self):
        nthreads = 8
        barrier = threading.Barrier(nthreads)

        def make_type(length):
            barrier.wait(timeout=SHORT_TIMEOUT)
            return c_int * length

        with ThreadPoolExecutor(nthreads) as pool:
            for length in range(1, 51):
                types = list(pool.map(make_type, [length] * nthreads))
                barrier.reset()
                self.assertEqual(len(set(types)), 1)


'''

ancora_main = "if __name__ == '__main__':\n    unittest.main()"
assert s.count(ancora_main) == 1, "ancora do main nao unica"
s = s.replace(ancora_main, teste.lstrip("\n") + ancora_main)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print(f"teste adicionado em {p}")

# ---------------- blurb ----------------
d = f"{arvore}/Misc/NEWS.d/next/Library"
os.makedirs(d, exist_ok=True)
bp = f"{d}/2026-11-06-12-00-00.gh-issue-160978.Kx7mQa.rst"
io.open(bp, "w", encoding="utf-8", newline="\n").write(
    "Fix :mod:`ctypes` handing out distinct array types for the same item type\n"
    "and length when the array type is created concurrently from several\n"
    "threads.\n"
)
print(f"blurb em {bp}")

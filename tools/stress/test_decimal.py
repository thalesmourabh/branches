"""Stress de concorrência em decimal.

Lacuna: nenhum dos 59 arquivos de `Lib/test/test_free_threading/` cobre
decimal, que tem a maior implementação em C da stdlib que mexe com estado por
thread (`Modules/_decimal/_decimal.c`, 243 KB).

Oráculo documentado — `Doc/library/decimal.rst`:

    Each thread has its own current context which is accessed or changed using
    the getcontext() and setcontext() functions

    getcontext() -> Return the current context for the active thread.
    setcontext(c) -> Set the current context for the active thread to c.

É promessa explícita de isolamento. Se a thread A observa a precisão que a
thread B acabou de gravar, a garantia caiu. Esse é o teste.

Escrito no idioma da suíte deles para poder ir a upstream sem reescrita.
"""

import unittest
from decimal import Decimal, getcontext, setcontext, localcontext, Context

from test.support import threading_helper
from test.support.threading_helper import run_concurrently

NTHREADS = 10
ITERS = 2_000

# Precisão distinta por thread. Valor por índice, não por get_ident(), para que
# a asserção seja determinística.
PRECS = [4, 7, 11, 14, 17, 21, 24, 28, 31, 34]


@threading_helper.requires_working_threading()
class TestDecimalContextIsolation(unittest.TestCase):
    def test_setcontext_is_per_thread(self):
        """Grava e lê a precisão na mesma thread, em loop.

        Dentro de uma thread, `setcontext` e depois `getcontext` tem que
        devolver o que foi gravado — sempre. Se um contexto escapar para outra
        thread, alguma iteração lê a precisão do vizinho.
        """
        counter = iter(range(NTHREADS))
        lock = __import__("threading").Lock()

        def worker():
            with lock:
                prec = PRECS[next(counter)]
            for _ in range(ITERS):
                setcontext(Context(prec=prec))
                self.assertEqual(getcontext().prec, prec)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)

    def test_localcontext_is_per_thread(self):
        """Mesma promessa, pela via do gerenciador de contexto."""
        counter = iter(range(NTHREADS))
        lock = __import__("threading").Lock()

        def worker():
            with lock:
                prec = PRECS[next(counter)]
            for _ in range(ITERS):
                with localcontext() as ctx:
                    ctx.prec = prec
                    self.assertEqual(getcontext().prec, prec)
                    # Uma operação de verdade, para que a precisão seja usada e
                    # não só lida de um campo.
                    self.assertEqual(len((Decimal(1) / Decimal(7)).as_tuple().digits), prec)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)

    def test_localcontext_nesting(self):
        """Aninhamento de localcontext não pode vazar entre threads."""

        def worker():
            base = getcontext().prec
            for _ in range(ITERS // 4):
                with localcontext() as a:
                    a.prec = 9
                    with localcontext() as b:
                        b.prec = 29
                        self.assertEqual(getcontext().prec, 29)
                    self.assertEqual(getcontext().prec, 9)
                self.assertEqual(getcontext().prec, base)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)

    def test_racing_arithmetic_shared_decimals(self):
        """Aritmética concorrente sobre os mesmos objetos Decimal.

        Decimal é imutável, então o resultado tem que ser idêntico em toda
        thread. Divergência significa estado compartilhado onde não deveria
        haver — cache de alocação, por exemplo. Crash também é achado.
        """
        operands = [Decimal(n) / Decimal(7) for n in range(1, 50)]
        expected = sum(operands)

        def worker():
            for _ in range(ITERS // 20):
                self.assertEqual(sum(operands), expected)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)


if __name__ == "__main__":
    unittest.main()

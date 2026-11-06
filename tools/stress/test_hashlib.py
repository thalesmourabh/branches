"""Stress de concorrência em hashlib.

Lacuna: nenhum dos 59 arquivos de `Lib/test/test_free_threading/` cobre
hashlib, e a doc dele é um dos poucos lugares da stdlib que fala de GIL
explicitamente — `Doc/library/hashlib.rst`:

    To allow multithreading, the Python GIL is released while computing a hash
    supplied more than 2047 bytes of data at once in its constructor or
    update() method.

Isso é interessante por dois motivos. Primeiro, dá o limiar exato — abaixo de
2048 bytes o caminho é outro, então todo teste aqui usa blocos maiores que
isso, de propósito. Segundo, a frase é sobre o build **com** GIL; no
free-threaded não há GIL para liberar, e a pergunta é se o lock por objeto
continua protegendo o estado interno do OpenSSL.

**O oráculo, que é a parte boa:** se todas as threads alimentam o mesmo objeto
com blocos *idênticos*, qualquer intercalação produz o mesmo fluxo de bytes —
`b"x" * total`. Então o digest final é previsível sem depender da ordem. Um
update perdido, duplicado ou parcialmente aplicado muda o digest e o teste
pega. Isso detecta corrupção silenciosa, não só crash.

**Incerteza registrada de propósito:** a doc não diz se alimentar o *mesmo*
objeto de hash de várias threads é suportado. Se o resultado divergir, antes de
abrir qualquer coisa é preciso decidir se isso é bug ou uso indefinido — foi
exatamente o erro que a caçada 003 custou. Por isso o teste de objeto
compartilhado está separado do de objetos por thread: o segundo é
inquestionavelmente garantido, o primeiro é a pergunta aberta.
"""

import hashlib
import unittest

from test.support import threading_helper
from test.support.threading_helper import run_concurrently

NTHREADS = 10
ITERS = 200

# Acima do limiar de 2047 citado na doc. É aqui que o caminho que libera o GIL
# entra, e é o caminho que interessa.
BLOCK = b"x" * 4096
assert len(BLOCK) > 2047


@threading_helper.requires_working_threading()
class TestHashlibPerThreadObjects(unittest.TestCase):
    """Garantido sem discussão: um objeto por thread tem que funcionar."""

    def test_racing_independent_hashers(self):
        expected = hashlib.sha256(BLOCK * ITERS).hexdigest()

        def worker():
            h = hashlib.sha256()
            for _ in range(ITERS):
                h.update(BLOCK)
            self.assertEqual(h.hexdigest(), expected)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)

    def test_racing_copy(self):
        """`copy()` concorrente a partir de um objeto base compartilhado."""
        base = hashlib.sha256()
        base.update(BLOCK)
        expected = hashlib.sha256(BLOCK * 2).hexdigest()

        def worker():
            for _ in range(ITERS):
                h = base.copy()
                h.update(BLOCK)
                self.assertEqual(h.hexdigest(), expected)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)


@threading_helper.requires_working_threading()
class TestHashlibSharedObject(unittest.TestCase):
    """A pergunta aberta: o mesmo objeto, alimentado por várias threads.

    A doc não promete nem nega. Divergência aqui exige decidir bug vs. uso
    indefinido ANTES de reportar.
    """

    def test_racing_update_same_object_digest_is_order_independent(self):
        h = hashlib.sha256()
        total = NTHREADS * ITERS * len(BLOCK)
        expected = hashlib.sha256(b"x" * total).hexdigest()

        def worker():
            for _ in range(ITERS):
                h.update(BLOCK)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)

        self.assertEqual(
            h.hexdigest(),
            expected,
            "digest divergiu: algum update foi perdido, duplicado ou aplicado "
            "parcialmente",
        )

    def test_racing_update_and_hexdigest(self):
        """Ler o digest enquanto outra thread alimenta.

        Sem oráculo de valor — o digest parcial legítimo depende de quantos
        blocos entraram. O que se caça é crash e exceção estranha dentro do
        OpenSSL.
        """
        h = hashlib.sha512()

        def feeder():
            for _ in range(ITERS):
                h.update(BLOCK)

        def reader():
            for _ in range(ITERS):
                self.assertEqual(len(h.hexdigest()), 128)

        run_concurrently(
            worker_func=[feeder] * (NTHREADS - 3) + [reader] * 3,
            nthreads=NTHREADS,
        )


if __name__ == "__main__":
    unittest.main()

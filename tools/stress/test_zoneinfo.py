"""Stress de concorrência em zoneinfo.

Lacuna: `Lib/test/test_free_threading/` tem 59 arquivos e **nenhum** cobre
zoneinfo, que tem implementação em C (`Modules/_zoneinfo.c`, 80 KB) e um cache
compartilhado entre threads.

O oráculo aqui é forte porque a própria doc enuncia a invariante, literalmente
como um assert — `Doc/library/zoneinfo.rst`, construtor primário:

    Calls to the primary constructor will always return objects that compare
    identically; [...] barring cache invalidation via ZoneInfo.clear_cache,
    for all values of key, the following assertion will always be true:

        a = ZoneInfo(key)
        b = ZoneInfo(key)
        assert a is b

Ou seja: se duas threads constroem a mesma zona e recebem objetos distintos, a
garantia documentada foi violada. Não é questão de interpretação.

Escrito no idioma da suíte deles (unittest + `run_concurrently`) para que, se
achar algo, o teste vá para upstream sem reescrita.
"""

import unittest

from test.support import threading_helper
from test.support.threading_helper import run_concurrently

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

NTHREADS = 10
ITERS = 500

# Chaves distintas aumentam a chance de bater em bucket diferente do cache e
# forçam mais de uma entrada viva ao mesmo tempo.
KEYS = [
    "America/Sao_Paulo",
    "UTC",
    "Europe/Lisbon",
    "Asia/Tokyo",
    "America/New_York",
]


def _tzdata_available():
    if ZoneInfo is None:
        return False
    try:
        ZoneInfo("UTC")
    except Exception:
        return False
    return True


@unittest.skipUnless(_tzdata_available(), "precisa da base de tz do sistema")
@threading_helper.requires_working_threading()
class TestZoneInfoCacheRaces(unittest.TestCase):
    def tearDown(self):
        ZoneInfo.clear_cache()

    def test_racing_constructor_returns_identical_object(self):
        """A invariante documentada: mesma chave -> mesmo objeto.

        Se o cache tem corrida de leitura-e-insere, duas threads erram o cache
        ao mesmo tempo, as duas constroem, e sobram dois objetos para a mesma
        chave. Aí este teste falha com a doc na mão.
        """
        ZoneInfo.clear_cache()
        key = "America/Sao_Paulo"
        seen_ids = set()
        lock = __import__("threading").Lock()

        def worker():
            local = [ZoneInfo(key) for _ in range(ITERS)]
            ids = {id(obj) for obj in local}
            with lock:
                seen_ids.update(ids)
            # Mantém as referências vivas até o fim para que o id() não possa
            # ser reciclado por um objeto novo no mesmo endereço, o que daria
            # falso negativo.
            self.assertTrue(all(obj is local[0] for obj in local))

        run_concurrently(worker_func=worker, nthreads=NTHREADS)

        self.assertEqual(
            len(seen_ids),
            1,
            f"a doc garante um objeto por chave; apareceram {len(seen_ids)}",
        )

    def test_racing_constructor_many_keys(self):
        """Mesma invariante, com várias chaves vivas ao mesmo tempo.

        **Cuidado que custou uma falsa pista.** A primeira versão deste teste
        não segurava as referências — fazia `per_key[key].add(id(ZoneInfo(k)))`
        e soltava o objeto. Deu 35 objetos distintos para uma chave, o que
        parecia violação grave da invariante documentada. Não era:

        - o cache fraco (`_weak_cache`) solta o objeto quando ninguém o
          referencia, por definição;
        - o cache forte tem no máximo 8 entradas e é LRU em lista ligada no
          estado do módulo, então sob contenção de 10 threads uma chave sai e
          volta;
        - com o objeto morto, `id()` é reciclado e a contagem vira ficção.

        O trecho da doc segura `a` enquanto constrói `b`. Então o teste tem que
        segurar também, senão não testa a invariante que a doc enuncia — testa
        taxa de acerto de cache, que não é promessa de ninguém.
        """
        ZoneInfo.clear_cache()
        per_key = {k: set() for k in KEYS}
        lock = __import__("threading").Lock()
        keep_alive = []

        def worker():
            held = []
            for _ in range(ITERS // len(KEYS)):
                for key in KEYS:
                    obj = ZoneInfo(key)
                    held.append(obj)  # sem isto, id() é reciclado
                    with lock:
                        per_key[key].add(id(obj))
            with lock:
                keep_alive.append(held)

        run_concurrently(worker_func=worker, nthreads=NTHREADS)

        for key, ids in per_key.items():
            self.assertEqual(len(ids), 1, f"{key}: {len(ids)} objetos distintos")

    def test_racing_constructor_and_clear_cache(self):
        """Construtor concorrente com clear_cache.

        Aqui **não** há oráculo de identidade: clear_cache invalida de
        propósito, então objeto novo é correto. O que este teste caça é crash,
        use-after-free ou exceção estranha — o cache é mexido em C enquanto
        outra thread o percorre.
        """
        ZoneInfo.clear_cache()

        def builder():
            for _ in range(ITERS):
                for key in KEYS:
                    self.assertIsNotNone(ZoneInfo(key).key)

        def clearer():
            for _ in range(ITERS):
                ZoneInfo.clear_cache()

        run_concurrently(
            worker_func=[builder] * (NTHREADS - 2) + [clearer] * 2,
            nthreads=NTHREADS,
        )

    def test_racing_no_cache_constructor(self):
        """`no_cache` devolve objeto novo sempre; conferir que nunca colide."""
        ZoneInfo.clear_cache()
        key = "America/Sao_Paulo"

        def worker():
            objs = [ZoneInfo.no_cache(key) for _ in range(50)]
            # Todos têm que ser distintos entre si: é o contrato de no_cache.
            self.assertEqual(len({id(o) for o in objs}), len(objs))
            # E nenhum pode ser o objeto cacheado.
            cached = ZoneInfo(key)
            self.assertTrue(all(o is not cached for o in objs))

        run_concurrently(worker_func=worker, nthreads=NTHREADS)


if __name__ == "__main__":
    unittest.main()

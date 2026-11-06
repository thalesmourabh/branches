"""Repro da gh-160978, nos dois caminhos que a issue descreve.

Invariante: para o mesmo (itemtype, length), `itemtype * length` tem que
devolver SEMPRE o mesmo objeto de tipo. O cache em
Modules/_ctypes/_ctypes.c (array_cache) existe justamente para isso.

A corrida: entre o miss em _PyDict_GetItemProxy (:5408) e a insercao em
PyDict_SetItemProxy (:5440), outra thread faz o mesmo. As duas criam, uma
sobrescreve a outra no cache, e cada uma devolve o proprio objeto.
"""
import sys
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

gil = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True
print("gil:", gil)

# ---------- caminho 1: threads, so falha no free-threaded ----------
from ctypes import c_int

falhas1 = 0
tentativas1 = 0
barrier = Barrier(8)


def make_type(n):
    barrier.wait()
    return c_int * n


with ThreadPoolExecutor(8) as pool:
    for n in range(1, 401):
        tipos = list(pool.map(make_type, [n] * 8))
        tentativas1 += 1
        if len({id(t) for t in tipos}) != 1:
            falhas1 += 1
print(f"1) threads: {falhas1}/{tentativas1} com tipos distintos para a mesma chave")

# ---------- caminho 2: __set_name__, deterministico nos dois builds ----------
import ctypes

barrier2 = Barrier(2)


class Meta(type(ctypes.c_int)):
    def __set_name__(cls, owner, name):
        barrier2.wait(timeout=5)


class C(ctypes.c_int, metaclass=Meta):
    pass


with ThreadPoolExecutor(2) as pool:
    a, b = pool.map(lambda _: C * 100, range(2))

print(f"2) __set_name__: a is b -> {a is b}   (esperado: True)")
try:
    a.from_param(b())
    print("   from_param: ok")
except TypeError as e:
    print(f"   from_param: TypeError -> {e}")

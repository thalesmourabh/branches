"""Diagnostico: o 35 != 1 e falha minha (id reusado) ou e real?

Experimento 1 -- SEM thread nenhuma. Se o id ja varia num loop de uma thread
so, o teste multi-thread nunca provou nada sobre concorrencia.
Experimento 2 -- com threads, SEGURANDO as referencias.
"""
import sys
import threading
from zoneinfo import ZoneInfo

KEYS = ["America/Sao_Paulo", "UTC", "Europe/Lisbon", "Asia/Tokyo", "America/New_York"]
print("gil:", sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True)
print("impl:", ZoneInfo.__module__, type(ZoneInfo))

# ---------- 1: uma thread, sem segurar referencia ----------
ZoneInfo.clear_cache()
ids = set()
for _ in range(100):
    for k in KEYS:
        ids.add(id(ZoneInfo(k)))
print("1) 1 thread, 5 chaves, SEM segurar ref -> ids distintos:", len(ids))

ZoneInfo.clear_cache()
ids1 = set()
for _ in range(100):
    ids1.add(id(ZoneInfo("America/Sao_Paulo")))
print("1b) 1 thread, 1 chave, SEM segurar ref -> ids distintos:", len(ids1))

# ---------- 2: uma thread, segurando ----------
ZoneInfo.clear_cache()
held = []
ids2 = set()
for _ in range(100):
    for k in KEYS:
        o = ZoneInfo(k)
        held.append(o)
        ids2.add(id(o))
print("2) 1 thread, 5 chaves, SEGURANDO ref  -> ids distintos:", len(ids2))

# ---------- 3: threads, segurando ----------
ZoneInfo.clear_cache()
lock = threading.Lock()
per_key = {k: set() for k in KEYS}
keep = []


def worker():
    local = []
    for _ in range(100):
        for k in KEYS:
            o = ZoneInfo(k)
            local.append(o)
            with lock:
                per_key[k].add(id(o))
    with lock:
        keep.append(local)


ts = [threading.Thread(target=worker) for _ in range(10)]
for t in ts:
    t.start()
for t in ts:
    t.join()
print("3) 10 threads, SEGURANDO ref -> distintos por chave:",
      {k: len(v) for k, v in per_key.items()})

# ---------- 4: o cache forte guarda 8; 5 chaves cabem? ----------
ZoneInfo.clear_cache()
a = ZoneInfo("America/Sao_Paulo")
first = id(a)
del a
# nada mais referencia; o cache forte deveria manter vivo
b = ZoneInfo("America/Sao_Paulo")
print("4) sem ref externa, mesmo objeto do cache forte?", id(b) == first)

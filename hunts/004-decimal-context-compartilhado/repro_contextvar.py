"""decimal e vitima ou culpado?

decimal usa PyContextVar_Get/Set. Se um ContextVar comum tambem vaza entre
threads, o defeito esta em contextvars e decimal e so o sintoma -- o que seria
muito mais grave, porque contextvars e a base de propagacao de contexto de
todo o asyncio.

Comportamento esperado: cada thread nova comeca num Context VAZIO. Logo, ler o
ContextVar numa thread nova tem que devolver o DEFAULT, nunca o valor que a
main gravou.
"""
import sys
import threading
import contextvars

print("gil:", sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True)

var = contextvars.ContextVar("var", default="DEFAULT")

# ---------- 1: valor da main vaza para thread nova? ----------
var.set("VALOR-DA-MAIN")
seen = []
lock = threading.Lock()


def reader():
    with lock:
        seen.append(var.get())


ts = [threading.Thread(target=reader) for _ in range(5)]
for t in ts:
    t.start()
for t in ts:
    t.join()
print("1) threads novas leem:", seen)
print("   -> esperado: 5x 'DEFAULT'. vazou:", any(v != "DEFAULT" for v in seen))

# ---------- 2: valor de uma thread vaza para outra? ----------
var2 = contextvars.ContextVar("var2", default="D")
results = []
barrier = threading.Barrier(2)


def setter():
    var2.set("DA-SETTER")
    barrier.wait()
    for _ in range(50000):
        if var2.get() != "DA-SETTER":
            with lock:
                results.append(("setter viu", var2.get()))
            return


def other():
    var2.set("DA-OTHER")
    barrier.wait()
    for _ in range(50000):
        if var2.get() != "DA-OTHER":
            with lock:
                results.append(("other viu", var2.get()))
            return


t1 = threading.Thread(target=setter)
t2 = threading.Thread(target=other)
t1.start(); t2.start(); t1.join(); t2.join()
print("2) cruzamento entre duas threads:", results or "nenhum")

# ---------- 3: copy_context e o Context da thread ----------
print("3) Context da main:", id(contextvars.copy_context()))
ctx_ids = []


def ctx_reader():
    with lock:
        ctx_ids.append(len(contextvars.copy_context()))


ts = [threading.Thread(target=ctx_reader) for _ in range(5)]
for t in ts:
    t.start()
for t in ts:
    t.join()
print("   tamanho do Context visto em cada thread nova:", ctx_ids)
print("   -> esperado: 5x 0 (Context vazio)")

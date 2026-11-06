"""A pergunta direta: getcontext() devolve o MESMO objeto em threads diferentes?

A doc promete: "Each thread has its own current context".

Se duas threads recebem o mesmo objeto de contexto, a promessa caiu -- e aí o
`ctx->status |= status` sem sincronizacao em _decimal.c:606 esta mexendo em
estado compartilhado, que e exatamente o que o TSan apontou.
"""
import sys
import threading
from decimal import getcontext, setcontext, localcontext, Decimal, Inexact

print("gil:", sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True)

# ---------- 1: o objeto de contexto e compartilhado entre threads? ----------
ids = []
lock = threading.Lock()


def who():
    ctx = getcontext()
    with lock:
        ids.append((threading.get_ident(), id(ctx)))


main_ctx_id = id(getcontext())
ts = [threading.Thread(target=who) for _ in range(5)]
for t in ts:
    t.start()
for t in ts:
    t.join()

ctx_ids = {cid for _, cid in ids}
print("1) id do contexto na main:", main_ctx_id)
print("   ids vistos nas threads:", ctx_ids)
print("   -> contextos distintos entre 5 threads:", len(ctx_ids))
print("   -> alguma thread compartilha com a main:", main_ctx_id in ctx_ids)

# ---------- 2: mutacao em uma thread vaza para outra? ----------
# Se o objeto e o mesmo, mexer em .prec numa thread muda na outra.
getcontext().prec = 28
observed = []
barrier = threading.Barrier(2)


def mutator():
    barrier.wait()
    getcontext().prec = 3


def observer():
    barrier.wait()
    for _ in range(100000):
        if getcontext().prec != 28:
            with lock:
                observed.append(getcontext().prec)
            return


t1 = threading.Thread(target=mutator)
t2 = threading.Thread(target=observer)
t1.start(); t2.start(); t1.join(); t2.join()
print("2) a thread observadora viu a precisao da outra:", observed or "nao")

# ---------- 3: as flags de status vazam? ----------
# Operacao inexata liga a flag Inexact no contexto. Se o contexto e
# compartilhado, a thread que nao fez nada inexato ve a flag ligada.
getcontext().clear_flags()
leaked = []


def make_inexact():
    barrier2.wait()
    for _ in range(2000):
        Decimal(1) / Decimal(7)


def check_clean():
    barrier2.wait()
    getcontext().clear_flags()
    for _ in range(2000):
        if getcontext().flags[Inexact]:
            with lock:
                leaked.append(True)
            return


barrier2 = threading.Barrier(2)
t3 = threading.Thread(target=make_inexact)
t4 = threading.Thread(target=check_clean)
t3.start(); t4.start(); t3.join(); t4.join()
print("3) flag Inexact vazou para a thread que nao fez conta inexata:",
      bool(leaked))

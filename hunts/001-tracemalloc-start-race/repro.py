"""
gh-126315 — _PyTraceMalloc_Start: assertion `tracemalloc_traceback == NULL' failed

MRE de devdanzin (comentario de 2026-04-15), reproduzido sem alteracao.
Fork isola o SIGABRT para que o processo pai possa reportar o sinal.

Build necessario: free-threading + --with-pydebug (a assertion so existe com
assertions ligadas).

    ~/src/cpython-ft/python repro.py
"""

import os
import signal
import threading
import tracemalloc


def toggler():
    for _ in range(500):
        try:
            tracemalloc.start()
            tracemalloc.stop()
        except Exception:
            pass


pid = os.fork()
if pid == 0:
    threads = [threading.Thread(target=toggler) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    os._exit(0)

_, status = os.waitpid(pid, 0)
if os.WIFSIGNALED(status):
    print(f"CRASH: {signal.Signals(os.WTERMSIG(status)).name}")
else:
    print("OK")

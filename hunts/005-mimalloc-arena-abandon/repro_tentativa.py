"""Candidato a repro autonomo da assertion do mimalloc.

Assertion que falha, em Objects/mimalloc/arena-abandon.c:162, no fim de
_mi_arena_segment_mark_abandoned:

    mi_assert_internal(_mi_bitmap_is_claimed(arena->blocks_inuse,
                                             arena->field_count, 1, bitmap_idx));

Leitura: um segmento esta sendo marcado como abandonado, mas o bitmap
blocks_inuse da arena diz que aquele bloco NAO esta em uso. Ou seja, o bloco de
arena que da suporte ao segmento ja foi devolvido enquanto o segmento ainda
esta sendo abandonado.

Abandono de segmento acontece quando uma thread MORRE ainda possuindo
segmentos. Entao a hipotese de mecanismo e: muita thread nascendo e morrendo
enquanto aloca, com parte dos objetos sobrevivendo a thread (para que o
segmento continue "used" e precise ser abandonado em vez de liberado).

Uso: python mi-repro.py [rodadas] [threads-por-rodada]
"""
import sys
import threading

RODADAS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
NTHREADS = int(sys.argv[2]) if len(sys.argv) > 2 else 8

# Objetos que sobrevivem as threads que os alocaram. Sem isto o segmento e
# liberado na saida da thread em vez de abandonado, e o caminho que interessa
# nao e exercitado.
sobreviventes = []
lock = threading.Lock()


def worker(rodada):
    # Mistura de tamanhos para cair em classes diferentes de bloco.
    locais = []
    for i in range(400):
        locais.append(b"x" * (16 + (i % 97)))
        locais.append([None] * (i % 23))
        locais.append({"k": i, "s": f"str-{rodada}-{i}"})
    # Uma fracao escapa da thread.
    with lock:
        sobreviventes.append(locais[::40])


for r in range(RODADAS):
    ts = [threading.Thread(target=worker, args=(r,)) for _ in range(NTHREADS)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    # Solta periodicamente, para que arena devolva bloco e o bitmap mexa.
    if r % 20 == 19:
        with lock:
            sobreviventes.clear()
    if r % 50 == 49:
        print(f"  rodada {r + 1}/{RODADAS}", flush=True)

print("FIM sem assertion")

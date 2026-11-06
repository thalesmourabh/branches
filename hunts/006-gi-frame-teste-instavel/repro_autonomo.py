"""A diferenca estrutural que faltava: 4 copias NO MESMO PROCESSO.

Minhas duas replicas anteriores rodaram uma copia do par runner/reader por
processo -- 300 tentativas isoladas e 1440 sob 24 processos. Nenhuma reproduziu.

Mas o `--parallel-threads=4` do regrtest roda 4 copias do METODO DE TESTE
concorrentes DENTRO do mesmo interpretador. Sao 8 threads por processo
compartilhando um runtime, nao 2. Essa condicao eu nunca testei.

Uso: python gi-inprocesso.py [tentativas] [copias]
"""
import sys
import threading

TENTATIVAS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
COPIAS = int(sys.argv[2]) if len(sys.argv) > 2 else 4

print("gil:", sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True)
print(f"tentativas={TENTATIVAS} copias_no_mesmo_processo={COPIAS}")

resultados = []
res_lock = threading.Lock()


def uma_copia():
    """Replica exata do corpo de test_concurrent_gi_frame."""
    frames = set()
    voltas = 0
    nao_none = 0

    def gen():
        for i in range(10000):
            yield i

    g = gen()
    done = threading.Event()
    barrier = threading.Barrier(2)

    def runner():
        barrier.wait()
        for _ in g:
            pass
        done.set()

    def reader():
        nonlocal voltas, nao_none
        barrier.wait()
        while not done.is_set():
            voltas += 1
            frame = g.gi_frame
            if frame:
                nao_none += 1
                frame.f_code
                frame.f_locals
                frames.add(frame)

    t1 = threading.Thread(target=runner)
    t2 = threading.Thread(target=reader)
    t1.start(); t2.start(); t1.join(); t2.join()

    with res_lock:
        resultados.append((len(frames), voltas, nao_none))


for n in range(TENTATIVAS):
    # COPIAS copias do metodo, concorrentes, no mesmo processo -- como o
    # --parallel-threads=N faz.
    ts = [threading.Thread(target=uma_copia) for _ in range(COPIAS)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    if n % 50 == 49:
        print(f"  {n + 1}/{TENTATIVAS}", flush=True)

vazios = [r for r in resultados if r[0] == 0]
mais_de_um = [r for r in resultados if r[0] > 1]

print()
print(f"execucoes do metodo:     {len(resultados)}")
print(f"frames vazio (0 != 1):   {len(vazios)}")
print(f"frames > 1:              {len(mais_de_um)}")
print(f"menor nº de voltas:      {min(r[1] for r in resultados)}")

if vazios:
    print()
    print("CASOS COM frames VAZIO (len, voltas, nao_none):")
    for r in vazios[:10]:
        print("   ", r)
    if all(r[1] == 0 for r in vazios):
        print(">>> voltas==0 em todos: ERA inanicao, minhas medidas anteriores")
        print("    nao criaram a condicao certa.")
    elif all(r[2] == 0 for r in vazios):
        print(">>> o reader RODOU e gi_frame veio None em TODAS as voltas.")
        print("    Isso e gi_frame mentindo sobre gerador vivo -- bug, nao")
        print("    teste frouxo.")
    else:
        print(">>> misto. Precisa olhar caso a caso.")
else:
    print()
    print("nao reproduziu nem com copias no mesmo processo.")

# Caçada 001 — `_PyTraceMalloc_Start`: assertion falha com `start()` concorrente

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython |
| **Issue upstream** | [gh-126315](https://github.com/python/cpython/issues/126315) |
| **Escada** | E1 triagem — verificação independente |
| **Como apareceu** | Issue reaberta em 2026-04-15, sem PR |
| **Status** | triado — alegação confirmada em 3.16, com um adendo |
| **Data** | 2026-11-05 |

---

## 1. Sintoma

Duas threads chamando `tracemalloc.start()` ao mesmo tempo, no build free-threaded com
assertions ligadas, abortam em:

```
python: Python/tracemalloc.c:871: _PyTraceMalloc_Start: Assertion `tracemalloc_traceback == NULL' failed.
```

## 2. Repro mínimo

[`repro.py`](repro.py) — MRE de `devdanzin`, reproduzido **sem alteração**, porque o objetivo
aqui era verificar a alegação dele, não produzir um repro novo.

```
~/src/cpython-ft/python repro.py
```

## 3. Matriz

| Build (mesmo commit `534605904df`) | Resultado |
|---|---|
| free-threaded + `--with-pydebug` | **SIGABRT** em 3/3 execuções |
| com GIL + `--with-pydebug` | `OK` |

Reportado por `devdanzin` em 3.15.0a7 (`4d0e8ee649c`, build com ASan), assertion na linha 824.
Aqui: **3.16.0a1+dev, sem ASan, assertion na linha 871.**

Isso é o dado novo. A reabertura foi testada em 3.15 e com ASan; a confirmação em 3.16 sem
sanitizer mostra que não depende de sanitizer nem daquele branch.

## 4. Bisect

Não fiz. A issue já identifica a janela, e o que estava em dúvida era se o fix
[gh-137992](https://github.com/python/cpython/issues/137992) (merged, fechou a issue em
2025-11-25) cobria este caso. Verifiquei estruturalmente em vez de bisecar:

`_PyEval_StopTheWorldAll(&_PyRuntime)` **está presente** em `Objects/object.c:3455`, dentro de
`PyRefTracer_SetTracer`. Ou seja, o fix está na árvore e o abort acontece de todo jeito.

## 5. Análise

A alegação de `devdanzin` se sustenta literalmente em 3.16. O código de
`_PyTraceMalloc_Start` (`Python/tracemalloc.c:852-907`):

```c
if (_PyTraceMalloc_IsTracing()) {
    return 0;                      /* check atômico, sem lock */
}

tracemalloc_config.max_nframe = max_nframe;
size_t size = TRACEBACK_SIZE(max_nframe);
assert(tracemalloc_traceback == NULL);        /* <-- aborta aqui (linha 871) */
tracemalloc_traceback = raw_malloc(size);
...
PyMem_SetAllocator(PYMEM_DOMAIN_RAW, &alloc);
PyMem_SetAllocator(PYMEM_DOMAIN_MEM, &alloc);
PyMem_SetAllocator(PYMEM_DOMAIN_OBJ, &alloc);

if (PyRefTracer_SetTracer(...) < 0) { ... }   /* aqui dentro ha o STW do gh-137992 */

TABLES_LOCK();
_Py_atomic_store_int_relaxed(&tracemalloc_config.tracing, 1);   /* publicação */
TABLES_UNLOCK();
```

Entre o check atômico e a publicação sob `TABLES_LOCK()`, nada serializa. Duas threads passam
pelo check, as duas entram no init, e a segunda encontra `tracemalloc_traceback` já preenchido.
O stop-the-world do gh-137992 está dentro de `PyRefTracer_SetTracer`, que é chamado **depois** do
assert — não ajuda.

### Adendo que não está na issue

A janela desprotegida não é só o assert. Há **três `PyMem_SetAllocator`** entre o assert e a
publicação, também fora de qualquer lock. Isso significa que:

- remover o assert não resolveria: a troca de alocador continuaria em corrida;
- essa é a mesma janela que `kumaraditya303` descreveu em 2025-07-08 na própria issue, quando
  listou *"it changes the allocator used by runtime while other threads could be allocating
  memory so it leads to data race in `PyMem_SetAllocator`"*.

A observação de 2025 e a análise de 2026 são o mesmo defeito, vistas de ângulos diferentes. Vale
registrar porque a issue as trata como coisas separadas.

## 6. Veredito

- [x] **Bug.** Abort reproduzível, confirmado em 3.16 com o fix anterior presente na árvore.

## 7. O que falta

A issue já traz a direção de correção proposta por `devdanzin` (tomar `TABLES_LOCK()` desde o
início, em double-checked locking, espelhando o que `_PyTraceMalloc_Stop` já faz). Não avaliei
se isso introduz risco de deadlock com o stop-the-world de `PyRefTracer_SetTracer`, que é a
pergunta que decidiria o patch. Isso é trabalho de E2, não de triagem.

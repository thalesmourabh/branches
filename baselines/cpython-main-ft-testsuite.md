# Baseline — CPython `main`, build pydebug, **free-threaded**

| Campo | Valor |
|---|---|
| Commit | `534605904dfa7db25bf19a1b959411b8562c2b80` |
| Assunto do commit | `Add hoodmane to CODEOWNERS for Emscripten files (#161437)` |
| Versão | Python 3.16.0a1+dev free-threading build, GCC 15.2.0 |
| Capturado em | 2026-11-06 |
| Comando | `./python -m test -j10 -W --timeout=600 --slowest` |
| Build | `./configure --with-pydebug --disable-gil` + `make -j10` |
| Árvore | `git worktree --detach` no mesmo commit, em `~/src/cpython-ft` |
| Host | WSL Ubuntu 26.04, 10 cores, 32 GB |
| `sys._is_gil_enabled()` | `False` |
| **Exit code da suíte** | **2 (FAILURE)** |
| Duração | 7 min 26 s |

## Por que este baseline existe

O baseline da S0 foi capturado no build **com GIL**, e lá os arquivos
`test_free_threading.*` ficam **todos skipados** — ele não valida nada da única área que
interessa aqui. Confirmado de novo nesta rodada: no build com GIL,
`test_free_threading.test_generators` reporta `1 test skipped`.

A diferença aparece na contagem de arquivos skipados:

| | GIL (S0) | free-threaded |
|---|---|---|
| arquivos skipados | **75** | **15** |
| testes rodados | 53.422 | **53.535** |

Os ~60 arquivos de diferença são a suíte de free-threading, que só roda aqui.

## Resultado

```
Total tests:      run=53,535  skipped=2,777
Total test files: run=551/562  failed=2  skipped=15  resource_denied=11
534 tests OK
Result: FAILURE
```

## Falha 1 — `test_perf_profiler`: ambiente, não é bug

Idêntica à do baseline com GIL: o `perf` do kernel do WSL não aceita a flag `-j` que o CPython
passa para `perf inject`. Limitação do ambiente. Não reportável.

## Falha 2 — `test_free_threading.test_generators`: **crash, e é novo aqui**

Esta o baseline da S0 **não podia** ter pegado, porque o arquivo é skipado no build com GIL.

Teste: `TestFTGenerators.test_concurrent_write`.

```
mimalloc: assertion failed: at "Objects/mimalloc/arena-abandon.c":162,
  _mi_arena_segment_mark_abandoned
assertion: "_mi_bitmap_is_claimed(arena->blocks_inuse, arena->field_count, 1, bitmap_idx)"
Fatal Python error: Aborted
```

Não é falha de asserção de teste — é **assertion do alocador**. O mimalloc detectou invariante
interna violada ao abandonar um segmento de arena. Num build sem `--with-pydebug` essa assertion
não existe, e o mesmo estado inconsistente passaria silencioso.

### Reprodutibilidade: **não reproduz isolado**

| Build | Comando | Resultado |
|---|---|---|
| free-threaded | `./python -m test test_free_threading.test_generators` × 5 | **0/5** — exit 0 sempre |
| com GIL | idem × 3 | `1 test skipped` (arquivo não roda) |

Só aconteceu **durante a suíte completa**, com `-j10` e load average em 12,71. É crash dependente
de carga.

### Por que não foi reportado

1. **Não sei reproduzir.** Uma ocorrência em suíte completa, 0/5 isolado. Relatar crash que eu não
   consigo provocar de novo é pedir a label `AI-needs-explanation` — e com razão, porque eu não
   conseguiria explicar como verificar.
2. Cruzei contra issues **e PRs abertos** (o filtro novo da caçada 004): nada sobre
   `arena-abandon.c` nem `_mi_arena_segment_mark_abandoned`. Há oito issues de mimalloc abertas,
   nenhuma desta. Então **pode ser achado novo** — mas sem repro não serve.
3. Contexto que aumenta a suspeita: o mimalloc foi atualizado recentemente (ver
   [gh-161420](https://github.com/python/cpython/issues/161420), *"since the mimalloc 2.5.2
   update"*, e [PR 159718](https://github.com/python/cpython/pull/159718), upgrade para o v3).
   Assertion de arena pouco depois de troca de versão de alocador é padrão de regressão.

### O que falta para virar reporte

O loop contínuo da S3.5: rodar este arquivo sob carga artificial, em repetição, até reproduzir com
taxa mensurável. Com taxa e `arquivo:linha`, vira issue. Sem isso, fica aqui.

## Sobre o ThreadSanitizer

`0` avisos — esperado, este build não tem TSan. O baseline sob TSan é
[outro arquivo](cpython-main-tsan-testsuite.md).

## Log cru

[`cpython-main-ft-testsuite.raw.log`](cpython-main-ft-testsuite.raw.log)

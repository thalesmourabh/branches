# Issue aberta — registro do texto

**Postada em 2026-11-06 como [gh-161489](https://github.com/python/cpython/issues/161489)**,
com aprovação explícita. O texto abaixo é o que foi enviado.

Decisões de redação, seguindo o que ficou valendo em
[PROCESSO.md](../../PROCESSO.md#ferramentas-de-ia--o-que-a-política-realmente-exige):

1. **Em inglês.**
2. **Sem declaração de uso de IA** — a política não exige, e só menciona
   descrição de PR, nunca issue. Decisão sua, de 2026-11-06.
3. **Não ofereço patch nem opinião sobre a correção.** O mecanismo implica duas
   saídas com coberturas diferentes, e a escolha é de quem mantém. Também não
   pergunto "posso trabalhar nisso?".
4. **Dois repros**: o comando deles primeiro, porque é o que eles rodam; o
   script autônomo depois, como prova do mecanismo.

Se você quiser, isto também cabe como comentário na
[gh-144446](https://github.com/python/cpython/issues/144446) em vez de issue
nova, já que é o teste daquela issue. Minha leitura: **issue própria é melhor**
— a gh-144446 é sobre corrida real em frame, e isto é defeito de teste; misturar
os dois atrapalha quem for triar a gh-144446 depois.

---

**Título:** `test_concurrent_gi_frame` is flaky under `--parallel-threads`: the reader thread may never run its loop body

---

> ## Bug description
>
> `test_free_threading.test_generators.TestFTGenerators.test_concurrent_gi_frame`
> fails intermittently with `AssertionError: 0 != 1` when run under
> `--parallel-threads`. The failure is in the test, not in the runtime.
>
> ```
> FAIL: test_concurrent_gi_frame (test.test_free_threading.test_generators.TestFTGenerators.test_concurrent_gi_frame)
> AssertionError: 0 != 1
> ```
>
> ### Reproducer
>
> On a `--with-pydebug --disable-gil` build at
> `534605904dfa7db25bf19a1b959411b8562c2b80`:
>
> ```
> ./python -m test test_free_threading.test_generators -F --parallel-threads=4 -j10 -W
> ```
>
> **5 out of 10 runs** reproduced, after 126 s, 160 s, 320 s, 368 s and 391 s.
> Build: GCC 15.2.0, 10 cores. Not sensitive to mimalloc purge settings
> (2/5 with `MIMALLOC_PURGE_DELAY=0 MIMALLOC_ARENA_PURGE_MULT=1`, 3/5 without).
>
> ### Cause
>
> `0 != 1` can only mean `len(frames) == 0`. I instrumented the test locally to
> record, on failure, how many times the `reader` loop body executed and how
> often `gi_frame` was non-`None`:
>
> ```
> DIAG frames=0 voltas=0 nao_none=0
> ```
>
> `voltas=0` — **the `reader` loop body never executed**. The `runner` consumed
> all 10 000 yields and called `done.set()` before `reader` reached its first
> `while not done.is_set()` check, so `frames` stayed empty:
>
> ```python
> def reader():
>     while not done.is_set():        # already True on first evaluation
>         frame = g.gi_frame
>         ...
>         frames.add(frame)
>     self.assertIsNone(g.gi_frame)
>
> threading_helper.run_concurrently([runner, reader])
> self.assertEqual(len(frames), 1)    # 0 != 1
> ```
>
> This rules out the alternative reading, which would have been a real bug:
> `gi_frame` returning `None` for a live generator. That would show a large
> `voltas` with `nao_none=0`; it does not happen.
>
> ### Why `--parallel-threads` triggers it
>
> `Lib/test/libregrtest/parallel_case.py` makes `num_threads` copies of the test
> case and releases them from one `threading.Barrier` simultaneously, in the same
> process. Each copy starts its own `runner`/`reader` pair, so
> `--parallel-threads=4 -j10` is roughly 80 threads on 10 cores. Under that
> oversubscription a `reader` can fail to be scheduled before its `runner`
> finishes — and 10 000 trivial yields finish quickly.
>
> ### Independent confirmation outside regrtest
>
> Both oversubscriptions are needed; neither alone is sufficient. Replicating the
> test body standalone on the same build:
>
> | Condition | Method executions | `frames` empty | min. loop iterations |
> |---|---|---|---|
> | 1 copy, 1 process | 300 | 0 | 271 |
> | 1 copy, 24 processes | 1440 | 0 | 196 |
> | 4 copies, 1 process | 800 | 0 | 67 |
> | **4 copies × 10 processes** | **1600** | **3** | **0** |
>
> All three captured cases were `(len=0, iterations=0, non_none=0)`, matching the
> instrumented run. Note the last column decreasing monotonically with load until
> it reaches zero: same phenomenon at increasing scale.
>
> ### Note
>
> `--parallel-threads=4` is the configuration used in
> `.github/workflows/reusable-san.yml` (`--tsan-parallel --parallel-threads=4`),
> so this is a plausible source of intermittent CI failures.
>
> The assertion the test appears to care about — that the reader never observes
> two distinct frame objects, per gh-144446 — holds in every run I saw
> (`frames > 1` never occurred in the 2400 executions where I tracked it).
> `len(frames) == 1`
> additionally requires the reader to be scheduled, which is not guaranteed. I
> have no opinion on which way to resolve that, since tolerating zero and
> synchronising to guarantee one iteration cover different things.
>
> Test added in #156037 for gh-144446; present since v3.16.0a1.

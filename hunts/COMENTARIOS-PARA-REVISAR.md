# Rascunhos dos comentários — aguardando sua revisão

Nada disto foi postado. Comentário em issue upstream é público e irreversível.

Decisões que tomei na redação, e que você pode reverter:

1. **Em inglês.** É a língua dos dois projetos.
2. **Fatos primeiro, sem opinião sobre o fix.** Em 002 e 001 eu não digo o que fazer; em 003 eu
   recomendo fechar, porque ali o veredito *é* o conteúdo.
3. **Não pergunto "posso trabalhar nisso?"** É ruído, e está na minha lista do que não fazer.
4. **Declaro uso de IA no fim de cada um.** `devdanzin` fez exatamente isso no comentário de
   reabertura da gh-126315 ("*done with assistance from Claude Code, reviewed by a human*"), então
   o precedente está no próprio thread. Acho que é o certo e protege você se alguém perguntar
   depois. Se discordar, é só cortar a linha.

---

## 1. gh-126315 — tracemalloc

**Valor:** confirma em 3.16 sem sanitizer o que foi relatado em 3.15 com ASan, e conecta duas
observações que a issue trata como separadas.

> Independent confirmation on current `main`, plus one addition.
>
> **Still reproduces on 3.16.** devdanzin's MRE aborts for me on `main` at
> `534605904dfa7db25bf19a1b959411b8562c2b80`, 3 out of 3 runs:
>
> ```
> python: Python/tracemalloc.c:871: _PyTraceMalloc_Start: Assertion `tracemalloc_traceback == NULL' failed.
> CRASH: SIGABRT
> ```
>
> The same script on a GIL-enabled build of the same commit prints `OK`.
>
> Two details that differ from the report above, and that I think make the data point worth
> adding: this is a plain `--disable-gil --with-pydebug` build with **no sanitizer**, and it is
> 3.16, not 3.15. So the abort does not depend on ASan or on that branch. The assertion has moved
> from line 824 to line 871. I verified `_PyEval_StopTheWorldAll(&_PyRuntime)` is present in
> `PyRefTracer_SetTracer` (`Objects/object.c:3455`), so gh-137992 is in the tree.
>
> **Addition: the unprotected window is wider than the assertion.** Between the unlocked
> `_PyTraceMalloc_IsTracing()` check and the publication under `TABLES_LOCK()`, there are also
> three `PyMem_SetAllocator` calls:
>
> ```c
> PyMem_SetAllocator(PYMEM_DOMAIN_RAW, &alloc);
> PyMem_SetAllocator(PYMEM_DOMAIN_MEM, &alloc);
> PyMem_SetAllocator(PYMEM_DOMAIN_OBJ, &alloc);
> ```
>
> Removing or weakening the assertion would therefore not be sufficient — the allocator swap stays
> racy. This also appears to be the same window @kumaraditya303 described on 2025-07-08 in this
> thread ("it changes the allocator used by runtime while other threads could be allocating
> memory"). The 2025 observation and the 2026 analysis look like one defect seen from two angles,
> which may matter for scoping a fix.
>
> *Reproduction and analysis done with assistance from Claude Code, reviewed by a human.*

---

## 2. gh-129139 — `__setstate__` em iterador exaurido

**Valor:** o maior dos três. Amplia a issue de 1 para 3 iteradores, mostra que um dos sintomas
atinge o build com GIL, e localiza os dois commits culpados.

> Triage: this affects three iterator types, not one, and one of the symptoms is present in the
> default (GIL-enabled) build.
>
> Both builds below are the same commit, `534605904dfa7db25bf19a1b959411b8562c2b80`, differing
> only in `--disable-gil`. Released versions are the python-build-standalone builds.
>
> | Version | `iter(list)` | `reversed(list)` | `iter(tuple)` |
> |---|---|---|---|
> | 3.12.16 | ok | ok | ok |
> | 3.13.18 (GIL) | ok | **resurrects** | ok |
> | 3.13.18t | **resurrects** | **resurrects** | ok |
> | 3.14.10 (GIL) | ok | **resurrects** | ok |
> | 3.14.10t | **resurrects** | **resurrects** | **resurrects** |
> | 3.16.0a1+dev (GIL) | ok | **resurrects** | ok |
> | 3.16.0a1+dev free-threaded | **resurrects** | **resurrects** | **resurrects** |
>
> "resurrects" means `list(it)` returns an element again after `it.__setstate__(0)` on an already
> exhausted iterator. Not affected in any build: `str`, `bytes`, `bytearray`, `range`, and the
> generic sequence iterator.
>
> **`reversed()` is affected in the GIL-enabled build, since 3.13.** That part is not
> free-threading specific:
>
> ```python
> >>> it = reversed([1]); list(it)
> [1]
> >>> it.__setstate__(0); list(it)
> [1]          # 3.13+, GIL-enabled; 3.12 returns []
> ```
>
> **Root cause.** `__setstate__` uses `it_seq == NULL` as the "exhausted" sentinel, while the
> thread-safety work changed `_next` to use `it_index < 0`. The `__setstate__` methods were not
> updated.
>
> In 3.12, `listreviter_next` always cleared `it_seq` when exhausted. After
> a2d4281415e67c62f91363376db97eb66a9fb716 it returns early instead:
>
> ```c
> Py_ssize_t index = FT_ATOMIC_LOAD_SSIZE_RELAXED(it->it_index);
> if (index < 0) {
>     return NULL;          /* returns before it_seq = NULL below */
> }
> ...
> FT_ATOMIC_STORE_SSIZE_RELAXED(it->it_index, -1);
> #ifndef Py_GIL_DISABLED
>     it->it_seq = NULL;    /* unreachable on the normal exhaustion path */
> #endif
> ```
>
> For `reversed([1])`: `it_index` starts at 0, the first `next()` yields the item and stores -1,
> the second `next()` takes the early return, and `it_seq` is never cleared. `__setstate__(0)`
> then sees `it_seq != NULL`, runs its body and rewinds the iterator.
>
> The forward list iterator escapes this in the GIL build because its exhaustion is detected by
> `list_get_item_ref` returning `NULL`, a path that still reaches `it->it_seq = NULL`. Under
> `--disable-gil` that assignment is compiled out, which is why the forward iterator is affected
> there.
>
> **Culprits:**
>
> - `reversed(list)`, GIL build: a2d4281415e67c62f91363376db97eb66a9fb716 ("gh-112087: Make
>   `__sizeof__` and `listiter_{len, next}` to be threadsafe", first in v3.13.0a4)
> - `iter(tuple)`, free-threaded: 388e1ca9f08ee5caefd1dd946dc6e236ce73d46f ("gh-115999: Make list
>   and tuple iteration more thread-safe", first in v3.14.0a6)
>
> The second one confirms what @eendebakpt predicted in the first comment on this issue: gh-128637
> did produce the equivalent behaviour for tuple iterators.
>
> **The correct shape already exists in the tree.** `Objects/iterobject.c:112` checks both
> sentinels, which is why the generic sequence iterator does not appear in the table:
>
> ```c
> if (index >= 0 && it->it_seq != NULL) {
> ```
>
> The three affected sites check only one: `Objects/listobject.c:4198`,
> `Objects/listobject.c:4350`, `Objects/tupleobject.c:1206`. This matches @Yhg1s's comment that it
> "just requires an extra check in the relevant `__setstate__` methods".
>
> For completeness: `bytesobject.c:3625/3641` and `unicodeobject.c:15100/15121` have the same
> `it_seq != NULL` guard but do not reproduce, so I have left them out.
>
> I have no opinion on whether this is worth fixing — that is the open question in this thread.
> I'm only putting the scope on record, since it is larger than the issue title suggests.
>
> *Reproduction, version matrix and root-cause analysis done with assistance from Claude Code,
> reviewed by a human.*

---

## 3. gh-126559 — lista vazia durante `sort()`

**Valor:** o menor. É limpeza de backlog: a issue está aberta há dois anos sem nada pendente.
Útil, mas não é descoberta.

> Triage: this is documented behaviour and I think the issue can be closed.
>
> Still reproduces on `main` at `534605904dfa7db25bf19a1b959411b8562c2b80`, and with a `Barrier`
> and two threads it is not intermittent — `len()` returns 0 in **200 out of 200** attempts on a
> free-threaded build, and 300/300 correct on a GIL-enabled build of the same commit. That is
> slightly stronger than the original report, which saw it a few times out of ten.
>
> But as @colesbury noted in 2024, the behaviour predates free-threading, and it is documented.
> `Doc/builtins/stdtypes.rst` on `list.sort`:
>
> > CPython implementation detail: While a list is being sorted, the effect of attempting to
> > mutate, or even inspect, the list is undefined. The C implementation of Python makes the list
> > appear empty for the duration, and raises `ValueError` if it can detect that the list has been
> > mutated during a sort.
>
> The reproducer inspects the list during a sort, which is exactly what the documentation calls
> undefined, and observes the documented "appears empty" state. Free-threading only made the
> window easy to hit.
>
> Both alternatives proposed in this thread were already declined on cost grounds (locking in
> `__len__`, and a sentinel in the size field). As far as I can tell nothing is pending here, so
> this looks closable as documented behaviour, with no code or doc change needed. The broader
> container atomicity discussion in gh-126136 and
> [PEP 703](https://peps.python.org/pep-0703/#container-thread-safety) is of course still open —
> just not this issue.
>
> *Reproduction and doc verification done with assistance from Claude Code, reviewed by a human.*

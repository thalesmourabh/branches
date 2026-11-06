# Rascunho do PR — aguardando sua aprovação

**Nada foi aberto.** E há um bloqueio antes disso: o [CLA](https://cla.python.org/).

Estado local, pronto para empurrar:

```
branch:  gh-160978-ctypes-array-cache   (em ~/src/cpython)
commit:  5ed12c7d340
arquivos: Modules/_ctypes/_ctypes.c
          Lib/test/test_ctypes/test_arrays.py
          Misc/NEWS.d/next/Library/2026-11-06-12-00-00.gh-issue-160978.Kx7mQa.rst
```

Decisões de redação, nas mesmas regras de sempre:

1. **Em inglês.**
2. **Sem declaração de uso de IA** — a política diz *"appreciated, while not
   required"*, e sua decisão de 2026-11-06 foi tirar.
3. **Sem `Co-Authored-By`**, pela mesma decisão.
4. **Explico a restrição de desenho**, porque é a parte que um revisor vai
   querer questionar: por que não um lock em volta da criação do tipo.
5. **Declaro o que não cobri**, em vez de deixar o revisor descobrir.

---

**Título:** `gh-160978: Return the same ctypes array type when created concurrently`

---

> `PyCArrayType_from_ctype()` looked the array type up in `array_cache`,
> created it on a miss, and only then stored it:
>
> ```c
> if (_PyDict_GetItemProxy(st->array_cache, key, &result) != 0) {
>     Py_DECREF(key);
>     return result;
> }
> /* not found */
> ...
> result = PyObject_CallFunction((PyObject *)st->PyCArrayType_Type, ...);
> ...
> if (PyDict_SetItemProxy(st, st->array_cache, key, result) < 0) { ... }
> return result;
> ```
>
> Creating the type runs Python code, so two threads can both miss the cache,
> both create a type, and each return its own. The second one overwrites the
> first in the cache, and callers end up holding distinct types for the same
> item type and length — hence the `TypeError: expected c_int_Array_1 instance
> instead of c_int_Array_1` in the issue.
>
> **Why not hold a lock around the whole miss path:** the type is created by
> `PyObject_CallFunction()`, which can run arbitrary Python code — the
> `__set_name__` reproducer in the issue is exactly that. Holding a lock across
> it invites re-entrancy and deadlock. So this serialises the *insertion*
> instead: `_PyDict_SetDefaultItemProxy()` uses `PyDict_SetDefaultRef()` so the
> first type to reach the cache wins, and a thread that loses the race drops
> the type it built and returns the cached one. Two threads may still both
> build a type, but they now agree on which one is canonical.
>
> If the cached entry has already been cleared by its `DictRemover`, the new
> type is installed instead, as before.
>
> **Tests.** Two, because they fail on different builds:
>
> | | default build | free-threaded |
> |---|---|---|
> | `test_concurrent_creation_with_set_name` | fails without the fix | fails without the fix |
> | `test_concurrent_creation_returns_identical_types` | passes | fails without the fix |
>
> The first one is the only one that guards the fix on the default build, which
> is why it is there even though the issue is about free-threading.
>
> **Checked.** Built and tested on `--with-pydebug` and
> `--with-pydebug --disable-gil` at the same commit: full `test_ctypes` passes
> on both (648 tests), and passes under `-R 3:3` on the free-threaded build.
> The reproducer in the issue goes from 397/400 failures to 0/400 there.
>
> **Not covered:** I did not audit the other proxy caches in `_ctypes`
> (`st->cache` for pointer types, for instance) for the same pattern. They look
> similar, but I have not reproduced anything there, so this change is limited
> to the array cache.

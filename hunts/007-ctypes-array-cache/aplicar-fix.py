"""Aplica o fix da gh-160978 numa arvore do CPython.

Uso: python aplicar-fix.py <caminho-da-arvore>

Desenho, e a restricao que manda nele: NAO se pode segurar lock durante a
criacao do tipo, porque ali roda codigo Python arbitrario -- e exatamente o
que o repro do __set_name__ explora. Entao a serializacao tem que estar na
INSERCAO, nao na criacao.

PyDict_SetDefaultRef faz isso: insere se ausente e devolve referencia forte ao
vencedor, atomicamente. Quem perder a corrida descarta o tipo que criou e
devolve o que ja estava no cache, de modo que `itemtype * length` sempre da o
mesmo objeto.
"""
import io
import sys

arvore = sys.argv[1]
p = f"{arvore}/Modules/_ctypes/_ctypes.c"
s = io.open(p, encoding="utf-8").read()

# ---------- 1. novo helper, logo depois de PyDict_SetItemProxy ----------
ancora_helper = """static int
_PyDict_GetItemProxy(PyObject *dict, PyObject *key, PyObject **presult)
{"""

helper = '''/* Like PyDict_SetItemProxy(), but does not replace an existing live entry.
   On success *presult is a new reference to whatever is cached for `key`
   afterwards: `item` itself, or the object another thread cached first.
   Returns 0 on success, -1 with an exception set on failure. */
static int
_PyDict_SetDefaultItemProxy(ctypes_state *st, PyObject *dict, PyObject *key,
                            PyObject *item, PyObject **presult)
{
    PyObject *obj = _PyObject_CallNoArgs((PyObject *)st->DictRemover_Type);
    if (obj == NULL) {
        return -1;
    }

    DictRemoverObject *remover = (DictRemoverObject *)obj;
    assert(remover->key == NULL);
    assert(remover->dict == NULL);
    remover->key = Py_NewRef(key);
    remover->dict = Py_NewRef(dict);

    PyObject *proxy = PyWeakref_NewProxy(item, obj);
    Py_DECREF(obj);
    if (proxy == NULL) {
        return -1;
    }

    PyObject *stored;
    int present = PyDict_SetDefaultRef(dict, key, proxy, &stored);
    Py_DECREF(proxy);
    if (present < 0) {
        return -1;
    }
    if (present == 0) {
        /* Our proxy was inserted; `item` is the canonical object. */
        Py_DECREF(stored);
        *presult = Py_NewRef(item);
        return 0;
    }

    /* Another thread cached an object for this key first. Prefer it, so that
       every caller gets the same object. */
    PyObject *existing = NULL;
    int rc = 0;
    if (PyWeakref_CheckProxy(stored)) {
        rc = PyWeakref_GetRef(stored, &existing);
    }
    Py_DECREF(stored);
    if (rc < 0) {
        return -1;
    }
    if (existing != NULL) {
        *presult = existing;
        return 0;
    }

    /* The cached entry had already been cleared; install ours instead. */
    if (PyDict_SetItemProxy(st, dict, key, item) < 0) {
        return -1;
    }
    *presult = Py_NewRef(item);
    return 0;
}

static int
_PyDict_GetItemProxy(PyObject *dict, PyObject *key, PyObject **presult)
{'''

assert s.count(ancora_helper) == 1, "ancora do helper nao unica"
s = s.replace(ancora_helper, helper)

# ---------- 2. usar o helper em PyCArrayType_from_ctype ----------
antigo = """    if (PyDict_SetItemProxy(st, st->array_cache, key, result) < 0) {
        Py_DECREF(key);
        Py_DECREF(result);
        return NULL;
    }
    Py_DECREF(key);
    return result;
}"""

novo = """    /* Creating the type above can run Python code (a metaclass
       __set_name__, for instance), so another thread may have created and
       cached an array type for the same key in the meantime. Insert ours only
       if the key is still absent, and otherwise return the cached object, so
       that `itemtype * length` always evaluates to the same type. */
    PyObject *cached;
    if (_PyDict_SetDefaultItemProxy(st, st->array_cache, key, result,
                                    &cached) < 0) {
        Py_DECREF(key);
        Py_DECREF(result);
        return NULL;
    }
    Py_DECREF(key);
    Py_DECREF(result);
    return cached;
}"""

assert s.count(antigo) == 1, "ancora do from_ctype nao unica"
s = s.replace(antigo, novo)

io.open(p, "w", encoding="utf-8", newline="\n").write(s)
print(f"patch aplicado em {p}")

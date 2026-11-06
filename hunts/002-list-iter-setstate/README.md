# Caçada 002 — `__setstate__` ressuscita iterador exaurido

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython |
| **Issue upstream** | [gh-129139](https://github.com/python/cpython/issues/129139) |
| **Escada** | E1 triagem |
| **Como apareceu** | Issue aberta, sem PR ativo (o PR 146269 foi fechado sem merge em 2026-03-22) |
| **Status** | triado — ampliado em duas direções |
| **Data** | 2026-11-05 |

---

## 1. Sintoma

Um iterador de lista já exaurido volta a produzir elementos depois de
`it.__setstate__(0)` no build free-threaded, mas não no build com GIL.

## 2. Repro mínimo

Não precisa de thread. É divergência determinística de semântica entre builds — o que torna a
comparação limpa e o veredito inquestionável.

Arquivos: [`repro.py`](repro.py) (caso da issue), [`repro_matriz.py`](repro_matriz.py) (varredura
de todos os tipos de iterador).

```
~/src/cpython/python    repro.py   # GIL         -> []
~/src/cpython-ft/python repro.py   # free-threaded -> [1]
```

## 3. Matriz — e aqui a issue fica pequena

Os dois builds de `main` são o **mesmo commit** (`534605904df`), diferindo só em `--disable-gil`.
As versões liberadas vieram do `uv`, inclusive as variantes `t` (free-threaded).

| Versão | `iter(list)` | `reversed(list)` | `iter(tuple)` |
|---|---|---|---|
| 3.12.16 | ok | ok | ok |
| 3.13.18 (GIL) | ok | **RESSUSCITA** | ok |
| 3.13.18t | **RESSUSCITA** | **RESSUSCITA** | ok |
| 3.14.10 (GIL) | ok | **RESSUSCITA** | ok |
| 3.14.10t | **RESSUSCITA** | **RESSUSCITA** | **RESSUSCITA** |
| 3.16.0a1+dev (GIL) | ok | **RESSUSCITA** | ok |
| 3.16.0a1+dev free-threaded | **RESSUSCITA** | **RESSUSCITA** | **RESSUSCITA** |

Não afetados em nenhum build: `str`, `bytes`, `bytearray`, `range`, iterador genérico de
sequência.

**Duas coisas que não estão na issue:**

1. São **três** iteradores afetados, não um: lista, lista reversa e tupla.
2. `reversed()` ressuscita **também no build com GIL**, desde 3.13. Isso não é um problema de
   free-threading — é regressão no build padrão, que ninguém reportou.

## 4. Bisect

Log: [`bisect.log`](bisect.log). Feito por arqueologia de `git log -L` sobre o corpo das funções,
com a fronteira de versão confirmada empiricamente — não por build a cada passo.

**`reversed()`, build com GIL** — culpado:

```
a2d4281415e67c62f91363376db97eb66a9fb716
Donghee Na, 2024-02-15
gh-112087: Make __sizeof__ and listiter_{len, next} to be threadsafe (gh-114843)
primeira tag: v3.13.0a4
```

**`iter(tuple)`, free-threaded** — culpado:

```
388e1ca9f08ee5caefd1dd946dc6e236ce73d46f
T. Wouters, 2025-02-18
gh-115999: Make list and tuple iteration more thread-safe. (#128637)
primeira tag: v3.14.0a6
```

Este segundo confirma empiricamente o que `eendebakpt` previu no primeiro comentário da issue, em
2025-01-21: que as mudanças do PR 128637 produziriam o mesmo efeito em iteradores de tupla.
Previsão correta.

## 5. Análise — a causa raiz

`__setstate__` usa `it_seq == NULL` como sentinela de "exaurido". O trabalho de free-threading
trocou a sentinela em `_next` para `it_index < 0`, e os `__setstate__` nunca foram atualizados.

**`listreviter_next` em v3.12.0** — limpava `it_seq` sempre:

```c
seq = it->it_seq;
if (seq == NULL) return NULL;            /* sentinela: it_seq */
index = it->it_index;
if (index >= 0 && index < PyList_GET_SIZE(seq)) {
    item = PyList_GET_ITEM(seq, index);
    it->it_index--;
    return Py_NewRef(item);
}
it->it_index = -1;
it->it_seq = NULL;                       /* SEMPRE executa ao exaurir */
Py_DECREF(seq);
return NULL;
```

**Depois de `a2d4281415e`** — o `return` antecipado pula a limpeza:

```c
Py_ssize_t index = FT_ATOMIC_LOAD_SSIZE_RELAXED(it->it_index);
if (index < 0) {
    return NULL;                         /* <-- sai antes de limpar it_seq */
}
PyListObject *seq = it->it_seq;
PyObject *item = list_get_item_ref(seq, index);
if (item != NULL) {
    FT_ATOMIC_STORE_SSIZE_RELAXED(it->it_index, index - 1);
    return item;
}
FT_ATOMIC_STORE_SSIZE_RELAXED(it->it_index, -1);
#ifndef Py_GIL_DISABLED
    it->it_seq = NULL;                   /* inalcançável no caminho normal */
#endif
```

Traço de `reversed([1])` em 3.13+, build com GIL:

1. `it_index` começa em 0 (tamanho − 1).
2. `next()`: índice 0 válido → devolve o item, grava `it_index = -1`.
3. `next()`: `index < 0` → **sai no `return` antecipado**, `it_seq` nunca é limpo.
4. `__setstate__(0)`: `it_seq != NULL` → o corpo roda → `it_index = 0` → ressuscitou.

O iterador **para frente** escapa disso no build com GIL porque a exaustão dele é detectada por
item fora de faixa (`list_get_item_ref` devolve `NULL`), caminho que ainda alcança
`it->it_seq = NULL`. Já no free-threaded o `#ifndef Py_GIL_DISABLED` desliga a limpeza, e aí
ele também ressuscita. A matriz do item 3 reflete exatamente isso.

### A forma correta já existe na mesma árvore

`Objects/iterobject.c:112` (iterador genérico de sequência) checa as **duas** sentinelas, e é por
isso que ele não aparece na matriz:

```c
if (index >= 0 && it->it_seq != NULL) {
```

Os três sítios afetados checam só uma:

| Arquivo | Linha | Guarda atual |
|---|---|---|
| `Objects/listobject.c` | 4198 | `if (it->it_seq != NULL) {` |
| `Objects/listobject.c` | 4350 | `if (it->it_seq != NULL) {` |
| `Objects/tupleobject.c` | 1206 | `if (it->it_seq != NULL) {` |

Isso é consistente com o que `Yhg1s` disse na issue em 2025-01-22 — *"it just requires an extra
check in the relevant `__setstate__` methods"*. O check é o `index >= 0` que o `iterobject.c` já
faz.

Candidatos que também testam `it_seq != NULL` mas **não** reproduzem, e portanto ficam de fora até
que alguém mostre o contrário: `bytesobject.c:3625/3641`, `unicodeobject.c:15100/15121`.

## 6. Veredito

- [x] **Bug.** E mais amplo do que a issue registra.

Três iteradores afetados, não um. E a parte do `reversed()` existe no build com GIL desde
3.13.0a4, o que tira o caso do escopo "só free-threading".

Não emito opinião sobre se vale corrigir — `Yhg1s` já disse *"I'm not sure it's worth it"* e essa
é decisão de core dev, não minha. O que mudou é a informação disponível para decidir: o alcance é
3 sítios e um dos sintomas atinge o build padrão.

## 7. O que falta

Não investiguei por que o PR [146269](https://github.com/python/cpython/pull/146269) foi fechado
sem merge em 2026-03-22. Se foi recusa de mérito, a decisão já está tomada e esta triagem só
acrescenta alcance.

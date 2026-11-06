# Caçada 003 — outra thread observa a lista vazia durante `list.sort()`

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython |
| **Issue upstream** | [gh-126559](https://github.com/python/cpython/issues/126559) |
| **Escada** | E1 triagem |
| **Como apareceu** | Issue parada desde 2024-11-08, sem PR |
| **Status** | triado — **comportamento documentado**, recomendo fechar |
| **Data** | 2026-11-05 |

---

## 1. Sintoma

Enquanto uma thread roda `lista.sort()`, outra thread lendo `len(lista)` observa `0`, num build
free-threaded.

## 2. Repro mínimo

[`repro.py`](repro.py) — reduzido do MRE do grupo de pesquisa que abriu a issue: tirei o
aninhamento de threads e o caso `__str__`, que não mudam o mecanismo. Mantive a `Barrier`, que é
o que alinha as duas threads na janela certa.

## 3. Matriz

| Build (mesmo commit `534605904df`) | `len()` observado | Reproduz |
|---|---|---|
| free-threaded | `0` em **200/200** tentativas | sim |
| com GIL | `300` em 200/200 tentativas | não |

Nota: com a `Barrier`, não é intermitente — é **100% reproduzível**. O relato original mostrava
"found bug: 0" em algumas tentativas de dez; com duas threads e barreira, acerta sempre. Vale
registrar porque muda a leitura: não é corrida rara, é a janela inteira.

## 4. Bisect

Não cabe. Não é regressão: o comportamento é intencional e antigo. `colesbury` já apontou na
própria issue, em 2024-11-07, que isso existe "since at least Python 2.x days".

## 5. Análise

`list.sort()` troca `ob_item` por vazio durante a ordenação, para detectar mutação concorrente.
Em `Objects/listobject.c` do commit testado:

```c
3043:    saved_ob_item = self->ob_item;
3045:    Py_SET_SIZE(self, 0);           /* a lista fica vazia aqui */
         ...
3263:    FT_ATOMIC_STORE_PTR_RELEASE(self->ob_item, saved_ob_item);   /* restaura */
```

Com GIL isso é quase sempre invisível porque nenhuma outra thread roda durante o `sort` em C.
Sem GIL, a janela fica observável.

**E está documentado.** `Doc/builtins/stdtypes.rst:1725-1728`, na entrada de `list.sort`:

> CPython implementation detail: While a list is being sorted, the effect of attempting to mutate,
> or even inspect, the list is undefined. The C implementation of Python makes the list appear
> empty for the duration, and raises ValueError if it can detect that the list has been mutated
> during a sort.

Ler a lista durante um `sort` é explicitamente comportamento indefinido, e "aparece vazia" é
exatamente o que a doc descreve. O repro faz precisamente o que a doc diz que é indefinido.

Observação: o arquivo migrou de `Doc/library/stdtypes.rst` para `Doc/builtins/stdtypes.rst` no
`main` — o texto continua idêntico.

## 6. Veredito

- [x] **Comportamento esperado e documentado.**

Eu entrei nessa achando que fosse um bug de atomicidade do free-threading. Não é. É um detalhe de
implementação documentado há duas décadas, que o free-threading apenas tornou fácil de observar.

A discussão na issue já chegou nesse ponto: `colesbury` disse *"I don't think this is worth
changing"*, duas alternativas de correção foram propostas e recusadas por custo (lock no `__len__`
e um sentinela no campo de tamanho). O que sobra é mecânica de backlog: a issue está aberta há
dois anos sem nada pendente.

**Recomendação: fechar como comportamento documentado.** Sem patch e sem mudança de doc — a doc
já cobre o caso.

## 7. O que falta

Nada nesta. O valor desta ficha é o veredito negativo: ela gasta uma issue do backlog e evita que
a próxima pessoa refaça o mesmo caminho.

A issue aponta para [gh-126136](https://github.com/python/cpython/issues/126136) como a discussão
mais ampla sobre atomicidade de containers, que remete à seção de thread safety do
[PEP 703](https://peps.python.org/pep-0703/#container-thread-safety). Essa discussão é de design
e continua legítima — só não é esta issue.

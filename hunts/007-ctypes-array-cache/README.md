# Caçada 007 — cache de tipo de array do `ctypes` devolve tipos distintos

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython |
| **Issue upstream** | [gh-160978](https://github.com/python/cpython/issues/160978), aberta por `ngoldbaum` em 2026-10-30 |
| **Escada** | **E2 — fix dirigido**, primeiro desta série |
| **Status** | **PR aberto: [gh-161494](https://github.com/python/cpython/pull/161494)**, CLA assinado, 40 checks passando, aguardando review |
| **Data** | 2026-11-06 |

---

## 1. Por que este alvo, e não os outros

Comparei três candidatos antes de escolher, e o critério foi risco de o trabalho
ser jogado fora.

| Alvo | Situação | Veredito |
|---|---|---|
| [gh-129139](https://github.com/python/cpython/issues/129139) `__setstate__` | triagem minha já postada, causa raiz localizada | **descartado**: `Yhg1s` disse *"I'm not sure it's worth it"*. Fix pronto não vale nada se a decisão for não corrigir |
| [gh-161366](https://github.com/python/cpython/issues/161366) deadlock no gc | 0 comentários, parecia livre | **descartado por R5**: tem PR aberto, o `gh-161444`. Meu filtro `-linked:pr` mentiu de novo — é a terceira vez nesta série |
| **gh-160978** cache do ctypes | 0 comentários, sem PR, **quem reportou já apontou o sítio do fix** | **escolhido** |

Uma ponta solta que eu precisava resolver antes: o PR
[146269](https://github.com/python/cpython/pull/146269) da gh-129139 foi fechado
sem merge, e eu nunca tinha olhado por quê. Olhei: o autor é `ghost` — conta
deletada — e `head: null`, o fork sumiu. **Zero reviews, nenhuma objeção de
mantenedor.** Morreu de abandono, não de mérito. Útil saber, mas não muda o
problema do *"not worth it"*.

## 2. O bug

Invariante: para o mesmo par `(itemtype, length)`, `itemtype * length` tem que
devolver **sempre o mesmo objeto de tipo**. O `array_cache` em
`Modules/_ctypes/_ctypes.c` existe para isso.

Quando duas threads criam o mesmo tipo ao mesmo tempo, cada uma recebe um objeto
diferente, e aí sai o erro mais absurdo que eu vi hoje:

```
TypeError: expected c_int_Array_1 instance instead of c_int_Array_1
```

## 3. Repro, nos dois builds

[`repro.py`](repro.py), nos dois builds do mesmo commit `534605904df`:

| Caminho | GIL | free-threaded |
|---|---|---|
| 8 threads criando `c_int * n` | 0/400 | **397/400** |
| metaclasse com `__set_name__` (determinístico) | **falha** | **falha** |

O segundo caminho é o que a issue traz e é o mais importante: ele falha **também
no build padrão**, porque `__set_name__` roda código Python exatamente na janela
da corrida. Então isto não é bug só de free-threading.

## 4. Mecanismo

`PyCArrayType_from_ctype`, em `_ctypes.c`:

```c
    if (_PyDict_GetItemProxy(st->array_cache, key, &result) != 0) {
        Py_DECREF(key);
        return result;                 /* acerto no cache */
    }
    /* erro no cache */
    ...
    result = PyObject_CallFunction(...);           /* cria o tipo */
    ...
    if (PyDict_SetItemProxy(st, st->array_cache, key, result) < 0) { ... }
    return result;                                  /* devolve O NOSSO */
```

Check-then-act clássico. As duas threads erram o cache, as duas criam o tipo, a
segunda sobrescreve a entrada da primeira, e **cada uma devolve o objeto que ela
mesma criou**.

O cache guarda **proxy fraco** com um `DictRemover` que apaga a chave quando o
tipo morre — detalhe que o fix tem que preservar.

## 5. A restrição que manda no desenho

Não se pode segurar lock durante a criação do tipo, porque `PyObject_CallFunction`
roda **código Python arbitrário** — é precisamente o que o `__set_name__` do
repro explora. Lock ali convida reentrância e deadlock.

Logo a serialização tem que estar na **inserção**, não na criação. A primitiva
certa é `PyDict_SetDefaultRef`: insere se ausente e devolve referência forte ao
vencedor, atomicamente.

O fix ([`aplicar-fix.py`](aplicar-fix.py)) adiciona
`_PyDict_SetDefaultItemProxy`, versão de `PyDict_SetItemProxy` que não
sobrescreve entrada viva e devolve quem ficou no cache. Quem perde a corrida
descarta o tipo que criou e devolve o que já estava lá.

Caso de borda tratado: se a entrada cacheada estiver **morta** (proxy já
limpo), instala a nossa. Não é pior que o comportamento atual.

## 6. Validação

| Checagem | GIL | free-threaded |
|---|---|---|
| compila sem erro nem aviso novo | ok | ok |
| `repro.py` depois do fix | 0/400 e `a is b` True | **0/400** e `a is b` True |
| `test_ctypes` completo (648 testes) | SUCCESS | SUCCESS |
| `test_ctypes -R 3:3` (refleak) | — | **SUCCESS** |

O refleak check importa porque valida o manejo de refcount do helper novo, que é
onde um fix deste tipo costuma vazar.

### RED verificado — o teste falha sem o fix

Teste de regressão que passa sem a correção não vale nada. Revertido só o C,
recompilado e rodado:

Revertido o C nos **dois** builds, recompilado e rodado:

| Teste | GIL sem fix | GIL com fix | FT sem fix | FT com fix |
|---|---|---|---|---|
| `..._with_set_name` | **FAIL** | ok | **FAIL** | ok |
| `..._returns_identical_types` | ok | ok | **FAIL** (`6 != 1`) | ok |

As mensagens:

```
AssertionError: <class '...Item_Array_100'> is not <class '...Item_Array_100'>
AssertionError: 6 != 1
```

Por isso são **dois** testes, e a tabela mostra por quê: o determinístico
(`__set_name__`) é o único que falha no build com GIL, então é ele que protege o
fix no CI padrão; o concorrente cobre o sintoma original da issue, que só
aparece no free-threaded. Nenhum dos dois é redundante.

## 7. Identidade de commit — ponta solta da S0, agora fechada

Desde a S0 ficou em aberto se `thalesmoura13@gmail.com`, o email configurado
para commit, está vinculado à conta do GitHub. Importa agora porque **o CLA
casa por email**: assinado com uma identidade e commitado com outra, o
`python-cla-bot` barra o PR mesmo depois da assinatura.

Verificado: dos 20 commits mais recentes do repo, **zero** ficaram sem
atribuição — todos aparecem como `thalesmourabh`. O email está vinculado e o
CLA vai casar.

## 8. Estado técnico — tudo verificado

| Checagem | Resultado |
|---|---|
| `make patchcheck` | **limpo** — 3 arquivos, *"Misc/NEWS.d updated with `blurb` ... yes"*, nada de espaço em branco, nada de doc ou `configure` pendente |
| commit local | `5ed12c7d340`, branch `gh-160978-ctypes-array-cache` |
| atraso em relação a `upstream/main` | 10 commits |
| `_ctypes` / `test_ctypes` mudaram upstream desde a base? | **não** — aplica sem conflito |
| email de commit vinculado à conta | sim (item 7) |

O `patchcheck` só acusou o blurb como ausente **antes** do commit local, porque
ele olha o diff contra `upstream/main` e arquivo untracked não entra. Depois do
commit, passou.

## 9. PR aberto, CLA resolvido

[python/cpython#161494](https://github.com/python/cpython/pull/161494), aberto em
2026-11-06 com aprovação explícita.

| | |
|---|---|
| estado | OPEN, label `awaiting review` aplicada pelo bedevere |
| autor | `thalesmourabh` |
| diff | +122 −3, exatamente os 3 arquivos |
| CI | rodando |
| **check `CLA Signing`** | **success** — *"The Contributor License Agreement is signed"* |
| checks | **40 passando, 0 falhando**, 15 em andamento |

O `python-cla-bot` comentou nomeando o email que falta:

> The following commit authors need to sign the Contributor License Agreement:
> * `thalesmoura13@gmail.com`

### Resolvido, e vale guardar a lição

**O bot casa pelo email do autor do commit**, não pela conta do GitHub. O commit
foi autorado com `thalesmoura13@gmail.com`, que é o `user.email` global. A
complicação: o email primário da conta Google tinha mudado para
`thalesmoura.ti@gmail.com`, deixando o antigo como secundário — e os dois lados
ficaram em identidades diferentes.

Resolvido **do lado do `cla.python.org`**, não por force-push. Isso importa:
force-push num PR do CPython dispara mais de cinquenta jobs de CI na
infraestrutura deles, e teria sido tentativa e erro, porque eu não tinha como
descobrir daqui sob qual email a assinatura estava registrada — o token do `gh`
não tem o escopo `user`, e o bot só informa o email do commit, não o registrado.

**Regra para as próximas:** o email do `git config user.email` tem que ser o
mesmo registrado no CLA. Trocar email primário de conta Google quebra isso sem
aviso. Conferir antes de abrir PR custa um comando; descobrir depois custa um
ciclo de CI.

## 10. O que falta

**O CLA.** O Thales tem 0 PRs no CPython e o
[Contributor License Agreement](https://cla.python.org/) não está assinado.
É pré-requisito para qualquer merge, exige a identidade dele, e **não há como eu
fazer por ele**. O `python-cla-bot` barra o PR até lá.

Depois disso: `make patchcheck`, branch, PR referenciando a gh-160978.

# Caçada 004 — contexto do `decimal` compartilhado entre threads

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython |
| **Issue upstream** | [gh-149142](https://github.com/python/cpython/issues/149142), [gh-141148](https://github.com/python/cpython/issues/141148) — **já existiam** |
| **Escada** | E3 tentativa de bug novo → **não era novo** |
| **Como apareceu** | Primeiro achado do aparato da S3 (stress test próprio + ThreadSanitizer) |
| **Status** | **encerrado sem reporte.** Já reportado upstream, com PR aberto |
| **Data** | 2026-11-06 |

---

## 1. Veredito, primeiro

**Nada aqui foi reportado, e nada deve ser.** Os dois defeitos que encontrei já
têm issue aberta e PR em andamento. A regra R5 do plano — não pegar issue que já
tem PR aberto — fecha a questão.

Esta ficha existe porque **veredito negativo bem documentado vale mais que
gaveta vazia**: ela registra duas vezes em que eu estava errado, e uma correção
de método que muda a S3 daqui para frente.

## 2. O que o aparato produziu

Primeira rodada dos stress tests nos três builds do mesmo commit
(`534605904df`):

| Teste | GIL | free-threaded | FT + TSan |
|---|---|---|---|
| `test_zoneinfo.py` | ok | **FAIL** | **FAIL** |
| `test_decimal.py` | ok | ok | **9 avisos do TSan** |
| `test_hashlib.py` | ok | ok | ok |

Duas pistas. Nenhuma sobreviveu — por motivos diferentes, e os dois motivos
ensinam algo.

## 3. Pista 1 — zoneinfo: **o teste estava errado, não o CPython**

`test_racing_constructor_many_keys` acusou **35 objetos distintos** para
`America/Sao_Paulo`, onde a doc garante 1:

> barring cache invalidation via `ZoneInfo.clear_cache`, for all values of key,
> the following assertion will always be true: `a = ZoneInfo(key)`;
> `b = ZoneInfo(key)`; `assert a is b`

Parecia violação grave de garantia documentada. Antes de escrever uma linha de
comentário, rodei o diagnóstico mais simples possível: **sem thread nenhuma.**

```
1 thread, 5 chaves, SEM segurar ref  -> 5 ids distintos    (correto)
1 thread, 1 chave,  SEM segurar ref  -> 1 id               (correto)
10 threads, SEGURANDO ref            -> 1 por chave nos DOIS builds
```

O defeito era meu. O teste fazia `add(id(ZoneInfo(k)))` e soltava o objeto na
mesma hora. Aí:

1. o `_weak_cache` solta o objeto quando ninguém referencia — é cache fraco, é
   o contrato dele;
2. o cache forte guarda no máximo 8 entradas, em lista ligada LRU no estado do
   módulo, então com 10 threads batendo a chave sai e volta;
3. objeto morto → `id()` reciclado → a contagem de 35 é ficção.

O trecho da doc **segura `a`** enquanto constrói `b`. Teste que não segura não
mede a invariante documentada; mede taxa de acerto de cache, que ninguém
prometeu. O outro teste do mesmo arquivo, que segurava as referências, passou —
e era essa a dica, que eu deveria ter lido antes de me animar.

Corrigido em [`tools/stress/test_zoneinfo.py`](../../tools/stress/test_zoneinfo.py),
com o erro anotado no docstring para não voltar.

Nota lateral, registrada e **não** reportada: no build com GIL a versão sem
segurar referência dá 1 e no free-threaded dá 35. É diferença real de eficácia
do cache sob contenção — mais parsing de TZif por chamada. Mas eficácia de
cache não é garantia documentada, não tenho benchmark, e abrir isso renderia
"já sabíamos". Fica aqui.

## 4. Pista 2 — decimal: real, e já reportado

O TSan apontou corrida de escrita-escrita em `Modules/_decimal/_decimal.c:606`:

```c
ctx->status |= status;      /* read-modify-write sem sincronizacao */
```

Duas threads, `Decimal + Decimal` via `sum()`, mesmo endereço. E **`decimal` não
está em nenhum dos dois arquivos de supressão do TSan**
(`Tools/tsan/suppressions.txt`, `suppressions_free_threading.txt`) — então não é
corrida conhecida-e-silenciada.

### Por que o contexto é compartilhado

Investiguei a causa antes de reportar, e aqui a investigação mudou o veredito.

`_decimal` é compilado com `WITH_DECIMAL_CONTEXTVAR` nos dois builds, e guarda o
contexto corrente num `ContextVar`. O que difere é
**`sys.flags.thread_inherit_context`**:

```
GIL : 0
FT  : 1
```

Com o flag ligado, `threading.Thread` começa com `copy_context()` do criador
(`Lib/threading.py:1133`) em vez de `Context()` vazio. A cópia carrega a
**mesma** referência ao objeto de contexto do `decimal`. Resultado medido:

```
GIL : 5 threads -> 5 contextos distintos, nenhum compartilhado com a main
FT  : 5 threads -> 1 contexto, compartilhado com a main
      precisao gravada numa thread -> observada na outra
      flag Inexact ligada numa thread -> vista por quem nao fez conta inexata
```

### E aí a parte que quase me fez errar feio

Testei se um `ContextVar` **comum** também vaza. Vaza: thread nova lê
`VALOR-DA-MAIN` em vez do default, e `copy_context()` dentro dela tem 1 entrada
em vez de 0. Por alguns minutos isso pareceu bug grave em `contextvars`, a base
de propagação de contexto do asyncio inteiro.

**Não é bug. É intencional e documentado.** `Doc/whatsnew/3.14.rst`, sobre
`thread_inherit_context`:

> This flag defaults to true for the free-threaded build and false for the
> GIL-enabled build.

E o mesmo parágrafo cita o `decimal` pelo nome:

> It also affects other modules that use context variables, such as the
> :mod:`decimal` context manager.

Ou seja: o comportamento que eu "descobri" está escrito no What's New, com o
módulo afetado nomeado. Se eu tivesse postado, seria o comentário mais
embaraçoso do caderno.

### O que sobrou, e por que também não vai

Sobraram dois defeitos de verdade:

1. **A corrida em si.** `ctx->status |= status` sem sincronização sobre objeto
   que agora é compartilhado por padrão.
2. **A doc do `decimal` está desatualizada.** `Doc/library/decimal.rst:999`
   ainda diz *"Each thread has its own current context"*, e :1005 / :1010
   dizem *"for the active thread"*. No build free-threaded com configuração
   padrão isso é falso — eu medi.

Os dois já estão cobertos, e melhor do que eu cobri:

| Upstream | O que é | Estado |
|---|---|---|
| [gh-149142](https://github.com/python/cpython/issues/149142) | a corrida no primitivo, **com a tabela de todos os sítios afetados** (linhas 616, 617, 625, 629, 715, 744, 747, 1407, 1421) | aberta, labels `type-bug` `docs` `topic-free-threading` |
| [gh-141148](https://github.com/python/cpython/issues/141148) | compartilhamento implícito via `contextvars` | aberta, 16 comentários |
| [PR 150598](https://github.com/python/cpython/pull/150598) | corrige a corrida de `mpd_context_t.status` | **aberto** |
| [PR 146482](https://github.com/python/cpython/pull/146482) | garante cópia nova do contexto por thread/task | **aberto** |
| [PR 151953](https://github.com/python/cpython/pull/151953) | `getcontext()` devolvendo cópia nova | **aberto** |

A gh-149142 chega a dizer, sobre a minha linha: *"#141148 + #146482 fix the
implicit sharing case (inherited context via contextvars). This issue is for the
underlying primitive"*. Está mais bem triada do que eu triei.

**R5 fecha:** três PRs abertos. Não se toca.

## 5. A correção de método, que é o que esta ficha entrega

Escolhi `decimal`, `zoneinfo` e `hashlib` por um critério que parecia bom:
**módulo em C, com estado compartilhado, e sem nenhum arquivo em
`Lib/test/test_free_threading/`**. Dos 59 arquivos lá, nenhum cobre esses três.

**O critério é fraco, e agora sei por quê.** O `decimal` tem zero arquivos de
teste de free-threading e **três PRs abertos** sobre corridas. Os mantenedores
rastreiam corrida por relatório de TSan e por auditoria de código, não por
cobertura de arquivo de teste. Então:

> Ausência de arquivo em `test_free_threading/` **não** indica território
> inexplorado. Indica apenas que o teste de regressão ainda não foi escrito —
> o que às vezes é consequência de o fix ainda estar em revisão.

**Novo critério, aplicado antes de escrever o teste e não depois:**

1. cruzar o módulo candidato contra issues **e PRs abertos**, não só issues;
2. ler `Doc/whatsnew/` da versão corrente procurando o módulo — mudança
   intencional recente é a explicação mais provável de divergência entre
   builds;
3. só então escrever o stress test.

Os passos 1 e 2 custam dois minutos. Custaram, aqui, depois de eu já ter
gastado o trabalho.

## 6. O que o aparato provou sobre si mesmo

Isto não é consolo: o aparato funcionou exatamente como o projeto previa.

- O build free-threaded + TSan **detecta e simboliza** corrida de verdade —
  verificado contra uma corrida conhecida antes de rodar qualquer coisa, com
  `arquivo:linha:coluna`.
- O teste diferencial nos três builds **separou** os casos sem ambiguidade:
  zoneinfo falhava só no free-threaded (e era meu bug), decimal só acusava sob
  TSan (e era real).
- Na primeira rodada de três módulos, **um** tinha corrida real em C. A veia
  existe.

O que faltou não foi aparato; foi **seleção de alvo**. Corrigido no item 5.

## 7. O que falta

Próximo alvo tem que passar pelo filtro novo antes de virar teste. Candidatos
que ainda não cruzei contra PRs abertos: `array`, `struct` (cache de formato),
`typing` (`_tp_cache`), `enum` (mapas lazy), `codecs` (registro lazy).

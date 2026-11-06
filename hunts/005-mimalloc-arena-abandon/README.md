# Caçada 005 — assertion do mimalloc ao abandonar segmento de arena

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython (e possivelmente microsoft/mimalloc) |
| **Issue upstream** | nenhuma. **Não reportado** |
| **Escada** | E3 bug novo, achado por aparato |
| **Como apareceu** | Baseline da suíte no build free-threaded, e depois o loop da S3.5 |
| **Status** | **lead aberto, não reportável** — 2 observações, 0/12 em tentativa deliberada |
| **Data** | 2026-11-06 |

---

## 1. Veredito, primeiro

**Não foi reportado e não deve ser, no estado atual.** Não tenho repro.

O que eu tenho: duas ocorrências de uma assertion de alocador, em condições
diferentes, e **zero** em doze tentativas deliberadas. Isso é lead, não achado.

Esta ficha existe para registrar o lead com precisão suficiente para alguém
(eu, depois) retomar, e para registrar um erro meu de método que vale mais que
o lead.

## 2. O que acontece

Assertion em `Objects/mimalloc/arena-abandon.c:162`, no fim de
`_mi_arena_segment_mark_abandoned`:

```
mimalloc: assertion failed: at "Objects/mimalloc/arena-abandon.c":162,
  _mi_arena_segment_mark_abandoned
assertion: "_mi_bitmap_is_claimed(arena->blocks_inuse, arena->field_count, 1, bitmap_idx)"
Fatal Python error: Aborted
```

O código:

```c
void _mi_arena_segment_mark_abandoned(mi_segment_t* segment)
{
  ...
  const bool was_unmarked = _mi_bitmap_claim(arena->blocks_abandoned, ..., bitmap_idx, NULL);
  if (was_unmarked) { mi_atomic_increment_relaxed(&subproc->abandoned_count); }
  mi_assert_internal(was_unmarked);
  mi_assert_internal(_mi_bitmap_is_claimed(arena->blocks_inuse, arena->field_count, 1, bitmap_idx));
}                                                                    /* <-- 162 */
```

Leitura: um segmento está sendo marcado como abandonado, mas o bitmap
`blocks_inuse` da arena diz que aquele bloco **não está em uso**. O bloco de
arena que dá suporte ao segmento já foi devolvido enquanto o segmento ainda
está sendo abandonado.

Abandono acontece quando uma thread morre ainda possuindo segmentos.
`arena.c:740` (`_mi_bitmap_unclaim_across(arena->blocks_inuse, ...)`) é onde
`blocks_inuse` é limpo. Hipótese de mecanismo, **não verificada**: liberação de
bloco de arena concorrente com abandono de segmento no mesmo bloco.

Num build sem `--with-pydebug` a assertion não existe. Se o estado está de fato
inconsistente, lá ele passa silencioso.

## 3. As duas observações

| | Build | Compilador | Arquivo | Método | Comando |
|---|---|---|---|---|---|
| 1 | free-threaded | GCC 15.2.0 | `test_free_threading.test_generators` | `test_concurrent_write` | suíte completa, `-j10` |
| 2 | free-threaded + TSan | Clang 21.1.8 | `test_free_threading.test_str` | `test_intern_unowned_string` | `-F --parallel-threads=4 -j10`, após 66 s |

O que isso sugere: **não está presa a teste nenhum.** Dois arquivos, dois
métodos, dois compiladores, e sem precisar de TSan — a primeira foi no build
sem sanitizer. O denominador comum é concorrência.

## 4. E aqui o erro, que é a parte útil

Depois da observação 2 eu disse que o loop "reproduziu" e dei o número 66 s
como se fosse taxa. **Estava errado.** Fui medir:

| Tentativa | Build | Resultado |
|---|---|---|
| suíte, 3 × 240 s | free-threaded | **0/3** |
| suíte, 3 × 240 s | free-threaded + TSan | **0/3** |
| repro autônomo, 3 × 180 s | free-threaded | **0/3** |
| repro autônomo, 3 × 180 s | free-threaded + TSan | **0/3** |

**0 de 12.** Mesmo comando da observação 2, mesmo build, mesmo teste: limpo.

Depois disso, mais uma fatia de 10 min com o caçador longo: também limpa.
Acumulado de caça deliberada por teste único: **~58 min, 0 ocorrências.**

### Segundo erro: 37 min de caça que não mediram nada

A primeira tentativa de caçar com a suíte inteira reportou **0 ocorrências em
37 min, em 9 passadas**. Esse número é **inválido**, e o motivo é bug do meu
aparato.

Cada passada durou ~250 s, quando uma passada completa da suíte leva ~7 min
(426 s). O sinal estava ali e eu quase não olhei: `-F` implica `--failfast`, e
o build FT tem a falha ambiental do `test_perf_profiler` (o `perf` do kernel do
WSL não aceita a flag `-j` que o CPython passa para `perf inject`). Então toda
passada parava **no mesmo ponto**, em ~250 s, antes de a suíte terminar.

Foram **9 passadas truncadas no mesmo lugar, zero passadas completas.** O
script reportou "limpo" nas nove, e eu teria registrado isso como evidência
contra a hipótese — quando a hipótese não foi testada nem uma vez.

Corrigido com `-x test_perf_profiler` no modo `SUITE`. O
`test_free_threading.test_generators` **não** entra na exclusão: o crash dele é
o que se procura, e parar nele é o comportamento certo. O tally antigo foi
renomeado para `tally-ft-SUITE.INVALIDO.tsv` em vez de apagado, para o erro
ficar no registro.

A lição é parente da anterior, mas não é a mesma: antes eu confundi **amostra
pequena** com taxa; aqui eu não conferi se o aparato **estava medindo o que eu
pensava**. Nove resultados idênticos com duração quase igual deveriam ter me
feito desconfiar na hora.

### Hipótese sobre o gatilho, não provada

Olhando de onde vieram as duas observações:

- a **1** aconteceu **durante a suíte completa**;
- a **2** foi a **primeira** execução de teste único, logo **depois** de a suíte
  completa sob TSan terminar.

E repetição de teste único desde então: **0 em ~26 min**.

Isso sugere que o gatilho precisa da **variedade da suíte** — muitos padrões de
alocação e muitas threads em arquivos diferentes — e não de repetir um caso.
Com n=2 isso não dá para afirmar; pode ser só variância de corrida rara. Mas a
suíte custa 7 min no build FT, então a hipótese é barata de testar, e o
`cacador-longo.sh` ganhou o alvo `SUITE` para isso.

Uma ocorrência não é taxa. Chamei de reprodução o que era amostra única, e o
número que eu reportei não sobreviveu à primeira verificação.

### A correção de método

Fazendo a conta que eu devia ter feito antes: ~2 ocorrências em ~1 h de
execução pesada é da ordem de **1 a cada 30 min**. Um trial de 4 min tem
chance baixa de pegar isso, e doze trials de 4 min somam 48 min — ou seja, meu
"0/12" é perfeitamente compatível com a corrida existir.

> Para corrida rara, **sequência de trials curtos limpos não é evidência de
> ausência**. O trial tem que ser longo o bastante para que a ausência
> signifique algo, e a unidade de medida é tempo acumulado, não número de
> tentativas.

Daí o [`cacador-longo.sh`](../../tools/stress/cacador-longo.sh): acumula tempo
e ocorrências num arquivo de tally que sobrevive entre execuções, para a taxa
sair de horas em vez de minutos.

## 5. Por que isso seria relevante se virar repro

O arquivo que falha tem **um único commit** na história do CPython:

```
aff7a2e23bd6ed68fa15c1ceda94a2fdd7f8cf7f
Donghee Na, 2026-10-21
gh-159111: Update vendored mimalloc to v2.5.2 (gh-159112)
```

`arena-abandon.c` não existia antes — em 2.1.2 esse código morava em
`arena.c`. O bump foi de **v2.1.2 direto para v2.5.2**.

Dois agravantes:

- O bump tem labels `3.14` e `3.15`, e o título da
  [gh-161420](https://github.com/python/cpython/issues/161420) confirma que o
  2.5.2 **já está em 3.14.10 e 3.15.2 liberados**. Não é só `main`.
- A gh-161420 é outro sintoma do mesmo bump (retenção de memória, picos de
  10 GB), e o autor dela reproduziu no **mimalloc puro, sem CPython**, e
  reportou upstream. É o modelo de como isso se encaminha corretamente.

### De quem é o bug, se existir

Não sei, e não vou chutar:

- `arena-abandon.c` é **pristino do upstream** v2.5.2, sem marca `CPython`.
- Mas `segment.c`, `free.c`, `init.c`, `heap.c` e `page.c` **têm** patch do
  CPython reaplicado no bump, e segmento e free participam deste caminho.

Então pode ser bug do mimalloc 2.5.2 ou da interação com os patches
reaplicados. Determinar isso é trabalho a mais.

## 6. Cruzamento — nada igual

Aplicado o filtro da caçada 004, contra issues **e** PRs:

| Onde | Busca | Resultado |
|---|---|---|
| python/cpython | `arena-abandon`, `_mi_arena_segment_mark_abandoned`, `mimalloc`, `test_concurrent_write` | 8 issues de mimalloc abertas, **nenhuma é esta** |
| microsoft/mimalloc | `arena-abandon`, `blocks_inuse`, `mark_abandoned` | nada com esta assertion |

A mais próxima no mimalloc é a
[#1306](https://github.com/microsoft/mimalloc/issues/1306), assertion no
caminho de abandono sob carga multi-thread — mas é a função do **v3**
(`_mi_arenas_page_abandon`, assertion `heap==_mi_theap_heap(current_theap)`),
fechada como corrigida no v3.4.4. O CPython está na linha **v2**. Se existe
análogo no v2, pode simplesmente não ter sido corrigido lá.

## 7. O build de controle — duas tentativas falhas

O objetivo era mostrar que o bump introduziu a assertion. Não consegui montar o
build de controle:

1. **Reverter só `Objects/mimalloc` + `Include/internal/mimalloc`.** Não
   compila: `pycore_mimalloc.h:70` usa `mi_subproc_t`, tipo que só existe no
   2.5.2. Código do CPython fora do vendor depende da versão nova.
2. **Reverter o commit inteiro do bump sobre o `main`.** Dá conflito —
   `pycore_mimalloc.h` foi mexido depois do bump.

Abandonei a abordagem, e pensando melhor ela estava errada de origem: árvore
sintética com revert em cima do `main` é árvore que ninguém distribui, e vale
menos como prova do que dois commits reais adjacentes.

Substituída por [`bisect-mimalloc.sh`](../../tools/stress/bisect-mimalloc.sh):
build de `aff7a2e23bd^` (2.1.2) contra `aff7a2e23bd` (2.5.2). Entre esses dois
a única diferença é o bump.

**Não executado**, e de propósito: bisect sem oráculo confiável não conclui
nada. "Limpo nos dois" seria o resultado mais provável hoje, e eu leria errado.
Primeiro a taxa, depois o bisect.

## 8. Canal — avaliação da R1

A regra R1 manda parar se é corrupção de memória ou crash alcançável a partir
de entrada não confiável. Avaliado: **não é caso de canal de segurança**, e
quando virar reportável vai como issue pública.

Razões:

- O gatilho é código Python criando e destruindo thread sob alocação, não
  entrada não confiável.
- É build marcado como experimental.
- É disparado pela **própria suíte de testes do projeto**, que o CI deles roda.
- No CPython, as issues de crash de mimalloc são todas públicas — por exemplo
  [gh-158529](https://github.com/python/cpython/issues/158529) ("mimalloc
  crashes on Android x86_64"). Precedente do próprio projeto.

A parte desconfortável é que bitmap de arena inconsistente é metadado de heap,
e em release isso poderia ser corrupção real. Mas eu **não** estabeleci que
build de release corrompe — tenho uma assertion de build de debug, que é
evidência de invariante violada, não prova de corrupção explorável. Dizer mais
que isso seria exagero.

## 9. O que falta, em ordem

1. **Taxa.** `cacador-longo.sh` acumulando horas. Sem isso nada avança.
2. Com taxa: rodar o `bisect-mimalloc.sh`.
3. Com bisect: decidir se o reporte vai para o CPython, para o mimalloc, ou
   para os dois, conforme o item 5.
4. Repro autônomo. O que escrevi (criação e morte de thread com objetos
   sobrevivendo) deu 0/6 — a hipótese de mecanismo pode estar errada, ou a
   pressão insuficiente.

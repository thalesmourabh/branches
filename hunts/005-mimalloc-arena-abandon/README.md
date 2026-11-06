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

### Terceiro erro: o mesmo problema um nível abaixo

Com o `-x test_perf_profiler` aplicado, a caça rodou de novo e deu
`358 s`, `198 s`, `1800 s` — e o script chamou **as três de "limpo"**.

Só a de 1800 s é caça de verdade: 1800 s é a fatia inteira, ou seja rodou o
tempo todo sem parar. As de 358 s e 198 s **terminaram antes**, o que com
`--failfast` significa que pararam em alguma falha — e o script não registrava
**por quê**. Somou as três como 39 min de caça quando ~30 min eram caça e
~9 min eram fatia truncada por outra coisa.

É o mesmo erro do parágrafo anterior, um nível abaixo: eu corrigi a causa
específica (`test_perf_profiler`) em vez de corrigir a **cegueira do
instrumento**. Enquanto o script não soubesse distinguir "rodou a fatia toda"
de "parou antes", qualquer falha nova reintroduzia o problema.

Corrigido de verdade agora. O caçador:

- grava sempre o rabo da saída, para dar para saber por que uma passada acabou;
- marca a fatia como `completa=sim/NAO` comparando duração medida com a
  duração esperada;
- classifica fatia curta como **`TRUNCADA`**, não como `limpo`, e registra em
  que teste parou;
- **não soma fatia truncada** no tempo de caça;
- e quando não acha nada, diz explicitamente que `0 em N min` **não é
  ausência**, é só o limite inferior do que aquela medição alcança.

Os dois tallies anteriores ficam no repositório —
`tally-INVALIDO-passadas-truncadas.tsv` e o de formato antigo — em vez de
apagados.

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

## 8b. Tempo de caça válido, e o veredito de esforço

Com o instrumento consertado, o que conta como caça de verdade:

| Regime | Tempo válido | Ocorrências |
|---|---|---|
| suíte completa, fatia inteira | 90 min | 0 |
| teste único, `-F --parallel-threads=4` | 58 min | 0 |
| **total** | **~2 h 28 min** | **0** |

Mais tudo o que foi descartado por fatia truncada, que não entra na conta.

Isso derruba minha própria estimativa inicial. Eu tinha calculado "~1 a cada
30 min" a partir das duas observações; duas horas e meia de caça dirigida com
zero ocorrências dizem que a frequência real é **bem menor que isso**, ou que
depende de alguma condição que eu não identifiquei.

Candidata para a condição, não testada a fundo: as duas observações
aconteceram em processo **recém-iniciado depois de uma carga longa anterior**
(a observação 1 durante a suíte completa; a 2 na primeira execução logo depois
de a suíte sob TSan terminar). Pode ser dependência de estado de fragmentação
de arena, que repetição em processo novo não reproduz.

### Última tentativa, derivada do mecanismo

Em vez de mais força bruta, uma tentativa raciocinada: a assertion diz que
`blocks_inuse` **não** está claimed. `blocks_inuse` é limpo em `arena.c:740`,
no caminho de liberar bloco de arena — ou seja, o parceiro da corrida é o
**purge de arena**. Forçando purge imediato, esse caminho roda o mais rápido
possível:

```
MIMALLOC_PURGE_DELAY=0        # purge imediato (default 10ms)
MIMALLOC_ARENA_PURGE_MULT=1   # sem multiplicador de atraso (default 10)
```

O mimalloc lê essas opções do ambiente nativamente, e o autor da gh-161420 usou
`MIMALLOC_PURGE_DELAY=0` com CPython exatamente assim.

**Primeiro resultado, e eu o interpretei errado.**

| Build | Teste | Resultado |
|---|---|---|
| FT + TSan | `test_str` | limpo, fatia completa de 600 s |
| FT | `test_generators` | truncada em 166 s — parou no próprio teste, **sem** a assertion |

Com esses dois eu declarei a hipótese do purge "não confirmada" e **fechei a
caçada**. Foi precoce, em duas frentes.

### Quarto erro: fechei um passo antes da reprodução

Fui investigar por que o `test_generators` tinha parado em 166 s. Rodei o mesmo
comando três vezes, **com purge ligado**, capturando a saída inteira:

| Rodada | Duração | Desfecho |
|---|---|---|
| 1 | **101 s** | **`mimalloc: assertion failed` em `arena-abandon.c:162`, no `test_concurrent_write`** |
| 2 | 271 s | `AssertionError: 0 != 1` em `test_concurrent_gi_frame` |
| 3 | 244 s | idem |

**Reproduziu.** Em 101 s, no `test_concurrent_write` — exatamente o teste da
observação 1. E reproduziu **com o purge ligado**, o que faz do meu "não
confirmou" uma conclusão tirada de duas amostras, logo antes de a terceira
contradizer.

Somando as quatro execuções com purge no `test_generators`: **1 assertion em
~13 min**, contra **0 em 2 h 28** de tudo o que eu tentei antes.

### E o quinto erro, que é o maior dos cinco

Eu passei a maior parte da caça no **`test_str`** e na **suíte inteira**. Nenhum
dos dois reproduziu.

A observação 1 — a primeira de todas, do baseline — foi em
`test_free_threading.test_generators`, método `test_concurrent_write`. **O alvo
certo estava apontado desde o começo e eu fui atrás do outro.** Persegui o
alvo da observação 2 (`test_str`, que foi onde a segunda ocorrência caiu) e
depois a suíte, quando a primeira ocorrência já nomeava o lugar.

As ~2 h 28 de caça não foram caça no lugar errado por falta de informação;
foram caça no lugar errado tendo a informação. É um erro de leitura das minhas
próprias notas, não de método de medição.

Com isso a caçada **reabre**, e com oráculo:

```bash
cd ~/src/cpython-ft
MIMALLOC_PURGE_DELAY=0 MIMALLOC_ARENA_PURGE_MULT=1 \
  ./python -m test test_free_threading.test_generators \
      -F --parallel-threads=4 -j10 -W
```

Está rodando experimento controlado de 5 execuções por braço (purge ligado vs.
default) para saber se o purge realmente ajuda ou se foi coincidência, e para
ter taxa dos dois lados.

### Achado lateral: `test_concurrent_gi_frame`

Duas das três rodadas acima falharam com `AssertionError: 0 != 1` em
`test_concurrent_gi_frame` — defeito **diferente** e mais frequente que a
assertion do mimalloc. Ver seção 10.

## 9. O que falta, em ordem

1. **Taxa.** `cacador-longo.sh` acumulando horas. Sem isso nada avança.
2. Com taxa: rodar o `bisect-mimalloc.sh`.
3. Com bisect: decidir se o reporte vai para o CPython, para o mimalloc, ou
   para os dois, conforme o item 5.
4. Repro autônomo. O que escrevi (criação e morte de thread com objetos
   sobrevivendo) deu 0/6 — a hipótese de mecanismo pode estar errada, ou a
   pressão insuficiente.

---

## 10. Achado lateral — `test_concurrent_gi_frame` falha com `0 != 1`

Mais frequente que a assertion do mimalloc: **2 de 3** rodadas de investigação,
e provavelmente também a fatia truncada de 166 s.

O teste, em `Lib/test/test_free_threading/test_generators.py`:

```python
def test_concurrent_gi_frame(self):
    frames = set()
    def gen():
        for i in range(10000):
            yield i
    g = gen()
    done = threading.Event()

    def runner():
        for _ in g:
            pass
        done.set()

    def reader():
        while not done.is_set():
            frame = g.gi_frame
            if frame:
                frame.f_code
                frame.f_locals
                frames.add(frame)
        self.assertIsNone(g.gi_frame)

    threading_helper.run_concurrently([runner, reader])
    self.assertEqual(len(frames), 1)      # <-- 0 != 1 falha aqui
```

`0 != 1` significa `len(frames) == 0`: o `reader` nunca guardou frame nenhum.

**Hipótese:** corrida de desenho do teste, não bug do CPython. Se o `runner`
termina os 10.000 yields antes de o `reader` chegar no primeiro
`while not done.is_set()`, o corpo do laço não roda nenhuma vez, `frames` fica
vazio, e a asserção final falha. O teste assume um escalonamento que não é
garantido.

**Status da hipótese: NÃO confirmada.** Medi em processo isolado, 300
tentativas no build free-threaded:

```
frames vazio (0 != 1):  0  (0.0%)
reader com ZERO voltas: 0
voltas do reader: min=271 max=103055
```

Ou seja: sozinho, o `reader` sempre roda pelo menos 271 voltas e nunca falha.
A falha precisa da inanição que o `--parallel-threads=4 -j10` cria — ~40
threads disputando 10 núcleos. Isso é **consistente** com a hipótese, mas não a
prova: eu ainda não observei diretamente o `reader` com zero voltas.

O teste de sobrecarga está escrito (24 cópias simultâneas do script de
mecanismo) e **não foi executado ainda**, para não corromper o experimento de
purge que está rodando — ele mede taxa sob carga definida, e 24 processos
extras invalidariam a medição.

### Procedência

| | |
|---|---|
| Teste introduzido por | [PR 156037](https://github.com/python/cpython/pull/156037), Kumar Aditya, merged 2026-09-02 |
| Para a issue | [gh-144446](https://github.com/python/cpython/issues/144446) *"Data races with frame objects"* — **ainda aberta** |
| Primeira tag | `v3.16.0a1` |
| Reportado como instável? | nada encontrado em issues nem PRs |

Se a hipótese se confirmar, é reporte pequeno e de baixa controvérsia: teste
instável, com mecanismo explicado e correção óbvia (barreira, ou asserção que
tolere o caso de o reader não ser escalonado). Seria candidato melhor a
primeira contribuição do que a assertion do mimalloc, justamente por ser
pequeno e verificável.

**Nada reportado.** A hipótese precisa de confirmação direta primeiro — e o
registro desta caçada já mostra o que acontece quando eu reporto antes de
medir.

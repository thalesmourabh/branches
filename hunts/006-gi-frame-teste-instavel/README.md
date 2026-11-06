# Caçada 006 — `test_concurrent_gi_frame` é teste instável

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython |
| **Issue upstream** | [gh-161489](https://github.com/python/cpython/issues/161489) — **aberta por mim em 2026-11-06** |
| **Escada** | E3 achado por aparato |
| **Como apareceu** | Efeito colateral da caçada [005](../005-mimalloc-arena-abandon/), ao investigar por que uma fatia de caça terminava cedo |
| **Status** | **reportada.** Mecanismo confirmado por instrumentação direta e por repro autônomo |
| **Data** | 2026-11-06 |

---

## 1. Veredito

`Lib/test/test_free_threading/test_generators.py::TestFTGenerators::test_concurrent_gi_frame`
falha de forma intermitente sob `--parallel-threads`. **É defeito do teste, não
do CPython.** A asserção final exige um escalonamento que o teste não garante.

Diferente da caçada 005, aqui eu **não** estou chutando: o mecanismo foi
confirmado medindo o estado interno no momento da falha.

## 2. Reprodução, com taxa medida

```bash
cd <build free-threaded com --with-pydebug>
./python -m test test_free_threading.test_generators -F --parallel-threads=4 -j10 -W
```

| | |
|---|---|
| Reproduções | **5 de 10** execuções |
| Tempo até falhar | 126 s, 160 s, 320 s, 368 s, 391 s |
| Build | `--with-pydebug --disable-gil`, GCC 15.2.0, commit `534605904df` |
| Sensível a `MIMALLOC_PURGE_DELAY`? | não — 2/5 com purge forçado, 3/5 sem |

Falha sempre igual:

```
AssertionError: 0 != 1
FAIL: test_concurrent_gi_frame (test.test_free_threading.test_generators.TestFTGenerators.test_concurrent_gi_frame)
```

## 3. O teste

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
    self.assertEqual(len(frames), 1)      # <-- 0 != 1
```

`0 != 1` só pode significar `len(frames) == 0`.

## 4. Mecanismo — confirmado, não inferido

Instrumentei o próprio teste no worktree de build (patch local, com restauração
automática por `trap`), para gravar na falha quantas voltas o `reader` deu e
quantas vezes `gi_frame` veio não-`None`. Primeira falha capturada:

```
DIAG frames=0 voltas=0 nao_none=0
```

**`voltas=0`.** O `reader` **não executou o corpo do laço nenhuma vez**.

Ou seja: o `runner` consumiu os 10.000 `yield` e chamou `done.set()` **antes**
de o `reader` chegar ao primeiro `while not done.is_set()`. Com o laço nunca
entrando, `frames` fica vazio e `assertEqual(len(frames), 1)` falha.

Isso descarta a leitura alternativa — que seria grave — de `gi_frame` devolver
`None` para um gerador vivo. Se fosse isso, `voltas` seria grande e `nao_none`
seria 0. Não é o caso.

### Por que a condição aparece

`--parallel-threads=4` não é só paralelismo difuso.
`Lib/test/libregrtest/parallel_case.py` faz 4 cópias do caso de teste e as
libera de uma `threading.Barrier(4)` **no mesmo instante, no mesmo processo**:

```python
cases = [copy.copy(self.test_case) for _ in range(self.num_threads)]
barrier = threading.Barrier(self.num_threads)
...
thread = threading.Thread(target=self.run_worker, args=(case, r, barrier), daemon=True)
```

Cada cópia abre seu próprio par `runner`/`reader`. Com `-j10` são 10 processos
× 4 cópias × 2 threads ≈ **80 threads disputando 10 núcleos**. Nessa
sobrecarga, um `reader` pode não ser escalonado até depois de o `runner`
terminar — e 10.000 `yield` triviais terminam rápido.

### O que o teste realmente quer provar

A asserção útil é *"o `reader` nunca vê dois objetos de frame diferentes"* — é
disso que trata a [gh-144446](https://github.com/python/cpython/issues/144446).
`len(frames) == 1` impõe, além disso, que o `reader` **seja escalonado**, o que
não é garantia de nada. Não emito opinião sobre a correção: tolerar `0`
(`assertLessEqual(len(frames), 1)`) e sincronizar para garantir ao menos uma
volta são caminhos diferentes, com implicações diferentes sobre o que o teste
cobre, e isso é decisão de quem mantém.

## 5. Confirmação independente, fora do regrtest

O mecanismo foi confirmado **duas vezes, por caminhos diferentes**. Além da
instrumentação do item 4, consegui reproduzir num script autônomo — mas só
depois de descobrir, por eliminação, qual era a condição necessária:

| Condição | Execuções do método | `frames` vazio | menor nº de voltas |
|---|---|---|---|
| 1 cópia, 1 processo | 300 | 0 | 271 |
| 1 cópia, 24 processos | 1440 | 0 | 196 |
| 4 cópias, 1 processo | 800 | 0 | 67 |
| **4 cópias × 10 processos** | **1600** | **3** | **0** |

Os três casos capturados vieram todos como `(len=0, voltas=0, nao_none=0)` —
idênticos ao que a instrumentação pegou dentro do teste real.

Repare na coluna da direita: o mínimo de voltas cai monotonicamente conforme a
sobrecarga sobe — 271 → 196 → 67 → **0**. É o mesmo fenômeno em escala
crescente, e só chega a zero quando as duas sobrecargas se combinam: cópias no
mesmo processo (`--parallel-threads`) **e** processos concorrentes (`-j`).

Nenhuma das duas isolada basta, o que explica por que minhas três primeiras
réplicas deram zero — e por que eu quase concluí que o mecanismo era outro.

Taxa autônoma: 3 em 1600 execuções, ~0,19% por execução do método. Sob o `-F`
do regrtest, que repete até falhar, isso acumula para os 5/10 do item 2.

Consequência para o reporte: dá para oferecer **os dois** repros — o comando
deles, que é o que importa para eles, e o script autônomo, que prova o
mecanismo sem depender do regrtest.

## 6. Procedência

| | |
|---|---|
| Teste introduzido por | [PR 156037](https://github.com/python/cpython/pull/156037), Kumar Aditya, merged 2026-09-02 |
| Para a issue | [gh-144446](https://github.com/python/cpython/issues/144446) *"Data races with frame objects"* — **aberta** |
| Primeira tag | `v3.16.0a1` |
| O CI deles roda `--parallel-threads`? | sim — `.github/workflows/reusable-san.yml` usa `--tsan-parallel --parallel-threads=4` |

O último ponto importa: a configuração que dispara a falha é a que **eles
próprios** rodam no CI, então isto é fonte plausível de falha intermitente no
CI deles.

## 7. Cruzamento — nada igual

Issues **e** PRs, aplicando o filtro da caçada 004: nada sobre
`test_concurrent_gi_frame`, nada sobre `test_generators` instável, nada sobre
instabilidade de `--parallel-threads`. Os resultados de `gi_frame` são todos de
outro assunto (cobertura de `inspect`, `repr` de gerador, `_GeneratorWrapper`).

## 8. Canal

Issue pública. Não é vulnerabilidade: é asserção de teste frouxa, sem efeito em
código de produção.

## 9. Por que este é o candidato bom

Comparado com a caçada 005, que consumiu horas e não rendeu reporte:

| | 005 — mimalloc | 006 — `gi_frame` |
|---|---|---|
| Reprodutível sob comando | não (0 em ~3 h 23) | **sim, 5/10** |
| Mecanismo | hipótese, duas já refutadas | **confirmado por instrumentação** |
| Já reportado upstream | não | não |
| Tamanho do reporte | grande e incerto | pequeno e verificável |

É pequeno, é verificável em uma linha de comando, tem mecanismo provado, e a
correção é de teste — risco baixo para quem revisa. É melhor primeira
contribuição de código do que qualquer coisa que a caçada 005 produziu.

## 10. Reportado

[gh-161489](https://github.com/python/cpython/issues/161489), aberta em 2026-11-06 com
aprovação explícita. Conferido antes de abrir que não havia duplicata, e depois
que tabela e blocos de código renderizaram.

Precedente que sustentou a escolha de issue própria em vez de comentário na
gh-144446: a [gh-136692](https://github.com/python/cpython/issues/136692)
(`test_free_threading.test_monitoring` flaky) mostra que teste instável de
free-threading ganha issue própria no projeto.

Sem label — labels de triagem são aplicadas por quem tem permissão, não por
quem reporta. Não cobrar, não fazer bump.

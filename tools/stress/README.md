# Stress tests de concorrência — o aparato da S3

Testes próprios de thread-safety para o build free-threaded do CPython. O objetivo não é passar;
é **falhar de um jeito que ensine algo**.

## Por que estes três módulos

`Lib/test/test_free_threading/` do CPython tem **59 arquivos e 7.834 linhas**. Os alvos óbvios
— `dict`, `list`, `set`, `itertools`, `functools`, `memoryview`, `weakref`, `io`, `re` — já estão
cobertos. Escrever mais um teste de `dict` concorrente seria trabalho jogado fora.

Então o critério de escolha foi: **implementação em C + estado compartilhado + zero cobertura de
free-threading + um oráculo que a documentação já dá**.

| Módulo | C | Cobertura deles | Oráculo documentado |
|---|---|---|---|
| `zoneinfo` | `Modules/_zoneinfo.c`, 80 KB | **nenhuma** | `assert ZoneInfo(k) is ZoneInfo(k)` — literal, na doc |
| `decimal` | `Modules/_decimal/_decimal.c`, 243 KB | **nenhuma** | *"Each thread has its own current context"* |
| `hashlib` | `Modules/_hashopenssl.c`, 84 KB | **nenhuma** | limiar de 2047 bytes que libera o GIL |

## A regra que veio da caçada 003

Antes de escrever o teste, **ler o que a doc promete**. A caçada 003 gastou tempo num
comportamento que estava documentado há vinte anos — "the list appear empty for the duration".
Teste sem oráculo documentado produz veredito fraco e comentário que leva "já sabíamos".

Consequência prática no código: onde a garantia existe, o teste a cita no docstring e assere
contra ela. Onde **não** existe, o teste fica numa classe separada e o docstring diz que
divergência ali exige decidir *bug vs. uso indefinido* antes de reportar. Ver
`test_hashlib.py`, que separa `TestHashlibPerThreadObjects` de `TestHashlibSharedObject`
exatamente nessa linha.

## O oráculo bom

O de `hashlib` vale explicar porque é o mais forte dos três e não é óbvio.

Se N threads alimentam o **mesmo** objeto de hash com blocos **idênticos**, qualquer intercalação
produz o mesmo fluxo de bytes: `b"x" * total`. Então o digest final é previsível **sem depender da
ordem de execução**. Um `update()` perdido, duplicado ou aplicado pela metade muda o digest, e o
teste pega.

Isso detecta **corrupção silenciosa**, que um teste de "não crashou" deixa passar.

## Idioma deles, de propósito

Os arquivos usam `unittest`, `@threading_helper.requires_working_threading()` e
`test.support.threading_helper.run_concurrently` — que já faz barreira e re-levanta exceção de
thread. São drop-in para `Lib/test/test_free_threading/`.

Decisão deliberada: se um destes achar algo, o teste vai para upstream **sem reescrita**. Repro
que já é teste no formato do projeto vale muito mais que repro em script solto.

## Como rodar

```bash
bash tools/stress/run.sh                    # os tres testes, nos tres builds
bash tools/stress/run.sh test_zoneinfo.py   # so um
```

Os três builds são o **mesmo commit** (`534605904df`); a única variável é o modo:

| Build | O que é | Papel |
|---|---|---|
| `~/src/cpython` | GIL, pydebug | controle — se falha aqui também, não é de free-threading |
| `~/src/cpython-ft` | free-threaded, pydebug | onde o bug aparece |
| `~/src/cpython-tsan` | free-threaded, pydebug, TSan | onde ele é explicado |

Logs em `runs/<timestamp>/` (fora do versionamento).

## TSan

Opções iguais às do CI deles (`.github/workflows/reusable-san.yml`), mais o caminho do
symbolizer, que no Ubuntu 26.04 não fica no `PATH`:

```
TSAN_OPTIONS="suppressions=$BUILD/Tools/tsan/suppressions_free_threading.txt
              handle_segv=0
              external_symbolizer_path=/usr/lib/llvm-21/bin/llvm-symbolizer"
```

Sem o `external_symbolizer_path` os relatórios saem com endereços em vez de `arquivo:linha`, e
viram inúteis para triagem. O aparato foi verificado contra uma corrida conhecida antes de rodar
qualquer coisa de verdade — detectou e simbolizou.

## Como ler um achado

1. Falhou no `ft` e passou no `gil`? → candidato. Falhou nos dois? → não é de free-threading.
2. O TSan aponta `arquivo:linha` nos dois lados da corrida? → anotar os dois.
3. Reproduz **sem** TSan, com repetição suficiente? → se não, pode ser só falso positivo do TSan.
4. Cruzar com as issues `topic-free-threading` **antes** de abrir qualquer coisa.
5. **Parada obrigatória:** corrupção de memória ou crash alcançável a partir de entrada não
   confiável → canal de segurança, nunca issue pública. Ver §4 do plano.

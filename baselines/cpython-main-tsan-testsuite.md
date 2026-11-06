# Baseline — CPython `main`, build pydebug, **free-threaded + ThreadSanitizer**

| Campo | Valor |
|---|---|
| Commit | `534605904dfa7db25bf19a1b959411b8562c2b80` |
| Versão | Python 3.16.0a1+dev free-threading build, **Clang 21.1.8** |
| Capturado em | 2026-11-06 |
| Comando | `./python -m test --tsan -j4 -W --timeout=600 --slowest` |
| Build | `CC=clang ./configure --with-pydebug --disable-gil --with-thread-sanitizer` |
| Árvore | `git worktree --detach` no mesmo commit, em `~/src/cpython-tsan` |
| `TSAN_OPTIONS` | `suppressions=Tools/tsan/suppressions_free_threading.txt handle_segv=0 external_symbolizer_path=/usr/lib/llvm-21/bin/llvm-symbolizer` |
| Módulos de extensão | 116 — **0 faltando, 0 falhando** |
| **Exit code da suíte** | **2 (FAILURE)** |
| Duração | 17 min |

## Por que este baseline existe, sendo o terceiro

O TSan muda **o que falha** e **o que estoura timeout**, então o baseline do free-threaded puro não
serve aqui. E `--tsan` roda só o subconjunto que eles consideram utilizável sob o sanitizer — 139
arquivos contra 551 da suíte inteira. É outra população de testes.

Opções de TSan iguais às do CI deles (`.github/workflows/reusable-san.yml`), mais o
`external_symbolizer_path`: no Ubuntu 26.04 o `llvm-symbolizer` não fica no `PATH`, e sem ele os
relatórios saem com endereços em vez de `arquivo:linha` — inúteis para triagem.

## Resultado

```
Total tests:      run=13,002  skipped=906
Total test files: run=139/139  failed=1  skipped=2
136 tests OK
Result: FAILURE
```

## O número que mais importa: **0 avisos do TSan**

Na suíte inteira sob as supressões deles, **zero** `WARNING: ThreadSanitizer`.

Isso é o que dá valor ao aparato: **o piso é limpo**. Qualquer aviso de TSan que um stress test
meu produzir é sinal, não ruído pré-existente. Sem este número, todo achado precisaria ser
comparado contra um fundo desconhecido.

Verificação independente de que o TSan está realmente ativo (não é "0 porque não ligou"): o build
foi testado contra uma corrida conhecida antes de rodar a suíte, e detectou com
`arquivo:linha:coluna` e nome de função. Ver [tools/stress/README.md](../tools/stress/README.md).

## A falha: `test_free_threading.test_str`: **crash**

Teste: `TestStr.test_maketrans_dict_concurrent_modification`.

```
python: ./Include/internal/pycore_dict.h:332:
  void _PyDict_NotifyEvent(PyDict_WatchEvent, PyDictObject *, PyObject *, PyObject *):
  Assertion `Py_REFCNT((PyObject*)mp) > 0' failed.
Fatal Python error: Aborted
```

Pilha em C: `PyDict_Pop` → `_PyDict_NotifyEvent` → assertion.
Pilha em Python: `Lib/test/test_free_threading/test_str.py:100`, em `work`.

Um dicionário com refcount ≤ 0 sendo operado é **use-after-free** — o objeto foi desalocado e
`PyDict_Pop` continuou mexendo nele.

### Reprodutibilidade: **não reproduz isolado**

| Build | Comando | Resultado |
|---|---|---|
| FT + TSan | `./python -m test test_free_threading.test_str` × 5 | **0/5** |
| free-threaded puro | idem × 5 | **0/5** |

Como o outro crash do baseline FT: só apareceu na suíte completa, sob carga paralela.

### Por que não foi reportado

Mesmo motivo do outro: **sem repro, não é reporte.** Uma ocorrência, 0/5 isolado nos dois builds.

Cruzei contra issues e PRs abertos antes de qualquer coisa — o filtro da caçada 004. Nada sobre
`test_maketrans_dict_concurrent_modification`. Em `_PyDict_NotifyEvent` há issues e PRs, mas de
outros assuntos: [gh-148393](https://github.com/python/cpython/issues/148393) (load atômico de
`_ma_watcher_tag`, **fechada**, PR mergeado) e
[gh-142731](https://github.com/python/cpython/issues/142731) (use-after-free por `__hash__`
re-entrante, outro caminho). Nenhuma é esta.

### Nota sobre canal

Os dois crashes do baseline são corrupção de memória em potencial, o que aciona a parada
obrigatória da regra R1. Avaliado: **não são caso de canal de segurança.** São bugs de
concorrência alcançáveis só por código Python que muta estrutura compartilhada de propósito, não
por entrada não confiável; estão num build marcado como experimental; e são disparados pela
**própria suíte de testes do projeto**, que o CI deles roda. Se virarem reportáveis, vão como
issue pública.

## Log cru

[`cpython-main-tsan-testsuite.raw.log`](cpython-main-tsan-testsuite.raw.log)

# Baseline — CPython `main`, build pydebug, **com GIL**

| Campo | Valor |
|---|---|
| Commit | `534605904dfa7db25bf19a1b959411b8562c2b80` |
| Assunto do commit | `Add hoodmane to CODEOWNERS for Emscripten files (#161437)` |
| Versão | Python 3.16.0a1+dev, GCC 15.2.0 |
| Capturado em | 2026-11-05 20:06:35Z |
| Comando | `./python -m test -j0` |
| Build | `./configure --config-cache --with-pydebug` + `make -s -j10` |
| Host | WSL Ubuntu 26.04, 10 cores, 32 GB |
| Módulos de extensão | 116/116 — **0 faltando** |
| `make patchcheck` | exit 0 |
| `blurb` | 2.3.0, em `~/.venvs/tools/bin/blurb` |
| **Exit code da suíte** | **2 (FAILURE)** |
| Duração | 5 min 16 s |

## Para que serve

Este é o estado da suíte **antes** de eu tocar em qualquer coisa. Sem ele não se distingue
"eu quebrei" de "já estava quebrado". Depois de cada patch, a comparação é contra este arquivo —
**não contra zero falhas**.

A suíte sai com exit 2 num ambiente íntegro. Isso é esperado e está explicado abaixo.

## Resultado

```
Total tests:      run=53,422  skipped=2,751
Total test files: run=551/562  failed=1  skipped=75  resource_denied=11
475 tests OK
Result: FAILURE
```

## A única falha: `test_perf_profiler`

```
[402/562/1] test_perf_profiler failed (2 errors)
Error: unknown switch `j'
 Usage: perf inject [<options>]
```

**Causa:** o `perf` do kernel do WSL não aceita a flag `-j` que o CPython passa para
`perf inject`. É limitação do ambiente, **não bug do CPython**, e não é reportável.

**Consequência prática:** esta falha é o piso. Se um dia a suíte voltar com 2 falhas, a nova é a
minha. Se voltar com 1 e for esta, está limpo.

## 11 testes negados por recurso (`resource_denied`)

```
test_curses  test_peg_generator  test_smtpnet  test_socketserver
test_tkinter  test_ttk  test_urllib2net  test_urllibnet  test_winsound
test_xpickle  test_zipfile64
```

Pedem rede, display ou disco grande. Para habilitar: `./python -m test -u all` (ou `-u network`,
`-u gui`, `-u largefile`). Deixei desligados de propósito: teste que depende de rede produz falha
intermitente e envenena o baseline.

## 75 testes skipados — e o achado que importa

| Grupo | Quantos | Por quê |
|---|---|---|
| **`test_free_threading.*`** | **62** | **Este build tem GIL. A suíte inteira de free-threading não roda.** |
| `test_asyncio.test_windows_*` | 2 | Específicos de Windows |
| Plataforma | 11 | `test_android`, `test_apple`, `test_devpoll`, `test_dtrace`, `test_kqueue`, `test_msvcrt`, `test_startfile`, `test_winapi`, `test_winconsoleio`, `test_winreg`, `test_wmi` |

### Por que isso muda o plano

Os 62 testes skipados são exatamente a suíte que a sessão **S3** precisa. Com GIL eles não
executam, então **este baseline não valida nada de free-threading**.

Consequência: S3 precisa de um **segundo baseline próprio**, capturado no build free-threaded, e
depois de um **terceiro** sob ThreadSanitizer (porque o TSan muda o que falha e o que é lento).
Três baselines, não um.

## Como reproduzir

```bash
cd ~/src/cpython
git checkout 534605904dfa7db25bf19a1b959411b8562c2b80
./configure --config-cache --with-pydebug
make -s -j10
./python -m test -j0
```

Log bruto completo: [`cpython-main-pydebug-testsuite.raw.log`](cpython-main-pydebug-testsuite.raw.log)

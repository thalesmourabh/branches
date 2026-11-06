# Plano — Caça a bugs upstream (CPython / Go)

> Escrito em 2026-11-05. Os números de backlog e as flags foram verificados nesta data contra a
> API do GitHub, `go.dev/doc/contribute` e `devguide.python.org`.
> Onde eu não consegui confirmar, está marcado **[CONFIRMAR]**.

---

## 0. Leitura honesta antes de começar

Cinco correções no enquadramento. Se você discordar de alguma, o plano muda.

### 0.1 Você não vai achar bug lendo código nesses dois repos

CPython e Go são dois dos códigos mais auditados do planeta. Milhões de horas de olho humano,
OSS-Fuzz rodando há anos, buildbots em dezenas de arquiteturas. A chance de achar bug **lendo**
`Objects/listobject.c` é perto de zero.

O que acha bug lá em 2026:

| Método | Por que funciona |
|---|---|
| Pressão de concorrência no build free-threaded do CPython | Código novo, pouco rodado; TSan acha sozinho |
| Fuzzing com alvos novos (não os que o OSS-Fuzz já cobre) | Máquina acha o que olho não acha |
| Teste diferencial (impl. A vs B, versão N vs N-1) | Oráculo automático — você não precisa saber a resposta certa |
| Sanitizers (ASan/TSan/UBSan) em caminhos pouco cobertos | Transforma bug silencioso em crash explícito |
| Divergência doc vs. código | Barato, real, mergeável |

Nenhum depende de genialidade. Dependem de **montar o aparato e deixar rodar**. É engenharia de
infraestrutura de teste, não leitura de código.

### 0.2 Existem três escadas, e você quer subir na ordem

| Escada | O que é | Backlog hoje | Dificuldade | Até ter algo público |
|---|---|---|---|---|
| **E1 — Triagem** | Reproduzir, bissecar e diagnosticar issue existente | CPython 3.029 `type-bug` · Go 5.098 `NeedsInvestigation` | Baixa | Dias |
| **E2 — Fix dirigido** | Corrigir issue já diagnosticada | Go 1.195 `NeedsFix` · CPython 66 `easy` | Média | 1–3 semanas |
| **E3 — Bug novo** | Achar o que ninguém sabia | Infinito, taxa de acerto baixa | Alta | 1–3 meses, incerto |

**Erro clássico:** começar em E3. Passa dois meses sem nada publicado, sem entender o processo de
review, e quando acha algo não sabe empacotar. Resultado: nada merged.

**Ordem correta:** E1 para aprender a máquina → E2 para conseguir merge e credibilidade → E3 como
aposta de longo prazo rodando em background.

Uma triagem boa (repro mínimo + bisect apontando o commit culpado) é **contribuição real**.
Mantenedor de CPython/Go gasta a maior parte do tempo nisso. Entregue isso pronto e você ajudou.

### 0.3 DDD não se aplica aqui — e eu tiraria do plano

Você pediu DDD. Discordo, e vou dizer por quê.

DDD é para **modelar um domínio de negócio que é seu**: Linguagem Ubíqua negociada com
especialistas, Agregados, Bounded Contexts. Tudo isso pressupõe que você está desenhando o
sistema. Em CPython você é hóspede, e não existe domínio de negócio — `Objects/dictobject.c` não
tem Agregado. Tentar aplicar DDD ali te faz parecer turista, e é o tipo de coisa que faz
mantenedor fechar PR.

**O que sobra dessa família, e é muito útil: Linguagem Ubíqua.** Não a sua — a *deles*. Usar a
palavra errada no primeiro PR é a forma mais rápida de ser descartado. Glossário obrigatório:

| Go | CPython |
|---|---|
| **CL** (change list) — não diga "PR" | **blurb** — entrada de changelog em `Misc/NEWS.d/next/` |
| **Gerrit** — o review de verdade | **buildbot** — CI deles, em plataformas exóticas |
| **trybot** — CI pré-merge | **refleak** — vazamento de referência (`-R :`) |
| **NeedsFix / NeedsInvestigation / NeedsDecision** | **free-threaded** — não diga "nogil" em PR |
| **GOEXPERIMENT**, **GODEBUG** | **pydebug** — build de desenvolvimento |
| **freeze** — 3 meses sem features por ciclo | **skip issue** — label para fix trivial sem issue |
| **proposal process** — mudança de API passa por lá | **patchcheck** — `make patchcheck` antes do PR |

Skill a usar: `domain-driven-design`, **só** o capítulo de Linguagem Ubíqua. O resto, ignore.

### 0.4 TDD se aplica, mas invertido: Repro-Driven

TDD clássico é test-first para feature nova. Aqui o ciclo é:

```
RED      → teste que falha reproduzindo o bug, NO estilo e NA suíte deles
           (CPython: Lib/test/test_x.py · Go: x_test.go no pacote afetado)
GREEN    → o fix mínimo que faz passar
REFACTOR → nada. Você não refatora código de outro projeto num bugfix. Ponto.
```

Não é adaptação forçada: os dois projetos **exigem** teste no patch. E o teste-primeiro te
protege — se você não consegue escrever o teste que falha, você não entendeu o bug, e o
mantenedor vai descobrir isso em público.

Skills: `octo:tdd` para a disciplina red-green · `octo:debug` para a investigação antes do RED.

### 0.5 "Publicar as Branches e mostrar que ajudo a comunidade"

Dois problemas práticos:

1. **Go não vive no GitHub.** O review é no Gerrit (`go-review.googlesource.com`). *Mas* existe o
   **GerritBot**: você abre PR normal no GitHub, o bot cria o CL correspondente e sincroniza os
   dois lados — *"a tool called GerritBot has been created to sync GitHub pull requests to
   Gerrit"*. Na aceitação **todos os commits são esmagados** e a descrição final vira
   título + corpo do PR. A rota GitHub funciona e deixa rastro visível; você ainda precisa de
   conta no Gerrit para responder reviewer.

2. **Taxa de conversão é baixa.** Expectativa realista pelo que vi dos dois processos: ~15 leads
   investigados → ~5 bugs de verdade → ~2–3 aceitos upstream. A maioria vira "working as
   intended" ou "won't fix". Isso é normal, não é fracasso.

**Conclusão:** o PR merged não pode ser o único artefato, senão você passa meses sem portfólio.
O ativo publicável é um **repo público de caçadas**: cada investigação é uma pasta com repro,
bisect, análise e link upstream — merged ou não. Demonstra mais competência que um merge de typo,
e existe desde a semana 1. Detalhe em §5.

---

## 1. Escolha de alvo

### 1.1 Recomendação: CPython, build free-threaded, primeiro (recomendado)

Motivos em ordem de peso:

- **É o código menos auditado dos dois projetos.** Free-threading é recente, o 3.15 já saiu com
  ele e a pressão de uso real está subindo agora.
- **A máquina acha por você.** TSan + a suíte deles em modo paralelo produz achados
  mecanicamente. Precedente direto: a issue
  [#149816](https://github.com/python/cpython/issues/149816) é *"22 free-threading race
  conditions"* achadas por **varredura estática**, com fixes backportados para 3.15 e 3.14.
  Alguém rodou ferramenta e colheu 22 bugs.
- **Mantenedores receptivos agora.** 127 issues abertas com `topic-free-threading`. Issue aberta
  é sinal de que eles querem relatos nessa área.
- **Workflow nativo GitHub.** Fork → branch → PR. Sem Gerrit, sem CLA do Google, sem
  "duas pessoas do Google envolvidas".
- **Seu ambiente já serve.** WSL Ubuntu 26.04, 12 cores, 32 GB. TSan é pesado em CPU e você tem CPU.

### 1.2 Go como segunda frente, não primeira

Go é mais lento para o seu objetivo:

- Gerrit + CLA do Google + instalar `git-codereview`.
- *"Excluding very trivial changes, all contributions should be connected to an existing issue."*
- *"A change needs the involvement of two Google employees"* (+1 ou mais).
- **Ciclo de freeze:** metade de cada ciclo de 6 meses é feature freeze. Go 1.27 saiu em
  agosto/2026, então o tree de 1.28 provavelmente está **em freeze agora**. Isso é **bom** para
  você: em freeze só entra bugfix, que é exatamente o que você quer entregar.
- Go **não tem** label `help wanted` nem `good first issue` — verifiquei, 0 resultados. O ponto de
  entrada é `NeedsFix`.

### 1.3 Números do backlog — verificados em 2026-11-05

```
python/cpython  label:easy                       66
python/cpython  label:topic-free-threading       127
python/cpython  label:topic-asyncio               72
python/cpython  label:type-bug                  3029
python/cpython  label:docs                       968

golang/go       label:NeedsFix                  1195
golang/go       label:NeedsInvestigation        5098
golang/go       label:Documentation              437
golang/go       label:fuzz                        29
golang/go       label:"help wanted"                0   <- não existe
```

### 1.4 A alternativa que eu colocaria na mesa

Se o objetivo real é **impacto na comunidade + visibilidade**, CPython e Go são alvos de
*prestígio*, não de *throughput*. Repos de porte médio e muito usados (`astral-sh/ruff`,
`astral-sh/uv`, `pydantic`, `encode/httpx`, `go-chi/chi`, `sqlc-dev/sqlc`) mergeiam em dias, não
meses, e os mantenedores respondem.

**Barbell que eu recomendaria:** 70% do esforço num repo médio responsivo (merge rápido, feedback
rápido, aprendizado rápido) e 30% no moonshot CPython free-threading. Está na lista de decisões.

---

## 2. Realidade da sua máquina (verificado)

| Item | Estado | Ação |
|---|---|---|
| `git` | OK — `C:\Program Files\Git` | — |
| `gh` | OK — autenticado como `thalesmourabh`, scopes `gist, read:org, repo, workflow` | — |
| `python` | OK — 3.12 no Windows | serve só para scripts auxiliares |
| `uv` | OK | útil para ferramentas Python |
| `wsl` | OK — **Ubuntu 26.04 rodando** | **este é o host de build** |
| compilador C (`gcc`/`clang`/`cl`) | **faltando** | instalar no WSL |
| `make` / `cmake` | **faltando** | instalar no WSL |
| `go` | **faltando** | instalar no WSL (sessão S5) |
| CPU / RAM / disco | 12 cores · 32 GB · 464 GB livres | suficiente com folga |

**Decisão técnica que eu já tomei (2-way door):** todo build e teste acontece **dentro do WSL**,
no filesystem Linux (`~/src/...`), **não** em `/mnt/c/...`. Build de CPython em `/mnt/c` é 5–10x
mais lento por I/O cross-filesystem. O repo público de caçadas fica no Windows
(`C:\Users\Thales\Documents\Branches`) para você abrir fácil; os clones upstream ficam no WSL.

---

## 3. Sessões

Cada sessão tem objetivo, pré-requisito, checklist, skills, **critério de sucesso verificável** e
tempo estimado. O tempo é de execução minha, não sua.

---

### S0 — Fundação: repo público + ambiente de build

**Objetivo:** ambiente onde você compila CPython em modo debug e roda a suíte inteira, e um repo
público onde cada caçada será registrada.

**Pré-requisito:** nenhum.

**Checklist**

- [ ] **S0.1** Criar o repo público de caçadas
  - [ ] `git init` em `C:\Users\Thales\Documents\Branches`
  - [ ] estrutura de pastas conforme §5
  - [ ] `README.md` explicando o que é (não é um projeto, é um caderno de campo)
  - [ ] `gh repo create` público
- [ ] **S0.2** Preparar o WSL
  - [ ] `sudo apt-get update && sudo apt-get build-dep python3`
  - [ ] `sudo apt-get install pkg-config build-essential clang gdb ripgrep`
- [ ] **S0.3** Clonar CPython no filesystem do WSL
  - [ ] fork de `python/cpython` via `gh repo fork`
  - [ ] clonar o fork em `~/src/cpython`
  - [ ] remotos exatamente como o devguide manda:
    ```
    git remote add upstream https://github.com/python/cpython
    git config --local branch.main.remote upstream
    git remote set-url --push upstream git@github.com:thalesmourabh/cpython.git
    ```
- [ ] **S0.4** Build de desenvolvimento
  - [ ] `./configure --config-cache --with-pydebug`
  - [ ] `make -s -j12`
  - [ ] `./python -VV` responde
  - [ ] *"You should always develop under a pydebug build of CPython."* — nunca medir performance nesse build
- [ ] **S0.5** Rodar a suíte inteira uma vez e **guardar o baseline**
  - [ ] `./python -m test -j0` → salvar saída em `baselines/`
  - [ ] anotar quais testes já falham ou são skipados **antes** de você tocar em nada
  - [ ] sem esse baseline você não distingue "eu quebrei" de "já estava quebrado"
- [ ] **S0.6** Validar as ferramentas de pré-PR
  - [ ] `make patchcheck` roda
  - [ ] `blurb` instalado (`uv tool install blurb`) — NEWS entry é obrigatória na maioria dos fixes
- [ ] **S0.7** Ler, de verdade, dois documentos
  - [ ] `devguide.python.org/getting-started/pull-request-lifecycle/`
  - [ ] `devguide.python.org/security/policy/` — para saber o que **não** virar issue pública

**Skills:** `git-github` (remotos, convenção de commit) · `clean-coder` (disciplina e ritmo)

**Critério de sucesso:** `./python -m test -j0` roda até o fim e o arquivo de baseline está
commitado no repo público. `make patchcheck` executa sem erro de ambiente.

**Tempo:** 1,5–2,5 h (a maior parte é `apt build-dep` e o primeiro `make`).

---

### S1 — Escada 1: aprender a máquina via triagem

**Objetivo:** três triagens entregues upstream. Zero código de produção escrito. Aqui você aprende
o vocabulário, o tom e o que eles consideram informação útil — **antes** de gastar reputação num
patch.

**Pré-requisito:** S0 completa.

**Checklist**

- [ ] **S1.1** Montar o funil de candidatos
  - [ ] issues `topic-free-threading` abertas, sem PR vinculado, sem atividade há 30+ dias
  - [ ] issues `type-bug` com repro em Python puro (reproduzível rápido)
  - [ ] descartar tudo com discussão de design em andamento — não é triagem, é decisão
- [ ] **S1.2** Para cada candidato, produzir o pacote de triagem
  - [ ] **repro mínimo**: o menor script que exibe o bug
  - [ ] **matriz de versões**: reproduz em 3.13 / 3.14 / 3.15 / `main`? GIL vs free-threaded?
  - [ ] **bisect**: `git bisect run` com script de teste → commit culpado
  - [ ] **análise**: o que o commit culpado mudou e por que causa o sintoma
  - [ ] **veredito**: é bug? é comportamento esperado? é doc errada?
- [ ] **S1.3** Postar como comentário na issue
  - [ ] fatos primeiro, sem opinião sobre o fix
  - [ ] não perguntar "posso trabalhar nisso?" — é ruído; se for fazer, faça
  - [ ] linkar o commit do bisect com SHA completo
- [ ] **S1.4** Registrar no repo público (`hunts/NNN-slug/`)

**Skills:** `octo:debug` (investigação sistemática) · `octo:research` (ler o histórico da issue
antes de falar) · `domain-driven-design` → só Linguagem Ubíqua

**Critério de sucesso:** 3 comentários de triagem postados, cada um com repro mínimo + resultado de
bisect com SHA. Sucesso **não** depende de resposta do mantenedor.

**Tempo:** 2–4 h por triagem. Total 6–12 h.

---

### S2 — Escada 2: primeiro merge

**Objetivo:** um PR merged em `python/cpython`. Pequeno, inquestionável, com teste.

**Pré-requisito:** S1 — você já sabe falar a língua deles.

**Checklist**

- [ ] **S2.1** Escolher o alvo, em ordem de probabilidade de merge
  - [ ] **(a)** divergência doc ↔ código achada em S1 — docs em `Doc/` não precisam de issue vinculada
  - [ ] **(b)** issue com label `easy` (66 abertas) **sem PR já aberto** — checar isso primeiro, muita gente pega essas
  - [ ] **(c)** teste faltando num comportamento que você mapeou em S1
  - [ ] **não** escolher: performance, mudança de API, refactor, nada em `_asyncio` ainda
- [ ] **S2.2** Ciclo Repro-Driven
  - [ ] branch: `git checkout -b gh-NNNNN-slug upstream/main`
  - [ ] **RED**: teste em `Lib/test/test_*.py` no estilo deles, que **falha**
  - [ ] **GREEN**: fix mínimo
  - [ ] só o teste: `./python -m test -v test_x`
  - [ ] a suíte: `./python -m test -j0` → comparar com o baseline de S0.5
  - [ ] se tocou código C: `./python -m test test_x -R 3:3` (caça refleak)
- [ ] **S2.3** Empacotar como eles esperam
  - [ ] `blurb add` → entrada em `Misc/NEWS.d/next/<Section>/`, imperativo ("Fix…", "Add…"),
        80 colunas, sem `-` na frente, sem número de issue no corpo
  - [ ] `make patchcheck` limpo
  - [ ] commit: primeira linha imperativa, **sem ponto final**
  - [ ] título do PR com prefixo `gh-NNNNN:` e descrição com `#NNNNN`
  - [ ] PEP 8 (Python) / PEP 7 (C)
  - [ ] **um problema por PR** — não misturar cosmética
- [ ] **S2.4** Revisar o próprio diff como adversário
  - [ ] rodar `/code-review` no diff antes de abrir o PR
  - [ ] rodar `/octo:review`
  - [ ] pergunta-teste: "um core dev olhando 30 segundos tem algum motivo pra fechar isso?"
- [ ] **S2.5** Abrir o PR e assinar o CLA
  - [ ] `python-cla-bot` comenta no PR → clicar, autorizar, assinar (uma vez só, vale pra sempre)
  - [ ] **não force-push durante review** — o devguide pede explicitamente
  - [ ] o merge deles é squash
- [ ] **S2.6** Disciplina de espera
  - [ ] sem comentário em 1 mês → ping na issue
  - [ ] sem resposta 1 semana depois → postar em Core Development no Discourse
  - [ ] *"we cannot force anyone to review pull requests"* — não é pessoal

**Skills:** `octo:tdd` (red-green) · `codigo-limpo` (o patch) · `git-github` (commit/PR) ·
`code-review` + `octo:review` (auto-revisão) · `clean-coder` (review duro sem reagir mal)

**Critério de sucesso:** PR aberto, CLA assinado, CI verde, `patchcheck` limpo, suíte igual ao
baseline. Merge é consequência, não critério — não depende de você.

**Tempo:** 4–8 h de trabalho. Calendário até merge: 2 semanas a 3 meses.

---

### S3 — Escada 3: o aparato de concorrência (a aposta principal)

**Objetivo:** uma máquina que gere achados de thread-safety no build free-threaded enquanto você
faz outra coisa. É aqui que mora a chance de bug novo e relevante.

**Pré-requisito:** S2 — você já tem um merge e sabe empacotar.

**Checklist**

- [ ] **S3.1** Build free-threaded
  - [ ] flag confirmada em 2026-11-05 no `./configure --help` da árvore:
        **`--disable-gil`** — *"enable support for running without the GIL (default is no)"*
  - [ ] build em diretório próprio, sem destruir o build do S0
  - [ ] `sys._is_gil_enabled()` retorna `False`
  - [ ] **segundo baseline, obrigatório.** O baseline do S0 foi capturado com GIL e lá os
        **62 testes `test_free_threading.*` ficam todos skipados** — ou seja, ele não valida
        nada de free-threading. Sem um baseline próprio deste build, não há como distinguir
        "eu quebrei" de "já estava quebrado" na única área que importa aqui.
- [ ] **S3.2** Build com ThreadSanitizer
  - [ ] `export CC=clang CXX=clang++`
  - [ ] `./configure --with-pydebug --with-thread-sanitizer` + a flag de free-threading
  - [ ] a doc deles diz que TSan *"is most useful on the free-threaded build"*
  - [ ] ASan / TSan / MSan / HWASan são **mutuamente exclusivos** — um build para cada
- [ ] **S3.3** Rodar a suíte sob TSan e separar sinal de ruído
  - [ ] `./python -m test --tsan`
  - [ ] `./python -m test --tsan-parallel --parallel-threads=4`
  - [ ] **terceiro baseline**: o que o TSan já reporta hoje, sem culpa sua. O TSan muda o que
        falha e o que estoura timeout, então o baseline do build free-threaded puro não serve
        aqui. São **três** baselines no total: GIL (feito em S0), free-threaded, free-threaded
        sob TSan.
  - [ ] cruzar cada achado contra as 127 issues `topic-free-threading` antes de abrir nada
- [ ] **S3.4** Escrever stress tests próprios — é aqui que está o diferencial
  - [ ] **filtro obrigatório ANTES de escrever o teste** — corrigido em 2026-11-06 depois da
        [caçada 004](hunts/004-decimal-context-compartilhado/), que gastou trabalho por não ter
        este passo:
    - [ ] cruzar o módulo contra issues **e PRs abertos**. "Sem arquivo em
          `Lib/test/test_free_threading/`" é sinal **fraco** de território inexplorado: o
          `decimal` tem zero arquivo lá e **três PRs abertos** sobre corridas. Eles rastreiam
          corrida por relatório de TSan, não por cobertura de teste.
    - [ ] procurar o módulo em `Doc/whatsnew/` da versão corrente. Mudança intencional recente é
          a explicação mais provável de divergência entre builds — foi o caso de
          `thread_inherit_context`, que está no What's New com o `decimal` citado pelo nome.
    - [ ] exigir **oráculo documentado**: o que a doc promete, literal. Sem isso o veredito é
          fraco. E se o teste não segurar as referências que o trecho da doc segura, ele não
          testa a promessa — testa taxa de acerto de cache. Ver o item 3 da caçada 004.
  - [ ] escolher módulos de stdlib sem teste de concorrência decente
  - [ ] padrão: N threads × M iterações × operação sobre objeto compartilhado
  - [ ] alvos de alto valor: estruturas com freelist, caches, objetos com estado lazy,
        `contextvars`, `asyncio` com thread de vida curta, `memoryview`, weakrefs
  - [ ] precedentes que mostram que a veia dá:
        [#121546](https://github.com/python/cpython/issues/121546) (ContextVar não thread-safe),
        [#129668](https://github.com/python/cpython/issues/129668) (freelist de MemoryError),
        [#159449](https://github.com/python/cpython/issues/159449) (asyncio com thread curta)
- [ ] **S3.5** Rodar em background, contínuo
  - [ ] script que roda os stress tests em loop sob TSan e arquiva relatórios
  - [ ] revisar os achados uma vez por dia, não ficar olhando
- [ ] **S3.6** Triar cada achado
  - [ ] **uma ocorrência não é taxa** — corrigido em 2026-11-06 depois da
        [caçada 005](hunts/005-mimalloc-arena-abandon/), onde eu chamei de "reproduzido" o que
        era amostra única, dei um número de 66 s como se fosse taxa, e no dia seguinte deu
        **0/12** na verificação. Antes de dizer que reproduz: medir.
  - [ ] **para corrida rara, sequência de trials curtos limpos NÃO é evidência de ausência.** A
        unidade é **tempo acumulado**, não número de tentativas. Uma corrida de ~1 a cada 30 min
        passa limpa em doze trials de 4 min sem nenhuma contradição. Usar o
        [`cacador-longo.sh`](tools/stress/cacador-longo.sh), que acumula tally entre execuções.
  - [ ] **bisect sem oráculo confiável não conclui nada** — "limpo nos dois lados" seria lido
        como "não é este commit" quando na verdade é "o gatilho é fraco". Taxa primeiro, bisect
        depois.
  - [ ] **conferir se o aparato está medindo o que você pensa, antes de acreditar no número.**
        Na caçada 005 eu rodei 37 min de caça que não mediram nada: `-F` implica `--failfast`,
        e a falha ambiental do `test_perf_profiler` truncava toda passada da suíte no mesmo
        ponto, aos ~250 s de 426. Nove passadas idênticas, zero completas, e o relatório dizia
        "0 ocorrências em 37 min". **Resultado repetido com duração quase igual é sinal de
        aparato travado, não de ausência do bug.** Conferir duração esperada vs. medida antes de
        tirar conclusão.
  - [ ] race de verdade ou falso positivo do TSan?
  - [ ] reproduz sem TSan, com repetição suficiente?
  - [ ] **PARADA OBRIGATÓRIA:** se é corrupção de memória ou crash alcançável a partir de entrada
        não confiável → **não abrir issue pública**. Ver §4.

**Skills:** `octo:debug` · `octo:tdd` (stress test é teste-primeiro por natureza) · `octo:skill-verify`

**Critério de sucesso:** build free-threaded + TSan funcionando, baseline de TSan catalogado, 5 ou
mais stress tests próprios escritos, loop contínuo rodando. Achar bug **não** é critério — é sorte
condicionada ao aparato existir.

**Tempo:** 6–10 h para montar. Depois ~30 min/dia de revisão.

---

### S4 — Fuzzing e teste diferencial

**Objetivo:** um segundo oráculo automático, independente do TSan.

**Pré-requisito:** S3 montada, ou em paralelo se S3 travar.

**Checklist**

- [ ] **S4.1** Mapear o que o OSS-Fuzz já cobre em CPython — não duplicar esforço
- [ ] **S4.2** Escolher alvos **não** cobertos
  - [ ] parsers de stdlib pouco fuzzados (formatos de arquivo, encodings, protocolos de texto)
  - [ ] round-trip: `parse(serialize(x)) == x`
  - [ ] property-based com Hypothesis — já achou bug real em CPython historicamente
- [ ] **S4.3** Teste diferencial (oráculo de graça — você não precisa saber a resposta certa)
  - [ ] CPython `main` vs 3.15 vs 3.14 no mesmo input
  - [ ] GIL build vs free-threaded build no mesmo input
  - [ ] implementação pura-Python vs acelerador em C do mesmo módulo (`_pickle`, `_json`, `_decimal`)
  - [ ] CPython vs PyPy onde a semântica é especificada
- [ ] **S4.4** Minimizar todo crash antes de reportar — ninguém triagem input de 4 KB

**Skills:** `octo:debug` · `octo:tdd` · agente `python-pro` para idioms de stdlib

**Critério de sucesso:** 3 ou mais alvos de fuzz/diferencial rodando em loop, com corpus persistido
e minimizador automático no pipeline.

**Tempo:** 5–8 h para montar.

---

### S5 — Abrir a segunda frente: Go

**Objetivo:** um CL em `golang/go`. Só começar depois que CPython já estiver dando retorno — duas
frentes desde o dia 1 significa zero progresso nas duas.

**Pré-requisito:** S2 fechada (no mínimo um PR aberto em CPython).

**Checklist**

- [ ] **S5.1** Setup (uma vez, e dá trabalho)
  - [ ] instalar Go no WSL
  - [ ] **escolher uma única conta Google** e garantir que `git config user.email` casa com ela
  - [ ] assinar o CLA em `cla.developers.google.com/clas`
  - [ ] gerar senha em `go.googlesource.com` → rodar o script → `.gitcookies`
  - [ ] login uma vez em `go-review.googlesource.com/login/`
  - [ ] `go install golang.org/x/review/git-codereview@latest` → validar com `git codereview help`
  - [ ] atalho: `go install golang.org/x/tools/cmd/go-contrib-init@latest` e rodar `go-contrib-init` no clone
  - [ ] clonar de `go.googlesource.com/go`, **não do GitHub**
- [ ] **S5.2** Validar o loop de build/teste antes de qualquer patch
  - [ ] `cd go/src && ./all.bash` até aparecer `ALL TESTS PASSED`
  - [ ] é demorado — saber quanto demora na sua máquina antes de precisar
- [ ] **S5.3** Escolher o alvo
  - [ ] `is:issue is:open label:NeedsFix` (1.195) **sem** CL vinculado — excluir com
        `-"golang.org/cl" -"go.dev/cl"`
  - [ ] `NeedsFix` significa *"fully understood and code can be written to fix it"* — é o alvo certo
  - [ ] **nunca** pegar `NeedsDecision` — o guia diz explicitamente para esperar a decisão
  - [ ] `NeedsInvestigation` (5.098) serve para **triagem** (escada 1), não para patch
  - [ ] estamos provavelmente **em freeze** → feature não entra, bugfix entra. Jogue a favor disso.
- [ ] **S5.4** Fazer o change
  - [ ] `git codereview change` (não `git commit`)
  - [ ] **um único commit** por branch · não editar a linha `Change-Id`
  - [ ] teste no pacote: `go test` passando inteiro
  - [ ] antes de mandar: `./all.bash` na árvore toda
  - [ ] commit: `pacote: resumo em minúscula sem ponto final` — tem que completar a frase
        *"This change modifies Go to ____"*.
        Ex.: `math: improve Sin, Cos and Tan precision for very large arguments`
  - [ ] corpo em frases completas, ~72 colunas, sem Markdown
  - [ ] `Fixes #12345` fecha a issue · `Updates #12345` só vincula
  - [ ] arquivo novo → header `// Copyright 2026 The Go Authors. All rights reserved.`
  - [ ] **não** atualizar ano de copyright em arquivo existente
- [ ] **S5.5** Mandar
  - [ ] via Gerrit: `git codereview mail` (recomendado e melhor suportado)
  - [ ] ou via GitHub + GerritBot, se você quiser o rastro no GitHub — os commits serão esmagados
  - [ ] responder **todo** comentário, com "Done" ou resposta
  - [ ] *"The Go community values very thorough reviews"* — várias rodadas é o normal, não rejeição
  - [ ] triagem costuma sair em poucos dias; aprovado e sem submit por dias → pedir submit em comentário

**Skills:** `git-github` · `codigo-limpo` · `clean-coder` (review do Go é duro e impessoal) · `code-review`

**Critério de sucesso:** CL enviado, trybots verdes, `./all.bash` passando local, mensagem de commit
no formato exato deles.

**Tempo:** setup 2–3 h · primeiro CL 4–10 h.

---

### S6 — Loop sustentável e publicação

**Objetivo:** transformar isso em rotina e tornar o trabalho visível.

**Checklist**

- [ ] **S6.1** Ritmo semanal
  - [ ] 1 triagem nova por semana (barata, mantém o fluxo)
  - [ ] revisar achados de TSan/fuzz 1x/dia, ~30 min
  - [ ] 1 PR/CL novo a cada 2 semanas
  - [ ] responder review **em até 48 h** — PR abandonado é pior que PR não aberto
- [ ] **S6.2** Repo público sempre atualizado (§5)
- [ ] **S6.3** Write-up por caçada concluída
  - [ ] o que você suspeitou, o que era de verdade, como o bisect provou
  - [ ] inclusive — e principalmente — as que deram "working as intended". Essas ensinam mais.
- [ ] **S6.4** Revisão mensal honesta
  - [ ] leads investigados / bugs confirmados / PRs abertos / merged
  - [ ] 2 meses sem nada aceito → o problema é escolha de alvo, não esforço → reconsiderar §1.4

**Skills:** `anthropic-skills:docs` ou `doc-coauthoring` (write-ups) · `octo:retro` (retrospectiva mensal)

---

## 4. Regras invioláveis (portas de mão única — me avise antes)

| # | Regra | Por quê |
|---|---|---|
| **R1** | **Achado com cara de vulnerabilidade NÃO vira issue pública.** CPython: `github.com/python/cpython/security/advisories/new` ou `security@python.org`. Go: `security@golang.org`, e **só** esse canal. | Divulgação pública de vuln em CPython/Go é dano real em escala global, e irreversível. A doc do CPython é explícita: *"Do not open a public GitHub issue to report a security vulnerability."* |
| **R2** | Nunca force-push em PR do CPython durante review. | O devguide pede explicitamente. Quebra o histórico de review. |
| **R3** | Nunca PR só de formatação ou estilo nos dois projetos. | *"Pure formatting PRs are usually rejected."* Queima reputação de graça. |
| **R4** | Mudança de API, linguagem ou CLI em Go → **proposal process**, nunca CL direto. | O CL vira ruído e é fechado. |
| **R5** | Não pegar issue que já tem PR/CL aberto sem falar com quem abriu. | Etiqueta. Vira atrito à toa. |
| **R6** | Não atualizar ano de copyright em arquivo existente. | CPython fecha o PR; Go proíbe. |
| **R7** | Um problema por PR. Sempre. | Os dois projetos dizem isso com todas as letras. |

---

## 5. Estrutura do repo público

```
Branches/
├── README.md                   # o que é isso: caderno de campo, não projeto
├── PLANO-CACA-BUGS.md          # este arquivo
├── GLOSSARIO.md                # Linguagem Ubíqua: Go e CPython (§0.3)
├── baselines/
│   ├── cpython-main-test-suite.txt
│   └── cpython-ft-tsan.txt     # o que TSan já reporta sem culpa sua
├── hunts/
│   └── 001-slug-do-bug/
│       ├── README.md            # ficha: hipótese → método → veredito → link upstream
│       ├── repro.py             # repro mínimo
│       ├── bisect.log           # saída do git bisect, com SHA culpado
│       ├── patch.diff           # o que você mandou, se mandou
│       └── outcome.md           # merged / won't fix / working as intended + o que aprendi
├── tools/
│   ├── stress/                 # stress tests de concorrência (S3.4)
│   ├── fuzz/                   # alvos de fuzz e corpus (S4)
│   └── diff/                   # harnesses de teste diferencial (S4.3)
└── writeups/
```

A ficha de cada caçada é o que demonstra competência. Um `outcome.md` dizendo "era comportamento
esperado, eu entendi errado por X" vale mais que um merge de typo — mostra método.

---

## 6. Métricas (expectativa calibrada)

```
20 leads investigados
 → 12 explicados (entendi o que acontece, mesmo não sendo bug)
 →  5 bugs confirmados
 →  3 PRs/CLs abertos
 →  1-2 merged
```

A métrica que você controla é **leads investigados e documentados**. Merge não é controlável:
depende de reviewer voluntário. Medir por merge é se frustrar com o que não é seu.

---

## 7. O que explicitamente NÃO fazer

- Ler código esperando achar bug (§0.1).
- Começar pela escada 3 (§0.2).
- Aplicar DDD a CPython (§0.3).
- Abrir issue sem repro mínimo.
- Comentar "posso trabalhar nisso?" — ruído. Se vai fazer, faça e abra o PR.
- Duas frentes (Go + CPython) desde o dia 1.
- Perseguir performance como primeiro patch: precisa de benchstat e hardware controlado, e é onde
  o reviewer é mais exigente.
- Reportar achado de TSan sem conferir contra o baseline e contra as 127 issues abertas.

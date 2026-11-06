# Processo de contribuição — checklist operacional

Destilado de `devguide.python.org` e `go.dev/doc/contribute`, lido em 2026-11-05.
Isto não é resumo para entender: é lista de conferência para executar antes de apertar enviar.

---

## CPython

### Antes de abrir o PR

```bash
cd ~/src/cpython
make patchcheck                       # verifica estilo, blurb, espaço em branco
./python -m test -v test_<modulo>     # o teste que você escreveu
./python -m test -j0                  # suíte inteira, comparar com baselines/
./python -m test test_<modulo> -R 3:3 # SÓ se tocou código C: caça refleak
~/.venvs/tools/bin/blurb add          # entrada de changelog
```

### Regras duras

| Regra | Detalhe |
|---|---|
| Branch | `git checkout -b gh-NNNNN-slug upstream/main`. Sempre de `main`, nunca de branch de manutenção. |
| Issue | Normalmente obrigatória. Exceção: typo em `Doc/` e `InternalDocs/` dispensa. Fix trivial precisa da label `skip issue`, aplicada por quem tem commit access. |
| Título do PR | Prefixo `gh-NNNNN:`. Descrição cita `#NNNNN`. |
| Commit | Primeira linha no imperativo, **sem ponto final**. Ex.: `Make the spam module more spammy`. |
| Escopo | Um problema por commit. Não misturar cosmética com fix. |
| Estilo | PEP 8 no Python, PEP 7 no C. |
| Force-push | **Proibido durante review.** Quebra o histórico. |
| Merge | Squash, feito por eles. |
| Copyright | Não adicionar ano novo em arquivo existente — PR assim é fechado. |
| Formatação pura | *"Pure formatting PRs are usually rejected."* |

### Ferramentas de IA — o que a política realmente exige

Fonte: [devguide, *Guidelines for using AI tools*](https://devguide.python.org/getting-started/ai-tools/).
Lido em 2026-11-06. É guia oficial do projeto, não regra informal.

| Ponto | O que diz |
|---|---|
| Declarar uso de IA | **Não é obrigatório.** *"Disclosure of the use of AI tools in the PR description is appreciated, while not required."* |
| Onde declarar, se declarar | Só menciona **descrição do PR**. Nada sobre commit, trailer ou comentário de issue. |
| `Co-Authored-By` de ferramenta | A política é **silenciosa**. Não permite nem proíbe. |
| Comentário em issue | **Não há regra.** A política fala de abrir issue e abrir PR. |
| Explicar o próprio trabalho | **Obrigatório.** *"We expect PR authors and those filing issues to be able to explain their proposed changes in their own words."* E: *"Be prepared to explain how the tool was used and what changes it made."* |
| Responsabilidade | É de quem submete, com ou sem IA. |
| Usar IA, por si só | **Não é motivo** para label nem para fechar. *"Using AI tools is not a reason on its own for an issue or PR to be labeled or closed."* |
| Burlar teste | Proibido. *"not acceptable to alter or bypass existing tests… in order to make a failing test pass."* |
| Reincidência em submissão ruim | Pode dar bloqueio no projeto. |

**As duas labels que importam**, aplicadas por maintainer, com comentário de bot:

- `AI-needs-explanation` — fica **aberto**. Pede: responda com as suas palavras, explique o que a
  mudança faz ou do que é a issue, e como você verificou que está certo.
- `AI-guidelines-not-met` — é **fechado**. Cabe resposta se houve mal-entendido.

**Consequência operacional, a única que muda o trabalho:** o risco não é a linha de declaração,
é não conseguir responder. Toda ficha em `hunts/` tem que deixar o *porquê* registrado, não só o
*quê* — é dela que sai a resposta com as próprias palavras. Ficha que só mostra resultado sem o
raciocínio é dívida.

### blurb

Vai em `Misc/NEWS.d/next/<Seção>/`, nome `<datetime>.gh-issue-<N>.<nonce>.rst`.
Uma ou duas frases no imperativo ("Fix…", "Add…"), markup tipo `` :func:`nome` ``, 80 colunas,
sem `-` na frente e **sem** número de issue no corpo.

**Dispensado em:** mudança só de documentação, só de teste, mudança interna sem efeito visível ao
usuário, e revert do que não saiu em release. Typo **não** está na lista de dispensa.

Mudança interessante também ganha entrada em `Doc/whatsnew/3.X.rst`.

### CLA — a armadilha do email

O `python-cla-bot` casa pelo **email do autor do commit**, não pela conta do
GitHub. Então `git config user.email` tem que ser exatamente o email registrado
no [cla.python.org](https://cla.python.org/).

Aconteceu no [PR gh-161494](https://github.com/python/cpython/pull/161494): o
email primário da conta Google tinha mudado, o commit saiu com o antigo, e o
bot barrou o PR mesmo com o CLA assinado.

**Conferir antes de abrir PR:**

```bash
git config user.email      # tem que bater com o registrado no CLA
```

Se não bater, corrigir **no cla.python.org**, não por force-push — force-push
num PR do CPython dispara mais de cinquenta jobs de CI na infraestrutura deles.

### Remotos (já configurados)

```
origin    https://github.com/thalesmourabh/cpython.git
upstream  https://github.com/python/cpython          (fetch)
upstream  https://github.com/thalesmourabh/cpython.git (push)
branch.main.remote = upstream
```

### Espera

Sem comentário em 1 mês → ping na issue. Sem resposta 1 semana depois → Core Development no
Discourse. *"We cannot force anyone to review pull requests."*

### Segurança

Nunca issue pública. Vai em
`github.com/python/cpython/security/advisories/new` ou `security@python.org`.
Texto simples, poucas frases, prova de conceito se possível, **sem CVSS**.

---

## Go

### Setup, uma vez só

```bash
# 1. uma única conta Google, e o git tem que casar com ela
git config --global user.email <conta-google>

# 2. CLA em cla.developers.google.com/clas
# 3. senha em go.googlesource.com -> rodar o script -> .gitcookies
# 4. login em go-review.googlesource.com/login/

go install golang.org/x/review/git-codereview@latest
git codereview help      # valida

# atalho que checa tudo acima:
go install golang.org/x/tools/cmd/go-contrib-init@latest
```

Clonar de `go.googlesource.com/go`, **não** do GitHub.

### Antes de mandar o CL

```bash
cd go/src
go test ./...     # no pacote afetado, tudo passando
./all.bash        # a árvore toda, tem que terminar em ALL TESTS PASSED
```

### Regras duras

| Regra | Detalhe |
|---|---|
| Issue | *"Excluding very trivial changes, all contributions should be connected to an existing issue."* |
| Label alvo | `NeedsFix` — *"fully understood and code can be written to fix it."* |
| Label proibida | `NeedsDecision` — esperar a decisão antes de escrever código. |
| Commit | `git codereview change`, **não** `git commit`. Um único commit por branch. |
| `Change-Id` | Nunca editar à mão. |
| Enviar | `git codereview mail` (apesar do nome, não usa e-mail). |
| Aprovação | Precisa de +2 de mantenedor, e do envolvimento de duas pessoas do Google. |
| Mudança de API/linguagem/CLI | Proposal process, nunca CL direto. |
| Copyright | Arquivo novo: `// Copyright 2026 The Go Authors. All rights reserved.` Não atualizar ano em arquivo existente. |
| Freeze | Metade de cada ciclo de 6 meses. Em freeze, bugfix entra e feature não. |

### Mensagem de commit

Primeira linha: `pacote: resumo em minúscula sem ponto final`.
Tem que completar a frase *"This change modifies Go to ____"*.

```
math: improve Sin, Cos and Tan precision for very large arguments

<corpo em frases completas, ~72 colunas, sem Markdown e sem HTML>

Fixes #12345
```

`Fixes #N` fecha a issue no submit. `Updates #N` vincula sem fechar.
Em repo `x/`, usar `Fixes golang/go#N`.

### Rota GitHub, se quiser rastro visível

Abre PR normal em `golang/go`; o **GerritBot** cria o CL e sincroniza os dois lados. Você ainda
precisa de conta no Gerrit para responder reviewer e marcar "Done". Na aceitação, **todos os
commits são esmagados** e a descrição final vira título + corpo do PR.

### Review

Triagem em poucos dias. *"The Go community values very thorough reviews"* — várias rodadas é
normal. Responder **todo** comentário. Aprovado e sem submit por alguns dias → pedir submit em
comentário.

### Segurança

`security@golang.org`, e **só** esse canal.

---

## Queries de busca de alvo

**CPython — `easy` sem PR aberto:**
```
repo:python/cpython is:issue is:open label:easy
```

**CPython — free-threading parado há 30+ dias:**
```
repo:python/cpython is:issue is:open label:topic-free-threading
```

**Go — `NeedsFix` sem CL vinculado:**
```
repo:golang/go is:issue is:open label:NeedsFix -"golang.org/cl" -"go.dev/cl"
```

**Go — nunca isto:**
```
label:NeedsDecision
```

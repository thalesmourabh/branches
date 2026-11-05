# Glossário — a linguagem de cada projeto

Usar a palavra errada no primeiro contato é a forma mais rápida de ser descartado. Este é o
vocabulário **deles**, não o meu.

---

## Go

| Termo | O que é |
|---|---|
| **CL** (*change list*) | A unidade de mudança. Não se diz "PR" quando se fala de Go, mesmo quando o envio foi por GitHub. |
| **Gerrit** | `go-review.googlesource.com`. É onde o review acontece de verdade. |
| **GerritBot** | Sincroniza pull request do GitHub com o CL correspondente. Na aceitação, os commits são esmagados num só. |
| **trybot** | A CI pré-merge, em várias arquiteturas. Um mantenedor dispara. |
| **NeedsInvestigation** | A causa raiz não é entendida ainda. Serve para triagem, não para patch. |
| **NeedsDecision** | Entendido, mas o time ainda não decidiu a abordagem. Não escrever código antes da decisão. |
| **NeedsFix** | *"Fully understood and code can be written to fix it."* É o alvo certo para patch. |
| **freeze** | Metade de cada ciclo de 6 meses é feature freeze. Durante o freeze, bugfix entra e feature não. |
| **proposal process** | Mudança de API, de linguagem ou da CLI do `go` passa obrigatoriamente por lá. CL direto é fechado. |
| **GOEXPERIMENT** | Liga funcionalidade experimental do toolchain em tempo de build. |
| **GODEBUG** | Liga ou restaura comportamento antigo em tempo de execução. Usado para compatibilidade. |
| **`git codereview`** | Substitui `git commit` e `git push` no fluxo Gerrit. `change` cria o commit, `mail` envia. |
| **Change-Id** | Linha no rodapé do commit que amarra o commit ao CL. Nunca editar à mão. |
| **`all.bash`** | A suíte completa da árvore. Tem que terminar com `ALL TESTS PASSED`. |

**Formato da mensagem de commit:** primeira linha `pacote: resumo em minúscula sem ponto final`,
que precisa completar a frase *"This change modifies Go to ____"*.
Exemplo real: `math: improve Sin, Cos and Tan precision for very large arguments`.
Corpo em frases completas, ~72 colunas, sem Markdown. `Fixes #N` fecha a issue, `Updates #N` só
vincula.

---

## CPython

| Termo | O que é |
|---|---|
| **blurb** | A ferramenta e o nome da entrada de changelog, em `Misc/NEWS.d/next/<Seção>/`. Obrigatória na maioria dos fixes. |
| **patchcheck** | `make patchcheck`. Verificação local antes de abrir o PR, inclusive se o blurb existe. |
| **pydebug** | O build de desenvolvimento (`--with-pydebug`). *"You should always develop under a pydebug build."* Nunca medir performance nele. |
| **refleak** | Vazamento de contagem de referência. Caça-se com `./python -m test <teste> -R 3:3`, necessário depois de mexer em código C. |
| **free-threaded** | O build sem GIL. **Não** dizer "nogil" num PR — é o nome antigo, do tempo do fork experimental. |
| **buildbot** | A CI deles, rodando em plataformas exóticas. Acha o que a sua máquina não acha. |
| **skip issue** | Label que dispensa issue vinculada num fix trivial. Só quem tem commit access aplica. |
| **PEP 7** | Guia de estilo do código **C** do CPython. |
| **PEP 8** | Guia de estilo do código **Python**. |
| **`main`** | O tronco. É a linha de desenvolvimento da próxima versão. Todo fix começa aqui e é portado para trás depois. |
| **backport** | Portar o fix para branch de manutenção. Feito por label, geralmente pelo bot. |
| **core dev** | Quem tem commit access. Só eles aprovam merge. Nenhum review é garantido: *"we cannot force anyone to review pull requests."* |

**Formato:** título do PR com prefixo `gh-NNNNN:` e descrição citando `#NNNNN`. Commit com
primeira linha no imperativo e **sem ponto final**. Um problema por PR. Merge deles é squash.

---

## Armadilhas de vocabulário

- Em Go, chamar o CL de "PR" numa conversa no Gerrit.
- Em CPython, dizer "nogil" em vez de "free-threaded".
- Dizer "bug" antes de ter repro mínimo. Até lá é "comportamento inesperado".
- Em Go, propor mudança de comportamento num CL em vez de no proposal process.
- Perguntar "posso trabalhar nisso?" numa issue. É ruído. Se for fazer, faz e abre o PR.

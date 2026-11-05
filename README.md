# Branches — caderno de campo

Isto não é um projeto de software. É o registro público das minhas investigações de bugs em
projetos open source upstream, principalmente **CPython** e **Go**.

Cada caçada fica em `hunts/NNN-slug/` e contém o que um mantenedor precisaria para julgar o caso
sozinho: repro mínimo, matriz de versões, resultado de `git bisect` com SHA, análise e veredito.

Registro **todas** as investigações, inclusive as que terminam em "comportamento esperado, eu
entendi errado". Essas são as que ensinam mais, e um caderno onde tudo dá certo não é um caderno
honesto.

## Estrutura

| Pasta | O que tem |
|---|---|
| `hunts/` | Uma pasta por investigação. `_TEMPLATE/` é a ficha em branco. |
| `baselines/` | Estado conhecido das suítes de teste antes de eu tocar em nada. Sem isso não se distingue "eu quebrei" de "já estava quebrado". |
| `tools/stress/` | Stress tests de concorrência para o build free-threaded do CPython. |
| `tools/fuzz/` | Alvos de fuzzing e corpus. |
| `tools/diff/` | Harnesses de teste diferencial (versão vs versão, C vs Python puro, GIL vs free-threaded). |
| `writeups/` | Texto longo sobre as caçadas concluídas. |

## Método

1. **Triagem** — reproduzir, bissecar e diagnosticar issue que já existe. É onde o mantenedor
   gasta a maior parte do tempo dele, e entregar isso pronto já é contribuição.
2. **Fix dirigido** — corrigir issue já diagnosticada, com teste, no formato que o projeto exige.
3. **Bug novo** — achado por ferramenta (ThreadSanitizer, fuzzing, teste diferencial), não por
   leitura de código.

O ciclo de patch é repro-first: primeiro o teste que falha na suíte do próprio projeto, depois o
fix mínimo. Sem refactor — não se refatora código de terceiro dentro de um bugfix.

## Divulgação responsável

Achado com cara de vulnerabilidade **não** vira issue pública. CPython vai por
[security advisory privado](https://github.com/python/cpython/security/advisories/new) ou
`security@python.org`; Go vai por `security@golang.org`.

## Plano

| Arquivo | Para que |
|---|---|
| [PLANO-CACA-BUGS.md](PLANO-CACA-BUGS.md) | O plano completo, com sessões, checklists e critérios de sucesso. |
| [PROCESSO.md](PROCESSO.md) | Checklist operacional de cada projeto: comandos pré-PR, formato de commit, canal de segurança. |
| [GLOSSARIO.md](GLOSSARIO.md) | O vocabulário de cada projeto. Palavra errada no primeiro contato custa caro. |

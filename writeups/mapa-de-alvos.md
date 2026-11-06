# Mapa de alvos de contribuição — quem realmente aceita, e onde o crédito aparece

Levantado em 2026-11-06. Dados da API do GitHub, amostra dos 100 PRs fechados mais recentes de
cada repo.

## O critério, e por que não é "repo famoso"

O objetivo declarado é contribuição que **um terceiro verifique em dez segundos**. Recrutador não
lê histórico de commit. O que ele consegue checar é:

1. teu nome num **changelog oficial de release**;
2. um **PR merged** num repo que ele reconhece;
3. um **crédito de CVE**.

Então as colunas que importam são: o repo aceita gente de fora, quanto se espera, e **o crédito é
publicado por nome**.

## Dois vieses que eu precisei corrigir no meio do caminho

Vale registrar porque qualquer um que repita esta medição cai neles.

**Viés 1 — bots.** `author_association` não distingue humano de robô. Sem excluir, o CPython
aparecia com mediana de **0,1 dia** até o merge (era o `miss-islington`, bot de backport) e o
`google/jax` parecia abertíssimo, com 94 PRs merged (**87 eram `copybara-service[bot]`**, a
ferramenta de export interno do Google).

**Viés 2 — mantenedor que não é membro da org.** No `facebook/zstd`, 13 dos PRs "de fora" eram do
próprio Yann Collet. A associação diz `CONTRIBUTOR` porque ele não é membro da org `facebook` no
GitHub, não porque seja externo. Daí a coluna `top1`: se um nome só responde por quase todos os
PRs "externos", é mantenedor disfarçado.

**Viés 3, que eu NÃO consegui corrigir.** Projeto que entra contribuição por *cherry-pick* ou
*rebase-and-push* fecha o PR **sem** marcar merge, e o indicador fica cego. Afeta `curl`,
`openssl` e `pytorch`, que aparecem com ~0 merged. **Não conclua que eles rejeitam contribuição** —
no caso do curl é o contrário, é um dos projetos mais acolhedores que existem. Para esses, o
indicador útil é outro: autores distintos com commit no branch principal (curl: 27, openssl: 47,
nos últimos 100 commits).

## O mapa

`fora_h` = PRs merged de **humano** de fora · `pessoas` = quantos humanos distintos ·
`top1` = PRs do mais prolífico deles · `med` = mediana de dias até o merge

| Repo | Tipo | merged | bots | fora_h | pessoas | top1 | med |
|---|---|---|---|---|---|---|---|
| `llvm/llvm-project` | C++ | 77 | 1 | 65 | **49** | 5 | 1,8 d |
| `vllm-project/vllm` | C++ / IA | 65 | 0 | 50 | **42** | 3 | 2,5 d |
| `modelcontextprotocol/rust-sdk` | Rust / Anthropic | 84 | 18 | 42 | **38** | 3 | 7,2 d |
| `ggml-org/llama.cpp` | C++ / IA | 64 | 0 | 38 | **30** | 4 | 2,1 d |
| `nodejs/node` | C++ | 69 | 9 | 30 | 21 | 5 | 7,6 d |
| `microsoft/mimalloc` | C | 58 | 7 | 38 | 20 | 11 | **0,8 d** |
| `huggingface/transformers` | IA | 75 | 0 | 23 | 18 | 4 | 5,7 d |
| `facebook/zstd` | C | 55 | 21 | 34 | 16 | 13 | 2,7 d |
| `valkey-io/valkey` | C | 89 | 5 | 35 | 16 | 9 | 3,0 d |
| `python/cpython` | C / Python | 76 | 33 | 24 | 16 | 4 | 5,2 d |
| `google/gemma.cpp` | C++ / IA / Google | 84 | 64 | 19 | 9 | 6 | 3,0 d |
| `google/jax` | IA / Google | 94 | **87** | 7 | 7 | 1 | 5,6 d |
| `modelcontextprotocol/python-sdk` | IA / Anthropic | 19 | 4 | **1** | 1 | 1 | 31,9 d |
| `protocolbuffers/protobuf` | C++ / Google | 44 | **41** | **0** | 0 | — | — |
| `modelcontextprotocol/servers` | IA / Anthropic | 80 | 3 | **0** | 0 | — | — |
| `curl/curl` | C | 2 | 0 | 1 | 1 | 1 | — |
| `openssl/openssl` | C | 0 | 0 | 0 | 0 | — | — |
| `pytorch/pytorch` | C++ / IA | 0 | 0 | 0 | 0 | — | — |

As três últimas linhas são o viés 3, não o veredito.

## Onde gastar tempo é desperdício

Isto responde diretamente o "ver os que realmente aceitam para não perder tempo".

| Repo | Por quê |
|---|---|
| `protocolbuffers/protobuf` | 44 merged, **41 bots, zero humano de fora**. Desenvolvimento é interno no Google, o GitHub é espelho. |
| `google/jax` | 87 dos 94 merged são `copybara-service[bot]`. Sobram 7 humanos externos numa amostra de 100. É export, não colaboração. |
| `anthropics/anthropic-sdk-python` | O `CONTRIBUTING.md` diz: *"Most of the SDK is generated code."* Só `src/anthropic/lib/` e `examples/` não são regenerados. PR em arquivo gerado é conflito garantido. |
| `modelcontextprotocol/servers` | 80 merged e **zero** de humano de fora — tudo `MEMBER`/`COLLABORATOR`. |
| `modelcontextprotocol/python-sdk` | 1 externo merged na amostra, mediana de **32 dias**. |

## Onde o crédito é publicado por nome

Esta é a coluna que o mapa acima não tem e que mais importa para o teu objetivo.

| Projeto | Crédito | Verificabilidade |
|---|---|---|
| **curl** | `RELEASE-NOTES` de **cada** release traz lista nominal: *"This release would not have looked like this without help, code, reports and advice from friends like these:"* — e credita quem só **reportou**, não só quem mandou código | **altíssima** |
| **CPython** | `Doc/whatsnew/3.15.rst` tem **255** ocorrências de *"Contributed by"*; 48 das 370 entradas pendentes de `Misc/NEWS.d` dizem *"Patch by \<nome\>"*. Isso vai para o changelog oficial em docs.python.org, permanente | **altíssima** |
| **node** | `CHANGELOG.md` (55 KB) lista commits com autor | média |
| **llama.cpp** | arquivo `AUTHORS` (99 KB) | média |
| **llvm**, **vllm**, **mimalloc**, **zstd**, **valkey** | só histórico de git | baixa |

O curl é o único que credita **relato**, não apenas patch. Para quem está começando, é a razão
de custo-benefício mais favorável do conjunto.

## Oferta de alvo no CPython, medida

Como já há trabalho em andamento lá, vale o número:

| Busca | Abertas |
|---|---|
| `label:topic-free-threading is:issue is:open` | **127** |
| idem + `label:type-bug` | 68 |
| idem + `-linked:pr` (sem PR associado) | 103 |
| `label:easy is:issue is:open` | 66 |
| `label:"good first issue"` | 0 — **o CPython não usa essa label** |

## Leitura

**O ativo mais raro já está montado, e não é um repo.** O aparato de três builds no mesmo commit
(GIL, free-threaded, free-threaded + ThreadSanitizer), com baseline limpo de TSan e o oráculo
diferencial, é o que custa caro e o que quase ninguém tem. Foi ele que produziu a
[gh-161489](https://github.com/python/cpython/issues/161489) por acidente, em um dia.

Dos 127 issues de free-threading abertos, 103 não têm PR. É a maior oferta de bug real e
não-trivial da tabela, num tema que recrutador reconhece, com crédito nominal no changelog
oficial do Python.

O ângulo C/C++ que você quer **também já está coberto por dentro**: o mimalloc é uma biblioteca C
da Microsoft **vendorizada dentro do CPython**, e a assertion da caçada
[005](../hunts/005-mimalloc-arena-abandon/) é um bug em C naquele código. Não precisa de repo
novo para ter contribuição em C.

Se ainda quiser abrir uma segunda frente, os dois melhores do mapa por motivos opostos:

- **curl** — crédito nominal por release incluindo relato, projeto reconhecidíssimo, C puro. Risco:
  Daniel Stenberg é rápido e exigente, e o padrão de código é rígido.
- **llvm** — 49 pessoas distintas de fora merged em 100 PRs, mediana de 1,8 dia. É o grande projeto
  de C++ mais genuinamente aberto da amostra. Risco: crédito só no git, e a barreira técnica é a
  mais alta da lista.

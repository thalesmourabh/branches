# Comentários postados — registro

**Status: os três foram postados em 2026-11-06, com aprovação explícita.**

| Caçada | Issue | Comentário |
|---|---|---|
| [001](001-tracemalloc-start-race/) | [gh-126315](https://github.com/python/cpython/issues/126315) | [issuecomment-6679277526](https://github.com/python/cpython/issues/126315#issuecomment-6679277526) |
| [002](002-list-iter-setstate/) | [gh-129139](https://github.com/python/cpython/issues/129139) | [issuecomment-6679279206](https://github.com/python/cpython/issues/129139#issuecomment-6679279206) |
| [003](003-list-sort-empty/) | [gh-126559](https://github.com/python/cpython/issues/126559) | [issuecomment-6679280566](https://github.com/python/cpython/issues/126559#issuecomment-6679280566) |

Estado das issues no momento de postar: as três abertas, sem comentário novo desde a triagem
(último comentário em cada uma: `devdanzin` 2026-04-15, `Yhg1s` 2025-01-22, `colesbury` 2024-11-08).

---

## Decisões de redação

Valem para os próximos comentários também.

1. **Em inglês.** É a língua dos dois projetos.
2. **Fatos primeiro, sem opinião sobre o fix.** Em 001 e 002 não digo o que fazer; em 003
   recomendo fechar, porque ali o veredito *é* o conteúdo.
3. **Não pergunto "posso trabalhar nisso?"** É ruído, e está na lista do que não fazer.
4. **Declaro uso de IA no fim de cada um.** `devdanzin` fez exatamente isso no comentário de
   reabertura da gh-126315 (*"done with assistance from Claude Code, reviewed by a human"*), então
   o precedente está no próprio thread.

## O que cada um entrega

**001 — gh-126315.** Confirma em 3.16 sem sanitizer o que foi relatado em 3.15 com ASan, e conecta
duas observações que a issue trata como separadas (a janela do assert e os três
`PyMem_SetAllocator`).

**002 — gh-129139.** O maior dos três. Amplia a issue de 1 para 3 iteradores, mostra que um dos
sintomas atinge o build com GIL desde 3.13, e localiza os dois commits culpados.

**003 — gh-126559.** Veredito negativo: comportamento documentado, recomendo fechar. Limpeza de
backlog, não descoberta.

## O que esperar

Comentário de triagem não gera notificação de revisão; depende de um core dev passar. Não
cobrar, não fazer bump. Se a gh-129139 render resposta, o próximo passo natural é E2 — patch nos
três `__setstate__`, que é mudança de comportamento e precisa de decisão de core dev antes.

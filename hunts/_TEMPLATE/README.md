# Caçada NNN — <título curto do sintoma>

| Campo | Valor |
|---|---|
| **Projeto** | python/cpython · golang/go · outro |
| **Issue upstream** | <link, ou "nenhuma — achado novo"> |
| **Escada** | E1 triagem · E2 fix dirigido · E3 bug novo |
| **Como apareceu** | TSan · fuzzing · teste diferencial · leitura de issue · relato de usuário |
| **Status** | investigando · triado · PR aberto · merged · won't fix · working as intended |
| **Data de início** | AAAA-MM-DD |

---

## 1. Sintoma

O que se observa, em uma frase. Sem teoria, sem causa, sem palpite.

## 2. Repro mínimo

Arquivo: `repro.py` (ou `repro_test.go`)

Como rodar:

```
<comando exato>
```

Saída esperada vs. saída obtida:

```
esperado:
obtido:
```

## 3. Matriz de versões

Onde reproduz e onde não. É isso que separa regressão de bug antigo.

| Versão / build | Reproduz? | Observação |
|---|---|---|
| 3.13 | | |
| 3.14 | | |
| 3.15 | | |
| `main` | | |
| free-threaded | | |
| com GIL | | |

## 4. Bisect

Log completo em `bisect.log`.

- Bom conhecido: `<SHA>`
- Ruim conhecido: `<SHA>`
- Script usado: `<comando que o git bisect run executou>`
- **Commit culpado:** `<SHA completo>` — <assunto do commit>

## 5. Análise

O que o commit culpado mudou e por que isso produz o sintoma. Mecanismo, não narrativa.

## 6. Veredito

Uma destas, explicitamente:

- [ ] **Bug.** Justificativa: a doc/especificação diz X e o código faz Y.
- [ ] **Comportamento esperado.** Eu entendi errado por: ...
- [ ] **Bug de documentação.** A doc está errada, o código está certo.
- [ ] **Indefinido.** Falta decisão de design do projeto.

## 7. O que eu fiz com isso

- Comentário na issue: <link>
- PR / CL: <link>
- Reportado em canal privado de segurança: sim / não — <por quê>

## 8. Resultado e aprendizado

Preencher em `outcome.md` quando fechar. Inclusive — e principalmente — se deu errado.

"""Mapa de repos candidatos, com os dois vieses do indicador anterior corrigidos.

Vies 1 -- BOTS. A associacao de autor nao distingue humano de bot. Sem excluir,
o CPython parecia ter mediana de 0,1 dia (era o miss-islington, bot de
backport) e o jax parecia abertissimo (87 de 94 eram copybara-service[bot],
a ferramenta de export interno do Google).

Vies 2 -- MANTENEDOR QUE NAO E MEMBRO DA ORG. No zstd, 13 dos PRs "de fora"
eram do proprio Yann Collet. author_association diz CONTRIBUTOR porque ele nao
e membro da org "facebook" no GitHub, nao porque ele seja de fora.

Correcao: excluir bots por nome, e reportar quantos HUMANOS DISTINTOS de fora
tiveram PR merged, com a contagem do mais prolifico -- se um unico nome
responde pela maioria, provavelmente e mantenedor, nao contribuidor externo.
"""
import json
import statistics
import subprocess
from collections import Counter
from datetime import datetime

REPOS = [
    ("curl/curl", "C"),
    ("llvm/llvm-project", "C++"),
    ("nodejs/node", "C++"),
    ("microsoft/mimalloc", "C"),
    ("facebook/zstd", "C"),
    ("valkey-io/valkey", "C"),
    ("openssl/openssl", "C"),
    ("ggml-org/llama.cpp", "C++ / IA"),
    ("python/cpython", "C / Python"),
    ("protocolbuffers/protobuf", "C++ / Google"),
    ("google/jax", "IA / Google"),
    ("google/gemma.cpp", "C++ / IA / Google"),
    ("pytorch/pytorch", "C++ / IA"),
    ("vllm-project/vllm", "C++ / IA"),
    ("modelcontextprotocol/python-sdk", "IA / Anthropic"),
    ("modelcontextprotocol/servers", "IA / Anthropic"),
    ("modelcontextprotocol/rust-sdk", "Rust / Anthropic"),
    ("huggingface/transformers", "IA"),
]

DENTRO = {"MEMBER", "OWNER", "COLLABORATOR"}
F = "%Y-%m-%dT%H:%M:%SZ"


def eh_bot(login):
    l = (login or "").lower()
    return ("[bot]" in l or l.endswith("-bot") or l.endswith("bot")
            or "islington" in l or "copybara" in l or "dependabot" in l)


def gh(path, jq):
    r = subprocess.run(["gh", "api", path, "--jq", jq],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


print(f"{'repo':34} {'tipo':18} {'merged':>6} {'bot':>4} {'fora_h':>7} "
      f"{'pessoas':>8} {'top1':>5} {'med.d':>7}")
print("-" * 100)

saida = []
for repo, tipo in REPOS:
    prs = gh(f"repos/{repo}/pulls?state=closed&per_page=100&sort=updated&direction=desc",
             '[.[] | {a: .author_association, m: .merged_at, c: .created_at, u: .user.login}]')
    if prs is None:
        print(f"{repo:34} {tipo:18} {'ERRO':>6}")
        continue

    merged = [p for p in prs if p.get("m")]
    bots = [p for p in merged if eh_bot(p.get("u"))]
    fora_h = [p for p in merged
              if p.get("a") not in DENTRO and not eh_bot(p.get("u"))]

    logins = Counter(p["u"] for p in fora_h)
    top1 = logins.most_common(1)[0][1] if logins else 0
    tempos = []
    for p in fora_h:
        try:
            tempos.append((datetime.strptime(p["m"], F) - datetime.strptime(p["c"], F)).total_seconds() / 86400)
        except Exception:
            pass
    med = statistics.median(tempos) if tempos else None

    print(f"{repo:34} {tipo:18} {len(merged):>6} {len(bots):>4} {len(fora_h):>7} "
          f"{len(logins):>8} {top1:>5} {(f'{med:.1f}' if med is not None else '-'):>7}")

    saida.append({
        "repo": repo, "tipo": tipo, "merged": len(merged), "bots": len(bots),
        "fora_humanos": len(fora_h), "pessoas_distintas": len(logins),
        "top1": top1, "mediana_dias": med,
        "top5": logins.most_common(5),
        "fechados_sem_merge": len(prs) - len(merged),
    })

with open("mapa-final.json", "w", encoding="utf-8") as f:
    json.dump(saida, f, indent=2, ensure_ascii=False)
print("\nlegenda: fora_h = PR merged de humano de fora | pessoas = humanos distintos")
print("         top1 = PRs do mais prolifico deles (se ~= fora_h, e mantenedor, nao externo)")

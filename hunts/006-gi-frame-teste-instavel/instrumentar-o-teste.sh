#!/usr/bin/env bash
# A hipotese de inanicao do reader foi refutada: 1440 tentativas sob 24x de
# sobrecarga, 0 frames vazio, reader sempre com >=196 voltas. Entao o
# len(frames)==0 do regrtest vem de outra coisa, e eu nao sei qual.
#
# Em vez de chutar, instrumentar: patch LOCAL no teste do worktree de build
# (nao e arvore upstream) para gravar, quando frames ficar vazio, quantas
# voltas o reader deu e o que gi_frame devolveu.
#
# Isso separa as duas unicas explicacoes possiveis:
#   voltas == 0  -> o reader nao rodou (inanicao, apesar do que medi)
#   voltas > 0   -> o reader rodou e gi_frame veio None SEMPRE, o que seria
#                   bug de verdade e exatamente o assunto da gh-144446
set -u
cd ~/src/cpython-ft || exit 1
T=Lib/test/test_free_threading/test_generators.py

# Guarda o original e garante restauracao mesmo se algo falhar.
cp "$T" /tmp/test_generators.orig.py
restaurar() { cp /tmp/test_generators.orig.py "$T"; echo "teste restaurado"; }
trap restaurar EXIT

python3 - "$T" <<'PYEOF'
import io, sys
p = sys.argv[1]
s = io.open(p, encoding='utf-8').read()

antigo = """        def reader():
            while not done.is_set():
                frame = g.gi_frame
                if frame:
                    frame.f_code
                    frame.f_locals
                    frames.add(frame)
            self.assertIsNone(g.gi_frame)

        threading_helper.run_concurrently([runner, reader])
        self.assertEqual(len(frames), 1)"""

novo = """        diag = {'voltas': 0, 'nao_none': 0}

        def reader():
            while not done.is_set():
                diag['voltas'] += 1
                frame = g.gi_frame
                if frame:
                    diag['nao_none'] += 1
                    frame.f_code
                    frame.f_locals
                    frames.add(frame)
            self.assertIsNone(g.gi_frame)

        threading_helper.run_concurrently([runner, reader])
        if len(frames) != 1:
            import sys as _s
            print(f"DIAG frames={len(frames)} voltas={diag['voltas']} "
                  f"nao_none={diag['nao_none']}", file=_s.stderr, flush=True)
        self.assertEqual(len(frames), 1)"""

if antigo not in s:
    print("ANCORA NAO ENCONTRADA", file=sys.stderr)
    sys.exit(1)
io.open(p, 'w', encoding='utf-8', newline='\n').write(s.replace(antigo, novo))
print("teste instrumentado")
PYEOF
[ $? -eq 0 ] || exit 1

echo "=== rodando ate falhar, 3 tentativas de 400s ==="
for i in 1 2 3; do
  out=$(timeout 400s ./python -m test test_free_threading.test_generators \
          -F --parallel-threads=4 -j10 -W 2>&1)
  if printf '%s' "$out" | grep -q 'DIAG'; then
    echo "  tentativa $i: capturado"
    printf '%s' "$out" | grep 'DIAG' | sort -u | head -5
    break
  elif printf '%s' "$out" | grep -q 'mimalloc: assertion'; then
    echo "  tentativa $i: caiu na assertion do mimalloc antes"
  else
    echo "  tentativa $i: sem falha de gi_frame"
  fi
done

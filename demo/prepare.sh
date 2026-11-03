#!/usr/bin/env bash
# Prépare la démo : fixtures propres, serveur de règles, page locale, profil, session tmux "sensai".
# À lancer depuis un terminal système, pas depuis celui de VS Code (snap) : Chrome n'y démarre pas.
set -e
DEMO_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$DEMO_DIR")"
WORK="${SENSAI_DEMO_WORK:-/tmp/sensai-demo}"
EX="$ROOT/docs/demo_assets/examples/demos"

for s in sensai mcp preview; do tmux kill-session -t "$s" 2>/dev/null || true; done
rm -rf "$WORK" /tmp/sensai/screenshot.jpg
mkdir -p "$WORK/home"
cp -R "$EX/python-tests" "$WORK/cart"
cp -R "$EX/feature-tour" "$WORK/preview"
cp "$ROOT/docs/demo_assets/demos/cart-spec.md" "$ROOT/personas.json" "$DEMO_DIR/personas-revue.json" "$ROOT/.env" "$WORK/"
ln -s "$ROOT/.venv" "$WORK/.venv"

tmux new-session -d -s mcp "cd '$ROOT' && .venv/bin/python demo/mcp_server.py"
tmux new-session -d -s preview "cd '$WORK/preview' && python3 -m http.server 18877 --bind 127.0.0.1"
# HOME isolé : le profil de démo n'écrase pas ~/.sensai/state.json.
tmux new-session -d -s sensai -x 130 -y 50 -c "$WORK" \
  "HOME='$WORK/home' PATH='$WORK/.venv/bin:$PATH' PS1='camille@atelier-nova \$ ' bash --norc"

launch() { tmux send-keys -t sensai -l "$1"; tmux send-keys -t sensai Enter; }
launch "sensai --persona tester"
sleep 6; launch camille; sleep 1; launch nova-demo; sleep 3; launch y; sleep 5
launch "/prefs add Pour les projets Python, lance les tests avec python3 -m pytest -q."
sleep 1; launch "/exit"; sleep 2; tmux send-keys -t sensai C-l

# Précharge le modèle pour éviter l'attente du premier appel.
curl -s http://localhost:11434/api/generate -d '{"model":"qwen3.5:latest","keep_alive":"60m"}' >/dev/null
curl -s http://localhost:11434/api/embed -d '{"model":"nomic-embed-text","input":"x"}' >/dev/null
echo "Prêt. Projeter : tmux attach -t sensai  |  Piloter : demo/souffleur.sh"

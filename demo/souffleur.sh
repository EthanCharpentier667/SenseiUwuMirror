#!/usr/bin/env bash
# Entrée = prompt suivant ; y, n, 1-9 = réponse transmise à Sensai ; r = renvoyer ; q = quitter.
# Sur demande, sans avancer dans le script : b = prompt navigateur ; c = prompt capture d'écran.
FILE="${1:-$(dirname "$0")/prompts.txt}"
TARGET=sensai
BROWSER_PROMPT="Avec les outils browser, ouvre http://127.0.0.1:18877/index.html, écris 0 dans le champ Item prices, clique sur Calculate subtotal, puis dis-moi le résultat affiché."
SCREENSHOT_PROMPT="Prends une capture d'écran et dis-moi quel sous-total tu vois sur la page."
mapfile -t LINES < "$FILE"
i=0
send() { tmux send-keys -t "$TARGET" -l "$1"; sleep 0.2; tmux send-keys -t "$TARGET" Enter; }
show() {
  while (( i < ${#LINES[@]} )) && [[ -z "${LINES[i]}" || "${LINES[i]}" == \#* ]]; do
    [[ -n "${LINES[i]}" ]] && printf '\033[36m%s\033[0m\n' "${LINES[i]}"
    ((i++))
  done
  (( i < ${#LINES[@]} )) && printf '\n\033[1mSuivant :\033[0m %s\n' "${LINES[i]}" || { echo "Fin du script."; exit 0; }
}
show
while IFS= read -rsn1 key; do
  case "$key" in
    "") send "${LINES[i]}"; last="${LINES[i]}"; ((i++)); show ;;
    [yn1-9]) send "$key"; echo "→ $key" ;;
    r) [[ -n "$last" ]] && send "$last" ;;
    b) send "$BROWSER_PROMPT"; last="$BROWSER_PROMPT"; echo "→ prompt navigateur envoyé" ;;
    c) send "$SCREENSHOT_PROMPT"; last="$SCREENSHOT_PROMPT"; echo "→ prompt capture envoyé" ;;
    q) exit 0 ;;
  esac
done

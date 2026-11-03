# Script de démo : Camille vérifie le panier avant la review de Malik

## Correspondance des codes

Les codes viennent de `features_catalog.pdf`. Le barème additionne les étoiles des fonctionnalités validées, avec un plafond de 12.

| Code | Fonctionnalité | Étoiles | Où | Ce qui le montre | État |
| --- | --- | --- | --- | --- | --- |
| B1 | Chatbot CLI | Base, 0 point | Acte 2 | Réponse en streaming, historique de session | Fonctionne |
| A1 | Boucle ReAct | ★★★ | Acte 2 | Réflexion, action et observation visibles | Fonctionne ; résumés parfois inexacts |
| T1 | MCP | ★★★ | Acte 3 | Outil `cart_rule` découvert, règle inconnue signalée | Fonctionne ; second serveur à préparer |
| T2 | Code en sandbox | ★★★ | Acte 5 | Erreur, correction, puis `OK` dans Docker | Fonctionne avec un prompt guidé |
| R1 | RAG | ★★ | Actes 1 et 2 | Spec indexée, puis `CART-EMPTY-001` citée | Fonctionne ; aucun seuil de pertinence |
| T3 | Recherche web | ★★ | Acte 6 | `web_search` et sa réponse | Fonctionne ; la requête sort vers `ollama.com` |
| A3 | Human-in-the-loop | ★ | Actes 2 et 4 | Approbation ou refus avant une action | Fonctionne ; classification par outil entier |
| M1 | Sessions et profils | ★ | Actes 1 et 8 | Préférences déjà là, session reprise | Fonctionne |
| A5 | Personas | ★ | Actes 1 et 7 | `--persona`, puis changement sans perdre l'historique | Fonctionne |
| X4 | Questions et formulaires | ★ | Acte 7 | Question à choix via `ask_user` | Fonctionne, mais fragile selon le prompt |
| M2 | Budget de tokens et compression | ★★ (★★★ si très bonnes mesures) | Acte 7 | `/stats`, résumé de l'historique | À ne pas revendiquer sur `main` |
| T4 | Accès aux fichiers avec permissions | ★ | Actes 2 et 4 | `file_read`, `file_write` avec approbation | Partiel : aucune liste de chemins |
| T5 | Sortie structurée | ★ | Acte 9 | JSON conforme au schéma | Partiel : aucune validation locale |
| M3 | Mémoire structurée | ★★ | Aucun | Rien à montrer | Non implémentée |

Hors catalogue, donc sans étoile : Bash (actes 2 et 4), navigateur (entre les actes 6 et 7), `/stats` et `--show-prompt` (actes 7 et 8), qui répondent à des critères du barème sur le contexte.

## Préparer

Dans un **terminal système**, pas celui de VS Code : son environnement snap fait planter Chrome.

```bash
demo/prepare.sh              # fixtures propres, serveurs locaux, profil, modèle préchargé
tmux attach -t sensai        # fenêtre projetée
demo/souffleur.sh            # second terminal, sur l'écran du présentateur
```

| Touche dans le souffleur | Effet |
| --- | --- |
| Entrée | Envoie le prompt suivant de `prompts.txt` |
| `y`, `n`, `1` à `9` | Transmet ta réponse à Sensai (approbation, question) |
| `r` | Renvoie le dernier prompt |
| `q` | Quitte |

Le souffleur ne décide jamais à ta place : chaque approbation reste un choix humain, visible à l'écran.

Avant de commencer : notifications coupées, fenêtres sensibles fermées, Docker démarré.

## Le déroulé

Durées mesurées lors de la dernière répétition complète, avec des approbations immédiates. Le total atteint environ 5 min sans vos explications ni l'étape du navigateur.

### Acte 1 : Camille arrive (M1, A5, R1)

```text
sensai --persona tester --model qwen3.5:latest --temperature 0.2 --trust partial --compression-threshold 3000 --files cart-spec.md
/prefs
```

- **Attendu :** `Successfully ingested file: cart-spec.md`, puis la préférence pytest déjà enregistrée.
- **À dire :** la spec reste indexée dans la session ; ses préférences sont injectées sans qu'elle les répète.
- **Limite :** SQLite n'est pas chiffré.

### Acte 2 : lancer et diagnostiquer (B1, A1, A3, R1, Bash, T4) · 37 s

```text
Lance les tests avec cd cart && python3 -m pytest -q, dis-moi quel comportement échoue et pourquoi, d'après la spécification jointe. Ne modifie rien pour l'instant.
```

- **Attendu :** une approbation, `1 failed, 1 passed`, `test_empty_basket`, `assert 1 == 0`, et la citation de `CART-EMPTY-001`.
- **À dire :** ReAct contraint plutôt qu'appel d'outils natif ; le code valide chaque étape et applique les budgets.
- **Limite observée à chaque répétition :** le modèle invente le nom du second test (`test_non_empty_basket`, `test_non_empty_cart`), alors qu'il s'appelle `test_regular_basket`. La preuve fiable est la sortie de l'outil, pas le résumé.
- **Limite T4 :** l'approbation protège les fichiers, mais il n'y a aucune liste de chemins, et `bash_tool` contourne les outils fichiers.

### Acte 3 : la règle de Malik (T1) · 32 s

```text
/mcp add-json atelier '{"url":"http://127.0.0.1:18876/mcp"}'
Lis la règle CART-EMPTY-001 sur le serveur de règles de Malik, puis la règle PAY-001.
```

- **Attendu :** `MCP connected: 1 tool(s) added.`, la règle lue, puis `PAY-001` non trouvée, sans invention.
- **À dire :** l'outil distant passe par la même boucle et les mêmes approbations que les outils intégrés.
- **À prévoir :** le catalogue annonce aussi un test avec un serveur existant, et il n'a pas été répété.

### Acte 4 : corriger et revérifier (A3, T4) · 42 s

```text
Le code est dans cart/cart.py. Corrige le défaut, puis relance cd cart && python3 -m pytest -q et donne le nouveau résultat.
```

- **Attendu :** `file_write` sur `cart/cart.py` avec `else 0`, puis `2 passed`.
- **Moment clé :** lis le `file_write` à voix haute. S'il modifie le test, réponds `n` : c'est la démonstration d'A3, car le modèle l'a déjà fait avec `llama3.2`.
- **Observé après un refus :** le modèle a demandé quoi faire avec `ask_user` au lieu d'inventer un résultat, mais `SOUCIS.md` rapporte un résumé inventé lors d'un autre essai.

### Acte 5 : vérification jetable (T2) · 57 s

```text
Exécute exactement ce code Python dans le sandbox, sans try/except : def subtotal(p): return sum(p) if p else 1 ; puis assert subtotal([]) == 0 ; puis print('OK'). Si l'exécution échoue, corrige la fonction d'après l'erreur et relance dans le sandbox.
```

- **Attendu :** `AssertionError`, une correction, puis `OK`.
- **À dire :** pas de réseau, système de fichiers en lecture seule, utilisateur non root, conteneur détruit.
- **Limite observée :** avec un prompt plus libre, le modèle a emballé l'assertion dans un `try/except` et n'a jamais vu l'échec. La correction marche quand l'erreur remonte, et ce prompt la guide. Dites-le.

### Acte 6 : chercher une documentation (T3) · 36 s

```text
Cherche sur le web comment pytest marque un test comme attendu en échec, en une phrase, avec l'URL de la source.
```

- **Attendu :** `@pytest.mark.xfail`.
- **Limite à dire :** la requête part vers `ollama.com` sans approbation en mode `partial`, ce qui contredit l'argument « tout reste dans l'entreprise ». L'acte 8 montre comment la couper.
- **Observé :** l'URL de `docs.pytest.org` est citée lors des trois répétitions du prompt renforcé.

### Entre les actes 6 et 7 : le navigateur (Browser)

```text
Avec les outils browser, ouvre http://127.0.0.1:18877/index.html, écris 0 dans le champ Item prices, clique sur Calculate subtotal, puis dis-moi le résultat affiché.
```

- **Attendu :** `Subtotal: 0`.
- **Limite observée :** quand Chrome a planté, le modèle s'est rabattu sur `xdg-open`, puis a voulu cliquer dans une page qu'il ne contrôlait pas. Lis chaque approbation.

### Acte 7 : le livrable pour Malik (A5, X4, compression) · 50 s

```text
/persona switch web_tester
Demande-moi avec ask_user si je veux un résumé court ou détaillé pour Malik.
Écris ce résumé pour Malik en cinq lignes, sans tableau ni question : le test qui échouait, la correction, le résultat final et ce qui n'a pas été testé.
/stats
/exit
```

- **Attendu :** le persona change sans perdre l'historique, puis une question à choix, à laquelle tu réponds `1`, puis un résumé en cinq lignes. `/stats` indique le remplissage du contexte et `Summary: yes` (21 messages résumés lors des deux derniers passages).
- **Limite observée à chaque répétition :** juste après ta réponse à la question, le modèle affiche une phrase sur `ask_user` ou l'appel brut au lieu d'un accusé de réception. Annonce-le, puis envoie le message suivant : c'est pour cela que le résumé est demandé à part.
- **Limite observée, à relire à voix haute :** le résumé a écrit que `PAY-001` « n'existe pas dans le codebase », alors que la règle est absente du serveur de Malik, et il n'a pas dit que le paiement n'a pas été testé. Une version plus longue a aussi posé la question à Malik et affirmé que seul `test_empty_basket` avait été vérifié. Dites que le résumé se relit avant d'être envoyé.
- **Sur M2 :** présentez le seuil, le déclenchement et ces limites. Le correctif et la mesure avec baseline sont sur `refactor/token-budgeting`, pas sur `main` : fusionnez avant de citer les chiffres (33 % → 80 % à `num_ctx` 4096, 100 % → 80 % à 16384).

### Acte 8 : le lendemain (M1, A5, désactivation, contexte) · 22 s

```text
sensai --model qwen3.5:latest --show-prompt --personas-file personas-revue.json --persona revue --disable tools rag compression
/session list
/session switch 1
Quel test échouait au départ, et qu'as-tu modifié ? Réponds en deux phrases.
/exit
```

- **Attendu :** historique repris, système fonctionnel malgré les fonctionnalités coupées, et un seul prompt affiché, d'environ 60 lignes. Dans une fenêtre de 50 lignes, seul le bloc JSON du début sort de l'écran.
- **À dire :** l'ordre des blocs : préférences et instructions, résumé, historique, cadrage, puis nouvelle demande. Sans RAG, il n'y a pas d'extraits.
- **À annoncer :** la persona `revue` et `--disable tools` servent à garder le prompt lisible. Avec `tester` et les outils, la même question affiche environ 280 lignes, réparties sur deux requêtes.
- **À vérifier :** avec plusieurs sessions, le numéro `1` peut changer ; lis la liste avant de l'envoyer.

### Acte 9 : sortie structurée (T5) · 10 s

```text
sensai --model qwen3.5:latest --disable tools --output-schema '{"type":"object","properties":{"test":{"type":"string"},"verdict":{"type":"string","enum":["pass","fail"]}},"required":["test","verdict"],"additionalProperties":false}'
Le test test_empty_basket a échoué avec assert 1 == 0. Donne le verdict.
/exit
```

- **Attendu et observé :** `{ "test": "test_empty_basket", "verdict": "fail" }`.
- **Limite à dire :** le schéma est transmis à Ollama, sans validation locale ni nouvelle tentative. Dans l'état, cela peut ne pas valider T5 : posez la question au suivi.

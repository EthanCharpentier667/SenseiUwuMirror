# Démo Sensai

**Scénario :** Camille vérifie le panier d'Atelier Nova avant la review de Malik. Un test échoue, elle le diagnostique avec Sensai, corrige le défaut, puis écrit un résumé pour Malik.

## Déroulé

| Acte | Ce qu'on fait | Fonctionnalités | Résultat attendu | Limite annoncée |
| --- | --- | --- | --- | --- |
| 1 | Lancer Sensai avec la spec du panier et afficher les préférences | M1, A5, R1 | Spec indexée, préférence pytest déjà présente | SQLite n'est pas chiffré |
| 2 (37 s) | Lancer les tests et expliquer l'échec d'après la spec | B1, A1, A3, R1, T4, Bash | `1 failed, 1 passed`, `assert 1 == 0`, `CART-EMPTY-001` citée | Le résumé du modèle peut être inexact (nom de test inventé en répétition) ; T4 sans liste de chemins |
| 3 (32 s) | Connecter le serveur MCP de Malik et lire une règle existante, puis une règle inconnue | T1 | `CART-EMPTY-001` lue, `PAY-001` signalée comme introuvable | Testé avec un seul serveur |
| 4 (42 s) | Corriger `cart/cart.py` et relancer les tests | A3, T4 | `else 0`, puis `2 passed` ; refus si le modèle modifie le test | Classification par outil entier |
| 5 (57 s) | Exécuter un code faux dans le sandbox et le faire corriger | T2 | `AssertionError`, correction, puis `OK` dans Docker | Prompt guidé : avec un prompt libre, le modèle a masqué l'erreur avec un `try/except` |
| 6 (36 s) | Chercher sur le web comment marquer un test en échec attendu | T3 | `@pytest.mark.xfail` | La requête sort vers `ollama.com` sans approbation |
| GIF | Vérifier le sous-total dans la page avec le navigateur, puis faire une capture d'écran | Hors catalogue | `Subtotal: 0` | Le GIF montre les outils seuls ; environ 4 min en direct, lançable si on nous le demande |
| 7 (50 s) | Changer de persona, poser une question à choix, écrire le résumé pour Malik | A5, X4, M2 | Historique conservé, question posée, résumé, `/stats` | Résumé parfois faux ; réponse brute juste après `ask_user` |
| 8 (22 s) | Reprendre la session avec des fonctionnalités coupées et le prompt visible | M1, A5 | Historique repris, prompt exact affiché | Persona courte et outils coupés pour garder le prompt lisible |
| 9 (10 s) | Demander un verdict au format JSON | T5 | `{ "test": "test_empty_basket", "verdict": "fail" }` | Schéma transmis à Ollama, sans validation locale |

## Étoiles visées

| État | Fonctionnalités | Étoiles |
| --- | --- | --- |
| Fonctionne | A1, T1, T2 (★★★ chacune), R1, T3 (★★ chacune), A3, M1, A5, X4 (★ chacune) | 17, plafonnées à 12 |
| Bancal, en cas de problème | M2 (★★), T4 (★), T5 (★) | 0 compté |

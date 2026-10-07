# Analyse des documents Sensai

Sources : `Sensai - Sensai_project.pdf` (5 pages PDF, dont couverture et page de version) et `Sensai - features_catalog.pdf` (10 pages PDF, dont couverture et page de version), tous deux en version `v1`. Analyse réalisée le 22 septembre 2026. Les numéros de page ci-dessous sont ceux imprimés dans les documents : la page imprimée 1 est la page 2 du PDF.

Ce document conserve les exigences et les distinctions utiles pour concevoir, implémenter, vérifier et présenter le projet. Les observations et recommandations sont distinguées des exigences des PDF.

## 1. Sujet, objectif et contraintes

**Objectif** (sujet, p. 1) : construire un assistant IA local aussi capable que possible, en partant d'un chatbot minimal puis en choisissant des fonctionnalités du catalogue. Chaque choix technique significatif doit être justifié par un cas d'usage réel et par ses compromis. Les exemples du sujet (assistant médical, agent de développement, professeur de japonais) illustrent des directions possibles ; aucun thème métier particulier n'est imposé.

**Contraintes techniques explicites** (sujet, p. 1) :

- Python **3.10 ou supérieur**.
- Aucun framework LLM : **LangChain, LlamaIndex, Haystack ou équivalent** sont interdits. Les bibliothèques standards et utilitaires pour les autres besoins (par exemple `requests`, `sqlite3`, `fastapi`) sont autorisés.
- **Tous les appels au modèle** passent **directement par l'API HTTP d'Ollama**. Un wrapper ou SDK qui cache ces appels ne satisfait pas la formulation explicite.

**Base obligatoire** (sujet, p. 1 ; catalogue, p. 1, B1) : un chatbot en ligne de commande relié à un modèle local Ollama, avec :

1. Réponse affichée progressivement pendant la génération (streaming réel, pas un affichage en bloc à la fin).
2. Historique de conversation pendant la session, retransmis au modèle lors des tours suivants.
3. Gestion propre des erreurs : modèle indisponible, entrée vide et échec de connexion sont cités explicitement.
4. Modèle sélectionnable par argument CLI ou fichier de configuration, sans modifier le code.

Le sujet dit que cette boucle de base est attendue à la fin du *bootstrap* et **ne rapporte aucun point à elle seule**. Le catalogue la marque obligatoire (👍). Il ne précise pas de modèle Ollama imposé.

## 2. Fonctionnalités au choix

Le catalogue contient **27 fonctionnalités supplémentaires**, regroupées en six domaines, en plus de B1. Le catalogue encourage moins de fonctionnalités bien intégrées et bien justifiées plutôt qu'une accumulation superficielle (introduction, p. 1). Pour chaque entrée, il donne une description, des exemples et **une série d'une à trois étoiles**. Le sujet promet deux axes de notation, difficulté (1 à 3 : effort d'implémentation) et valeur pédagogique (1 à 3 : profondeur d'apprentissage). **Le catalogue n'explicite pas à quel axe correspondent ses étoiles et ne donne pas deux notes séparées. Il ne faut donc pas présenter les étoiles comme une note certaine de difficulté ou de valeur pédagogique.**

### Mémoire et contexte (catalogue, pp. 1–2)

| Code | Étoiles visibles | Ce qui est attendu | Exemples du catalogue |
| --- | --- | --- | --- |
| M1 Session Persistence & Profiles | ★ | Sauvegarder et recharger l'historique entre plusieurs sessions **et** maintenir un profil utilisateur persistant (préférences, instructions) injecté au démarrage. | Instructions personnalisées ; allergies connues ; langage de programmation préféré. |
| M2 Token Budgeting & Semantic Compression | ★★ + « Depends on metrics » | Compter les tokens par tour par rapport à un budget ; à l'approche de la limite, résumer les échanges les plus anciens dans une fenêtre glissante en conservant les faits critiques. La dépendance à des métriques est signalée sans mécanisme détaillé. | Longue conversation ou ticket de support condensé. |
| M3 External Structured Memory | ★★ | Passer des fichiers plats à une base SQLite/NoSQL ; l'agent lit, crée, met à jour et supprime lui-même des enregistrements structurés (faits, entités, relations) sur le long terme. | Dossier client CRM ; base de faits de recherche. |
| M4 Artifact & State Document | ★★ | Maintenir un document vivant séparé du transcript, mis à jour progressivement. Le modèle produit des modifications **analysables par le code**, ciblant les bonnes sections sans réécrire ou corrompre l'ensemble. | Spécification, résumé de code ou article construit au fil des tours. |

### Outils (catalogue, pp. 2–3)

| Code | Étoiles visibles | Ce qui est attendu | Exemples du catalogue |
| --- | --- | --- | --- |
| T1 MCP | ★★★ | Le modèle décide pendant la génération d'appeler une fonction externe ; il émet nom et arguments structurés, le programme exécute l'outil, renvoie le résultat au modèle, qui poursuit sa réponse. **L'évaluation utilisera un outil MCP créé par l'équipe et un outil MCP préexistant.** | Calculatrice ; vérification d'un calendrier. |
| T2 Sandboxed Code Execution | ★★★ | Exécuter du code généré dans un environnement isolé (Docker ou sous-processus isolé), récupérer sortie standard et tracebacks, puis permettre au modèle de corriger ses erreurs à partir de ce retour. | Analyse de CSV ; cycle génération, exécution, correction. |
| T3 Web Search | ★★ | Laisser l'agent faire une recherche Web en direct, analyser les résultats et les injecter dans le contexte. | Réponse sourcée sur l'actualité ; veille quotidienne. |
| T4 File Access within Permissions | ★ | Opérations de lecture, écriture et création de fichiers **avec vérification des droits sur fichiers et répertoires avant chaque opération**. | Agent limité à `/src` ; demande d'accès à des dossiers système. |
| T5 Structured Output | ★ | Obtenir du modèle du JSON valide respectant un schéma défini, plutôt qu'un simple texte libre. | Données destinées à une base ou une interface. |

### RAG (catalogue, p. 4)

| Code | Étoiles visibles | Ce qui est attendu | Exemples du catalogue |
| --- | --- | --- | --- |
| R1 Basic RAG | ★★ | Chaîne complète : ingestion de documents locaux, découpage, embeddings, stockage vectoriel local, recherche par similarité sémantique et injection des meilleurs passages dans le contexte. | Questions sur contrats ou documentation ; consultation de documents personnels. |
| R2 Advanced RAG | ★★★ | **Étend R1** avec reranking, filtres de métadonnées et score de pertinence par passage pour écarter les résultats presque pertinents. | Recherche documentaire filtrée par date, auteur ou service. |

### Orchestration et raisonnement (catalogue, pp. 4–6)

| Code | Étoiles visibles | Ce qui est attendu | Exemples du catalogue |
| --- | --- | --- | --- |
| A1 Reasoning Loops (ReAct) | ★★★ | Boucles de raisonnement itératives qui rendent le cheminement du modèle explicite et vérifiable. | Vérification du code généré ; domaines où la traçabilité compte. |
| A2 Multi-Agent Orchestration | ★★★ | Plusieurs agents spécialisés coordonnent un travail et se transmettent des tâches. | Routage entre experts ; recherche, rédaction et critique ; choix de modèles selon la complexité. |
| A3 Human-in-the-Loop | ★ | Avant une action critique ou irréversible, suspendre l'exécution, présenter le plan et attendre une confirmation explicite. | Modification de fichiers sensibles ; opération financière. |
| A4 Prompt Versioning | ★ | Versionner les prompts avec date, comparaison et retour arrière ; comparer leur qualité, latence ou comportement de manière contrôlée. | Suivi d'un prompt de production. |
| A5 Persona | ★ | Nom, ton, rôle et périmètre configurables sans modifier le code ; **plusieurs profils d'agent**, sélectionnables et modifiables pendant une session **sans effacer l'historique**. | Assistant juridique ou professeur de mathématiques ; agents par matière. |
| A6 Semantic Cache | ★★ | Servir directement une réponse mise en cache pour une requête sémantiquement similaire (embeddings), sans appel au modèle. | Réponses fréquentes d'un support, avec gain de temps et CPU. |
| A7 Automated Prompt Optimization | ★ | Construire dynamiquement les prompts selon le contexte : choix automatique d'exemples few-shot, reformulation adaptative ou optimisation itérative à partir d'un signal de qualité. | Sélection d'exemples pertinents ; optimisation de pipeline de prompts. |

### Évaluation (catalogue, pp. 6–7)

| Code | Étoiles visibles | Ce qui est attendu | Exemples du catalogue |
| --- | --- | --- | --- |
| EV1 Automated Eval & Hallucination Detection | ★★★ | Évaluer automatiquement pertinence, cohérence et fidélité aux sources ; un LLM juge attribue des scores comparables entre versions ; signaler les affirmations invérifiables ou contradictoires avec les sources. | Évaluation RAG ; score de factualité. |
| EV2 Content & Privacy Guardrails | ★★★ | Interception **en entrée et en sortie** : bloquer les demandes dangereuses ou hors périmètre avant le modèle ; détecter des données personnelles ou du contenu inapproprié dans la réponse et anonymiser ou refuser selon des règles configurables. | Assistant RH limitant les données salariales ; assistant médical anonymisant des données patient. |
| EV3 Logging & Monitoring Dashboard | ★★ | Journaliser de façon structurée chaque interaction (prompt, réponse, outils, latence, tokens) et afficher des métriques (volume, latence, erreurs, dérive au fil du temps). | Détecter qu'une modification du prompt a doublé la latence. |
| EV4 Adversarial Testing | ★★ | Créer une suite de tests de jailbreak, d'injection de prompt et d'entrées malformées, avec documentation des échecs et des résistances. | Tests de sécurité internes et benchmarks adversariaux. |

### UX et cycle de vie (catalogue, pp. 7–8)

| Code | Étoiles visibles | Ce qui est attendu | Exemples du catalogue |
| --- | --- | --- | --- |
| X1 Web UI | ★ | Frontend Web découplé au-dessus du backend CLI : saisie, affichage en streaming, usage des tokens/contexte en direct, changement d'agent et configuration de base ; la logique backend reste la même. | Interface de chat Web. |
| X2 Branching — Resume & Interrupt | ★★ | **Resume** : modifier un ancien message et bifurquer vers une autre conversation en gardant la branche originale. **Interrupt** : interrompre une génération en cours et la rediriger immédiatement avec de nouvelles instructions. | Explorer plusieurs réponses ; corriger une rédaction longue en cours. |
| X3 Export & Publication | ★ | Exporter conversations **et artefacts** dans des formats utilisables (JSON, Markdown, PDF) **et** créer un lien public sans authentification permettant leur lecture dans un navigateur. | Partage d'une conversation ; archivage PDF. |
| X4 Questions & Forms | ★ | Fournir un moyen fluide à l'utilisateur de répondre aux questions posées par le LLM. Le catalogue ne détaille pas davantage les critères. | Aucun exemple supplémentaire donné. |
| X5 Scheduling | ★ | Exécuter automatiquement des tâches de l'agent à intervalles définis, sans intervention manuelle. | Synthèse quotidienne ; surveillance et alerte horaires. |

## 3. Livrables et user stories (sujet, p. 2)

Le dépôt doit contenir **au minimum** : tout le code source ; un `README.md` avec installation, liste de fonctionnalités et exemples d'utilisation ; `requirements.txt` ou équivalent de spécification des dépendances ; les user stories.

Pour **chaque fonctionnalité implémentée**, fournir **au moins deux user stories** ancrées dans des cas d'usage crédibles. Le modèle imposé est : « En tant que [type d'utilisateur], je veux [action], afin de [résultat] », suivi de critères d'acceptation **observables** (le gabarit montre trois comportements). Le sujet insiste sur le lien entre les fonctionnalités et les problèmes réellement résolus. Par prudence, documenter également des histoires pour B1 si la portée de « chaque fonctionnalité » est discutée.

## 4. Présentation finale : keynote (sujet, p. 3)

1. Ouvrir sur un scénario concret : utilisateur, objectif et contexte.
2. Montrer en direct les fonctionnalités au service **d'un système cohérent**, sans succession de démos déconnectées.
3. Expliquer pour chaque fonctionnalité importante, ou groupe de fonctionnalités, les choix techniques, les autres options envisagées et celles écartées.
4. Conclure honnêtement : ce qui fonctionne, les limites actuelles et ce qui serait fait différemment.
5. Préparer une démonstration de secours (captures ou enregistrement) pour les éléments sensibles au réseau ou au calcul lourd. Un plantage ou blocage pendant la keynote est considéré comme un manque de préparation.

## 5. Points de vigilance et questions ouvertes

### Distinctions qui changent l'implémentation

- **B1 / M1 / M3 / M4** : l'historique pendant une session, la persistance entre sessions avec profil, les données structurées que l'agent maintient, et un document de travail modifié par sections sont quatre capacités différentes.
- **T1 / outils simples** : MCP implique un appel choisi par le modèle pendant sa génération, puis un retour de résultat au modèle ; un menu CLI qui appelle directement une fonction ne suffit pas à la description.
- **R1 / R2** : R2 suppose une chaîne R1 complète, puis ajoute filtrage, reranking et score par passage.
- **A5** : configurer un seul prompt système ne couvre pas le changement entre plusieurs personas à chaud, en gardant l'historique.
- **X1** : l'interface Web s'ajoute à une logique réutilisable depuis la CLI ; elle ne remplace pas la base CLI obligatoire.
- **X2** : bifurcation et interruption sont deux sous-capacités exigées ensemble par cette entrée.
- **X3** : export de données et partage par lien public sont demandés ensemble.
- **EV2** : des contrôles seulement à l'entrée ou seulement à la sortie ne couvrent pas la définition complète.

### Ambiguïtés à clarifier avec l'équipe pédagogique si elles pèsent sur le choix des fonctions

- Le sujet annonce deux notes par fonction, mais les étoiles du catalogue n'ont pas de légende ni de seconde valeur. Leur signification précise doit être confirmée.
- La mention « Depends on metrics » pour M2 ne nomme pas le système de métriques attendu.
- X4 est très peu défini ; demander si une interface de questions structurées donnée correspond bien à la fonctionnalité.
- Le nombre minimum de fonctionnalités supplémentaires, le barème détaillé, le délai, le modèle Ollama, les performances visées et les formats exacts de tests ne sont **pas précisés dans ces deux PDF**.
- Le catalogue invite explicitement à demander lors du *Follow-up* si une implémentation compte comme une fonctionnalité donnée ; une fonctionnalité absente peut être proposée au référent pédagogique.

### Recommandations issues de l'analyse, non imposées par les PDF

- Choisir d'abord un public et un scénario réel, puis les capacités qui permettent de résoudre ce cas de bout en bout.
- Pour chaque fonction retenue, définir deux user stories et leurs critères observables avant de coder. Cela clarifie aussi ce qu'il faudra montrer en démo.
- Garder la boucle Ollama, la mémoire de contexte et les fonctionnalités supplémentaires dans des composants séparés afin de pouvoir conserver la CLI et ajouter une interface Web éventuelle.
- Prévoir une vérification par scénario complet et une démo de secours pour les fonctions qui dépendent du réseau, de modèles lourds ou d'un serveur externe.

## 6. État du dépôt observé le 22 septembre 2026

Cette section est un **instantané**, pas une propriété du sujet. Le `README.md` du dépôt décrit une installation avec `uv` et `uv run sensai`, les commandes qualité (Ruff, mypy, pytest) et les quatre membres de l'équipe. `pyproject.toml` exige Python `>=3.11`, compatible avec le minimum `>=3.10` du sujet, et n'a pas de dépendances de production déclarées à cette date. L'entrée `sensai` existante affiche un message de bienvenue ; la boucle CLI Ollama n'est pas encore implémentée. Le fichier `src/sensai/__init__.py` contient actuellement un import `requests` non déclaré dans `pyproject.toml`. Le dépôt contient déjà des modifications de travail indépendantes : elles ne doivent pas être écrasées lors de l'implémentation.

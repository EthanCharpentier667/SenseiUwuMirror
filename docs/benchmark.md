# Benchmark des familles de LLM pour SensaiUwu

**Dossier de décision pour la soutenance — sources consultées le 14 octobre 2026.**

SensaiUwu doit permettre de changer de modèle selon le matériel et la tâche.
Les données publiées soutiennent deux choix complémentaires : **Llama 3.2 3B
comme référence légère**, et **Qwen 3.5 9B comme candidat pour les tâches plus
exigeantes**. Les modèles GPT et Claude servent de références externes de
capacité ; leurs versions propriétaires ne sont pas exécutables localement
avec Ollama. Les chiffres ci-dessous proviennent de sources identifiées, sans
prétendre être des mesures réalisées par notre équipe.

## 1. Quel problème le projet résout-il ?

SensaiUwu est un assistant Python en ligne de commande qui communique directement
avec l'API Ollama. Il combine dialogue, historique, réponse en streaming,
recherche dans des documents et accès à des outils. Le choix du modèle doit
donc tenir compte de son intégration dans cette application.

| Besoin de SensaiUwu | Éléments du dépôt | Ce qu'il faut comparer |
| --- | --- | --- |
| Dialogue et modèle configurable | [`config.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/config.py), [`client.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/client.py) | Qualité de réponse, français, latence et poids à charger |
| Planification et actions | [`agent.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/agent.py), [`react.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/features/react/react.py) | Respect du schéma JSON, choix d'action et arguments corrects |
| Questions sur des documents | [`rag.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/features/rag/rag.py), [`embedder.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/features/rag/embedder.py) | Compréhension des passages, fidélité et capacité à reconnaître une information absente |
| Outils et connexions MCP | [`registry.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/features/tools/registry.py), [guide MCP](mcp-server.md) | Réussite des tâches après appel d'outil, gestion des erreurs |
| Code Python exécuté dans Docker | [`sandboxed_code.py`](https://github.com/EthanCharpentier667/SenseiUwuMirror/blob/e9808b6eaf473e6cfbde099637fe67251bdc5d7a/src/sensai/features/tools/sandbox/sandboxed_code.py) | Exactitude du code et prise en compte du résultat d'exécution |

**Particularité importante de notre agent :** le modèle propose une action
en JSON contraint ; le contrôleur Python valide cette proposition et décide
de l'exécution. Les limites actuelles sont 10 étapes, 10 appels d'outils au total
et 2 appels par outil. La réponse finale est ensuite générée en streaming.
Un bon score de function calling est un indicateur utile, mais ne mesure pas
directement la réussite de cette boucle SensaiUwu.

Le RAG utilise un modèle d'embeddings distinct, `nomic-embed-text` par défaut.
Remplacer Llama par Qwen ne remplace donc pas automatiquement la recherche
vectorielle. La configuration propose actuellement `gemma4:e4b`, `qwen3.5:9b`
et `llama3.2:latest`, avec Llama comme défaut. Notre analyse de Gemma 3 plus bas
ne doit pas être attribuée à Gemma 4.

Les fonctionnalités RAG, ReAct, outils, MCP et compression d'historique peuvent
être activées ou désactivées. Pour comparer les modèles dans SensaiUwu, conserver
les mêmes fonctionnalités actives : une différence de configuration pourrait
sinon être prise à tort pour une différence de qualité du modèle.

## 2. Sources retenues et lecture des scores

| Source | Nature | Utilité pour ce dossier | Limite |
| --- | --- | --- | --- |
| [Artificial Analysis](https://artificialanalysis.ai/models) | Évaluateur indépendant ; indices, performances et prix API | Comparer des modèles nommés dans un même référentiel | Certains indices sont estimés ; les performances API ne sont pas celles de notre PC |
| [LiveBench](https://livebench.ai/#/) | Benchmark indépendant ; classement daté et données publiques | Situer les capacités de code, raisonnement et travail sur plusieurs étapes | La version 2.0 mesure aussi des agents complets et des capacités hors de SensaiUwu |
| [IA-Top](https://ia-top.fr/comparateur-llm/) | Comparateur et agrégateur | Vue française des familles et repérage des sources | Son indice propre ne se confond pas avec les deux précédents |
| [Meta — fiche Llama](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct) et [Qwen — fiche 9B](https://huggingface.co/Qwen/Qwen3.5-9B) | Évaluations déclarées par les éditeurs | Détail des épreuves et identification exacte des variantes | Évaluations non indépendantes ; protocoles différents entre éditeurs |
| [Catalogue Ollama](https://ollama.com/library) | Fiches de distribution | Disponibilité locale, quantification, capacités et taille des fichiers | Le contexte annoncé et la taille des poids ne donnent pas la RAM réelle nécessaire |

L'**Artificial Analysis Intelligence Index v4.3.2** combine dix évaluations,
avec des poids de 30 % pour les agents, 20 % pour le code, 20 % pour le
raisonnement scientifique et 30 % pour les capacités générales. Il est
principalement textuel et anglophone. Un score de 11 est un indice composite,
pas « 11 % de bonnes réponses à toutes les questions ».
[Source : méthodologie AA](https://artificialanalysis.ai/methodology/intelligence-benchmarking).

IA-Top affiche notamment **49 ± 8,1** pour Qwen3.5 9B Reasoning, avec un statut
**provisoire**, faute de catégorie code. Ce chiffre ne contredit pas l'indice AA
de 11 : les échelles et compositions sont différentes. Nous retenons IA-Top
comme aide de lecture, et citons directement les évaluateurs pour les mesures
centrales. [Source : comparateur IA-Top](https://ia-top.fr/comparateur-llm/).

**Règle de comparaison :** même benchmark, même version, même variante et même
mode de raisonnement. Une moyenne entre AA, LiveBench et MMLU n'aurait pas de
signification. Les chiffres sont un instantané consulté à la date du dossier ;
des pages de recherche ou des fiches plus anciennes peuvent afficher d'autres
valeurs.

## 3. Comparaison par famille

Une famille contient plusieurs tailles et générations. Chaque ligne décrit
un représentant précis, pas une note universelle de son éditeur. Les
représentants ci-dessous servent à comparer les modes de déploiement et les
candidats locaux ; ils ne prétendent pas tous être les dernières sorties.

### 3.1. Repères chiffrés dans Artificial Analysis

**Référentiel affiché : Intelligence Index v4.3.2 ; valeur élevée préférable.**
Le statut « estimé » est conservé, y compris lorsque la FAQ de la fiche le
mentionne alors que son résumé n'affiche pas d'astérisque.

| Famille / éditeur | Modèle et mode exact | Indice AA | Statut du chiffre | Déploiement et intérêt pour SensaiUwu |
| --- | --- | --- | --- | --- |
| GPT / OpenAI | [GPT-5.4, Low](https://artificialanalysis.ai/models/gpt-5-4-low) | **28** | Estimé | API propriétaire ; référence externe, pas un modèle Ollama local |
| Claude / Anthropic | [Sonnet 4.6, Non-reasoning, High Effort](https://artificialanalysis.ai/models/claude-sonnet-4-6/) | **25** | Estimé selon la FAQ | API propriétaire ; référence externe pour la qualité d'assistance |
| Mistral / Mistral AI | [Mistral Small 3.2, 24B](https://artificialanalysis.ai/models/mistral-small-3-2) | **8** | Estimé | Poids disponibles ; alternative à étudier avec davantage de mémoire |
| Qwen / Alibaba | [Qwen3.5 9B, Reasoning](https://artificialanalysis.ai/models/qwen3-5-9b) | **11** | Score publié sans marque d'estimation | Poids disponibles ; candidat déjà installé pour raisonnement et code |
| Llama / Meta | [Llama 3.2 Instruct 3B](https://artificialanalysis.ai/models/llama-3-2-instruct-3b/) | **6** | Estimé selon la FAQ | Poids disponibles ; référence légère et modèle par défaut du projet |
| Gemma / Google | [Gemma 3 4B Instruct](https://artificialanalysis.ai/models/gemma-3-4b/) | **5** | Estimé | Petit modèle multimodal ; ce chiffre ne concerne pas Gemma 4 |
| DeepSeek / DeepSeek | [R1 Distill Llama 8B](https://artificialanalysis.ai/models/deepseek-r1-distill-llama-8b) | **6** | Estimé | Variante distillée sur une base Llama ; différente du grand R1 |

**Ce que ce tableau justifie :** retenir plusieurs niveaux de modèle, et
examiner Qwen 9B pour les tâches complexes. **Ce qu'il ne prouve pas :** que
Qwen sera meilleur sur chaque prompt français de SensaiUwu, ou que tous les
modèles d'une famille auront ces résultats. Les tailles, budgets de pensée
et conditions de service ne sont pas identiques.

Les poids disponibles permettent l'auto-hébergement sous la licence du modèle.
Cela ne signifie pas automatiquement « open source sans restriction ». Les
GPT propriétaires du tableau ne doivent pas être confondus avec une éventuelle
offre GPT à poids ouverts. Le client actuel est un client Ollama : utiliser
une API GPT ou Claude nécessiterait un adaptateur supplémentaire.

### 3.2. LiveBench : situer le projet face aux grands modèles

Le site affiche **LiveBench 2.0, mise à jour du 13 octobre 2026**. Les fichiers
publics utilisés portent l'identifiant `2026_09_02`, que l'interface associe à
cette mise à jour. Voici une sélection couvrant cinq familles, avec les
identifiants exacts du CSV. Mistral, Qwen3.5 et Llama3.2 sont absents de ce
fichier : nous ne leur inventons pas de score LiveBench 2.0.

| Famille | Identifiant du modèle | Code /100 | Travail prolongé /100 | Raisonnement /100 | Global /100 |
| --- | --- | --- | --- | --- | --- |
| GPT | `gpt-6.1-sol` | 96,0 | 73,0 | 92,6 | **85,4** |
| Claude | `claude-opus-5.5` | 96,3 | 85,0 | 92,2 | **86,5** |
| Gemini | `gemini-3.8-flash` | 82,2 | 30,1 | 89,3 | **67,3** |
| Qwen | `qwen3.8-max` | 60,3 | 42,3 | 88,2 | **64,2** |
| DeepSeek | `deepseek-v4.1-flash` | 85,4 | 43,8 | 86,7 | **77,3** |

Sources : [CSV public LiveBench](https://livebench.ai/table_2026_09_02.csv),
[catégories](https://livebench.ai/categories_2026_09_02.json),
[notes de mesure](https://livebench.ai/notes_2026_09_02.json).
Une [copie des lignes retenues](benchmark-sources/livebench-selection-2026-10-14.csv)
est conservée pour la soutenance.

Les cellules sont les notes moyennes d'une suite sur une seule exécution.
Le global, recalculé ici puis arrondi à une décimale, est la moyenne des
**sept** suites disponibles : design, recherche, navigateur, code, travail
prolongé, analyse de données et raisonnement. Il ne se limite pas aux trois
colonnes détaillées. Le site indique employer l'effort maximal pris en charge,
sauf exception signalée dans la ligne détaillée.

**Utilité pour le jury :** une bonne note de raisonnement ne garantit pas une
bonne exécution sur plusieurs étapes. Pour SensaiUwu, la réussite de la boucle
d'agent reste un critère à part. Ces données de grands modèles ne sont pas
transférables à Qwen 9B, Llama 3B ou à notre contrôleur Python. Les notes de
code concernent des tâches de correction, pas une garantie générale de code
correct. [Lecture des scores : LiveBench](https://livebench.ai/#/methodology).

## 4. Comparaison ciblée : Qwen 3.5 et Llama 3.2

### 4.1. Les deux modèles réellement installés

Inventaire relu sur Ollama **0.34.2** le 14 octobre 2026. Le tag local Llama
est `latest`, mais ses caractéristiques identifient la variante 3B. Les
identifiants ci-dessous permettent de distinguer cet inventaire du catalogue
en ligne, dont un tag peut évoluer.

| Critère | Llama 3.2 3B | Qwen 3.5 9B | Conséquence pour SensaiUwu |
| --- | --- | --- | --- |
| Tag installé | `llama3.2:latest` | `qwen3.5:9b` | Comparer ces variantes précises |
| Identifiant abrégé | `a80c4f17acd5` | `56671c2ab938` | Retrouver les poids réellement utilisés |
| Paramètres annoncés localement | 3,2B | 9,0B, plus un projecteur vision | Tailles différentes ; ce n'est pas un test à paramètres égaux |
| Quantification | Q4_K_M | Q4_K_M | Même catégorie de quantification, pas même consommation mémoire |
| Poids sur disque | **2,0 GB** | **6,6 GB** | Qwen représente environ 3,3 fois le volume de fichiers |
| Contexte maximal annoncé | **131 072 tokens** | **262 144 tokens** | Potentiel documentaire plus grand, dépendant du contexte configuré et de la RAM |
| Capacités déclarées | Texte, outils | Texte, vision, outils, thinking | Qwen ouvre davantage d'usages ; leur intégration doit être vérifiée |
| Licence | Llama 3.2 Community License | Apache 2.0 | Conditions de réutilisation différentes |

Sources : commandes locales `ollama list` et `ollama show`, ainsi que les fiches
[Llama 3.2 3B](https://ollama.com/library/llama3.2:3b) et
[Qwen 3.5 9B](https://ollama.com/library/qwen3.5:9b).

La configuration de SensaiUwu fixe `num_ctx` à **16 384** par défaut. Une fenêtre
théorique de 262k ne signifie donc pas que SensaiUwu utilise effectivement 262k.
La vision de Qwen est une possibilité d'évolution : le support actuel de
documents via extraction de texte ne démontre pas une chaîne multimodale
image→modèle déjà intégrée.

### 4.2. Mesure indépendante disponible

Dans le référentiel AA retenu : **Qwen3.5 9B Reasoning = 11**, contre **Llama
3.2 Instruct 3B = 6 estimé**. C'est un signal en faveur de Qwen sur cet indice,
avec une réserve forte sur l'estimation Llama. Ce n'est ni un gain de 5 points
sur tous les usages ni une preuve que Qwen est « presque deux fois meilleur ».
Les modèles diffèrent aussi en taille, génération et budget de raisonnement.
Sources : [Qwen AA](https://artificialanalysis.ai/models/qwen3-5-9b),
[Llama AA](https://artificialanalysis.ai/models/llama-3-2-instruct-3b/).

AA publie pour Qwen 9B Reasoning **65,7 tokens/s** et des tarifs médians API
de **0,135 $ par million de tokens entrants** et **0,20 $ par million sortant**.
La fiche Llama n'affiche pas de vitesse exploitable. Ces mesures de services
hébergés ne permettent donc aucune conclusion chiffrée sur la vitesse relative
des deux modèles sous Ollama. Une tarification affichée à zéro ou absente ne
signifie pas que l'inférence locale n'a aucun coût.
[Source : fiche Qwen AA](https://artificialanalysis.ai/models/qwen3-5-9b).

### 4.3. Épreuves publiées par les éditeurs

Les deux tableaux suivants sont volontairement séparés : ils précisent les
compétences pertinentes, mais leurs protocoles ne permettent pas tous un
calcul direct d'écart entre Qwen et Llama.

**Qwen : résultats déclarés pour les variantes 3.5 9B et 4B.**

| Épreuve | Capacité | Qwen 3.5 9B | Qwen 3.5 4B |
| --- | --- | --- | --- |
| MMLU-Pro | Connaissances et raisonnement | **82,5** | **79,1** |
| GPQA Diamond | Questions scientifiques difficiles | **81,7** | **76,2** |
| IFEval | Respect d'instructions vérifiables | **91,5** | **89,8** |
| LiveCodeBench v6 | Résolution de problèmes de code | **65,6** | **55,8** |
| BFCL-V4 | Appels de fonctions | **66,1** | **50,3** |
| LongBench v2 | Compréhension en contexte long | **55,2** | **50,0** |

Source : [fiche officielle Qwen3.5-9B, tableau Language](https://huggingface.co/Qwen/Qwen3.5-9B).
Il s'agit de chiffres éditeur, sans mesure de notre quantification Q4_K_M.
Les conditions de génération et de pensée doivent être conservées avec la
fiche pour reproduire ces résultats.

**Meta : résultats déclarés pour Llama 3.2 3B Instruct en BF16.**

| Épreuve et protocole Meta | Score publié | Intérêt pour SensaiUwu |
| --- | --- | --- |
| MMLU, 5-shot, macro accuracy | **63,4** | Connaissances générales |
| MMLU français, 5-shot | **54,6** | Repère spécifique au français |
| IFEval, moyenne prompt/instruction et loose/strict | **77,4** | Contraintes de réponse |
| GSM8K, CoT, 8-shot | **77,7** | Problèmes arithmétiques |
| BFCL V2, 0-shot | **67,0** | Appels de fonctions |

Source : [fiche officielle Llama 3.2 3B Instruct, tableaux Instruction Tuned et Multilingual](https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct).
Le BF16 n'est pas le Q4_K_M installé. Meta rapporte aussi **73,9** sur IFEval
pour une variante Vanilla PTQ, donnée de comparaison non distribuée : cela
illustre l'effet possible de la quantification, sans prédire notre score.

**Comparaisons à éviter à l'oral :** MMLU n'est pas MMLU-Pro ; BFCL V2 n'est
pas BFCL-V4 ; le résumé IFEval de Meta précise une agrégation que le tableau
Qwen ne détaille pas de la même façon. Nous ne calculons donc pas un « gain
Qwen » par soustraction de ces colonnes. La preuve comparative indépendante
retenue est l'indice AA, avec ses réserves ; les tableaux éditeur expliquent
pourquoi chaque candidat mérite d'être testé dans SensaiUwu.

### 4.4. Décision pour le projet

| Situation | Choix proposé | Justification et limite |
| --- | --- | --- |
| Démonstration sur matériel limité | Llama 3.2 3B | Poids nettement plus petits ; la latence locale reste à mesurer |
| Raisonnement, code et documents complexes | Qwen 3.5 9B | Indice indépendant plus élevé et résultats éditeur pertinents ; davantage de mémoire et de calcul possibles |
| Comparaison avec une taille proche de Llama | Ajouter Qwen 3.5 4B | Réduit l'écart de taille ; ses chiffres éditeur sont disponibles, mais ce modèle n'est pas installé |
| Usage d'images | Qwen 3.5, après intégration | Capacité vision déclarée ; Llama 3.2 3B est textuel |
| Confidentialité du contenu du prompt | Mode Ollama local | Pas de fournisseur LLM externe pour cette inférence ; les outils web/MCP peuvent toutefois transmettre des données |

**Recommandation :** conserver Llama comme option légère et proposer Qwen
3.5 9B pour les tâches qui bénéficient de ses capacités. Démontrer la sélection
du modèle comme un choix fonctionnel du projet, puis valider le compromis
qualité/latence sur les scénarios réels. Cette recommandation découle des
sources et des fichiers installés ; elle n'est pas une victoire locale mesurée.

## 5. Traçabilité

- Date de consultation : **14 octobre 2026**, heure de référence Europe/Paris.
- Dépôt examiné : commit `e9808b6`, avec les fichiers de travail présents à la consultation.
- Sources de chaque chiffre : liens dans les tableaux et paragraphes concernés.
- [Relevé structuré des valeurs retenues](benchmark-sources/measurements-2026-10-14.json) : statut, variante, unité et provenance.
- [Sélection brute LiveBench](benchmark-sources/livebench-selection-2026-10-14.csv) : sept suites, sans arrondi des notes de source.
- Statuts distincts : score indépendant publié, estimation, score éditeur, caractéristique locale.
- Les classements évoluent : actualiser les fiches avant une soutenance ultérieure en conservant cet instantané.

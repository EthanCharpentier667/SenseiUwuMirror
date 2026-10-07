# Feuille de route — T2 : Sandboxed Code Execution

Analyse du 7 octobre 2026, branche `13-feature-sandboxed-code-execution`.
Ce document propose une implémentation ; les valeurs et choix ci-dessous ne sont
pas des exigences supplémentaires du sujet.

## Objectif et critères de réussite

D'après [l'analyse du sujet](ANALYSE_SENSAI.md), T2 demande d'exécuter du code
généré dans un environnement isolé, de récupérer stdout et les tracebacks,
puis de permettre au modèle de corriger ses erreurs à partir du résultat.

La fonctionnalité est terminée quand une demande utilisateur déclenche la chaîne :

```text
Utilisateur → Ollama → appel sandboxed_code(code)
                         ↓
                conteneur Python temporaire
                         ↓
                sortie + erreurs + statut
                         ↓
              Ollama → correction éventuelle
                         ↓
                nouvelle exécution → réponse
```

Chaque appel utilise un nouveau conteneur. La correction est décidée par le
modèle dans la boucle existante ; l'exécuteur ne modifie pas le code lui-même.
Les appels au modèle continuent de passer par l'API HTTP d'Ollama.

## État réel de cette branche

- `src/sensai/tools/sandboxed_code.py` définit déjà l'outil et son argument `code`.
  Son `execute()` renvoie un texte de démonstration ; il n'exécute rien.
- `src/sensai/tools/docker/Dockerfile` contient seulement `FROM python:3.12-slim`.
- `src/sensai/tools/registry.py:get_all_tools()` ne déclare pas `SandboxedCode`.
- `src/sensai/core/setup.py` construit l'agent avec ce registre.
- `src/sensai/agent.py` sait attendre les outils asynchrones, sérialiser leurs
  résultats en JSON, ajouter un message `role=tool`, puis rappeler le modèle.
  La boucle est déjà bornée à dix tours par défaut.
- Une exception levée par un outil interrompt actuellement la boucle. Une erreur
  du programme Python doit donc être un résultat exploitable, pas une exception
  propagée par l'exécuteur.
- `pyproject.toml` ne déclare pas le SDK Docker ; mypy fonctionne en mode strict.
- `tests/tools/test_registry.py` attend actuellement trois outils.
- La CLI Docker locale annonce la version 24.0.7. L'accès au daemon depuis
  l'environnement de l'assistant est refusé ; sa version serveur, ses images et
  ses protections n'ont pas été vérifiées.

La section « État du dépôt » de `ANALYSE_SENSAI.md` date du 22 septembre : utiliser
les observations ci-dessus pour cette branche. Les modifications existantes du
Dockerfile et le fichier d'analyse sont conservés.

## Connaissances à acquérir et choix proposés

Une **image** est le modèle préparé contenant Python et ses dépendances ; un
**conteneur** est une instance exécutée à partir de cette image. Construire une
image par demande est inutile : construire à l'installation, instancier à chaque
appel, supprimer après collecte du résultat.

Les conteneurs partagent le noyau de leur hôte Linux. Docker apporte une isolation
utile, mais sa robustesse dépend aussi du noyau, du daemon et de leur maintenance.
L'accès à son daemon donne des pouvoirs importants au programme qui le pilote.
Le code généré ne doit jamais recevoir le socket Docker. Voir la
[sécurité de Docker Engine](https://docs.docker.com/engine/security/).

Je propose **Docker + SDK Python** pour le premier périmètre. Docker correspond
au squelette existant ; le SDK permet de suivre le cycle de vie et de distinguer
les erreurs Docker des erreurs du programme. Un sous-processus ordinaire ne
constitue pas une isolation des fichiers et du réseau ; le rendre isolé nécessite
d'autres mécanismes système. Une VM ou gVisor pourra être étudiée ultérieurement
si le contexte exige une isolation plus forte.

Le SDK expose notamment `create`, `start`, `wait`, `logs`, `kill` et `remove`,
ainsi que les paramètres de ressources et de sécurité. Éviter la suppression
automatique avant d'avoir récupéré logs et état. Le timeout de `wait` concerne
l'attente de l'API : prévoir explicitement l'arrêt du conteneur.
[Documentation du SDK](https://docker-py.readthedocs.io/en/stable/containers.html).

Les appels synchrones du SDK doivent s'exécuter hors de la boucle asyncio, par
exemple dans un worker lancé avec `asyncio.to_thread`. Annuler la coroutine ne
termine pas automatiquement le travail du thread : celui-ci doit lui-même
respecter une échéance et terminer le conteneur.
[Documentation Python 3.11](https://docs.python.org/3.11/library/asyncio-task.html#asyncio.to_thread).

## Périmètre initial

Python uniquement, bibliothèque standard, code fourni comme texte. Aucun package
installé à la demande, accès Internet, montage du projet, secret transmis ou état
persistant entre les exécutions. Pour une première analyse CSV, utiliser de petites
données intégrées au programme. L'import de fichiers autorisés pourra venir
ensuite, avec des permissions explicites, en coordination avec T4.

L'image, les limites et les protections sont choisis par Sensai. Le modèle reçoit
uniquement l'argument `code` ; il ne choisit ni volumes, ni réseau, ni commande
hôte, ni privilèges. Ne pas utiliser une liste d'imports interdits comme frontière
d'isolation.

## Étapes de réalisation

### 1. Définir le contrat avant Docker

Dans `sandboxed_code.py`, définir et documenter un résultat JSON stable :

| Champ | Sens |
| --- | --- |
| `status` | `success`, `execution_error`, `timeout`, `output_limit`, `resource_limit`, `invalid_input` ou `sandbox_error` |
| `stdout`, `stderr` | Textes capturés séparément ; le traceback Python est dans stderr |
| `exit_code` | Code du processus, ou null quand il est indisponible |
| `duration_ms` | Durée mesurée avec une horloge monotone |
| `truncated` | Indique une sortie limitée |
| `error` | Diagnostic d'entrée/infrastructure, ou null |

Valider type, contenu non vide et taille maximale du code avant de créer un
conteneur. Distinguer les erreurs Python des indisponibilités Docker. Ne pas
transformer toute erreur en « succès », ni prétendre connaître la cause d'un arrêt
uniquement à partir de son code de sortie : inspecter notamment `OOMKilled`.

**Terminé quand :** le contrat couvre succès, traceback, entrée invalide et erreur
d'infrastructure, avec des exemples de résultats lisibles.

### 2. Préparer l'image et les prérequis

Compléter `src/sensai/tools/docker/Dockerfile` avec un utilisateur sans privilèges
et un répertoire de travail. Ajouter le SDK Docker via `uv`, mettre à jour le lock
et vérifier les besoins de typage et du hook mypy dans `.pre-commit-config.yaml`.
Préparer une image identifiée et reproductible ; documenter sa reconstruction
pour recevoir les mises à jour de sécurité.

Premiers contrôles manuels, dans un terminal autorisé à accéder à Docker :

```bash
docker version
docker info
docker build -t sensai-sandbox:dev src/sensai/tools/docker
```

Vérifier la version serveur, les protections disponibles et l'application des
cgroups. Étudier le mode rootless : ses limites CPU/mémoire/PID nécessitent cgroup
v2 et systemd. Ne pas considérer une limite ignorée comme une protection active.
[Docker rootless](https://docs.docker.com/engine/security/rootless/).

**Terminé quand :** l'image démarre en utilisateur non-root et les prérequis sont
documentés. Une image absente produit un message actionnable ; aucune construction
ni installation automatique pendant un appel du modèle.

### 3. Construire l'exécuteur avec ses protections

Séparer l'adaptateur `SandboxedCode` du cycle Docker, par exemple dans
`src/sensai/tools/sandbox_runner.py`, afin de tester celui-ci indépendamment du LLM.

Valeurs de départ proposées, à ajuster après les tests :

| Ressource/protection | Proposition |
| --- | --- |
| Durée d'exécution | 10 secondes ; délais API et nettoyage également bornés |
| Mémoire / mémoire + swap | 256 MiB / 256 MiB |
| CPU | Quota équivalent à 1 CPU |
| Processus | 32 maximum |
| Code | 64 KiB maximum en UTF-8 |
| Sorties retournées | 64 KiB cumulés, stdout + stderr |
| Fichiers temporaires | tmpfs de 32 MiB, avec droits pour l'utilisateur du conteneur |
| Réseau | Désactivé, aucun port publié |
| Système de fichiers | Racine en lecture seule ; espace temporaire borné |
| Privilèges | Non-root, toutes les capabilities retirées, `no-new-privileges` |
| Profils système | Conserver seccomp et AppArmor/SELinux quand disponibles |

Docker ne limite pas les ressources par défaut ; les imposer et les vérifier.
Les interactions entre mémoire et swap sont documentées dans
[Resource constraints](https://docs.docker.com/engine/containers/resource_constraints/).

Transmettre le code comme donnée, sans interpolation dans une commande shell.
Pour le premier périmètre borné, un argument à `python -I -B -u -c` dans une liste
d'arguments est une option simple. Garder le TTY désactivé pour séparer les flux.
Ne transmettre que les variables d'environnement nécessaires, jamais celles de
Sensai en bloc.

Cycle attendu : valider → créer → démarrer → collecter les flux sous échéance →
inspecter l'état → arrêter si nécessaire → supprimer dans un `finally`.
Prévoir également annulation utilisateur, erreurs API et panne pendant la
collecte. Identifier les conteneurs par labels Sensai pour diagnostiquer les
orphelins après un crash, sans toucher aux autres conteneurs de la machine.

**Point à concevoir avant le premier vrai lancement :** lire toute la sortie puis
la tronquer protège seulement le résultat envoyé au modèle. Utiliser une collecte
incrémentale bornée et arrêter l'exécution si elle dépasse le budget. Borner aussi
les logs stockés par Docker ; le driver `local` propose une rotation configurable.
Tester la séparation stdout/stderr et le comportement après rotation.
[Driver de logs local](https://docs.docker.com/engine/logging/drivers/local/).

**Terminé quand :** succès, erreur, timeout et dépassement de sortie aboutissent
tous à un résultat structuré et au nettoyage du conteneur.

### 4. Brancher l'outil dans Sensai

Ajouter `SandboxedCode` à `get_all_tools()` et adapter `test_registry.py`.
Éviter de contacter le daemon dès l'import ou la construction du registre :
le reste du chatbot doit démarrer même quand Docker est indisponible.

Décrire clairement dans le schéma de l'outil : Python, bibliothèque standard,
absence de réseau et de fichiers hôtes, résultat contenant les erreurs. Vérifier
que les instructions permettent les nouvelles tentatives lorsqu'une exécution
a été demandée par l'utilisateur. Conserver la boucle de l'agent existante et sa
limite de tours ; une indisponibilité Docker ne doit pas provoquer des tentatives
inutiles de correction du programme.

La boucle attendue est : appel d'outil → message de résultat → nouvel appel au
modèle. Elle correspond à la
[documentation du tool calling Ollama](https://docs.ollama.com/capabilities/tool-calling).

**Terminé quand :** l'agent reçoit un traceback, produit un programme corrigé,
exécute à nouveau l'outil, puis répond avec un résultat vérifié.

### 5. Vérifier le comportement et les limites

Deux niveaux : tests unitaires avec un backend Docker simulé, puis tests
d'intégration avec le vrai daemon. Déclarer un marqueur pytest pour les seconds,
avec une commande explicite ; l'absence de Docker ne doit pas masquer l'absence
de validation réelle.

| Scénario | Résultat observable |
| --- | --- |
| `print(2 + 2)` | stdout contient 4, code 0, statut success |
| Sorties stdout et stderr | Les deux flux restent distincts |
| Division par zéro / syntaxe invalide | Traceback ou diagnostic Python conservé, statut execution_error |
| Boucle infinie | Arrêt après l'échéance, statut timeout, aucun conteneur restant |
| Production massive de sortie | Collecte bornée, arrêt, troncature signalée |
| Dépassement mémoire / création de processus | Limites effectives, Sensai reste utilisable |
| Connexion réseau / écriture sur la racine | Opération refusée |
| Fichier ou secret témoin uniquement sur l'hôte | Inaccessible depuis le conteneur |
| Fichier temporaire créé au premier appel | Absent dans le second conteneur |
| Annulation / erreur de collecte | Nettoyage vérifié |
| Image absente / daemon indisponible | sandbox_error compréhensible, aucune exécution locale de secours |
| Faux client Ollama : erreur puis correction | Le second appel reçoit l'erreur ; résultat final correct |

Tester les limites avec de petites valeurs dans un environnement de test prévu
pour cela. Vérifier l'état Docker et le comportement réel, pas seulement les
paramètres passés au mock. Faire ensuite un essai de bout en bout avec le modèle
Ollama choisi ; sa capacité à corriger le code reste à mesurer.

Vérifications qualité à exécuter après implémentation :

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

**Terminé quand :** les tests déterministes passent, les limites réelles sont
vérifiées et la démonstration Ollama fonctionne.

### 6. Documenter et préparer la démonstration

Ajouter au README : prérequis Docker, construction de l'image, lancement,
limitations, dépannage et commandes des tests d'intégration. Fournir au moins
deux user stories, avec critères observables :

1. **En tant qu'étudiant en Python, je veux faire exécuter un calcul par Sensai,
   afin de vérifier le résultat obtenu.** Le calcul passe par l'outil ; la sortie
   vaut la valeur attendue ; le conteneur est supprimé après exécution.
2. **En tant que développeur, je veux que Sensai utilise une erreur d'exécution
   pour corriger un script, afin d'obtenir une solution qui fonctionne.** Le premier
   résultat contient le traceback ; le modèle lance une version corrigée ; la
   réponse finale s'appuie sur une exécution réussie dans un nouveau conteneur.

Préparer une démo « calcul → erreur Python → correction → résultat » et une démo
de timeout. Conserver une capture ou un enregistrement de secours. Expliquer
les compromis : Docker, absence de réseau, ressources bornées, conteneurs jetables,
limites de l'isolation et caractère variable de la correction par le modèle.

## Ordre de travail recommandé

Six lots cohérents pour la branche : contrat et tests unitaires ; image et
prérequis ; exécuteur protégé ; intégration au registre et à l'agent ; tests Docker
et scénario de correction ; documentation et démo. Chaque lot doit satisfaire
son critère « terminé quand » avant de passer au suivant.

Le prochain travail concret est **l'étape 1**, puis la vérification des prérequis
Docker de l'étape 2. L'implémentation du runner dépend de ces deux décisions.

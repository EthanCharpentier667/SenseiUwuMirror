# Connecter un serveur MCP à Sensai

Ce guide explique comment ajouter les outils d'un serveur MCP à une conversation
Sensai. Pour Gmail ou GitHub, le serveur est déjà hébergé par le fournisseur :
vous lancez uniquement Sensai sur votre ordinateur.

La commande actuelle est **`/mcp add-json <nom> '<json>'`**. Elle se saisit dans
le chat Sensai, à l'invite `Vous >`, après avoir lancé l'application.

## 1. Préparer Sensai

Depuis la racine du dépôt :

```bash
uv sync
uv run sensai
```

Terminez la connexion à votre profil Sensai. Si Sensai n'est pas encore installé
ou configuré, suivez le [guide de démarrage](index.md#quickstart), notamment la
configuration de l'accès au modèle Ollama. Le token du modèle et les identifiants
MCP concernent des services différents.

Les exemples suivants contiennent deux types de blocs :

- `bash` : commandes à exécuter dans votre terminal système.
- `text` : commandes ou messages à saisir dans le chat Sensai.

Ne copiez pas le préfixe `Vous >`. Remplacez les placeholders comme
`YOUR_GITHUB_PAT`, `TON_CLIENT_ID` et `TON_CLIENT_SECRET` avant de soumettre.
Sensai ne remplace pas automatiquement les variables d'environnement dans le JSON.

## 2. Comprendre la commande et le format JSON

```text
/mcp add-json mon-serveur '{"type":"http","url":"https://example.com/mcp"}'
```

`https://example.com/mcp` illustre le format ; ce n'est pas un serveur de test.
Remplacez cette adresse par l'endpoint MCP indiqué par votre fournisseur.

| Élément | Rôle | Exemple |
| --- | --- | --- |
| `mon-serveur` | Nom choisi pour cette connexion, unique dans la session | `gmail` |
| `type` | Transport pris en charge ; doit être `http` | `"http"` |
| `url` | Endpoint MCP complet, pas la page d'accueil du service | `"https://api.githubcopilot.com/mcp/"` |
| `headers` | Headers HTTP facultatifs ; noms et valeurs doivent être des chaînes | `{"Authorization":"Bearer TOKEN"}` |
| `oauth` | Options facultatives pour activer l'authentification OAuth | Voir les exemples OAuth |

Copiez chaque commande `/mcp` sur une seule ligne. Les apostrophes entourent tout
le JSON, dont les clés et chaînes utilisent des guillemets doubles. Cela préserve
les espaces, notamment celui de `Bearer TOKEN`. Écrivez `https://`, sans `\` avant
les deux-points. Les placeholders des exemples ne contiennent pas d'apostrophes.

Sensai attend l'objet d'un seul serveur. Les enveloppes `mcpServers` ou `servers`,
la clé `serverUrl`, et un chemin vers un fichier JSON ne sont pas acceptés à la
place de cet objet. Convertissez la configuration en `type`, `url`, `headers` et
`oauth` comme dans ce guide.

Actuellement, le CLI utilise **Streamable HTTP**. Les serveurs `stdio` lancés avec
`command` / `args` et les anciens endpoints HTTP + SSE ne sont pas pris en charge.
Un objet `oauth` ne peut pas être combiné avec un header `Authorization`, quelle
que soit sa casse. Les autres headers peuvent accompagner OAuth.

## 3. Exemple complet sans authentification

Le dépôt fournit un serveur local de démonstration. C'est le seul exemple de ce
guide qui demande de lancer le serveur MCP sur votre ordinateur.

Dans un premier terminal, depuis la racine du dépôt :

```bash
uv run python src/sensai_mcp/sensai_server.py
```

Laissez ce terminal ouvert. Le serveur écoute sur `http://127.0.0.1:8000/mcp`.

Dans un deuxième terminal :

```bash
uv run sensai
```

Dans le chat Sensai :

```text
/mcp add-json local '{"type":"http","url":"http://127.0.0.1:8000/mcp"}'
```

Résultat attendu :

```text
MCP connected: 1 tool(s) added.
```

Puis envoyez :

```text
Utilise l'outil add pour calculer 2 + 3.
```

Approuvez l'appel si Sensai vous le demande. Le résultat de l'outil doit être `5`.
Le serveur expose aussi une ressource `greeting://{name}` et un prompt
`summarize_text`, mais le CLI ajoute uniquement les outils retournés par
`list_tools()`. Il est donc normal de voir un seul outil ajouté.

## 4. Exemple GitHub avec un token personnel

Le [serveur MCP distant GitHub](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/set-up-the-github-mcp-server)
accepte un token personnel (PAT) transmis dans un header `Authorization`.

1. Créez votre token en suivant le [guide GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
2. Donnez-lui l'accès aux dépôts et les permissions nécessaires aux outils que vous utiliserez. Les politiques de votre organisation peuvent restreindre cet accès.
3. Lancez `uv run sensai`, puis remplacez `YOUR_GITHUB_PAT` dans la commande ci-dessous.

```text
/mcp add-json github '{"type":"http","url":"https://api.githubcopilot.com/mcp/","headers":{"Authorization":"Bearer YOUR_GITHUB_PAT"}}'
```

Conservez le mot `Bearer` et l'espace qui le suit. Aucun bloc OAuth n'est
nécessaire pour cette connexion par token statique.

Après le message de connexion, essayez :

```text
Utilise les outils GitHub pour consulter les informations de mon compte.
```

Une réponse obtenue par un outil distant valide l'accès réel. Le nombre d'outils
ajoutés dépend de ce que le serveur expose. Un token expiré doit être remplacé
manuellement ; relancez Sensai pour reconnecter cette URL avec le nouveau token.

## 5. Comprendre les options OAuth

OAuth permet d'autoriser Sensai depuis une page de connexion du fournisseur.
Le SDK obtient le jeton et gère son renouvellement si un refresh token est fourni.
Consultez la [documentation OAuth du SDK MCP](https://py.sdk.modelcontextprotocol.io/client/oauth-clients/).

| Champ dans `oauth` | Utilisation actuelle |
| --- | --- |
| `redirectUri` | URL de retour après autorisation. Valeur par défaut : `http://localhost:8080/callback`. Doit correspondre à celle enregistrée chez le fournisseur. |
| `scope` | Permissions demandées, sous forme d'une chaîne. Séparez plusieurs scopes par un espace. Facultatif ; les valeurs dépendent du fournisseur. |
| `clientId` | Identifiant d'une application OAuth préenregistrée. Facultatif si le serveur permet l'enregistrement géré par le SDK. |
| `clientSecret` | Secret de cette application, si nécessaire. Exige `clientId`. |
| `issuer` | Identité du serveur d'autorisation auquel les identifiants appartiennent. Obligatoire avec `clientId`. Ce n'est pas l'URL MCP. |
| `tokenEndpointAuthMethod` | Méthode d'authentification auprès de l'endpoint de jetons. Pour ce parcours, utilisez celle du fournisseur, par exemple `none`, `client_secret_post` ou `client_secret_basic`. |

Avec `clientSecret`, la méthode par défaut est `client_secret_post`. Sinon, elle
est `none`. Sensai ne demande pas de scopes par défaut. Pour une application
préenregistrée, récupérez l'issuer dans les métadonnées du fournisseur ; n'utilisez
pas une URL arbitraire.

Si votre fournisseur autorise l'enregistrement du client par le SDK, le format
minimal est le suivant. Remplacez l'endpoint et le scope par ceux de ce serveur :

```text
/mcp add-json protected '{"type":"http","url":"https://example.com/mcp","oauth":{"redirectUri":"http://localhost:8080/callback","scope":"tools:read"}}'
```

Cet exemple est un modèle de configuration, pas une commande utilisable telle
quelle contre `example.com`.

### Terminer l'autorisation dans Sensai

1. Lorsque le navigateur s'ouvre, connectez-vous chez le fournisseur et acceptez les permissions demandées.
2. Après la redirection, copiez l'adresse complète depuis la barre d'adresse.
3. Dans Sensai, collez cette adresse à l'invite suivante :

```text
Paste the URL you were redirected to:
```

L'adresse aura une forme similaire à :

```text
http://localhost:8080/callback?code=CODE_RECU&state=STATE_RECU
```

Ces valeurs sont un exemple : collez celles de votre propre redirection, sans les
modifier. Si l'URL contient aussi `iss`, conservez-le. Sensai attend l'URL complète,
pas uniquement le code. Le SDK vérifie `state` et l'issuer retourné.

Le callback actuel est **manuel** : Sensai ne démarre pas de serveur HTTP sur le
port `8080`. Le navigateur peut donc afficher une erreur de connexion sur la page
de retour ; copiez quand même son adresse. Ce port correspond au retour OAuth,
pas au serveur MCP distant. L'autorisation peut être demandée à la connexion ou
lors d'une requête protégée : la réussite d'un appel d'outil confirme l'accès.

## 6. Exemple Gmail hébergé par Google

### Préparer l'accès Google

Le [guide officiel Gmail MCP](https://developers.google.com/workspace/gmail/api/guides/configure-mcp-server?hl=fr)
indique actuellement ces prérequis : accès au programme Preview développeur
Workspace et projet Google Cloud. Activez **l'API Gmail** et **l'API Gmail MCP**
dans ce projet.

Dans **Google Auth Platform**, configurez l'écran de consentement, ajoutez votre
compte comme utilisateur de test si l'application est externe, puis ajoutez le
scope `https://www.googleapis.com/auth/gmail.readonly` dans **Accès aux données**
pour commencer par un test de lecture.

Créez ensuite un client **Application Web** dans **Clients → Créer un client**.
Enregistrez exactement cette URI de redirection et récupérez l'ID et le secret :

```text
http://localhost:8080/callback
```

Cette adaptation pour Sensai utilise le retour localhost accepté pour les tests
par la [documentation OAuth Google](https://developers.google.com/identity/protocols/oauth2/web-server).
Les URI de retour de Claude ou Antigravity ne correspondent pas à Sensai.

### Connecter Gmail depuis le chat

Lancez uniquement `uv run sensai`. Remplacez les deux placeholders ci-dessous
par les identifiants du client Google que vous venez de créer :

```text
/mcp add-json gmail '{"type":"http","url":"https://gmailmcp.googleapis.com/mcp/v1","oauth":{"clientId":"TON_CLIENT_ID","clientSecret":"TON_CLIENT_SECRET","issuer":"https://accounts.google.com","redirectUri":"http://localhost:8080/callback","scope":"https://www.googleapis.com/auth/gmail.readonly","tokenEndpointAuthMethod":"client_secret_post"}}'
```

Google déclare cet issuer et cette méthode dans ses
[métadonnées OAuth](https://accounts.google.com/.well-known/openid-configuration).
Complétez ensuite le parcours navigateur et collez l'URL de retour comme décrit
plus haut. Aucun serveur MCP Gmail ne tourne sur votre machine.

Après la connexion, envoyez ce test de lecture :

```text
Utilise les outils Gmail pour lister les libellés de ma boîte mail.
```

Le serveur fournit l'outil `list_labels`. Une exécution réussie vérifie
l'authentification et l'accès à Gmail. Pour créer des brouillons, Google documente
aussi le scope `https://www.googleapis.com/auth/gmail.compose` ; ajoutez-le aux
permissions et à la chaîne `scope` uniquement si vous voulez ces fonctionnalités.
Voir les [outils et scopes Gmail](https://developers.google.com/workspace/gmail/api/guides/configure-mcp-server?hl=fr).

Le parcours OAuth est couvert par des tests simulés dans ce dépôt. La connexion
à votre compte Google doit encore être validée avec vos propres identifiants,
permissions et accès au programme Preview.

## 7. Durée de vie des connexions

- Les outils distants sont ajoutés à la conversation actuelle, sans réinitialiser l'agent.
- Les connexions restent ouvertes jusqu'à la sortie du CLI.
- Un nom déjà connecté est refusé. La même URL sous un autre nom n'ouvre pas une deuxième connexion.
- Plusieurs URL peuvent être connectées si leurs outils ont des noms différents. Le nom de connexion ne préfixe pas les noms des outils.
- Les configurations, jetons et informations OAuth restent en mémoire. Après fermeture, soumettez de nouveau les commandes et autorisez de nouveau l'accès si nécessaire.
- `/help` affiche la syntaxe disponible ; `/exit` termine la session et ferme les connexions.

Ne publiez pas vos commandes contenant de vrais tokens ou secrets. Les exemples
utilisent uniquement des placeholders ; les valeurs réelles permettent d'accéder
à vos services.

## 8. Dépannage

| Message ou symptôme | Action |
| --- | --- |
| `Usage: /mcp add-json <name> '<json>'` | Saisissez la commande dans Sensai avec un nom et un objet JSON entouré d'apostrophes. `/mcp <url>` n'est plus accepté. |
| `Invalid MCP JSON at line ...` | Vérifiez les guillemets doubles, les virgules et les accolades. Retirez les échappements comme `https\://`. |
| `No closing quotation` | Fermez les apostrophes autour du JSON et copiez la commande sur une seule ligne. |
| La configuration doit avoir `"type": "http"` | Fournissez l'objet d'un seul serveur, sans enveloppe `mcpServers` ou `servers`. |
| `This MCP server name is already connected.` | Choisissez un nom différent pour une autre URL, ou relancez Sensai pour remplacer une connexion. |
| `This MCP server is already connected.` | Cette URL est déjà active ; réutilisez ses outils. |
| `MCP tool names conflict ...` | Les noms d'outils entrent en conflit. Choisissez un ensemble d'outils différent côté serveur ou ouvrez une nouvelle session. |
| HTTP `401` / `403` | Vérifiez le mode d'authentification, les permissions du compte et la validité du token. Pour Gmail, vérifiez aussi les API activées et l'accès au programme Preview. |
| Google affiche `redirect_uri_mismatch` | Enregistrez exactement le `redirectUri` du JSON dans le client OAuth Google : même protocole, hôte, port et chemin. |
| `Could not open the browser ...` | Exécutez Sensai dans une session où un navigateur peut être lancé. Le parcours actuel nécessite une interaction utilisateur. |
| Page localhost inaccessible après autorisation | Attendu avec le callback manuel : copiez l'URL complète depuis la barre d'adresse et collez-la dans Sensai. |
| `OAuth authorization was refused or failed ...` | Recommencez l'autorisation et vérifiez que le compte peut accéder à l'application. |
| Le callback doit contenir un `code` et un `state` | Collez l'URL complète de la dernière tentative, pas le code seul. Ne modifiez pas les paramètres. |
| Échec de vérification du state ou de l'issuer | Utilisez la redirection de la tentative actuelle et vérifiez l'issuer associé au client OAuth. |
| Connexion réussie mais appel d'outil refusé | La découverte des outils ne prouve pas toutes les permissions. Vérifiez les scopes nécessaires à cet outil. |

Pour le serveur local uniquement, si le port `8000` est occupé :

```bash
ss -ltnp 'sport = :8000'
```

La documentation MkDocs utilise aussi ce port par défaut. Pour la consulter en
même temps que le serveur local :

```bash
uv run --group docs mkdocs serve -a 127.0.0.1:8001
```

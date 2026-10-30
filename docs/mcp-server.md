# Connect an MCP server to Sensai

This guide explains how to add an MCP server's tools to a Sensai conversation.
For the GitHub examples, the server is already hosted by GitHub:
you only run Sensai on your computer.

The current command is **`/mcp add-json <name> '<json>'`**. Enter it in
the Sensai chat, at the `Vous >` prompt, after launching the application.

## 1. Set up Sensai

From the repository root:

```bash
uv sync
uv run sensai
```

Complete the sign-in process for your Sensai profile. If Sensai is not installed
or configured yet, follow the [getting started guide](index.md#quickstart),
including the Ollama model access configuration. The model token and MCP
credentials are for different services.

The following examples contain two types of blocks:

- `bash`: commands to run in your system terminal.
- `text`: commands or messages to enter in the Sensai chat.

Do not copy the `Vous >` prefix. Replace placeholders such as
`YOUR_GITHUB_PAT`, `YOUR_GITHUB_CLIENT_ID`, and `YOUR_GITHUB_CLIENT_SECRET` before submitting.
Sensai does not automatically substitute environment variables in the JSON.

## 2. Understand the command and JSON format

```text
/mcp add-json my-server '{"url":"https://example.com/mcp"}'
```

`https://example.com/mcp` illustrates the format; it is not a test server.
Replace this address with the MCP endpoint specified by your provider.

To insert JSON from the CLI:

1. Enter `/mcp add-json my-server`, with a space after the name.
2. Press **Tab** to display the **HTTP**, **HTTP + Bearer token**,
   and **HTTP + OAuth** templates. Select a template using the arrow keys, then
   press **Enter** to insert it without sending the command.
3. Replace the URL and, for the Bearer template, `YOUR_TOKEN`. Fill in the OAuth
   options if your provider requires them, then send the command.

The single quotes around the JSON are inserted automatically. Autocompletion
also works if you have started typing the beginning of a template, for example
`'{"url"`; it does not change values you have already customized.

| Element | Purpose | Example |
| --- | --- | --- |
| `my-server` | Name chosen for this connection, unique within the session | `github` |
| `url` | Full MCP endpoint, not the service's home page | `"https://api.githubcopilot.com/mcp/"` |
| `headers` | Optional HTTP headers; names and values must be strings | `{"Authorization":"Bearer TOKEN"}` |
| `oauth` | Optional settings to enable OAuth authentication | See the OAuth examples |

Copy each `/mcp` command onto a single line. Single quotes surround the entire
JSON object, whose keys and strings use double quotes. This preserves spaces,
including the one in `Bearer TOKEN`. Write `https://`, without a `\` before
the colon. The example placeholders do not contain single quotes.

Sensai expects an object for a single server. The `mcpServers` or `servers`
wrappers, the `serverUrl` key, and a path to a JSON file are not accepted in place
of this object. Convert the configuration to `url`, `headers`, and
`oauth` as shown in this guide.

The CLI currently uses **Streamable HTTP**. `stdio` servers launched with
`command` / `args` and legacy HTTP + SSE endpoints are not supported.
An `oauth` object cannot be combined with an `Authorization` header, regardless
of its capitalization. Other headers can be used alongside OAuth.

## 3. Complete example without authentication

The repository provides a local demo server. This is the only example in this
guide that requires you to run the MCP server on your computer.

In a first terminal, from the repository root:

```bash
uv run python src/sensai_mcp/sensai_server.py
```

Leave this terminal open. The server listens on `http://127.0.0.1:8000/mcp`.

In a second terminal:

```bash
uv run sensai
```

In the Sensai chat:

```text
/mcp add-json local '{"url":"http://127.0.0.1:8000/mcp"}'
```

Expected result:

```text
MCP connected: 1 tool(s) added.
```

Then send:

```text
Use the add tool to calculate 2 + 3.
```

Approve the call if Sensai asks you to. The tool's result should be `5`.
The server also exposes a `greeting://{name}` resource and a
`summarize_text` prompt, but the CLI only adds the tools returned by
`list_tools()`. Seeing just one tool added is therefore normal.

## 4. GitHub example with a personal access token

The [GitHub remote MCP server](https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp/set-up-the-github-mcp-server)
accepts a personal access token (PAT) sent in an `Authorization` header.

1. Create your token by following the [GitHub guide](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens).
2. Grant it access to the repositories and the permissions required by the tools you will use. Your organization's policies may restrict this access.
3. Launch `uv run sensai`, then replace `YOUR_GITHUB_PAT` in the command below.

```text
/mcp add-json github '{"url":"https://api.githubcopilot.com/mcp/","headers":{"Authorization":"Bearer YOUR_GITHUB_PAT"}}'
```

Keep the word `Bearer` and the space after it. No OAuth block is
needed for this static token connection.

After the connection message, try:

```text
Use the GitHub tools to look up my account information.
```

A response from a remote tool confirms actual access. The number of tools added
depends on what the server exposes. An expired token must be replaced manually;
restart Sensai to reconnect to this URL with the new token.

## 5. Understand the OAuth options

OAuth lets you authorize Sensai through the provider's sign-in page.
The SDK obtains the token and handles renewal if a refresh token is provided.
See the [MCP SDK OAuth documentation](https://py.sdk.modelcontextprotocol.io/client/oauth-clients/).

| Field in `oauth` | Current usage |
| --- | --- |
| `redirectUri` | Required callback URL, chosen for your environment. No default value. Must exactly match the one registered with the provider. |
| `scope` | Requested permissions, as a string. Separate multiple scopes with a space. Optional; values depend on the provider. |
| `clientId` | Identifier of a preregistered OAuth application. Optional if the server allows registration managed by the SDK. |
| `clientSecret` | Secret for this application, if needed. Requires `clientId`. |
| `issuer` | Identity of the authorization server the credentials belong to. Required with `clientId`. This is not the MCP URL. |
| `tokenEndpointAuthMethod` | Authentication method for the token endpoint. For this flow, use the provider's method, such as `none`, `client_secret_post`, or `client_secret_basic`. |

With `clientSecret`, the default method is `client_secret_post`. Otherwise, it
is `none`. Sensai does not request any scopes by default. For a preregistered
application, retrieve the issuer from the provider's metadata; do not use
an arbitrary URL.

If your provider allows client registration through the SDK, the minimal format
is as follows. Replace the endpoint and scope with those of that server:

```text
/mcp add-json protected '{"url":"https://example.com/mcp","oauth":{"redirectUri":"http://localhost:8080/callback","scope":"tools:read"}}'
```

This example is a configuration template, not a command you can run as is
against `example.com`.

### Choose the callback for your environment

The autocompletion template contains `https://your-callback.example/callback`:
replace this address before sending the command. Sensai does not choose a
callback for you or create an HTTP service at that address.

- **Local execution**: if the provider accepts it, you can choose
  `http://127.0.0.1:9000/my-callback` or another registered redirect URL.
- **VPS or machine without a browser**: Sensai displays the authorization link if
  no browser can open. Open it on your computer, complete authorization,
  and paste the full redirect URL into the VPS CLI.
  `localhost` in the browser refers to your computer, not the VPS.
- **Public HTTPS callback**: use an address you control that is registered
  with the provider. You are responsible for configuring and hosting this page;
  Sensai still expects you to enter the redirect URL manually in the CLI.

Choose a URL accepted by the provider and preserve its exact
scheme, host, port, and path in `oauth.redirectUri`.

### Complete authorization in Sensai

1. When the browser opens, sign in with the provider and accept the requested permissions.
2. After the redirect, copy the full address from the address bar.
3. In Sensai, paste this address at the following prompt:

```text
Paste the URL you were redirected to:
```

The address will look similar to this:

```text
http://localhost:8080/callback?code=RECEIVED_CODE&state=RECEIVED_STATE
```

These values are examples: paste those from your own redirect without changing
them. If the URL also contains `iss`, keep it. Sensai expects the full URL,
not just the code. The SDK checks `state` and the returned issuer.

The current callback is **manual**: Sensai does not start an HTTP server at
the configured address. The browser may therefore display a connection error on
the redirect page; copy its address anyway. This address is the OAuth redirect,
not the remote MCP server. Authorization may be requested when connecting or
during a protected request: a successful tool call confirms access.

## 6. GitHub example with OAuth

### Register an OAuth App

The [GitHub MCP integration guide](https://github.com/github/github-mcp-server/blob/main/docs/host-integration.md)
requires a preregistered application: the remote server does not support Dynamic
Client Registration. This example uses a GitHub **OAuth App** with an
interactive authorization-code flow.

Follow [Creating an OAuth App](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/creating-an-oauth-app):

1. Open **Settings → Developer settings → OAuth Apps → New OAuth App** on GitHub.
2. Set **Application name** to `Sensai CLI` and **Homepage URL** to your application's public URL, such as your GitHub project page.
3. Set **Authorization callback URL** to the exact value below, then register the application.
4. Copy the **Client ID** and generate a **Client secret** for your application.

```text
http://localhost:8080/callback
```

The callback uses Sensai's manual flow described above. Use the same address in
the application registration and in the JSON configuration.

### Connect GitHub from the chat

Launch `uv run sensai`. Replace the two placeholders with your OAuth App's
credentials, then submit this command in the chat:

```text
/mcp add-json github '{"url":"https://api.githubcopilot.com/mcp/","oauth":{"clientId":"YOUR_GITHUB_CLIENT_ID","clientSecret":"YOUR_GITHUB_CLIENT_SECRET","issuer":"https://github.com/login/oauth","redirectUri":"http://localhost:8080/callback","scope":"read:user","tokenEndpointAuthMethod":"client_secret_post"}}'
```

GitHub documents `https://github.com/login/oauth` as its authorization
[issuer](https://docs.github.com/en/apps/github-authentication-discovery-endpoints).
Sensai's SDK discovers the authorization and token endpoints from the provider's
metadata. The `client_secret_post` method sends the app credentials in the token
request body, as described in [Authorizing OAuth Apps](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps).
The [`read:user` scope](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)
requests access to profile data for this first test.

Authorize the app in the browser. Copy the complete redirect URL, including
`code`, `state` and `iss` when present, and paste it at Sensai's prompt:

```text
Paste the URL you were redirected to:
```

The browser can show a connection error at localhost because Sensai does not
host the callback page. Copy that address anyway. No GitHub MCP server needs
to run locally.

### Verify access with a tool call

After connecting, send:

```text
Use the GitHub get_me tool to read my authenticated profile and report my GitHub login. Do not modify any repository.
```

Approve the tool call when prompted. The remote server's
[tool configuration](https://github.com/github/github-mcp-server/blob/main/docs/server-configuration.md)
includes `get_me`. A successful call confirms authenticated access; tool discovery
alone does not establish that repository operations are authorized.

The `read:user` scope does not grant repository write access. Additional operations
require suitable permissions and any organization approval. If the PAT example
is already connected to this URL, restart Sensai before trying OAuth: duplicate
URLs are rejected, even under a different connection name.

The example JSON is validated against Sensai's configuration parser. Completing
GitHub authorization requires your own registered application and credentials.

## 7. Connection lifetime

- Remote tools are added to the current conversation without resetting the agent.
- Connections remain open until you exit the CLI.
- A name that is already connected is rejected. Using the same URL under another name does not open a second connection.
- Multiple URLs can be connected if their tools have different names. The connection name is not used as a prefix for tool names.
- Configurations, tokens, and OAuth information remain in memory. After closing the application, submit the commands again and authorize access again if needed.
- `/tools list` lists the currently available tools, including those from connected MCP servers, grouped as `mcp:<server>`. `/tools disable mcp:<server>` turns off all the tools of one server.
- `/help` displays the available syntax; `/exit` ends the session and closes the connections.

Do not publish commands containing real tokens or secrets. The examples use
placeholders only; real values grant access to your services.

## 8. Troubleshooting

| Message or symptom | Action |
| --- | --- |
| `Usage: /mcp add-json <name> '<json>'` | Enter the command in Sensai with a name and a JSON object enclosed in single quotes. `/mcp <url>` is no longer accepted. |
| `Invalid MCP JSON at line ...` | Check double quotes, commas, and braces. Remove escapes such as `https\://`. |
| `No closing quotation` | Close the single quotes around the JSON and copy the command onto one line. |
| The configuration must be a JSON object | Provide an object for a single server, without an `mcpServers` or `servers` wrapper. |
| `This MCP server name is already connected.` | Choose a different name for another URL, or restart Sensai to replace a connection. |
| `This MCP server is already connected.` | This URL is already active; reuse its tools. |
| `MCP tool names conflict ...` | Tool names conflict. Choose a different set of tools on the server or open a new session. |
| HTTP `401` / `403` | Check the authentication method, granted scopes, account access and organization approval for the GitHub OAuth App. |
| GitHub rejects the callback URL | Register the JSON's exact `redirectUri` in the OAuth App, including scheme, host, port and path. |
| OAuth client registration fails or returns `404` | GitHub does not support Dynamic Client Registration. Supply a preregistered app's `clientId`, `clientSecret` and correct `issuer`. |
| OAuth requires `redirectUri` | Add a callback URL suitable for your environment and registered with the provider. |
| Localhost page unavailable after authorization | Expected with the manual callback: copy the full URL from the address bar and paste it into Sensai. |
| `OAuth authorization was refused or failed ...` | Retry authorization and check that the account can access the application. |
| The callback must contain a `code` and a `state` | Paste the full URL from the latest attempt, not just the code. Do not change the parameters. |
| State or issuer verification fails | Use the redirect from the current attempt and check the issuer associated with the OAuth client. |
| Connection succeeds but a tool call is denied | Tool discovery does not prove all permissions have been granted. Check the scopes required by that tool. |

For the local server only, if port `8000` is occupied:

```bash
ss -ltnp 'sport = :8000'
```

The MkDocs documentation also uses this port by default. To view it
while running the local server:

```bash
uv run --group docs mkdocs serve -a 127.0.0.1:8001
```

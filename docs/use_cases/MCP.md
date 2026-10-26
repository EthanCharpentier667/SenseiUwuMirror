# MCP servers

MCP connections extend Sensai with tools exposed by an HTTP server. The tools are
discovered during the conversation, adapted to Sensai's tool interface and made
available to the same ReAct and approval pipeline as built-in tools.

## Scenario

Malik Benali maintains review requirements separately from Camille's code checkout.
For the demonstration, a local read-only MCP server exposes the cart rule
`CART-EMPTY-001`. Camille retrieves that rule without copying it manually into
every prompt, then compares it with the observed empty-cart result.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova). Camille uses the terminal and local Ollama between development tasks; the workflow allows time for inference rather than requiring an instant production response.

## User stories

### US-MCP-01 — Retrieve a review rule through a connected tool

**As Camille Moreau, the developer checking the cart requirements, I want Sensai to discover a rule-reading tool from a configured MCP server, so that the review can refer to the requirement held by that service.**

Preconditions: the local demo server is running and MCP is enabled.

| Acceptance criterion | Expected result |
| --- | --- |
| Connection | `/mcp add-json atelier` accepts the HTTP configuration and discovers `cart_rule`. |
| Registration | The discovered tool becomes available to the agent with its declared argument schema. |
| Known rule | Calling `cart_rule` with `CART-EMPTY-001` returns the empty-cart subtotal rule of 0. |
| Unknown rule | A nonexistent identifier returns an explicit unavailable-rule response rather than an invented requirement. |

### US-MCP-02 — Keep connections and tool registration consistent

**As Malik Benali, the reviewer managing the demonstration environment, I want failed or closed MCP connections to leave tool registration consistent, so that the assistant does not offer disconnected or ambiguous tools.**

Preconditions: MCP tools are registered through the application connection manager.

| Acceptance criterion | Expected result |
| --- | --- |
| Validation | Malformed JSON or an unsupported URL is rejected before registration. |
| Names | Duplicate tool names conflicting with existing tools prevent the new registration. |
| Lifecycle | Connections remain open while their tools are in use. |
| Cleanup | Closing the manager removes its remote tools and closes its connections. |

## How it works

`/mcp add-json <name> '<json>'` accepts an HTTP(S) URL, optional headers and optional
OAuth settings. The connection manager opens the transport, discovers tools and
checks for name conflicts before retaining the connection. It keeps clients alive
with an asynchronous exit stack and removes registered remote tools on closure.

An adapter exposes the remote description and input schema to the agent and forwards
arguments to the server. JSON strings are decoded for schema fields expecting arrays
or objects. Remote tools default to `safe=False`, so normal approval rules apply.
[Detailed connection settings](../mcp-server.md) cover the supported authentication
and JSON configuration.

## Demonstration

![MCP servers: actual component walkthrough](../demo_assets/assets/demos/mcp.gif)

The recording starts a real, local, read-only MCP fixture and uses Sensai's connection
manager over HTTP. It discovers `cart_rule`, retrieves the known rule, requests an
unknown rule, then closes the connection and confirms tool removal. It calls the
component directly; it does not demonstrate a remote GitHub write or OAuth flow.

## Replay this demonstration

From the repository root, complete the [shared replay prerequisites](../demo_assets/demos/replay.md#shared-prerequisites).
The launcher opens the actual Sensai CLI with a temporary fictional profile and
working copies. Type the following commands and questions at `Vous >`; `/exit`
cleans up. Compare the stated facts and tool results, not identical model wording.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py mcp
```

1. The launcher starts the read-only fixture on loopback port 18876. Connect it
   through the actual chat command:

```text
/mcp add-json atelier '{"url":"http://127.0.0.1:18876/mcp"}'
```

2. Expect one discovered tool. Send:

```text
Use cart_rule with rule_id CART-EMPTY-001, then report the actual rule returned by the server. Do not use web search or invent a rule.
```

3. Inspect and approve the tool call. Expect the requirement that an empty cart
   has subtotal `0`.
4. Send `Use cart_rule with rule_id MISSING and report the server response.`
   Approve it. Expect an unknown-rule response, rather than an invented requirement.
5. `/exit` closes the MCP connections and the local fixture.

The component GIF shows the same discovery and rule calls directly, then confirms
that closing the connection removes the registered tool. The interactive path also
lets you inspect the model's interpretation of the returned rule.

For the exact automated component sequence and a new GIF:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py mcp
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_features.py mcp
```

## Architecture choices and tradeoffs

MCP avoids writing a bespoke integration for every external service and preserves
its advertised schema. It adds transport, authentication and remote-service lifecycle
constraints. A built-in rule tool would be simpler for this one fixture, but would
not generalize to independent services as easily.

## Limitations

Authentication support depends on each server's OAuth registration behavior or a
valid configured credential. Discovery does not imply permission to perform every
remote action. Tools can expose sensitive data or side effects. The demo fixture
is local and read-only; it does not validate third-party availability or all
remote error conventions. CLI-provided configuration must not expose real secrets
in shared terminal recordings.

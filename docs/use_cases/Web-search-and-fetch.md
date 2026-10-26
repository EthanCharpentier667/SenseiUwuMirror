# Web search and web fetch

`web_search` finds external references and `web_fetch` reads a selected page through
Ollama's web services. These complement local project evidence when the assistant
needs documentation that is not already in the conversation or attached files.

## Scenario

Camille encounters a testing-framework message that the local project does not
explain. She wants an external documentation reference before changing the code.
Malik needs to know whether the answer came from an actual fetched page or whether
external lookup was unavailable. Private cart data is not needed for that query.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova). Camille uses the terminal and local Ollama between development tasks; the workflow allows time for inference rather than requiring an instant production response.

## User stories

### US-WEB-01 — Find documentation for an unfamiliar test failure

**As Camille Moreau, the developer diagnosing an unfamiliar framework message, I want Sensai to search for a relevant reference, so that I can understand the requirement before changing the tests.**

Preconditions: external lookup is permitted, `API_TOKEN` is configured and the provider is reachable.

| Acceptance criterion | Expected result |
| --- | --- |
| Query | `web_search` receives the framework message without private project data. |
| Source | The answer identifies the external reference used. |
| Reuse | Relevant information already present in the conversation is reused rather than unnecessarily searched again. |
| Failure | Unavailable lookup is not replaced with fabricated search results. |

### US-WEB-02 — Distinguish a fetched page from unavailable lookup

**As Malik Benali, the reviewer checking a documentation-based explanation, I want the assistant to distinguish fetched content from unavailable lookup, so that I can judge the evidence behind a suggested fix.**

Preconditions: a specific documentation URL is supplied; the negative case has no configured API token.

| Acceptance criterion | Expected result |
| --- | --- |
| Fetch | `web_fetch` sends the supplied URL to the provider when configured. |
| Missing token | Without `API_TOKEN`, both tools return an unavailable message without sending a request. |
| Provider failure | A non-success HTTP status is not treated as page content. |
| Scope | The answer does not claim the page was read if no content was returned. |

## How it works

The tools call `https://ollama.com/api/web_search` and
`https://ollama.com/api/web_fetch` with bearer authentication from `API_TOKEN`.
This credential is separate from the chat client's `TOKEN`. Each call uses a
100-second HTTP timeout. Both tools are declared `safe=True`.

Search instructions prioritize local conversation evidence and describe search
as a last resort. Fetch instructions prioritize readable page content over CSS,
JavaScript or framework details. These are model instructions rather than a
hard-coded guarantee that the model will always choose the right source.

## Demonstration

![Web search and web fetch: actual component walkthrough](../demo_assets/assets/demos/web.gif)

This component capture shows the actual missing-token path for both tools. No API
key is supplied and no external request is made. The implementation returns
“Web search is not available.” for both calls, including fetch. The recording
demonstrates unavailability handling, not successful web research.

## Replay this demonstration

From the repository root, complete the [shared replay prerequisites](../demo_assets/demos/replay.md#shared-prerequisites).
The launcher opens the actual Sensai CLI with a temporary fictional profile and
working copies. Type the following commands and questions at `Vous >`; `/exit`
cleans up. Compare the stated facts and tool results, not identical model wording.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py web
```

1. The launcher intentionally removes `API_TOKEN` from its own environment while
   leaving the original shell and `.env` unchanged.
2. Send `Use web_search for pytest assertion failure empty cart. Report the actual tool response; do not invent search results.`
   Approve if prompted. Expect `Web search is not available.`
3. Send `Use web_fetch for https://docs.pytest.org/. Report whether any page content was returned.`
   Approve if prompted. The current implementation returns the same unavailable
   message for fetch when its token is absent.
4. Confirm that the answer does not claim to have read documentation from a page
   that was not returned.

This reproduces the GIF's unavailable-service case. A successful web lookup needs
a real provider credential and is not demonstrated by this recording. Supplying
a chat token does not replace the separate web `API_TOKEN`.

For the exact automated component sequence and a new GIF:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py web
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_features.py web
```

## Architecture choices and tradeoffs

A shared provider avoids implementing a crawler and search backend. It also adds
a network dependency and sends queries or URLs outside the local machine. A local
documentation corpus would keep more data local and work without this credential,
but would need ingestion, maintenance and coverage of the relevant references.

## Limitations

Successful provider-backed search and fetch are not demonstrated in this capture.
Unavailable and failed responses use `message` rather than the agent's structured
`error` key, so a tool can be recorded as completed despite returning no content.
The model must not mistake that for evidence. Network exceptions may propagate to
the agent; retrieved pages may contain incomplete, irrelevant or untrusted text.
Local chat inference does not make these external calls local.

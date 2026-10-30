# Atelier Nova feature demonstrations

These fictional fixtures support the English feature sheets. They contain no
customer records, credentials or connection to a production shop.

| Fixture | Purpose |
| --- | --- |
| [Cart specification](cart-spec.md) | Document ingestion, real embeddings and session-scoped retrieval. |
| `docs/demo_assets/examples/demos/feature-tour/index.html` | A local cart form with populated, empty and invalid input cases. |
| `docs/demo_assets/examples/demos/feature-tour/personas.json` | Evidence-focused QA and code-review roles. |
| `docs/demo_assets/scripts/demos/mcp_server.py` in the repository | A local, read-only MCP rule server. |

The companion [faulty cart](python-tests.md) has one failing test and one
passing test. The [correct cart](python-tests-passing.md) has two passing
tests. The file-access demonstration corrects a temporary copy and verifies both
outcomes without rewriting either original fixture.

## Recorded scope

Eight GIFs remain automated component walkthroughs. Their recording script
calls actual SensaiUwu tools, command handlers, database functions and HTTP clients;
it does not replace their outputs with scripted model replies. Component sequences
are chosen by the recording script, rather than autonomously planned by the model.
The earlier pytest GIF and the updated file-access, MCP, sandbox, streaming and
web GIFs record the real interactive application. For those five updates, only the
human messages and approvals are scripted: model decisions and tool execution
come from SensaiUwu itself.

| Recording | Actual scope |
| --- | --- |
| File access | Real CLI: permission modes, denied write to a read-only file, approved correction, read-back and actual pytest result. |
| Screenshot | Actual image acquisition on an isolated display, followed by a vision-model answer reading the displayed values. |
| Browser | Real browser tools on the local cart form; a preopened portable Chromium page replaces the normal visible Chrome launch. |
| Sandbox | Real CLI: model-requested Docker execution with successful checks and UID, followed by an executed failing assertion. |
| Web | Real CLI: successful provider-backed search for official pytest documentation, then a fetch of that page and a source-based reply. |
| MCP | Real CLI: connection, discovery, approved MCP rule calls and answers using the returned values, including an unknown rule. |
| RAG | Ingestion, actual document-based model reply with a unique marker, then a document-free session showing a hallucinated reference. |
| Compression | Actual local model summary and a follow-up reply using it; observed summary drift and increased character count. |
| Profiles | Saved preferences/instructions used in a real reply, followed by persistence and password verification. |
| Personas | QA and reviewer selection followed by actual answers to the same message, plus an unknown-role warning. |
| Models | Capability discovery, model selection and real answers from both models; no model-quality benchmark. |
| Flags | Actual availability changes and a model reply with tools disabled. |
| Streaming | Real CLI: partial answer text appears progressively before the final reply, captured with terminal cursor movements. |

The GIF frame and captions are presentation elements. Playback pauses are adjusted
for readability and are not timing benchmarks. Where an image is shown, its pixels
come from the actual screenshot tool. Raw captures, intermediate images and
recording metadata are retained in `docs/demo_assets/artifacts/demos/`; the published GIFs and
video remain in `docs/demo_assets/assets/demos/`. Feature sheets do not require reading
the raw capture files.

Historical captures retain their original commands and paths as evidence of the
recorded execution. Current replay instructions use `docs/demo_assets/examples/demos/` for executable
fixtures. The renderer resolves archived image events from `docs/demo_assets/artifacts/demos/`,
including events containing paths from before the reorganization.

The generated recording manifest (`docs/demo_assets/artifacts/demos/feature-recordings.json`)
identifies artifacts and checksums. The five updated interactive recordings also
have individual `<feature>-cli.json` metadata files. It documents the recorded runs rather than
claiming every user-story acceptance criterion passed.

## Interactive replay

The [manual replay guide](replay.md) explains shared prerequisites and the disposable
CLI launcher. Each feature sheet gives the exact commands, messages and expected
observations for its own GIF.

## Reproducing a component recording

The optional scripts are `docs/demo_assets/scripts/demos/record_features.py` and
`docs/demo_assets/scripts/demos/render_features.py`, invoked from the repository root. The Python
environment must include the project's dependencies plus `pyte`, Pillow,
Playwright and `pyscreenshot`. A working font installation is required for rendering.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py file-access
.venv/bin/python docs/demo_assets/scripts/demos/render_features.py file-access
```

Supported names are `file-access`, `screenshot`, `browser`, `sandbox`, `web`,
`mcp`, `rag`, `compression`, `profiles`, `personas`, `models`, `flags` and
`streaming`. Each recording uses a new temporary database and fictional account.
Recording writes raw output and intermediate images to `docs/demo_assets/artifacts/demos/`;
rendering writes the final GIF to `docs/demo_assets/assets/demos/`. Each command overwrites
only that recording's generated files and removes its temporary working directory
when finished.

The recorded Ollama endpoint is `http://127.0.0.1:11434/api/chat`, with
`llama3.2:latest` for generated text, `qwen3.5:9b` for model/vision demonstrations and
`nomic-embed-text` for embeddings. Model tags can change: the manifest retains
an inventory collected for this run. Text generated in a new run can differ.

The browser recording requires Playwright's Chromium headless shell. During this
run it was installed under `/tmp/sensai-demo-browsers`; the corresponding
`PLAYWRIGHT_BROWSERS_PATH` environment variable selects that temporary cache.
Screenshot recording requires Xephyr, `xmessage` and an accessible parent X display;
it creates and closes its own `:88` display. It redirects the screenshot destination
to the temporary workspace.

Docker is required for sandbox recording. The MCP fixture binds only to loopback
port 18876 and is stopped after the recording. The updated web recording requires
a valid `API_TOKEN` and makes actual public-documentation lookups. No credential
is printed or entered as a recorded command. The demo scripts do not modify the
application's source or use a real account keyring.

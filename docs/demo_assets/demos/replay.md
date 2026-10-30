# Replay the demonstrations yourself

Each feature sheet contains an interactive replay section: launch the real SensaiUwu
CLI, type the listed messages and inspect its responses. The launcher supplies a
fictional account and disposable copies of the fixtures, so the steps do not depend
on your personal profile or on changing the repository's original demo projects.
It uses the actual agent, HTTP client, command handlers and application chat path.
It bypasses the account wizard and keyring; it is not an authentication demonstration.

## Shared prerequisites

From the repository root, install the project and the optional recording dependencies:

```bash
uv sync
uv pip install --python .venv/bin/python pyte pillow playwright pyscreenshot pexpect
```

Start a local Ollama instance if one is not already running:

```bash
ollama serve
```

In another terminal, make the models required by your chosen demonstration available:

```bash
ollama pull llama3.2:latest
ollama pull nomic-embed-text
ollama pull qwen3.5:9b
```

Text demonstrations use `llama3.2:latest`. Only RAG needs `nomic-embed-text`;
Screenshot and the model-switch demonstration need `qwen3.5:9b`. Downloading every
model is unnecessary if you are replaying only a text demonstration.
The launcher targets `http://127.0.0.1:11434/api/chat`; its dummy bearer token
is only for a local Ollama service without authentication.

Browser replay uses the same preopened portable Chromium session as its recording:

```bash
PLAYWRIGHT_BROWSERS_PATH=/tmp/sensai-demo-browsers .venv/bin/python -m playwright install chromium --only-shell
```

Keep that environment variable on the browser launch command shown in its sheet.
Sandbox replay requires a working Docker daemon. Screenshot replay additionally
requires Xephyr, `xmessage`, a usable parent `DISPLAY`, and a free `:88` display;
it captures a dedicated fictional window rather than your desktop. The renderer
uses DejaVu fonts from `/usr/share/fonts/truetype/dejavu`.

## Interactive sessions

For example:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py personas
```

The terminal prints a temporary workspace. It contains:

| Path inside the workspace | Contents |
| --- | --- |
| `cart-failing/` | The original intentional defect: one passing test and one failing test. |
| `cart-passing/` | The correct implementation: two passing tests. |
| `cart-working/` | Another faulty copy which can be edited during the file-access demo. |
| `cart-readonly.py` | A mode-`444` source file for a real permission-denied write. |
| `cart-spec.md` | The fictional specification, including its unique review marker. |
| `personas.json` | The QA and reviewer personas used by the recordings. |
| `.venv` | A link to the repository's Python environment for the commands below. |

Type slash commands and questions at the actual `Vous >` prompt. Enter submits;
Alt+Enter inserts a newline. Approve a proposed tool call only after checking its
arguments. `/exit` ends the session and removes its temporary database and copies.
Start a new process for a fresh profile and conversation. Run replay sessions one
at a time when they use the dedicated display or loopback fixture ports.

RAG replay attaches and embeds the specification before showing the prompt.
Compression replay loads the documented fictional review history and summarizes it
before the follow-up question. The MCP and browser sessions start their local
fixtures and stop them when the session ends. The web session uses `API_TOKEN`
from the environment or local `.env` for actual searches and page fetches. Its value
never needs to be typed into a recorded terminal. Add `--without-web-token` only
when replaying the unavailable-service case.

The five interactive recordings (file access, MCP, sandbox, streaming and web) use
`--model llama3.2:latest`. The launcher configures an 8192-token context and limits the
available tools to those needed by the selected feature. File and sandbox tool
output is enabled using the real CLI output option. Tool decisions, permissions,
HTTP responses, Docker execution and text streaming use the application unchanged.

## Expected results and variability

Compare observable facts rather than identical wording: test counts, exit codes,
rule identifiers, the document marker, role prefixes, visible form totals or whether
a call was executed. Model responses and tool choices are not deterministic.
The exact configured model, Ollama version and hardware also affect timing.
A heading, citation or failure may differ on a rerun; do not replace the actual
response with the expected text if the model fails the scenario.

The recordings show some known failures, including lossy compression and invented
references in a document-free RAG session. Their feature sheets distinguish the
required behavior from what was actually observed.

## Record the real interactive scenarios

The five updated GIFs are captured from a real pseudo-terminal. The automation
submits the documented messages and answers `y` at actual approval prompts; the
SensaiUwu agent chooses and executes the tools and generates every answer.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_cli.py file-access mcp sandbox streaming web
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_cli.py file-access mcp sandbox streaming web
```

The capture is an asciicast-compatible terminal stream. The renderer honors ANSI
cursor movements and samples intermediate screen states, preserving incremental
streaming. It shortens idle waits and keeps each GIF below 1000 KiB. These playback
timings are not latency benchmarks. Per-recording metadata retains the model,
messages, approval count, real elapsed time and artifact checksums.

## Replay the original component sequence

For a step-for-step replay of a component GIF, including the recorded tool arguments:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py rag
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_features.py rag
```

Use this component path for the remaining component GIFs. The five updated
interactive GIFs use `record_cli.py` and `render_cli.py` above. This optional path
calls the recorded components directly, writes a new capture to `docs/demo_assets/artifacts/demos/`
and overwrites that feature's GIF in `docs/demo_assets/assets/demos/` when rendered. Executable
fixtures live in `docs/demo_assets/examples/demos/`; guides and the cart specification remain in
`docs/demo_assets/demos/`. The interactive launcher does not rewrite GIF assets.
The earlier pytest GIF used a separate interactive capture; its ReAct, trust and
Bash sheets give the equivalent manual foreground run on the same test data.

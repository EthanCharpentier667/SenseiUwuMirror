# Replay the demonstrations yourself

The feature sheets contain shell examples and the messages to enter in the real
SensaiUwu CLI. All setup commands are included below. The examples use fictional
Atelier Nova data and temporary working copies of the cart projects.

## Shared prerequisites

From the repository root, install the project:

```bash
uv sync
```

Start Ollama in a separate terminal if it is not already running:

```bash
ollama serve
```

Download the models needed for your chosen demonstration:

```bash
ollama pull llama3.2:latest
ollama pull nomic-embed-text
ollama pull qwen3.5:9b
```

Text examples use `llama3.2:latest`. RAG also needs `nomic-embed-text`;
screenshot interpretation and model switching need `qwen3.5:9b`.
Docker must be running for sandbox execution. Browser tools require Google Chrome
and a graphical display. Screenshot capture also requires a working capture
backend and a display; its feature sheet includes an isolated-window example.
Web lookup requires a valid `API_TOKEN` in the environment or the local `.env`.

## Example workspace setup

Run this Bash example from the repository root. Keep the same terminal open for
the launch examples in the feature sheets, which use the exported paths.

```bash
export SENSAI_DEMO_ROOT="$PWD"
export SENSAI_DEMO_WORK="$(mktemp -d /tmp/sensai-demo.XXXXXX)"

cp -R "$SENSAI_DEMO_ROOT/docs/demo_assets/examples/demos/python-tests" \
  "$SENSAI_DEMO_WORK/cart-failing"
cp -R "$SENSAI_DEMO_ROOT/docs/demo_assets/examples/demos/python-tests-passing" \
  "$SENSAI_DEMO_WORK/cart-passing"
cp -R "$SENSAI_DEMO_WORK/cart-failing" "$SENSAI_DEMO_WORK/cart-working"
cp "$SENSAI_DEMO_WORK/cart-working/cart.py" "$SENSAI_DEMO_WORK/cart-readonly.py"
chmod 444 "$SENSAI_DEMO_WORK/cart-readonly.py"
cp "$SENSAI_DEMO_ROOT/docs/demo_assets/demos/cart-spec.md" "$SENSAI_DEMO_WORK/cart-spec.md"
cp "$SENSAI_DEMO_ROOT/docs/demo_assets/examples/demos/feature-tour/personas.json" \
  "$SENSAI_DEMO_WORK/personas.json"
ln -s "$SENSAI_DEMO_ROOT/.venv" "$SENSAI_DEMO_WORK/.venv"

export HASH_ALGORITHM=sha256 HASH_ITERATIONS=600000 SALT_BYTES=32
cd "$SENSAI_DEMO_WORK"
printf 'Demo workspace: %s\n' "$SENSAI_DEMO_WORK"
```

The resulting workspace contains:

| Path | Purpose |
| --- | --- |
| `cart-failing/` | Intentional defect: one failing test and one passing test. |
| `cart-passing/` | Correct implementation: two passing tests. |
| `cart-working/` | Editable copy used for the correction demonstration. |
| `cart-readonly.py` | Mode-`444` source file for a permission-denied write. |
| `cart-spec.md` | Fictional specification with its unique review marker. |
| `personas.json` | The QA and reviewer roles used by the examples. |
| `.venv` | Link to the installed project environment. |

## Example application launch

From the prepared workspace:

```bash
"$SENSAI_DEMO_ROOT/.venv/bin/sensai" \
  --url http://127.0.0.1:11434/api/chat \
  --embed-url http://127.0.0.1:11434/api/chat \
  --token local-demo-placeholder --embed-token local-demo-placeholder \
  --model llama3.2:latest --num-ctx 8192 --trust none \
  --db-path "$SENSAI_DEMO_WORK" --personas-file personas.json \
  --disable rag compression mcp
```

The placeholder token is for a local Ollama instance without authentication.
Complete the normal registration or login flow with a dedicated demo profile,
for example Camille. Account creation is interactive and is not bypassed.
The database is stored in the temporary workspace. The application uses its normal
credential-storage behavior when signing in.

At `Vous >`, submit the feature sheet's messages one at a time. Enter submits;
Alt+Enter inserts a newline. Inspect each tool request before answering `y` or `n`.
`/exit` closes the application. The workspace remains available for inspection;
repeat the setup example to start with fresh fixtures and a separate database.

The launch examples specify the features needed for each scenario. RAG uses
`--files cart-spec.md`; compression uses a low threshold; MCP and the browser
require a second terminal for their local fixture. Their feature sheets include
the corresponding commands. Text-only examples disable tools explicitly.

## Expected results and variability

Compare facts such as exit codes, test counts, permission errors, rule identifiers,
document markers and source URLs. Model wording, tool choices and latency vary.
Recorded captures may include a preconfigured account or additional tool-output
panels; the examples above use the normal application entry point and sign-in flow.
A tool's result can be available to the bot even when the CLI displays only its
completion indicator. Ask the bot to report the observed output when needed.

The archived recordings include known failures, such as lossy compression and
invented references in a document-free RAG session. The feature sheets distinguish
those observations from the intended behavior. A repeat must retain the actual
response even when the model fails the scenario.

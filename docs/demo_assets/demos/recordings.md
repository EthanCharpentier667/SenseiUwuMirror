# Atelier Nova feature demonstrations

These fictional fixtures support the English feature sheets. They contain no
customer records, credentials or connection to a production shop.

| Fixture | Purpose |
| --- | --- |
| [Cart specification](cart-spec.md) | Document ingestion, real embeddings and session-scoped retrieval. |
| `docs/demo_assets/examples/demos/feature-tour/index.html` | A local cart form with populated, empty and invalid input cases. |
| `docs/demo_assets/examples/demos/feature-tour/personas.json` | Evidence-focused QA and code-review roles. |
| Inline server example in the [MCP feature sheet](../../use_cases/MCP.md#replay-this-demonstration) | A local, read-only MCP rule server. |

The companion [faulty cart](python-tests.md) has one failing test and one
passing test. The [correct cart](python-tests-passing.md) has two passing
tests. The file-access demonstration corrects a temporary copy and verifies both
outcomes without rewriting either original fixture.

## Recorded scope

Eight GIFs are archived component walkthroughs using actual Sensai tools, command
handlers, database functions and HTTP clients. Their sequences were automated;
their tool order was not autonomously planned by the model.
The earlier pytest GIF and the updated file-access, MCP, sandbox, streaming and
web GIFs record the real interactive application. For those five updates, only the
human messages and approvals are scripted: model decisions and tool execution
come from Sensai itself.

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
fixtures. Archived media and terminal captures retain their original paths and
outputs as evidence of the recorded run.

The generated recording manifest (`docs/demo_assets/artifacts/demos/feature-recordings.json`)
identifies artifacts and checksums. The five updated interactive recordings also
have individual `<feature>-cli.json` metadata files. It documents the recorded runs rather than
claiming every user-story acceptance criterion passed.

## Interactive replay

The [manual replay guide](replay.md) includes workspace setup and application-launch
examples. Each feature sheet gives the exact commands, messages and expected
observations for its own GIF.

## Example: convert a terminal recording to a GIF

Launch Sensai with the command from the feature sheet and record the terminal
using a desktop recorder. Keep the actual approval prompts, tool outcomes and
model responses. Save the recording as `/tmp/sensai-demo.mp4`, then run this
standalone FFmpeg example:

```bash
ffmpeg -i /tmp/sensai-demo.mp4 \
  -vf "fps=8,scale=1280:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=32[p];[b][p]paletteuse=dither=none" \
  -loop 0 /tmp/sensai-demo.gif
```

FFmpeg must be installed separately. The example creates a GIF in `/tmp` and does
not replace existing project media. Check readability and file size before
publishing; the repository's file-size limit is 1000 KiB. If needed, lower the
frame rate, shorten the recording or reduce its dimensions.

The archived text runs used `llama3.2:latest`, the vision/model demonstrations
used `qwen3.5:9b`, and embeddings used `nomic-embed-text`. The manifest retains
the recorded inventory; a new run can produce different text and timings.

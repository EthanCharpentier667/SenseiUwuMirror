# Demonstration assets

The demonstration material is grouped under `docs/demo_assets/`:

```text
docs/demo_assets/
├── demos/        # Replay guides, fixture documentation and cart specification
├── examples/     # Cart projects, browser page and persona configuration
├── artifacts/    # Archived terminal captures, images and recording metadata
└── assets/       # GIFs and video displayed in the feature sheets
```

The [manual replay guide](demos/replay.md) contains a complete shell example for
preparing temporary fixtures and launching Sensai. Each
[feature sheet](../use-case.md#features) includes its application command, chat
messages and expected observations. The [recording guide](demos/recordings.md)
describes the existing captures and includes a video-to-GIF example.

For example, after the workspace setup in the replay guide:

```bash
"$SENSAI_DEMO_ROOT/.venv/bin/sensai" \
  --url http://127.0.0.1:11434/api/chat \
  --token local-demo-placeholder --model llama3.2:latest \
  --db-path "$SENSAI_DEMO_WORK" --personas-file personas.json \
  --disable tools rag compression mcp
```

MkDocs publishes the guides and final media. Executable fixtures and archived
artifacts remain in the repository and are excluded from the generated website.

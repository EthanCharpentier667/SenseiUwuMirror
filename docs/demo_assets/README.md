# Demonstration assets

All demonstration material is grouped under `docs/demo_assets/`, including guides,
executable fixtures, recording/replay scripts, raw captures and final media.

```text
docs/demo_assets/
├── demos/        # Replay guides, test-fixture documentation and cart specification
├── examples/     # Executable cart projects, browser page and persona configuration
├── scripts/      # Interactive replay, recording, rendering and API-reference generation
├── artifacts/    # Raw terminal captures, intermediate images and recording metadata
└── assets/       # Final GIFs and video used by the feature sheets
```

The [manual replay guide](demos/replay.md) lists prerequisites and explains how to
open the real CLI on disposable fixtures. Each [feature sheet](../use-case.md#features)
contains its own messages, commands and expected observations. The
[recording guide](demos/recordings.md) describes the captured workflows and evidence.

Run commands from the repository root, for example:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py personas
```

MkDocs publishes the guides and final media. Executable examples, scripts and raw
artifacts remain available in this repository folder and are excluded from the
generated website. Historical captures retain the paths used when they were recorded;
the current replay commands use the consolidated layout above.

# File access: `file_read` and `file_write`

File tools let Sensai inspect source code and test reports, then create or replace
text files when an approved change is needed. They connect a diagnosis to the
actual project files rather than a description pasted into the conversation.

## Scenario

Camille Moreau is investigating the empty-cart failure before Malik Benali reviews
her change. She needs to inspect `cart.py`, understand why an empty cart returns 1,
and check a corrected copy without altering the original demonstration fixture.
The same workflow applies to reading a test module or a generated coverage report.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova). Camille uses the terminal and local Ollama between development tasks; the workflow allows time for inference rather than requiring an instant production response.

## User stories

### US-FILE-01 — Inspect the code responsible for a failing test

**As Camille Moreau, the developer investigating the cart regression, I want Sensai to read the relevant source file, so that its explanation refers to the implementation that actually failed.**

Preconditions: the faulty project is accessible and the requested read is approved when required.

| Acceptance criterion | Expected result |
| --- | --- |
| Content | `file_read` returns the UTF-8 contents of the requested `cart.py`. |
| Diagnosis input | The observation contains the branch returning 1 for an empty list. |
| Missing file | A nonexistent path returns an explicit error, with no invented contents. |
| Integrity | Reading does not modify the file. |

### US-FILE-02 — Verify a proposed correction on a disposable copy

**As Camille Moreau, the developer responsible for her branch, I want Sensai to write an approved correction and rerun the existing tests, so that I can check the change before including it in my merge request.**

Preconditions: a disposable copy exists, its parent directory is writable, and the proposed write and test command are approved when required.

| Acceptance criterion | Expected result |
| --- | --- |
| Write | `file_write` writes the supplied corrected source into the selected copy. |
| Verification | The copy changes from `1 failed, 1 passed` to `2 passed` when the same two tests run. |
| Original fixture | The separate faulty demo fixture retains its intentional defect. |
| Invalid destination | An inaccessible path or nonexistent parent directory returns an error rather than a success claim. |

## How it works

| Tool | Inputs | Result |
| --- | --- | --- |
| `file_read` | `file_path` | Contents and a document path, or an explicit error. |
| `file_write` | `file_path`, `content` | Written content and a document path, or an explicit error. |

Reads check that the path is a readable regular file and decode it as UTF-8.
Writes check the destination, then create or overwrite the file. Parent directories
are not created automatically. Both tools are declared `safe=False` and therefore
require confirmation in `none` and `partial` trust modes.

The document path lets the application ingest the file for [RAG](RAG.md) when that
feature is enabled. The [Bash tools](Bash.md) provide the subsequent test execution;
writing a file by itself does not establish that a fix works.

## Demonstration

![File access: `file_read` and `file_write`: actual component walkthrough](../demo_assets/assets/demos/file-access.gif)

The walkthrough calls the actual file and Bash tools on a temporary copy. It reads
the faulty implementation, obtains one failing test, writes a supplied correct
implementation, and obtains two passing tests. A final read of a missing file
shows the error response. The correction is provided by the recording script;
this capture does not demonstrate the model generating a patch.

## Replay this demonstration

From the repository root, complete the [shared replay prerequisites](../demo_assets/demos/replay.md#shared-prerequisites).
The launcher opens the actual Sensai CLI with a temporary fictional profile and
working copies. Type the following commands and questions at `Vous >`; `/exit`
cleans up. Compare the stated facts and tool results, not identical model wording.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py file-access
```

1. Ask `Use file_read to show cart-working/cart.py. Do not modify it.` Approve the read.
   The implementation contains the empty-list branch returning 1.
2. Send:

```text
Use bash_tool with background=false to run exactly .venv/bin/python -m pytest -c cart-working/pytest.ini --no-cov -q cart-working. Report the actual result.
```

3. Approve the command. Expect `1 failed, 1 passed`, code `1`.
4. Supply the correction explicitly, as in the component recording:

```text
Use file_write to replace only cart-working/cart.py with the one-line Python source "def subtotal(prices): return sum(prices)" followed by a newline. Do not change the tests or any other file.
```

5. Inspect and approve the write. The content must contain the supplied function,
   followed by a newline.
6. Repeat the exact test command from step 2. Expect `2 passed`, code `0`.
7. Ask `Use file_read to read cart-working/missing.py.` Approve it and expect an
   explicit missing-file error, without invented file contents.

Only the disposable working copy is corrected. `cart-failing` still contains the
intentional defect. The supplied one-line correction has the same behavior as the
correct implementation in the GIF.

For the exact automated component sequence and a new GIF:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py file-access
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_features.py file-access
```

## Architecture choices and tradeoffs

A small text-file interface supports source code, READMEs, JUnit XML and coverage
reports without separate tools for each format. Whole-file writes keep the interface
simple but replace more content than a targeted patch. A patch-based alternative
could expose a smaller change and detect stale source, at the cost of additional
matching and conflict handling.

## Limitations

There is no built-in project-root allowlist, transactional patch application,
backup or version-control rollback. A permitted write can overwrite existing work.
Large reads are loaded before ReAct truncates the observation, and binary or
non-UTF-8 content may fail. Profile instructions about protected files guide the
model; they do not enforce filesystem permissions.

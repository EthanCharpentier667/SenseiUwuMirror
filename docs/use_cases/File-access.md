# File access: `file_read` and `file_write`

File tools let SensaiUwu inspect source code and test reports, then create or replace
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

**As Camille Moreau, the developer investigating the cart regression, I want SensaiUwu to read the relevant source file, so that its explanation refers to the implementation that actually failed.**

Preconditions: the faulty project is accessible and the requested read is approved when required.

| Acceptance criterion | Expected result |
| --- | --- |
| Content | `file_read` returns the UTF-8 contents of the requested `cart.py`. |
| Diagnosis input | The observation contains the branch returning 1 for an empty list. |
| Missing file | A nonexistent path returns an explicit error, with no invented contents. |
| Integrity | Reading does not modify the file. |

### US-FILE-02 — Verify a proposed correction on a disposable copy

**As Camille Moreau, the developer responsible for her branch, I want SensaiUwu to write an approved correction and rerun the existing tests, so that I can check the change before including it in my merge request.**

Preconditions: a disposable copy exists, its parent directory is writable, and the proposed write and test command are approved when required.

| Acceptance criterion | Expected result |
| --- | --- |
| Write | `file_write` writes the supplied corrected source into the selected copy. |
| Verification | The copy changes from `1 failed, 1 passed` to `2 passed` when the same two tests run. |
| Original fixture | The separate faulty demo fixture retains its intentional defect. |
| Permissions | An approved write to a read-only file returns access denied; approval does not bypass filesystem permissions. |
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

![File permissions, approved writes and verification](../demo_assets/assets/demos/file-access.gif)

Camille asks SensaiUwu to inspect the filesystem permissions and the faulty cart source.
The CLI displays the real `stat` output: `cart-readonly.py` is mode `444`, while
`cart-working/cart.py` is writable. A proposed write to the read-only file is
approved by Camille but refused by the operating system. Human approval does not
override filesystem permissions.

Camille then approves a correction to the writable copy. SensaiUwu writes it with
`file_write`, reads it back with `file_read` and runs the existing pytest suite.
The visible tool output contains the saved source and the actual test result.

The capture uses the real interactive CLI, the local `llama3.2:latest` model and a
fictional preconfigured account. Only human messages and approval keystrokes are
automated. Idle waits are shortened for readability; the displayed application
output and generated answers are preserved.

## Replay this demonstration

Complete the [shared prerequisites](../demo_assets/demos/replay.md#shared-prerequisites),
then launch from the repository root:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py file-access --model llama3.2:latest
```

At the `Vous >` prompt, submit the following messages in order. Inspect each
proposed tool call before answering `y` to its approval prompt.

1. Approve the `bash_tool` and `file_read` requests. Inspect the permission modes and the branch returning `1` for an empty cart.

    ```text
    Use bash_tool with only the command argument to run stat -c '%a %n' cart-readonly.py cart-working/cart.py, then use file_read on cart-working/cart.py. Explain the empty-cart bug briefly. Do not write yet.
    ```

2. Approve the proposed write. The tool must display `File is not writable (Access Denied).` The bot must stop rather than changing the permissions.

    ```text
    Use file_write to replace cart-readonly.py with "def subtotal(prices): return sum(prices)\n". If access is denied, report it and stop. Do not change permissions or use Bash.
    ```

3. Inspect the proposed path and source, then approve the write. The saved function must use `sum(prices)`.

    ```text
    Use file_write to replace cart-working/cart.py with "def subtotal(prices): return sum(prices)\n". Report success in one short sentence, no JSON.
    ```

4. Approve the fresh `file_read` call. Check the actual saved function rather than a copy from the conversation.

    ```text
    Read cart-working/cart.py from disk now using file_read. I need a fresh read, not the content from our chat. Show only the saved function, no JSON or metadata.
    ```

5. Approve the foreground pytest command. The corrected copy must report `2 passed` with exit code `0`.

    ```text
    Use bash_tool with only the command argument to run .venv/bin/python -m pytest -c cart-working/pytest.ini --no-cov -q cart-working. Copy the actual test count exactly into one short sentence. No JSON.
    ```

Finish with `/exit` to close connections and remove the temporary workspace.
A fresh launch resets the scenario. Model wording and latency may vary; compare
the actual tool calls, returned values and errors.

To create a new capture and GIF of this same interactive scenario:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_cli.py file-access
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_cli.py file-access
```

## Architecture choices and tradeoffs

A small text-file interface supports source code, READMEs, JUnit XML and coverage
reports without separate tools for each format. Whole-file writes keep the interface
simple but replace more content than a targeted patch. A patch-based alternative
could expose a smaller change and detect stale source, at the cost of additional
matching and conflict handling.

## Current limits

There is no built-in project-root allowlist, transactional patch application,
backup or version-control rollback. A permitted write can overwrite existing work.
Large reads are loaded before ReAct truncates the observation, and binary or
non-UTF-8 content may fail. Profile instructions about protected files guide the
model; they do not enforce filesystem permissions.

# Sandboxed code

`sandboxed_code` executes Python or Bash in a disposable Docker container, with
resource limits and restricted access. It provides a separate environment for
small generated checks rather than running them directly on the host.

## Scenario

Camille wants to check the cart subtotal on empty and non-empty inputs using a
small Python reference function. She wants the experiment separated from her
working tree and an assertion failure reported as a failure. The source under test
must be supplied explicitly; the container does not mount her project.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova). Camille uses the terminal and local Ollama between development tasks; the workflow allows time for inference rather than requiring an instant production response.

## User stories

### US-SANDBOX-01 — Run a disposable reference check

**As Camille Moreau, the developer investigating cart behavior, I want to execute a small Python reference check outside my working tree, so that the experiment does not modify project files.**

Preconditions: Docker is available, the sandbox image can be built and the call is approved when required.

| Acceptance criterion | Expected result |
| --- | --- |
| Input | Raw Python source is provided with `language=python`, preserving indentation. |
| Checks | The supplied reference checks for `[10, 20]` and `[]` pass and print an explicit result. |
| Identity | The container runs as the unprivileged user configured in its image. |
| Isolation | No host project directory or Docker socket is mounted into the code container. |

### US-SANDBOX-02 — Keep failing experiments visible and clean them up

**As Malik Benali, the reviewer assessing generated experiments, I want a failing assertion to be reported and its container removed, so that a failed check does not become a false success or leave a running worker.**

Preconditions: a sandbox call supplies `assert 1 == 0` or another known failing check.

| Acceptance criterion | Expected result |
| --- | --- |
| Failure | A nonzero container exit produces an execution error with bounded output. |
| Cleanup | Container removal runs in `finally`, including failure and wait-error paths. |
| Timeout | The client waits at most 20 seconds for execution before cleanup is attempted. |
| No invented result | A failed experiment is not described as a passed test. |

## How it works

The tool takes `language` (`python` or `bash`) and raw `code`. It builds the
corresponding image and runs it in a worker thread, keeping the asynchronous
interface available.

| Restriction | Configured value |
| --- | --- |
| CPU allocation | Half a core |
| Memory | 512 MB |
| Process count | 64 |
| Network | Disabled for the code container |
| Root filesystem | Read-only |
| Privileges | Capabilities dropped; no new privileges; non-root image user |
| Writable workspace | Temporary `/workspace` and `/tmp` mounts |
| Wait | 20 seconds, followed by cleanup on exit or error |
| Returned output | Up to 64 KiB |

The Python image uses isolated interpreter mode. The tool returns the execution
output; a failed container exit raises an error which the agent can turn into an
observation. Normal host builds and test suites use [Bash](Bash.md), not a project
mount inside this sandbox.

## Demonstration

![Successful and failing code executed inside Docker](../demo_assets/assets/demos/sandbox.gif)

Camille asks the bot to run two cart checks inside the Python sandbox. The model
requests `sandboxed_code`; Camille inspects and approves the source. The CLI shows
the actual Docker execution output: `2 cart checks passed` and
`container uid: 10001`.

She then submits a deliberate failing assertion. A second sandbox call executes
that source and the CLI displays the resulting `AssertionError`.
The bot reports the failure. Both cases execute in disposable containers; neither
imports the host project or runs the supplied Python on the host.

The capture uses the real interactive CLI, the local `llama3.2:latest` model and a
fictional preconfigured account. Only human messages and approval keystrokes are
automated. Idle waits are shortened for readability; the displayed application
output and generated answers are preserved.

## Replay this demonstration

Complete the [shared prerequisites](../demo_assets/demos/replay.md#shared-prerequisites),
then launch from the repository root:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py sandbox --model llama3.2:latest
```

At the `Vous >` prompt, submit the following messages in order. Inspect each
proposed tool call before answering `y` to its approval prompt.

1. Check that Docker is running. Approve the sandbox request after inspecting `language` and `code`. Expect the two successful checks and UID `10001` in the tool output.

```text
Use sandboxed_code with language=python to execute: import os; assert sum([10, 20]) == 30; assert sum([]) == 0; print('2 cart checks passed'); print('container uid:', os.getuid()). Report the actual output in one short sentence, no JSON. Do not run on the host.
```

2. Approve this second execution. Expect an actual sandbox error containing `AssertionError`, followed by a failure report.

```text
Actually execute sandboxed_code now with language=python and code="assert sum([]) == 1". I need the real Docker error, even if you can predict the result. Report the observed error in one short sentence, no JSON. Do not repair or retry.
```

Finish with `/exit` to close connections and remove the temporary workspace.
A fresh launch resets the scenario. Model wording and latency may vary; compare
the actual tool calls, returned values and errors.

To create a new capture and GIF of this same interactive scenario:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_cli.py sandbox
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_cli.py sandbox
```

## Architecture choices and tradeoffs

Disposable containers give experiments a separate filesystem and process boundary,
with limits more explicit than direct host execution. Image builds and startup add
latency. A persistent restricted worker could reduce startup cost, but would need
stronger state-reset and cross-request isolation controls.

## Current limits

Docker availability and image builds are prerequisites; builds may require network
access even though the code container has networking disabled. The 20-second wait
is a client-side wait, with forced removal in cleanup; image build time is outside
that limit. The container cannot automatically test host code it cannot access.
Container isolation reduces exposure but does not prove immunity to daemon or
kernel vulnerabilities. Returned output limits do not replace all runtime quotas.

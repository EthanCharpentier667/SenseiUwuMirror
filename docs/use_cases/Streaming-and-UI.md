# Streaming and event-driven UI

Sensai streams model text through asynchronous UI callbacks and reports tool
requests, results, errors and progress through the same interface contract.
The agent does not need to write terminal rendering code for each event.

## Scenario

Camille waits for local inference while checking the cart. She wants visible
progress and incremental text rather than a frozen terminal until completion.
Malik needs errors and incomplete responses to remain distinguishable from
finished evidence; seeing text arrive does not establish that tests ran.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova). Camille uses the terminal and local Ollama between development tasks; the workflow allows time for inference rather than requiring an instant production response.

## User stories

### US-UI-01 — Follow a response while the local model generates it

**As Camille Moreau, the developer waiting for a local testing explanation, I want text to appear progressively, so that I can follow the response before generation finishes.**

Preconditions: the selected model is reachable through an Ollama streaming chat endpoint.

| Acceptance criterion | Expected result |
| --- | --- |
| Chunks | More than one streamed content callback can update the displayed answer. |
| Completion | A final stream-end event finishes the UI display. |
| Content | The accumulated response contains the text actually received from the model. |
| Evidence | A streamed explanation is not presented as proof of test execution. |

### US-UI-02 — Keep progress and errors visible through the UI contract

**As Malik Benali, the reviewer following the assistant’s actions, I want progress, approval and error events handled separately from answer text, so that I can tell what the assistant is doing and whether the operation completed.**

Preconditions: an asynchronous UI handler is attached to the agent.

| Acceptance criterion | Expected result |
| --- | --- |
| Progress | Thinking and execution stages can start and stop the progress indicator. |
| Approval | A tool request can show its arguments and wait for a human decision. |
| Failure | A model or tool error can be reported through the error callback. |
| Incomplete stream | A stream ending without Ollama’s completion event raises an incomplete-response error. |

## How it works

The HTTP client reads line-delimited JSON from Ollama and sends content to an
asynchronous callback as it arrives. It accumulates the final text and records
usage metadata from the completion event. It rejects provider error chunks and
streams that terminate without a completion event.

`AsyncUIHandler` separates content chunks, stream completion, thinking chunks,
approval requests, tool results, errors, messages and progress indicators.
`CLIHandler` renders these events with Rich and prompt_toolkit. The same contract
could support another interface, while the currently implemented application is
the terminal UI. ReAct's displayed planning text is generated content, not a
verified explanation of the model's internal reasoning.

## Demonstration

![Streaming and event-driven UI: actual component walkthrough](../demo_assets/assets/demos/streaming.gif)

The capture sends an actual English prompt to local `llama3.2:latest` through
Sensai's HTTP client. The real CLI handler renders the response incrementally;
the recorded run receives 51 content callbacks and reports 52 generated tokens.
These are counts for one demonstration, not latency or quality benchmarks. The
prompt requests an explanation rather than execution of tests.

## Replay this demonstration

From the repository root, complete the [shared replay prerequisites](../demo_assets/demos/replay.md#shared-prerequisites).
The launcher opens the actual Sensai CLI with a temporary fictional profile and
working copies. Type the following commands and questions at `Vous >`; `/exit`
cleans up. Compare the stated facts and tool results, not identical model wording.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py streaming
```

1. Send the recorded request:

```text
In English, give three short numbered checks for an empty-cart subtotal function. Do not claim execution.
```

2. Watch the actual terminal while the local model generates the answer. Content
   should appear incrementally, then the finished answer should remain readable.
3. The request is explanatory: no test suite has been run. Evaluate the text on
   its own merits rather than treating streaming as correctness evidence.
4. For the callback counts shown by the GIF, run the component replay below.
   That run instruments the actual CLI handler and prints the count after completion.

The original capture observed 51 content callbacks and 52 generated tokens. A
rerun can produce different counts, text and timings; progressive rendering and
proper completion are the reproducible behaviors.

For the exact automated component sequence and a new GIF:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py streaming
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_features.py streaming
```

## Architecture choices and tradeoffs

Streaming improves visibility while inference proceeds but does not reduce the
model's total computation by itself. UI callbacks separate presentation from the
agent and allow different frontends. A blocking single-response display would
be simpler but provide less feedback during a longer local generation.

## Limitations

Streamed text can still be inaccurate or incomplete. Not every network chunk is
a token, and perceived progress is not a throughput measurement. The current
callback interface is not a durable event bus or a guaranteed cancellation system.
The demonstration does not validate a web frontend, interruption at every stage
or recovery from every network failure. [UI architecture](../events.md) describes
the interface in more detail.

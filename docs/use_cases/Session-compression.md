# Session compression

Session compression replaces older conversation turns in the outgoing context
with a running model-generated summary. The original messages remain stored;
the summary and later turns become the context used for subsequent requests.

## Scenario

Camille investigates the empty-cart regression over several exchanges with Sensai.
She wants to retain the expected value, the observed failure and the fact that payment
is outside the check, without resending an ever-growing conversation to the local
model. Malik must still be able to distinguish original results from a generated
summary that may have changed their meaning.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova). Camille uses the terminal and local Ollama between development tasks; the workflow allows time for inference rather than requiring an instant production response.

## User stories

### US-COMP-01 — Continue a review using a running summary

**As Camille Moreau, the developer continuing a long cart investigation, I want older exchanges folded into a summary, so that later questions can use the established context without resending every old turn.**

Preconditions: compression is enabled and the completed turn exceeds the configured prompt-token threshold.

| Acceptance criterion | Expected result |
| --- | --- |
| Trigger | Compression occurs only when the completed response reports a prompt count greater than the threshold. |
| Model | The summary uses the model selected for the completed exchange. |
| Boundary | A summary and the last summarized message identifier are stored. |
| Next turn | Older summarized turns are excluded from the next outgoing history, while later turns remain available. |

### US-COMP-02 — Preserve the meaning of test evidence

**As Malik Benali, the reviewer relying on a compressed investigation, I want the summary to preserve which tests failed and what remains untested, so that I do not approve a change based on a rewritten result.**

Preconditions: the history states that the empty-cart test failed, a separate correct version passed, and payment was not tested.

| Acceptance criterion | Expected result |
| --- | --- |
| Failure identity | The summary continues to identify `test_empty_basket` as the initially failing test. |
| Version distinction | It does not turn a separate correct fixture into an asserted code change. |
| Untested scope | Payment remains explicitly untested. |
| Evidence distinction | A generated summary is not treated as an independent execution result. |

## How it works

The default `--compression-threshold` is 3,000 prompt tokens. After a response,
the application compares its reported prompt token count with this threshold.
The summary request combines the previous summary with unsummarized conversation
messages, using the same model as that response.

The resulting text and a summarized-message boundary are persisted in SQLite.
Context construction places profile preferences/instructions first, followed by
the running summary, remaining history, context framing, optional retrieved chunks
and the new request. Tool traces remain stored separately and are not resent as
ordinary conversation history.

## Demonstration

![Session compression: actual component walkthrough](../demo_assets/assets/demos/compression.gif)

The recording summarizes a supplied fictional review history using actual local
`llama3.2:latest`, then sends a new question through the application using that
summary. Outgoing message count changes from 5 to 3, but content grows from 694
to 991 characters on this short example. The generated summary introduces a
contradictory statement about a new payment test, while the actual follow-up
answer identifies an empty-cart failure and untested payment.

An earlier retained capture also mislabeled the initially failing test as passing.
These observed errors expose the fidelity limitation in US-COMP-02. The recording
shows summarization being used for a subsequent answer, not an automatic threshold
crossing or a measured quality/size improvement.

## Replay this demonstration

From the repository root, complete the [shared replay prerequisites](../demo_assets/demos/replay.md#shared-prerequisites).
The launcher opens the actual Sensai CLI with a temporary fictional profile and
working copies. Type the following commands and questions at `Vous >`; `/exit`
cleans up. Compare the stated facts and tool results, not identical model wording.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py compression
```

1. The launcher supplies the same three fictional review messages as the GIF:
   empty cart should return 0 but returned 1; the suite had one passing test and
   failing `test_empty_basket`; a separate correct version passed both tests and
   payment remains untested. It calls the real compression function and prints
   its generated summary before opening the chat.
2. Send:

```text
Using the previous review context, which test originally failed and what remains untested? Answer in at most three lines.
```

3. Inspect the actual reply. The source facts are the empty-cart failure and
   untested payment. Check that the model does not infer a payment test passed
   or claim to have corrected the code.
4. Compare the generated summary with those original facts. On the recorded run,
   message count fell from 5 to 3 but context characters grew from 694 to 991.
   The summary introduced a contradictory claim about a new payment test; the
   follow-up nevertheless reported an empty-cart failure and untested payment.

This reproduces explicit summarization followed by a question using its result.
The automatic threshold path is a separate mechanism: normal sessions trigger it
after the completed prompt count exceeds `--compression-threshold`. Summary text
and character counts can change on rerun; reduction and perfect retention are not
guaranteed.

For the exact automated component sequence and a new GIF:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py compression
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_features.py compression
```

## Architecture choices and tradeoffs

A running summary supports longer sessions within a limited context budget.
It adds another model call and can introduce irreversible information loss in the
outgoing context. A larger context window or a rolling window would avoid generated
summary drift, but would respectively consume more resources or drop older context.
The short recorded case shows why compression is not automatically beneficial.

## Limitations

A summary can invert results, invent a change or grow longer than the original
history. The configured threshold is checked after the completed turn, not before
an oversized prompt is sent. Stored original messages are not automatically compared
against every claim in the summary. No measured improvement or faithful-retention
rate is established by this example.

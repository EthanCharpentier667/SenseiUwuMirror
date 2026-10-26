# Screenshot

The `screenshot` tool captures the current display and attaches an image to the
model's observation. It supports checks whose result is visual, such as whether
a preview window opened and which values or error messages it displays.

## Scenario

Camille opens a cart preview while preparing the review. A successful process exit
or a clean terminal does not tell Malik whether the visible cart shows the expected
amount. She wants an image of that state, with fictional cart data, and an assistant
that only attempts visual interpretation when its model supports images.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova). Camille uses the terminal and local Ollama between development tasks; the workflow allows time for inference rather than requiring an instant production response.

## User stories

### US-SCREEN-01 — Inspect the visible cart preview

**As Camille Moreau, the developer checking the cart preview, I want Sensai to capture the visible window, so that I can compare the displayed subtotal with the test expectation.**

Preconditions: a display is available, a vision-capable model is selected and the screenshot call is approved when required.

| Acceptance criterion | Expected result |
| --- | --- |
| Capture | The tool returns a JPEG image from the current display. |
| Dimensions | The image fits within 1920 by 1080 pixels while preserving its aspect ratio. |
| Evidence | The preview visibly identifies the cart and its amounts; a capture is not treated as proof of unshown interactions. |
| Privacy | The demo uses a dedicated display containing only fictional data. |

### US-SCREEN-02 — Avoid unsupported visual requests

**As Malik Benali, the reviewer checking the scope of the assistant, I want visual tools to be withheld from a text-only model, so that the assistant does not receive an image it cannot interpret.**

Preconditions: the selected model capabilities are obtained from Ollama.

| Acceptance criterion | Expected result |
| --- | --- |
| Text model | `screenshot` is absent from eligible tools when `vision` is missing. |
| Vision model | Selecting a model reporting `vision` makes the enabled screenshot tool eligible. |
| Unavailable capabilities | A failed capability lookup does not establish vision support. |
| Scope | A text-only diagnostic does not claim to have visually inspected the window. |

## How it works

`screenshot` has no arguments. It captures the current display with `pyscreenshot`,
converts the image to RGB, downsizes it to at most 1920 × 1080 and encodes it as
JPEG at quality 80. The result contains an `images` attachment and a saved-image
message. The normal destination is the temporary `sensai/screenshot.jpg` path.

The tool requires `vision` and is declared `safe=False`. The agent separates the
image attachment from the text observation and provides it to a compatible model.
This differs from [browser screenshots](Browser.md), which capture the browser page.

## Demonstration

![Screenshot: actual component walkthrough](../demo_assets/assets/demos/screenshot.gif)

The recording captures an actual window on a dedicated nested X display containing
only fictional Atelier Nova data. The screenshot tool returns a 1024 × 640 image,
which is then sent through Sensai's HTTP client to local `qwen3.5:9b`. Its actual
reply reads `ATELIER NOVA`, subtotal `30` and empty cart `0` from those pixels.
The saved-image destination is redirected to a temporary demo directory. This
shows image acquisition and interpretation; it does not establish that the cart
tests ran or that the preview's underlying calculation is correct.

## Replay this demonstration

From the repository root, complete the [shared replay prerequisites](../demo_assets/demos/replay.md#shared-prerequisites).
The launcher opens the actual Sensai CLI with a temporary fictional profile and
working copies. Type the following commands and questions at `Vous >`; `/exit`
cleans up. Compare the stated facts and tool results, not identical model wording.

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/replay.py screenshot --model qwen3.5:9b
```

1. The launcher opens a dedicated nested display with the fictional Atelier Nova
   window. The visible amounts are 30 for the filled cart and 0 for the empty cart.
2. Send:

```text
Use screenshot to capture the dedicated demo display, then read the image. Give the title, subtotal and empty-cart amount in at most three short lines. Do not claim tests ran.
```

3. Approve `screenshot`. Expect a captured image, then a real model reply identifying
   `ATELIER NOVA`, subtotal `30` and empty cart `0`.
4. `/exit` closes the session and the dedicated display.

The regenerated GIF shows both acquisition and interpretation of the returned
image by `qwen3.5:9b`. Screenshot interpretation is distinct from actually running
the cart tests. A usable parent X display and Xephyr are prerequisites; running
a text-only model will not offer the screenshot tool.

For the exact automated component sequence and a new GIF:

```bash
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/record_features.py screenshot
PYTHONPATH=src .venv/bin/python docs/demo_assets/scripts/demos/render_features.py screenshot
```

## Architecture choices and tradeoffs

An image provides evidence unavailable in process output, but consumes more context
and requires a larger or vision-capable model. Capturing the whole display is simple
and works across applications; capturing a specific window or region would provide
better privacy and focus but needs additional selection controls.

## Limitations

A display and a working capture backend are required. The whole screen may include
unrelated or confidential windows. The saved screenshot path is overwritten by later
captures, and an image may omit transient states or details lost during resizing.
A visible window does not prove that its underlying behavior is correct.

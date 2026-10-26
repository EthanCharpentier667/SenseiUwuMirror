"""Render recorded component output as GIFs, pacing playback for readability.

The source output is never rewritten. Image events show pixels returned by the
screenshot tools. The frame and English captions are presentation elements.
"""

import argparse
import json
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[4]
ASSETS = ROOT / "docs/demo_assets/assets/demos"
ARTIFACTS = ROOT / "docs/demo_assets/artifacts/demos"
FONT_ROOT = Path("/usr/share/fonts/truetype/dejavu")
FONT = ImageFont.truetype(str(FONT_ROOT / "DejaVuSansMono.ttf"), 17)
BOLD = ImageFont.truetype(str(FONT_ROOT / "DejaVuSansMono-Bold.ttf"), 17)
TITLE = ImageFont.truetype(str(FONT_ROOT / "DejaVuSans-Bold.ttf"), 24)
SMALL = ImageFont.truetype(str(FONT_ROOT / "DejaVuSans.ttf"), 15)
COLORS = {
    "default": "#e2e8f0",
    "cyan": "#67e8f9",
    "green": "#86efac",
    "red": "#fda4af",
    "blue": "#93c5fd",
    "magenta": "#d8b4fe",
    "yellow": "#fde68a",
    "brown": "#fde68a",
    "white": "#f8fafc",
    "black": "#94a3b8",
    "brightblack": "#94a3b8",
}


def frame(screen, feature, picture):
    image = Image.new("RGB", (1280, 880), "#080e1c")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((12, 12, 1268, 868), 18, fill="#111827", outline="#334155", width=2)
    for x, color in [(36, "#fb7185"), (58, "#facc15"), (80, "#4ade80")]:
        draw.ellipse((x, 32, x + 12, 44), fill=color)
    draw.text(
        (120, 23), "Sensai | " + feature.replace("-", " ").title(), font=TITLE, fill="#f8fafc"
    )
    draw.text((930, 31), "ACTUAL COMPONENT OUTPUT", font=SMALL, fill="#a5b4fc")
    draw.line((28, 70, 1252, 70), fill="#334155")
    for y in range(screen.lines):
        for x in range(screen.columns):
            char = screen.buffer[y][x]
            if char.data and char.data != " ":
                draw.text(
                    (30 + x * FONT.getlength("M"), 90 + y * 21),
                    char.data,
                    font=BOLD if char.bold else FONT,
                    fill=COLORS.get(char.fg, "#e2e8f0"),
                )
    if picture:
        captured = Image.open(picture).convert("RGB")
        captured.thumbnail((1120, 510))
        draw.rectangle((40, 265, 1240, 814), fill="#172033", outline="#64748b", width=2)
        draw.text(
            (55, 274),
            "Image returned by the tool | fictional demo data",
            font=SMALL,
            fill="#e0e7ff",
        )
        image.paste(captured, ((1280 - captured.width) // 2, 304))
    draw.line((28, 830, 1252, 830), fill="#334155")
    draw.text(
        (30, 842),
        "Automated component walkthrough | actual results | playback paced for readability",
        font=SMALL,
        fill="#a5b4fc",
    )
    return image


def render(feature):
    rows = (ARTIFACTS / f"{feature}.cast").read_text().splitlines()
    header = json.loads(rows[0])
    events = [json.loads(row) for row in rows[1:]]
    screen = pyte.Screen(header["width"], header["height"])
    stream = pyte.Stream(screen)
    frames, durations = [], []
    picture = None
    previous_time = 0
    last_render_time = -1
    for index, (timestamp, kind, output) in enumerate(events):
        if kind == "image":
            # Historical captures contain absolute paths from before the cleanup.
            # Images now live alongside the captures; new events use basenames.
            picture = ARTIFACTS / Path(output).name
        elif kind == "o":
            if ">>>" in output:
                picture = None
            stream.feed(output.replace("\n", "\r\n"))
        following = events[index + 1][0] if index + 1 < len(events) else timestamp + 2
        if following - timestamp < 0.08 and timestamp - last_render_time < 0.18:
            continue
        if frames:
            elapsed = timestamp - previous_time
            durations[-1] = (
                max(1800, min(3500, round(elapsed * 1000)))
                if elapsed > 0.3
                else max(80, round(elapsed * 1000))
            )
        frames.append(frame(screen, feature, picture))
        durations.append(1800)
        previous_time = timestamp
        last_render_time = timestamp
    frames[0].save(
        ASSETS / f"{feature}.gif",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
    )
    print(feature, len(frames), "frames", round(sum(durations) / 1000, 2), "seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("features", nargs="+")
    for feature in parser.parse_args().features:
        render(feature)

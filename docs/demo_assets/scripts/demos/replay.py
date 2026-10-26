"""Open the actual Sensai CLI on disposable Atelier Nova fixtures for manual replay."""

import argparse
import asyncio
import contextlib
import os
import shutil
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from record_features import FIXTURE, ROOT, SPECIFICATION, WORK, setup

from sensai.data.session.manager import compress_session
from sensai.data.session.message import create_message
from sensai.data.session.session import get_session
from sensai.features.rag.embedder import Embedder
from sensai.features.rag.rag import ingest_document
from sensai.ui.app import CLIApp


async def main(args):
    ctx, client = setup()
    for name, source in [
        ("cart-failing", "python-tests"),
        ("cart-passing", "python-tests-passing"),
        ("cart-working", "python-tests"),
    ]:
        shutil.copytree(ROOT / "docs/demo_assets/examples/demos" / source, WORK / name)
    (WORK / ".venv").symlink_to(ROOT / ".venv", target_is_directory=True)
    shutil.copyfile(SPECIFICATION, WORK / "cart-spec.md")
    ctx.agent.model = args.model
    ctx.config.args.model = args.model
    ctx.agent.system_prompt = (
        "You are Atelier Nova's testing assistant. Reply concisely in English. "
        "Use actual observations, do not invent execution results, and follow the user's exact tool request. "
        "Commands run in the displayed temporary workspace. Never change the original repository."
    )
    for name in ["rag", "compression", "mcp"]:
        ctx.config.features.set(name, enabled=False)
    for name in ["web_search", "web_fetch"]:
        ctx.config.features.set_tool(name, enabled=False)
    if args.feature in {"personas", "profiles", "rag", "compression", "streaming"}:
        ctx.config.features.set("tools", enabled=False)
    processes = []
    server = None
    browser_module = None
    try:
        if args.feature == "rag":
            ctx.config.features.set("rag", enabled=True)
            ctx.agent.system_prompt = (
                "You are Atelier Nova's evidence-focused assistant. Reply in English in at most 100 words. "
                "Use attached excerpts for document-specific questions. Cite their document/excerpt labels. "
                "If no excerpts are available, explicitly say the specification is unavailable. "
                "Never invent a rule identifier or review marker."
            )
            if not args.without_document:
                message = create_message(
                    ctx.database, ctx.session.id, "Attached cart-spec.md", "user", 0
                )
                await ingest_document(
                    ctx.database,
                    Embedder(client),
                    message.id,
                    (WORK / "cart-spec.md").read_bytes(),
                    "cart-spec.md",
                )
                print("Attached cart-spec.md with real local embeddings.")
        if args.feature == "compression":
            for role, content in [
                (
                    "user",
                    "Atelier Nova: empty cart must return 0. The faulty version returned 1. Use pytest. Do not edit payment code.",
                ),
                (
                    "assistant",
                    "The observed suite had one passing test and one failing test: test_empty_basket.",
                ),
                (
                    "user",
                    "The separate correct version passed both tests. Payment remains untested.",
                ),
            ]:
                create_message(ctx.database, ctx.session.id, content, role, 0)
            ctx.session = get_session(ctx.database, ctx.session.id)
            ctx.session = await compress_session(ctx.database, ctx.session, client, args.model)
            print("Preloaded fictional review history; actual generated summary:")
            print(ctx.session.summary)
        if args.feature == "web":
            os.environ.pop("API_TOKEN", None)
            for name in ["web_search", "web_fetch"]:
                ctx.config.features.set_tool(name, enabled=True)
            print("Web replay intentionally has no API_TOKEN; it demonstrates unavailability.")
        if args.feature == "mcp":
            ctx.config.features.set("mcp", enabled=True)
            processes.append(
                subprocess.Popen(
                    [sys.executable, str(ROOT / "docs/demo_assets/scripts/demos/mcp_server.py")],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            await asyncio.sleep(2)
            if processes[-1].poll() is not None:
                raise RuntimeError("The loopback MCP fixture could not start on port 18876.")
        if args.feature == "browser":
            from playwright.async_api import async_playwright

            from sensai.features.tools.browser import page as browser_module

            class Quiet(SimpleHTTPRequestHandler):
                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(
                ("127.0.0.1", 18877), partial(Quiet, directory=str(FIXTURE))
            )
            threading.Thread(target=server.serve_forever, daemon=True).start()
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(viewport={"width": 960, "height": 650})
            browser_module._STATE.session = browser_module._Session(playwright, browser, page)
            print("Local cart preview: http://127.0.0.1:18877/")
        if args.feature == "screenshot":
            from sensai.features.tools.screenshot import screenshot as module

            display = os.environ.get("SENSAI_DEMO_DISPLAY", ":88")
            processes.append(
                subprocess.Popen(
                    [
                        "Xephyr",
                        display,
                        "-screen",
                        "1024x640",
                        "-ac",
                        "-noreset",
                        "-nolisten",
                        "tcp",
                        "-no-host-grab",
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            )
            await asyncio.sleep(2)
            if processes[-1].poll() is not None:
                raise RuntimeError(
                    "The dedicated display could not start. Check the parent DISPLAY and that :88 is free."
                )
            os.environ["DISPLAY"] = display
            processes.append(
                subprocess.Popen(
                    [
                        "xmessage",
                        "-geometry",
                        "820x380+70+60",
                        "-title",
                        "Atelier Nova - review",
                        "ATELIER NOVA\n\nCart check\n\nItems: 10 + 20\nSubtotal: 30\nEmpty cart: 0\n\nFictional demo data only.",
                    ]
                )
            )
            module.SAVE_DIRECTORY = WORK
            module.SAVE_PATH = WORK / "screenshot.jpg"
        app = CLIApp(ctx.agent, ctx.database, ctx.session, client, ctx.config, "Camille")
        print(f"\nWorkspace: {WORK}\nFeature: {args.feature}\nModel: {args.model}")
        print("Working copies: cart-failing/, cart-passing/, cart-working/. Type /exit to finish.")
        print(
            "This is the actual CLI with a preconfigured fictional account; login/keyring are outside this demo.\n"
        )
        await app.run()
    finally:
        if browser_module is not None:
            await browser_module.close_browser()
        if server is not None:
            server.shutdown()
            server.server_close()
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=5)
                if process.poll() is None:
                    process.kill()
                    process.wait()
        ctx.database.close()
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "feature",
        choices=[
            "react",
            "trust",
            "bash",
            "file-access",
            "screenshot",
            "browser",
            "sandbox",
            "web",
            "mcp",
            "rag",
            "compression",
            "profiles",
            "personas",
            "models",
            "flags",
            "streaming",
        ],
    )
    parser.add_argument("--model", default="llama3.2:latest")
    parser.add_argument(
        "--without-document",
        action="store_true",
        help="Use a fresh RAG session without attaching the specification.",
    )
    asyncio.run(main(parser.parse_args()))

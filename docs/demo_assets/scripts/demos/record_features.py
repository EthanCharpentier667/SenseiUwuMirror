"""Record actual Sensai component output; never substitute model or tool results.

Run one feature per process. Optional capture dependencies are documented in the
feature-tour recording guide. Mutable demo data lives in a temporary directory.
"""

import argparse
import asyncio
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src"))
ARTIFACTS = ROOT / "docs/demo_assets/artifacts/demos"
FIXTURE = ROOT / "docs/demo_assets/examples/demos/feature-tour"
SPECIFICATION = ROOT / "docs/demo_assets/demos/cart-spec.md"
START = time.monotonic()
EVENTS = []
WORK = Path(tempfile.mkdtemp(prefix="sensai-feature-demo-"))
os.environ.update(
    TOKEN="local-demo-placeholder",
    HASH_ALGORITHM="sha256",
    HASH_ITERATIONS="600000",
    SALT_BYTES="32",
)

from rich.console import Console

from sensai.agent import Agent
from sensai.client import OllamaClient
from sensai.config import Config
from sensai.core.setup import setup_database
from sensai.data.profile.manager import create_new_profile, login, logout
from sensai.data.session.manager import build_messages, create_new_session
from sensai.features.tools.registry import get_tools
from sensai.ui.cli import CLIHandler
from sensai.ui.command import CommandContext


class Capture(io.TextIOBase):
    """Keep the actual output and its timing, without exposing process environment."""

    def write(self, text):
        if text:
            EVENTS.append([time.monotonic() - START, "o", text])
            sys.__stdout__.write(text)
            sys.__stdout__.flush()
        return len(text)

    def flush(self):
        sys.__stdout__.flush()


def show(value):
    print(
        json.dumps(value, indent=2, ensure_ascii=True)
        if isinstance(value, (dict, list))
        else str(value),
        flush=True,
    )


async def step(label):
    await asyncio.sleep(0.8)
    print("\n\033[36m>>> " + label + "\033[0m", flush=True)


def preview(path):
    EVENTS.append([time.monotonic() - START, "image", path.name])


def setup():
    config = Config()
    config.parse_args(
        [
            "--url",
            "http://127.0.0.1:11434/api/chat",
            "--token",
            "local-demo-placeholder",
            "--model",
            "llama3.2:latest",
            "--db-path",
            str(WORK),
        ]
    )
    shutil.copyfile(FIXTURE / "personas.json", WORK / "personas.json")
    os.chdir(WORK)
    database = setup_database(config)
    profile = create_new_profile(database, "Camille", "fictional-demo-password")
    session = create_new_session(database, profile.id, "Cart review")
    ui = CLIHandler()
    ui.console = Console(force_terminal=True, width=100)
    client = OllamaClient(config.url, token="local-demo-placeholder", timeout=300)
    agent = Agent(
        model="llama3.2:latest",
        client=client,
        tools=get_tools(),
        ui_handler=ui,
        features=config.features,
    )
    return CommandContext(database, ui, agent, config, session), client


async def ask(ctx, client, prompt, *, embedder=None):
    """Send a real message through the application's retrieval/chat/storage path."""
    from sensai.ui.app import CLIApp

    ctx.config.features.set("tools", enabled=False)
    ctx.config.features.set("compression", enabled=False)
    app = CLIApp(ctx.agent, ctx.database, ctx.session, client, ctx.config, "Camille", embedder)
    try:
        await step("Camille > " + prompt)
        await app._handle_chat(prompt)
        ctx.session = app.session
        reply = next(
            message.content
            for message in reversed(app.session.messages)
            if message.role == "assistant"
        )
        print("\n")
        return reply
    finally:
        await app.mcp_commands.aclose()


async def file_access(ctx, client):
    from sensai.features.tools.bash import BashTool
    from sensai.features.tools.fileaccess.fileread import FileRead
    from sensai.features.tools.fileaccess.filewrite import FileWrite

    project = WORK / "cart"
    shutil.copytree(ROOT / "docs/demo_assets/examples/demos/python-tests", project)
    await step("file_read: inspect the faulty cart implementation")
    show(FileRead().execute(file_path=str(project / "cart.py"))["content"])
    await step("bash_tool: run the original two tests")
    command = (
        f"{ROOT / '.venv/bin/python'} -m pytest -c {project / 'pytest.ini'} --no-cov -q {project}"
    )
    before = await BashTool().execute(command=command)
    show({"exit_code": before["exit_code"], "result": before["output"].splitlines()[-1]})
    assert before["exit_code"] == 1
    await step("file_write: correct only the temporary demo copy")
    source = (ROOT / "docs/demo_assets/examples/demos/python-tests-passing/cart.py").read_text()
    result = FileWrite().execute(file_path=str(project / "cart.py"), content=source)
    assert "error" not in result
    show(FileRead().execute(file_path=str(project / "cart.py"))["content"])
    await step("bash_tool: check the corrected copy")
    after = await BashTool().execute(command=command)
    show({"exit_code": after["exit_code"], "result": after["output"].splitlines()[-1]})
    assert after["exit_code"] == 0
    await step("file_read: missing file is an explicit error")
    show(FileRead().execute(file_path=str(project / "missing.py")))


async def screenshot(ctx, client):
    from sensai.features.tools.screenshot import screenshot as module

    display = os.environ.get("SENSAI_DEMO_DISPLAY", ":88")
    nested = subprocess.Popen(
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
        env={**os.environ, "DISPLAY": os.environ.get("DISPLAY", ":1")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    await asyncio.sleep(2)
    if nested.poll() is not None:
        raise RuntimeError(nested.stderr.read().decode())
    os.environ["DISPLAY"] = display
    window = subprocess.Popen(
        [
            "xmessage",
            "-display",
            display,
            "-geometry",
            "820x380+70+60",
            "-title",
            "Atelier Nova - review",
            "ATELIER NOVA\n\nCart check\n\nItems: 10 + 20\nSubtotal: 30\nEmpty cart: 0\n\nFictional demo data only.",
        ]
    )
    try:
        await asyncio.sleep(1)
        await step("screenshot: capture the dedicated demo display")
        module.SAVE_DIRECTORY = WORK
        module.SAVE_PATH = WORK / "screenshot.jpg"
        result = module.Screenshot().execute()
        image = ARTIFACTS / "screenshot-captured.jpg"
        image.write_bytes(base64.b64decode(result["images"][0]))
        from PIL import Image

        show(
            {
                "captured": True,
                "image_size": Image.open(image).size,
                "requires": sorted(module.Screenshot().requires),
                "display": display,
            }
        )
        preview(image)
        await asyncio.sleep(2)
        await step("Ask qwen3.5:9b to read the image returned by screenshot")
        result = await client.chat(
            messages=[
                {
                    "role": "user",
                    "content": "Read this fictional cart preview. Give its title, subtotal and empty-cart amount in at most three short lines. Do not claim tests ran. /no_think",
                    "images": result["images"],
                }
            ],
            model="qwen3.5:9b",
            ui_handler=ctx.ui,
            options={"temperature": 0, "num_predict": 768},
        )
        show({"actual_visual_reply": result.response})
        assert result.response.strip(), "The vision model returned no answer"
    finally:
        window.terminate()
        window.wait(timeout=5)
        nested.terminate()
        nested.wait(timeout=5)


async def browser(ctx, client):
    import threading
    from functools import partial
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from playwright.async_api import async_playwright

    from sensai.features.tools.browser import page as module
    from sensai.features.tools.browser.browser_click import BrowserClick
    from sensai.features.tools.browser.browser_navigate import BrowserNavigate
    from sensai.features.tools.browser.browser_screenshot import BrowserScreenshot
    from sensai.features.tools.browser.browser_type import BrowserType

    class Quiet(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(Quiet, directory=str(FIXTURE)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    playwright = await async_playwright().start()
    chrome = await playwright.chromium.launch(headless=True)
    page = await chrome.new_page(viewport={"width": 960, "height": 650})
    module._STATE.session = module._Session(playwright, chrome, page)
    try:
        await step("browser_navigate: open the local cart page")
        show(await BrowserNavigate().execute(url=f"http://127.0.0.1:{server.server_port}/"))
        await step("browser_click: calculate 10 + 20")
        result = await BrowserClick().execute(name="Calculate subtotal")
        show(result)
        assert "Subtotal: 30" in result
        await step("browser_type: clear Item prices; browser_click: calculate")
        await BrowserType().execute(name="Item prices", text="")
        result = await BrowserClick().execute(name="Calculate subtotal")
        show(result)
        assert "Subtotal: 0" in result
        await step("browser_type: invalid input produces a visible form error")
        await BrowserType().execute(name="Item prices", text="invalid")
        result = await BrowserClick().execute(name="Calculate subtotal")
        show(result)
        assert "Invalid prices" in result
        image_result = await BrowserScreenshot().execute()
        image = ARTIFACTS / "browser-captured.png"
        image.write_bytes(base64.b64decode(image_result["images"][0]))
        preview(image)
        await asyncio.sleep(1)
        await step("browser_navigate: file URLs are rejected")
        result = await BrowserNavigate().execute(url="file:///etc/passwd")
        show(result)
        assert "error" in result
    finally:
        await module.close_browser()
        server.shutdown()
        server.server_close()


async def sandbox(ctx, client):
    from sensai.features.tools.sandbox.sandboxed_code import SandboxedCode

    await step("sandboxed_code: check both cart cases inside Docker")
    code = "def subtotal(prices):\n    return sum(prices)\nassert subtotal([10,20]) == 30\nassert subtotal([]) == 0\nprint('2 cart checks passed')\nimport os\nprint('uid:', os.getuid())\n"
    result = await SandboxedCode().execute(language="python", code=code)
    show(result["output"])
    assert "2 cart checks passed" in result["output"]
    await step("sandboxed_code: a failing assertion is reported as an error")
    try:
        await SandboxedCode().execute(
            language="python", code="assert 1 == 0, 'empty cart regression'"
        )
    except RuntimeError as error:
        show(str(error))
    else:
        raise AssertionError("The failing sandbox case unexpectedly succeeded")


async def web(ctx, client):
    from sensai.features.tools.web_fetch import WebFetch
    from sensai.features.tools.web_search import WebSearch

    os.environ.pop("API_TOKEN", None)
    await step("web_search: behavior without an API token")
    result = WebSearch().execute(query="pytest assertion failure empty cart")
    show(result)
    assert result == {"message": "Web search is not available."}
    await step("web_fetch: behavior without an API token")
    show(WebFetch().execute(url="https://docs.pytest.org/"))
    print("No web request was made. No fetched content is claimed.")


async def mcp(ctx, client):
    from sensai.ui.commands.mcp.mcp_commands import MCPCommands

    server = subprocess.Popen(
        [sys.executable, str(ROOT / "docs/demo_assets/scripts/demos/mcp_server.py")],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    commands = MCPCommands(ctx.agent)
    try:
        await asyncio.sleep(2)
        await step("/mcp add-json atelier: connect to the local read-only rule server")
        await commands._execute(
            ctx, ["add-json", "atelier", '{"url":"http://127.0.0.1:18876/mcp"}']
        )
        tool = next(tool for tool in ctx.agent.tools if tool.name == "cart_rule")
        show({"discovered_tool": tool.name})
        await step("cart_rule: retrieve CART-EMPTY-001 over MCP")
        result = await tool.execute(rule_id="CART-EMPTY-001")
        show(result)
        assert "subtotal 0" in json.dumps(result)
        await step("cart_rule: an unknown rule produces no invented requirement")
        show(await tool.execute(rule_id="MISSING"))
        await step("Close the MCP connection and remove its tools")
        await commands.aclose()
        show(
            {
                "cart_rule_still_registered": any(
                    tool.name == "cart_rule" for tool in ctx.agent.tools
                )
            }
        )
    finally:
        await commands.aclose()
        server.terminate()
        server.wait(timeout=10)


async def rag(ctx, client):
    from sensai.data.session.manager import retrieve_chunks
    from sensai.data.session.message import create_message
    from sensai.features.rag.embedder import Embedder
    from sensai.features.rag.rag import ingest_document

    embedder = Embedder(client)
    await step("Ingest the Atelier Nova cart specification with real Ollama embeddings")
    message = create_message(ctx.database, ctx.session.id, "Attached cart-spec.md", "user", 0)
    document = await ingest_document(
        ctx.database, embedder, message.id, SPECIFICATION.read_bytes(), "cart-spec.md"
    )
    show({"document_id": document.id, "embedding_model": embedder.model})
    await step("Retrieve the expected behavior of an empty cart")
    chunks = await retrieve_chunks(
        ctx.database, embedder, ctx.session, "What is CART-EMPTY-001 for an empty cart?"
    )
    show(
        [
            {"document": chunk.document_id, "excerpt": chunk.position + 1, "content": chunk.content}
            for chunk in chunks
        ]
    )
    assert any("subtotal of 0" in chunk.content for chunk in chunks)
    ctx.agent.system_prompt = (
        "You are Atelier Nova's evidence-focused assistant. Reply in English in at most 100 words. "
        "Use attached excerpts for document-specific questions. Cite their document/excerpt labels. "
        "If no excerpts are available, explicitly say the specification is unavailable. "
        "Never invent a rule identifier or review marker."
    )
    question = (
        "According to the attached specification, what is the empty-cart subtotal, "
        "which rule and review marker support it, and does this cover payment? Cite the excerpt."
    )
    reply = await ask(ctx, client, question, embedder=embedder)
    show(
        {
            "document_marker_in_reply": "NOVA-QA-4827" in reply,
            "rule_in_reply": "CART-EMPTY-001" in reply,
        }
    )
    assert "NOVA-QA-4827" in reply and "CART-EMPTY-001" in reply
    await step("A new session with no attached documents retrieves nothing")
    empty = create_new_session(ctx.database, ctx.session.profile_id, "Separate review")
    result = await retrieve_chunks(ctx.database, embedder, empty, "empty cart")
    show({"retrieved_chunks": len(result)})
    assert result == []
    ctx.session = empty
    reply = await ask(ctx, client, question, embedder=embedder)
    assert "NOVA-QA-4827" not in reply, "An unprovided marker was invented"


async def compression(ctx, client):
    from sensai.data.session.manager import compress_session
    from sensai.data.session.message import create_message

    create_message(
        ctx.database,
        ctx.session.id,
        "Atelier Nova: empty cart must return 0. The faulty version returned 1. Use pytest. Do not edit payment code.",
        "user",
        0,
    )
    create_message(
        ctx.database,
        ctx.session.id,
        "The observed suite had one passing test and one failing test: test_empty_basket.",
        "assistant",
        0,
    )
    create_message(
        ctx.database,
        ctx.session.id,
        "The separate correct version passed both tests. Payment remains untested.",
        "user",
        0,
    )
    from sensai.data.session.session import get_session

    ctx.session = get_session(ctx.database, ctx.session.id)
    await step("build_messages: inspect the uncompressed review history")
    before = build_messages(ctx.session, "What remains untested?")
    show(
        {
            "messages_before": len(before),
            "context_characters": sum(len(m["content"]) for m in before),
        }
    )
    await step("compress_session: summarize through the local llama3.2 model")
    compressed = await compress_session(ctx.database, ctx.session, client, "llama3.2:latest")
    show({"summary": compressed.summary, "summarized_message_id": compressed.summarized_message_id})
    assert compressed.summary and compressed.summarized_message_id
    await step("build_messages: the next turn uses the stored summary")
    after = build_messages(compressed, "What remains untested?")
    show(
        {
            "messages_after": len(after),
            "context_characters": sum(len(m["content"]) for m in after),
            "last_user_request": after[-1]["content"],
        }
    )
    ctx.session = compressed
    reply = await ask(
        ctx,
        client,
        "Using the previous review context, which test originally failed and what remains untested? Answer in at most three lines.",
    )
    show({"follow_up_answer_received": bool(reply.strip())})


async def profiles(ctx, client):
    from sensai.data.session.message import create_message
    from sensai.ui.commands.prefs import inst_execute, prefs_execute

    await step("/prefs add: Camille prefers concise English test summaries")
    await prefs_execute(ctx, ["add", "Use concise English summaries and pytest -q."])
    await step("/inst add: preserve the payment module")
    await inst_execute(ctx, ["add", "Do not edit payment code."])
    await step("build_messages: inspect the profile context injected into a turn")
    show(build_messages(ctx.session, "Check the cart.")[0])
    await ask(
        ctx,
        client,
        "Which test command should I use and which module must I leave untouched? Answer using my saved preferences and instructions, not an assumed convention.",
    )
    create_message(ctx.database, ctx.session.id, "Cart review started.", "user", 0)
    await step("Log out, then authenticate the same fictional profile")
    logout()
    profile = login("Camille", "fictional-demo-password", ctx.database)
    assert profile
    show(
        {
            "profile": profile.name,
            "preferences": profile.preferences,
            "instructions": profile.instructions,
        }
    )
    await step("A wrong demo password does not authenticate")
    logout()
    show({"authenticated": login("Camille", "wrong-password", ctx.database) is not None})


async def personas(ctx, client):
    from sensai.ui.commands.persona import persona_execute

    await step("/persona list: load the two fixture personas")
    await persona_execute(ctx, ["list"])
    await step("/persona switch qa: use the evidence-focused testing role")
    await persona_execute(ctx, ["switch", "qa"])
    show({"active_system_prompt": ctx.agent.system_prompt})
    question = (
        "I observed one passing test and one failing test: test_empty_basket returns 1 "
        "instead of 0. I have not checked payment. Summarize this for my review; do not run tools."
    )
    reply = await ask(ctx, client, question)
    show({"qa_role_used_in_reply": "QA CHECK" in reply})
    assert "QA CHECK" in reply
    await step("/persona switch reviewer: use Malik's review role")
    await persona_execute(ctx, ["switch", "reviewer"])
    show({"active_system_prompt": ctx.agent.system_prompt})
    reply = await ask(ctx, client, question)
    show({"reviewer_role_used_in_reply": "REVIEW NOTE" in reply})
    assert "REVIEW NOTE" in reply
    previous = ctx.agent.system_prompt
    await step("An unknown persona leaves the current role unchanged")
    await persona_execute(ctx, ["switch", "missing"])
    show({"unchanged": ctx.agent.system_prompt == previous})


async def models(ctx, client):
    from sensai.ui.commands.model import model_execute

    await step("llama3.2: inspect real Ollama capabilities and eligible visual tools")
    show(
        {
            "model": ctx.agent.model,
            "capabilities": sorted(await client.capabilities(ctx.agent.model)),
        }
    )
    ctx.agent.system_prompt = (
        "Reply in English in at most two short sentences. Do not claim test execution."
    )
    await ask(ctx, client, "Explain why a cart containing no items has subtotal zero.")
    ctx.config.features.set("tools", enabled=True)
    show(
        {
            "visual_tools_offered": [
                tool.name for tool in await ctx.agent._usable_tools() if tool.requires
            ]
        }
    )
    await step("/model qwen3.5:9b: switch to an installed vision-capable model")
    await model_execute(ctx, ["qwen3.5:9b"])
    show(
        {
            "model": ctx.agent.model,
            "capabilities": sorted(await client.capabilities(ctx.agent.model)),
        }
    )
    show(
        {
            "visual_tools_offered": [
                tool.name for tool in await ctx.agent._usable_tools() if tool.requires
            ]
        }
    )
    await ask(ctx, client, "Explain why a cart containing no items has subtotal zero.")
    await step("An unsupported runtime model name is rejected")
    await model_execute(ctx, ["missing-demo-model"])


async def flags(ctx, client):
    from sensai.ui.commands.tool import tool_execute

    await step("/tools disable bash_tool: remove host command execution")
    await tool_execute(ctx, ["disable", "bash_tool"])
    show({"bash_tool_available": any(t.name == "bash_tool" for t in ctx.agent.available_tools())})
    await step("/tools enable bash_tool: restore the tool")
    await tool_execute(ctx, ["enable", "bash_tool"])
    show({"bash_tool_available": any(t.name == "bash_tool" for t in ctx.agent.available_tools())})
    await step("Disable the tools feature: the agent still provides a text-only response")
    ctx.config.features.set("tools", enabled=False)
    show({"available_tools": len(ctx.agent.available_tools())})
    response = await ctx.agent.run(
        "In one sentence, explain why an empty cart subtotal should be zero. Do not claim to have run tests."
    )
    show({"actual_model_response": response.response})


async def streaming(ctx, client):
    await step("Stream an English testing explanation through the actual CLI event handler")
    count = 0

    async def on_chunk(text):
        nonlocal count
        count += 1
        await ctx.ui.on_stream_chunk(text)

    response = await client.chat(
        messages=[
            {
                "role": "user",
                "content": "In English, give three short numbered checks for an empty-cart subtotal function. Do not claim execution.",
            }
        ],
        model="llama3.2:latest",
        on_chunk=on_chunk,
    )
    await ctx.ui.on_stream_end()
    show(
        {
            "stream_callbacks": count,
            "generated_tokens": response.eval_count,
            "completed_response": bool(response.response),
        }
    )
    assert count > 1


FEATURES = {
    "file-access": file_access,
    "screenshot": screenshot,
    "browser": browser,
    "sandbox": sandbox,
    "web": web,
    "mcp": mcp,
    "rag": rag,
    "compression": compression,
    "profiles": profiles,
    "personas": personas,
    "models": models,
    "flags": flags,
    "streaming": streaming,
}


async def main(feature):
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    sys.stdout = Capture()
    ctx, client = setup()
    try:
        print(
            "SENSAI | "
            + feature.upper()
            + "\nActual component execution; fictional Atelier Nova data."
        )
        await FEATURES[feature](ctx, client)
        await asyncio.sleep(1)
        print("\nComponent demonstration completed.")
    finally:
        ctx.database.close()
        (ARTIFACTS / f"{feature}.cast").write_text(
            json.dumps({"version": 2, "width": 100, "height": 34, "title": f"Sensai — {feature}"})
            + "\n"
            + "\n".join(json.dumps(event) for event in EVENTS)
            + "\n"
        )
        shutil.rmtree(WORK, ignore_errors=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("feature", choices=FEATURES)
    asyncio.run(main(parser.parse_args().feature))

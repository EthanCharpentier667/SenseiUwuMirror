"""Measure session compression against a baseline without it, on a real Ollama model.

Replays ``session.json`` through the code the app uses, one exchange at a time, in a
throwaway database, then asks the same questions with and without compression at each
context size. The answers are scored with regular expressions, so a result can be
reread and challenged. The ReAct loop and the tools aren't exercised.

    uv run python evals/compression/run.py --output docs/benchmark-sources/compression.json
"""

import argparse
import asyncio
import json
import re
import statistics
import tempfile
import time
from pathlib import Path
from typing import Any

from sensai.client import OllamaClient, estimated_tokens
from sensai.config import DEFAULT_COMPRESSION_KEEP_TURNS, DEFAULT_COMPRESSION_TOKEN_THRESHOLD
from sensai.data.database.database import Database
from sensai.data.profile.profile import create_profile
from sensai.data.session.manager import build_messages, maybe_compress_session
from sensai.data.session.message import create_message
from sensai.data.session.session import Session, create_session, get_session

SESSION_FILE = Path(__file__).with_name("session.json")
SYSTEM_PROMPT = (
    "You are SensaiUwu, a testing assistant. Answer briefly, using only this conversation. "
    "If the conversation doesn't contain the answer, say that it wasn't run or isn't known."
)
SYSTEM_MESSAGE = {"role": "system", "content": SYSTEM_PROMPT}
DEFAULT_CONTEXT_SIZES = [4096, 16384]


def progress(message: str) -> None:
    """Print a progress line right away, even when the output is piped to a file."""
    print(message, flush=True)


class ProgressUI:
    """The part of the UI compression uses, printing why a compression was skipped."""

    async def start_spinner(self, _message: str) -> None:
        """Nothing to animate here."""

    async def stop_spinner(self) -> None:
        """Nothing to animate here."""

    async def on_error(self, error: Exception | str, *, title: str = "Error") -> None:
        """Print the reason on a progress line."""
        progress(f"    {title}: {error}")


def is_correct(answer: str, patterns: list[str]) -> bool:
    """Whether an answer matches every expected pattern."""
    return all(re.search(pattern, answer, re.IGNORECASE) for pattern in patterns)


async def replay(  # noqa: PLR0913
    db: Database,
    profile_id: int,
    client: OllamaClient,
    model: str,
    turns: list[dict[str, str]],
    *,
    compress: bool,
    threshold: int,
    keep_turns: int,
) -> tuple[Session, list[dict[str, Any]]]:
    """Add the exchanges one by one, compressing before each as the app does."""
    session = create_session(db, profile_id)
    assert session.id is not None
    compressions: list[dict[str, Any]] = []
    for number, turn in enumerate(turns, start=1):
        progress(f"  replay {number}/{len(turns)}")
        if compress:
            before = estimated_tokens([SYSTEM_MESSAGE, *build_messages(session, turn["user"])])
            started = time.perf_counter()
            if before > threshold:
                progress(f"    over the threshold ({before} tokens), summarizing...")
            compressed = await maybe_compress_session(
                db,
                session,
                before,
                threshold,
                client,
                model=model,
                keep_turns=keep_turns,
                ui_handler=ProgressUI(),  # type: ignore[arg-type]
            )
            if compressed is not session:
                session = compressed
                after = estimated_tokens([SYSTEM_MESSAGE, *build_messages(session, turn["user"])])
                compressions.append(
                    {"before": before, "after": after, "seconds": time.perf_counter() - started}
                )
                progress(f"    compressed: {before} -> {after} tokens")
            elif before > threshold:
                progress("    not compressed")
        create_message(db, session.id, turn["user"], "user", 0.0)
        create_message(db, session.id, turn["assistant"], "assistant", 0.0)
        session = get_session(db, session.id) or session
    return session, compressions


async def ask(
    client: OllamaClient, model: str, session: Session, question: dict[str, Any], seed: int
) -> dict[str, Any]:
    """Ask one question on top of the replayed session and score the answer."""
    messages = [SYSTEM_MESSAGE, *build_messages(session, question["question"])]
    started = time.perf_counter()
    response = await client.chat(messages=messages, model=model, options={"seed": seed})
    return {
        "question": question["id"],
        "seed": seed,
        "correct": is_correct(response.response, question["all_of"]),
        "estimated_prompt_tokens": estimated_tokens(messages),
        "prompt_eval_count": response.prompt_eval_count,
        "seconds": time.perf_counter() - started,
        "answer": response.response,
    }


async def run_configuration(
    args: argparse.Namespace, data: dict[str, Any], num_ctx: int, *, compress: bool
) -> dict[str, Any]:
    """Replay the session once, then ask every question ``args.passes`` times."""
    client = OllamaClient(base_url=args.url, token=None, timeout=args.timeout, num_ctx=num_ctx)
    with tempfile.TemporaryDirectory() as directory:
        db = Database(path=directory, name="eval.db")
        db.initialize()
        profile = create_profile(db, "Eval", "eval")
        assert profile.id is not None
        session, compressions = await replay(
            db,
            profile.id,
            client,
            args.model,
            data["turns"],
            compress=compress,
            threshold=args.threshold,
            keep_turns=args.keep_turns,
        )
        answers: list[dict[str, Any]] = []
        total = args.passes * len(data["questions"])
        for seed in range(args.passes):
            for question in data["questions"]:
                answer = await ask(client, args.model, session, question, seed)
                answers.append(answer)
                verdict = "ok" if answer["correct"] else "WRONG"
                progress(
                    f"  answer {len(answers)}/{total} pass {seed + 1}/{args.passes} "
                    f"{question['id']}: {verdict} ({answer['seconds']:.1f}s)"
                )
        summary = session.summary or ""
        db.close()
    retained = {
        question["id"]: is_correct(summary, question["summary_terms"])
        for question in data["questions"]
        if question["summary_terms"]
    }
    return {
        "num_ctx": num_ctx,
        "compression": compress,
        "accuracy": sum(answer["correct"] for answer in answers) / len(answers),
        "median_seconds": statistics.median(answer["seconds"] for answer in answers),
        "estimated_prompt_tokens": answers[0]["estimated_prompt_tokens"],
        "compressions": compressions,
        "summary": summary,
        "facts_retained_in_summary": retained if compress else None,
        "answers": answers,
    }


def report(results: list[dict[str, Any]], questions: list[dict[str, Any]]) -> None:
    """Print one comparable line per configuration, then the accuracy per question."""
    print("num_ctx  compression  prompt_tokens  accuracy  median_s  compressions  compress_s")
    for result in results:
        spent = sum(entry["seconds"] for entry in result["compressions"])
        print(
            f"{result['num_ctx']:>7}  {'on' if result['compression'] else 'off':>11}  "
            f"{result['estimated_prompt_tokens']:>13}  {result['accuracy']:>8.0%}  "
            f"{result['median_seconds']:>8.1f}  {len(result['compressions']):>12}  {spent:>10.1f}"
        )
    for question in questions:
        scores = []
        for result in results:
            own = [a["correct"] for a in result["answers"] if a["question"] == question["id"]]
            label = "on" if result["compression"] else "off"
            scores.append(f"{result['num_ctx']}/{label}: {sum(own)}/{len(own)}")
        print(f"{question['id']:<16} " + "  ".join(scores))


def parse_args() -> argparse.Namespace:
    """Read the measurement's inputs from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="llama3.2:latest")
    parser.add_argument("--url", default="http://127.0.0.1:11434/api/chat")
    parser.add_argument("--passes", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--num-ctx", type=int, nargs="+", default=DEFAULT_CONTEXT_SIZES)
    parser.add_argument("--threshold", type=int, default=DEFAULT_COMPRESSION_TOKEN_THRESHOLD)
    parser.add_argument("--keep-turns", type=int, default=DEFAULT_COMPRESSION_KEEP_TURNS)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


async def main() -> None:
    """Run every configuration, print the comparison and optionally save it."""
    args = parse_args()
    data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    configurations = [(num_ctx, compress) for num_ctx in args.num_ctx for compress in (False, True)]
    results = []
    for number, (num_ctx, compress) in enumerate(configurations, start=1):
        label = "on" if compress else "off"
        progress(
            f"Configuration {number}/{len(configurations)}: num_ctx={num_ctx}, compression={label}"
        )
        results.append(await run_configuration(args, data, num_ctx, compress=compress))
    progress("")
    report(results, data["questions"])
    if args.output:
        inputs = {key: str(value) for key, value in vars(args).items() if key != "output"}
        document = {"inputs": inputs, "results": results}
        args.output.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        progress(f"\nSaved to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())

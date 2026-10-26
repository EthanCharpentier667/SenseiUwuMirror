# Scope and decisions

This page explains which features SensaiUwu has and why, starting from its
[use case](use-case.md), which features we left out on purpose, and how we made our
major technical decisions.

Our constraints are the project's:

- **bare Python**, with no LLM framework (no LangChain, no LlamaIndex);
- **Ollama** as the only model API;
- **the user's own hardware**, a laptop that is also building and running the project
  under test;
- **the use case**: a testing assistant that acts on the machine rather than only
  talking.

---

## Scope, from the usage scenario

The [flagship scenario](use-case.md#flagship-scenario-does-ethans-vulkan-window-open)
is checking that a Vulkan window opens without errors. Its cycle is **read → run →
observe → conclude → fix → check again**. Each feature is there because a step of that
cycle needs it:

| Step of the cycle | What it needs | Feature |
|---|---|---|
| Read how the project runs | Read files, remember them | `file_read`, RAG on documents |
| Run the project | Run commands, including programs that never exit | `bash_tool` (with `background`), `bash_job` |
| Observe the result | Exit code and logs, the screen, a web page | Command output, `screenshot`, browser tools |
| Conclude | Chain several observations before answering | ReAct loop |
| Fix | Edit the code or the tests | `file_write` |
| Check again | Run the same command again, in the same session | Session history, compression |
| Throughout: the user stays in control | Approve what changes the machine | Trust levels |
| Throughout: tests that need extras | A reference implementation, a fuzzer, a doc lookup | Sandbox, `web_search`, MCP |

The test frameworks themselves (GoogleTest, Criterion, pytest, cargo test) have **no
dedicated integration**: they are commands, and `bash_tool` reaches them all. This
saves one integration per framework, at the cost of making the model read their output.

### Features left out on purpose

| Feature | Why we left it out |
|---|---|
| **Semantic cache** (issue #24) | The answer to a testing question depends on the current state of the code. A cache hit on *"do my tests pass?"* would serve an old "yes" after a commit that broke the build. A wrong answer to a tester is worse than a slow one. The cost we cut with a cache is better cut by the budgets and the cut observations |
| **Multi-agent orchestration** (issue #20) | With a local 3B model, each extra agent multiplies the LLM calls, so the latency, on a laptop that is also running the project under test. One test is a single sequential cycle, and one ReAct loop covers it. Splitting it into a "runner" and a "reviewer" would add messages between agents, which a small model gets wrong more often, without any step of the scenario needing it |
| **Web UI** (issue #30) | Our users test from a terminal, where their build and their tests already run. A web UI would duplicate the interface without serving the scenario. The core talks to the interface through events ([Event System](events.md)), so a web UI can be added later without touching the agent |
| **Automated prompt optimization** (issue #25) | Our prompts are short and tied to the controller's rules (allowed actions, JSON shape). The failures we saw came from the model (invented refs, reports of fake successes), and we fixed them in the code: name targeting, `failed` status, re-asking without the schema. Optimizing prompts automatically would need an eval suite we don't have yet (see the [retrospective](retrospective.md)) |

---

## Major decisions

### 1. A constrained ReAct loop, instead of Ollama's native tool calling

**What we did.** At each step, the model only returns JSON (`thought`, `action`,
`args`), constrained by a schema (Ollama's `format`) that lists the actions still
allowed. A Python controller (`features/react/react.py`) checks each step before
running it: unknown tool, missing or mistyped argument, an identical call already made.
It also enforces the budgets: 10 steps, 10 tool calls, 2 per tool. The final reply is a
separate call, without tools, streamed.

**Alternative considered:** Ollama's native tool calling (`tools` in `/api/chat`). The
model chooses one or more tools in the same call, and the loop continues as long as it
returns `tool_calls`.

| Constraint | Native tool calling | Constrained ReAct (chosen) |
|---|---|---|
| Reliability with a 3B model | The model decides on its own when to stop. Invalid arguments are only seen once the tool runs | The schema only allows actions that are valid now. Invalid steps are rejected by the code, and the model is told why |
| Cost in calls and latency | The model can answer in the same call that uses the last tool | One planning call per step, plus one for the reply: more calls, so more latency |
| Control and safety | Budgets enforced from outside, by counting `tool_calls` | Budgets and refusals are part of the loop: an action is no longer offered once its budget is spent |
| Model compatibility | Needs a model with the `tools` capability | Works with any model that can write JSON. When the server ignores the schema (Ollama Cloud), the JSON shape is spelled out in the instructions instead |

**Why.** With our default model (3B, chosen for the hardware), reliability matters
more than latency. One wrong step on the host (a command with bad arguments, a click in
a loop) costs the user more than a few seconds of planning. Streaming each thought makes
the extra calls visible instead of silent.

### 2. One SQLite file with hybrid search, instead of a JSON file or a vector database

**What we did.** Profiles, sessions, messages, documents and their chunks all live in
one SQLite file, through `peewee`. Embeddings (768 dimensions, `nomic-embed-text`) go
in a `vec0` table (`sqlite-vec` extension), and the text goes in an FTS5 index.
Retrieval merges both rankings with Reciprocal Rank Fusion (`_RRF_K = 60`,
`data/session/chunk.py`).

**Alternatives considered:**

- **A JSON file** for the memory: no dependency, but it is rewritten whole on each save,
  can't be searched without loading it all, and has no transactions.
- **A separate vector database** (Chroma, Qdrant): good semantic search, but one more
  service to install and run, and two stores to keep in sync.

| Constraint | JSON file | Vector database | SQLite + sqlite-vec + FTS5 (chosen) |
|---|---|---|---|
| Installation on the user's machine | Nothing | A service or a large dependency | One Python package, one file |
| Integrity (crash in the middle of a save) | File can be corrupted | Two stores can disagree | Transactions, `ON DELETE CASCADE` between session, messages and chunks |
| Search on identifiers | Linear scan | Weak: embeddings blur `VUID-vkCmdDraw-None-08600` or `test_parse_empty` | FTS5 finds the exact identifier, and vectors find the meaning |
| Semantic search | None | Very good | Good enough for a session's documents (a few hundred chunks) |

**Why.** A tester's queries are full of exact identifiers: error codes, function and
test names, file paths. Embeddings alone handle these poorly, and keyword search alone
misses reformulations, hence the hybrid search. One file also fits the single user on
one laptop that we target. The cost is that SQLite doesn't handle many users writing at
the same time, which isn't our use case.

**Chunk size.** We cut chunks at 1,500 characters with a 200-character overlap
(`DEFAULT_CHUNK_SIZE`, `DEFAULT_CHUNK_OVERLAP`). Two constraints pull against each
other:

- **Precision:** a smaller chunk is more precise, but cuts a function or a protocol
  section in half.
- **Context:** a bigger chunk keeps the context, but 3 retrieved chunks
  (`DEFAULT_RETRIEVED_CHUNKS`) take more of the 16k window, which the trajectory also
  needs.

1,500 characters is about one section of a subject or one medium function.

### 3. Built-in browser tools, instead of a Playwright MCP server

**What we did.** Five tools written on the Playwright Python API (`features/tools/
browser/`) drive the installed Chrome. The page is given to the model as its
accessibility tree, as text, cut at 5,500 characters, with noise removed. Elements are
targeted by their name as the snapshot shows it, or by their ref.

**Alternative considered:** connecting the official Playwright MCP server, which Sensai
can already do (`/mcp add-json`), with no code to write.

| Constraint | Playwright MCP server | Built-in tools (chosen) |
|---|---|---|
| Setup for the user | Node.js, then adding the server by hand | Nothing beyond Chrome. The tools are there from the first launch |
| Tokens per observation | Fixed by the server: full snapshots, plus console and tabs | Under our control: noise removed, cut at 5,500 characters to fit the 6,000-character observation limit |
| Reliability with a small model | Targets elements by `ref` only. In our runs, the model invented refs and clicked `<body>` | Targets by name first (exact, then partial), and asks for the ref only when names are ambiguous. A failure returns the current page |
| Result for the agent | Plain text: the controller can't tell an error from a success | `{"error": ...}`, so the step is marked `failed` and reported as such |
| Maintenance | Done by Microsoft | Ours: five tools and a shared module, covered by tests |
| Number of actions | Dozens of tools (tabs, dialogs, uploads…) | Five, so the allowed actions stay short for a small model |

**Why.** What decided it was what the model sees: the number of tokens per step, and
how reliably a 3B model can target an element. We confirmed this on a real page (the
`/dev/login` page of a Phoenix app), where named targeting found the email field, the
password field and the submit button that refs had missed. The MCP server is still
there for what our five tools don't cover.

### 4. A 3B model by default, with bigger models as an option

Discussed in detail in the [benchmark](benchmark.md) and in
[business impact](responsibility.md#model-size-against-the-hardware-users-own).

- **Alternative:** Qwen 3.5 9B by default (Artificial Analysis index 11, against an
  estimated 6 for Llama 3.2 3B; vision; 262k context).
- **The constraints:**
  - quality per step against the memory and compute left for the project under test
    (2.0 GB against 6.6 GB of weights);
  - token speed on a laptop with no GPU.
- **The decision:** default to the model every user can run, put the reliability in the
  controller (decision 1), and offer `/model` to switch to Qwen for vision or harder
  cases.

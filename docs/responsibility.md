# Limits, impact and risks

This page covers what SensaiUwu, the [testing assistant](use-case.md), is allowed to do
with the data it touches, what our technical choices cost the people who use it, how it
could harm its own host or someone else's system, and how the user's experience shaped
those choices.

Every statement points to the code that implements it. Where something is still
missing, we say so.

---

## 1. Legal and ethical limits on the data

### Who is responsible for what: Sensai is a self-hosted tool

Sensai is not a hosted service like ChatGPT or Claude. It is a program its **operator**
installs and runs on their own infrastructure, and the operator can be:

- **a single developer:** Sensai, the database and Ollama all run on their laptop;
- **a company:** Sensai runs on its developers' machines, and the models run on an
  Ollama server the company owns, shared by its teams.

In both cases, "local" means **on hardware the owner of the data controls**. That
changes who is responsible for securing that data:

| | Hosted assistant (ChatGPT, Claude) | Sensai (self-hosted) |
|---|---|---|
| Where conversations are stored | On the provider's servers | In `sensai.db`, on the operator's machine |
| Who runs the model | The provider | The operator: their laptop or their company's Ollama server |
| What our team receives | Not applicable | **Nothing.** We host no server, collect no data and have no telemetry |
| Who is the data controller (GDPR) | The provider, at least as a processor | The operator |
| Who secures storage, access, backups and retention | The provider, for every customer at once | The operator, with the tools they already have: disk encryption, OS accounts, the company's network rules and retention policy |

A hosted provider holds all its customers' data in one place. It has to encrypt it,
separate customers, keep audit logs, sign processing contracts and erase data on
request, because no customer can do it for them.

Sensai never holds anyone's data. Building those layers into the program would
duplicate what the operator's system already provides (an encrypted disk protects
`sensai.db` better than an encryption scheme of our own), and add friction for a single
developer who doesn't need them. That is why we **did not build** the following:

- encryption of the database;
- multi-tenant access control;
- retention policies;
- audit logs.

**What stays our responsibility, as the publisher**, is what the program itself does
with the data the operator gives it:

- **never leak more than the operator chose to send:** tools can be turned off one by
  one, and tools that change something ask for approval;
- **never store a secret we don't need:** passwords are hashed with PBKDF2, the saved
  login goes in the OS keychain, MCP tokens too;
- **keep users apart in a shared database:** retrieval and profile instructions are
  scoped to the session's owner;
- **say what goes where,** which is the purpose of this page.

### What the assistant handles, and where it ends up

A testing assistant sees much more than a chatbot: it reads source code, runs commands,
looks at the screen and types into web pages. All of that can contain personal or
confidential data.

| Data | Where it is stored | Who can read it |
|---|---|---|
| Profile: name, password | `sensai.db` (SQLite, in the working folder). The password is hashed with PBKDF2-HMAC and a random salt (`data/profile/manager.py`), with parameters read from the environment | Anyone who can read the file. The password itself can't be read back |
| Saved login | The user name goes in `~/.sensai/state.json`, the password in the OS keychain (`keyring`, `core/state.py`) | The OS user |
| Preferences, instructions | `sensai.db`, in plain text | Anyone who can read the file |
| Conversation history | `sensai.db`, in plain text | Anyone who can read the file |
| Tool trace: tool, arguments, observation | `sensai.db`, in plain text, as `tool` messages. They are never sent back to the model | Anyone who can read the file |
| Documents (RAG corpus) | `sensai.db`: chunks, their embeddings and a full-text index | Searched only for the session they were attached to (`get_document_ids_by_session`) |
| Screenshots | `$TMPDIR/sensai/screenshot.jpg`, overwritten on each capture | The OS user |
| MCP OAuth tokens | The OS keychain | The OS user |

`*.db` and `.env` are in `.gitignore`, so the history and the secrets aren't committed
by accident.

### Sending data to a remote server

**This is the main limit.** Sensai talks to Ollama over HTTP, and the whole prompt goes
to the server at `--url`. **The rule:** that server must belong to whoever owns the
data, the user or their company. The limit is crossed when the prompt goes to a server
that doesn't.

| Service | What is sent | Default? |
|---|---|---|
| Ollama server at `--url` | The whole prompt: history, files read, command output, page snapshots, screenshots (vision models) | **Yes.** `DEFAULT_URL` is our team's own Ollama server (`ollama.tanouminou.com`), run by a team member for the project. Anyone else deploying Sensai points `--url` at their own server |
| Ollama Cloud (`gemma4:cloud`) | The same, processed by Ollama, a third party | **No.** Only when the user picks Gemma 4 because a task needs a much more capable model than what runs locally. This is an explicit choice to send the prompt outside |
| `web_search`, `web_fetch` (`ollama.com/api/...`) | The search query or the URL, which the model may build from the code | Only when the model calls them (feature enabled by default) |
| MCP servers | Whatever their tools receive as arguments | Only the servers the user adds |

What crossing this limit means:

- **A company's code or a client's data**: sending source code or logs to a server the
  company hasn't approved usually breaks a confidentiality agreement (NDA). With
  personal data, it also means transferring it to a processor without a contract, which
  the GDPR forbids (Art. 28).
- **Secrets**: a `file_read` on `.env`, or a `bash_tool` that prints environment
  variables, sends API keys to the model's server, where they may be logged.
- **School work**: an exam subject or a classmate's code sent to a cloud service may
  break the rules of the exam.

What we do about it:

- **The user chooses the server.** `--url` points Sensai at a local Ollama
  (`http://localhost:11434/api/chat`), and then nothing leaves the machine except
  through web tools and MCP.
- **Leaky tools can be turned off.** `--disable-tool web_search --disable-tool
  web_fetch`, or `--disable mcp`, removes the other ways out (see
  [Feature flags](use-case.md#feature-flags-and-settings)).
- **Nothing is sent without being visible.** With the `none` and `partial` trust
  levels, every tool that isn't read-only asks for approval and shows its arguments
  first.

**What we'd improve:** the default URL fits our team, but a new operator should choose
their server, not inherit ours. Asking for it on first launch is noted in the
[retrospective](retrospective.md).

### Personal data in the database and the trace

- **The tool trace can hold secrets.** Since the trace is saved, a `browser_type` call
  that fills a password field during a login test stores that password in plain text in
  `sensai.db`, with the call's arguments. The same goes for a command's output that
  prints a token. The trace is never sent back to the model, but it stays on disk.
  - **Planned fix:** redact the `text` argument of `browser_type` when the field is a
    password, and secret-looking values (`*_TOKEN`, `*_KEY`, `password=`) in
    observations, before saving them.
- **Erasing data is the operator's job.** `sensai.db` is the operator's file, on their
  machine. A developer erases their data by deleting it; a company applies its own
  retention policy to it, as it does for any other file on its machines. The GDPR right
  to erasure (Art. 17) applies to the operator as the data controller, not to us. A
  `/session delete` command would still be a convenience, and the `ON DELETE CASCADE`
  constraints would already remove the messages, documents and chunks with the session.
- **Isolation between users holds.** Retrieval only searches the documents of the
  current session. Profile preferences are only added when the active profile owns the
  session (`_profile_context_message`), so one user's instructions can't leak into
  another's session.

### Documents in the RAG corpus

The corpus is what the user gives (`--files`) or what the agent reads with `file_read`.
Indexing a document copies it into the database, in chunks. For a copyrighted document
(a purchased book, a paid standard), keeping a copy for one's own work is generally
allowed (France's private-copy exception, CPI L122-5), but sharing that database is
not. The database is therefore personal and must not be shared or committed (`*.db` is
ignored).

### The models' licences

| Model | Licence | What it means for us |
|---|---|---|
| `llama3.2` (default) | Llama 3.2 Community License | Allowed for our use. It comes with Meta's Acceptable Use Policy, and a product built on it must say "Built with Llama" |
| `qwen3.5:9b` | Apache 2.0 | No restriction, beyond keeping the licence notice |
| `gemma4:cloud` | Google's Gemma terms, served by Ollama Cloud | Only used in the cloud, when a task needs a much more capable model. It runs on Ollama's servers, so the user accepts Ollama Cloud's terms too |
| `nomic-embed-text` | Apache 2.0 | No restriction |

Breaking a licence (for example, using Llama for something its Acceptable Use Policy
forbids) ends the right to use the model. A commercial product would then have to change
models, and re-index the whole corpus if the embedding model is the one affected (see
[decisions](scope-and-decisions.md)). Licences are listed in
[the benchmark](benchmark.md#41-les-deux-modeles-reellement-installes).

---

## 2. Business impact of our technical choices

### Model size against the hardware users own

Our target user is a student or a developer testing a project on their own laptop. The
model must run there, next to the project under test: an IDE, a build, a Vulkan app,
Chrome.

| Model | Weights on disk | Capabilities | Who can run it |
|---|---|---|---|
| `llama3.2` 3B, Q4_K_M | 2.0 GB | Text, tools | Almost any recent laptop, while the project under test is running |
| `qwen3.5:9b`, Q4_K_M | 6.6 GB | Text, vision, tools, thinking | A machine with a GPU or 16 GB of unified memory |

Sizes come from `ollama show`, in [the benchmark](benchmark.md).

**Impact:** a 9B model by default would leave out part of our target users, or slow
down their machine while it builds and runs their project. The test result could then
be wrong: for example, a timeout reached only because the LLM was taking the CPU. So we
ship the 3B model by default and let users pick a bigger one (`/model`).

The cost of that choice is reliability. A 3B model makes more mistakes when planning,
so we put the safeguards in the code instead: the JSON schema, the controller's checks,
the budgets and failure reporting (see the [decisions](scope-and-decisions.md)).

### Response time against adoption

A ReAct message isn't one LLM call. It is one planning call per step, then the reply,
so **up to 11 calls** with the current budgets (`DEFAULT_MAX_STEPS = 10`, plus the
answer). Each planning call sends the whole context again, and the trajectory grows by
one observation per step (at most 6,000 characters, `DEFAULT_OBSERVATION_LIMIT`).

A developer who waits several minutes for an answer they could get by running `pytest`
themselves stops using the tool. Our answers to this:

- **The model's reasoning is streamed live**, step by step, and so is the reply. The
  user can see right away whether the agent is on the right track, and stop it early.
- **Observations are cut** (6,000 characters, page snapshots at 5,500, the end of a
  command's output at 8,000), so the prompt doesn't grow without limit.
- **Long programs run in the background** (`background: true`), so the agent doesn't
  block for 30 s waiting on a server that never exits.

### Local inference against a cloud API

An order of magnitude, estimated from the code (about 4 characters per token):

| Message | LLM calls | Input tokens (estimate) |
|---|---|---|
| A simple question, no tool | 1 | ~2,000 to 3,000 |
| A typical test (4 steps, short outputs) | 5 | ~20,000 |
| Worst case (10 steps, observations at 6,000 characters) | 11 | ~100,000 |

- **Cloud API.** At the median API price published for Qwen 3.5 9B ($0.135 per million
  input tokens, [benchmark](benchmark.md#42-mesure-independante-disponible)), even the
  worst case costs about $0.01 per message. The money isn't the problem with a cloud
  API: the problem is confidentiality (section 1).
- **Local.** No cost per token, but time. The ~100,000 tokens of the worst case all have
  to be evaluated on the user's machine, so a long session costs minutes rather than
  cents.
  - We haven't measured this on our machines yet. `Response` already records
    `prompt_eval_count`, `eval_count` and `total_duration`, so the measurement only
    needs the scenarios of the use case to be run.

**Our choice:** local inference by design (privacy, no account, no cost per call).
"Local" can be the developer's laptop, or a GPU server the company owns and shares
between its developers. The second option changes the business picture:

- one machine is bought once;
- every developer gets the 9B model without needing the hardware;
- the code never leaves the company.

Ollama Cloud remains an opt-in, for the rare task that needs a much more capable model
(`gemma4:cloud`). The worst case also
brings its own risk, described below: the context can overflow.

---

## 3. How our choices could disrupt a system

| Risk | Whose system | What could happen | How we handle it |
|---|---|---|---|
| **`bash_tool` on the host** | The user's | A wrong or misunderstood command (`rm -rf`, `git push --force`, `DROP TABLE`) has irreversible effects, with the user's rights | `bash_tool` isn't `safe`: it asks for approval in `none` and `partial`, with the full command shown. Foreground commands stop after 30 s. Each command runs in its own process group (`start_new_session`) so it can be stopped completely, and every background job is stopped when Sensai exits. The sandbox exists for throwaway code |
| **Browser on a real site** | Someone else's | `browser_click` and `browser_type` act like a user: on a production site, a test could send a form, delete an account or place an order | Both tools aren't `safe`, so they ask for approval. Chrome is visible, so the user sees what happens. `file://` URLs are refused, so the browser can't read local files without the approval `file_read` asks for. The use case targets the user's own app (`localhost`) |
| **Calls to external services** | ollama.com, the sites fetched | A small model in a loop could call `web_search` or `web_fetch` again and again | The budgets are enforced by the code, not the model: 10 tool calls per message, 2 per tool, and an identical call is refused. One message makes at most 2 searches |
| **Load on a shared Ollama server** | Other users of the server | Up to 11 LLM calls per message with a 16k context use the GPU of a server that others share | The same budgets cap the number of calls. A user with a shared server can lower `--num-ctx` |
| **Context overflow** | Ours | 10 observations at 6,000 characters exceed the 16,384-token `num_ctx`. Ollama then truncates the prompt, and the instructions or the user's question can be lost | Observations are cut, and failed or rejected steps are short. **Not solved:** the controller doesn't yet budget the trajectory in tokens. Tracked in the [retrospective](retrospective.md) |
| **Sandbox reaching the host** | The user's | Code run in `sandboxed_code` tries to reach the host | Disposable container with no network, a read-only filesystem, half a CPU, 512 MB, 64 processes, a 20 s limit, and output cut at 64 KB. **Limit:** Sensai needs access to the Docker daemon, which is equivalent to root on Linux; the risk is Docker's, not the container's |
| **Compression losing facts** | Ours | Folding the history into a summary can drop the detail a later message needs (the exact error, the file already fixed) | The summary is written by the same model, with the instruction to keep facts, decisions and context. Tool results are never in it, so the summary can't turn a stale result into a fact. Since the trace is saved, what actually ran can still be checked in the database |
| **A report that lies** | The user's trust | The model announces "✅ login works" when the click failed | A tool error comes back as `{"error": ...}`. The step is marked `failed`, and the reply's instructions list failed steps as failed. We saw this happen on a real run before the fix |

### A choice we made because of a risk: no semantic cache

A semantic cache (issue #24) answers a question similar to an earlier one without
calling the model. For a testing assistant, the answer to *"do my tests pass?"* depends
on the code **now**, not on the code an hour ago. A cache hit would serve "everything
passes" after a commit that broke the build. We left this feature out on purpose (see
[scope](scope-and-decisions.md#features-left-out-on-purpose)).

---

## 4. The user's experience in our technical choices

| Choice | What the user sees | Why |
|---|---|---|
| **Streaming** of the thoughts and the reply (`StreamingThoughtExtractor`) | The thought behind each step, then `→ tool {args}`, then the reply as it is written | Perceived speed: a 30 s test with visible progress feels shorter than 30 s of silence. The user can also stop a wrong path early |
| **Live display limited to the screen's height** (`_Tail`, `transient=True`), then the final reply printed once | A long reply no longer prints itself again and again | A real bug we fixed: the terminal filled up with copies of the reply |
| **Three trust levels** | `none`: every tool asks. `partial`: read-only tools run on their own. `total`: nothing asks | Human-in-the-loop has a cost: approving every `bash_job` or `browser_snapshot` is tiring and makes the user approve without reading. `partial` only asks when something can change |
| **A refusal doesn't stop the agent** | The model sees "refused" and suggests another approach | The user stays in control without having to start again |
| **Visible sources** | RAG excerpts are given to the model as `[Document N, excerpt M]`, with the instruction to say when they don't contain the answer | The user can check where a claim comes from |
| **Honest failures** | "The click on *Log in* failed: no element with that name" instead of a made-up success | Trust: one false "✅" is enough for a tester to stop believing the tool |
| **Elements targeted by name** | `browser_click(name="Se connecter")` instead of `ref="e27"` | Small models invented refs; names come from the page and are reliable |
| **Tools hidden when unusable** | No screenshot offered to a model without vision | No step wasted on a call that would fail |
| **Saved trace** | What ran can be read back after the session | Trust: the user can check what the agent really did, not just what it says it did |

# If we started over

This page answers the question _"if you started over, what would you change?"_. For
each change, it gives a concrete alternative, which constraints it handles better than
what we built, and why it is doable with a local Ollama model, no LLM framework, our
hardware and the project timeline.

---

## 1. Have the verdict computed by code, not by the model

### What we built

The model reads raw command output (the last 8,000 characters, cut to 6,000 for the
model), decides on its own whether the tests passed, and writes the verdict.

Our real runs showed where this breaks:

- a 3B model sometimes announced a success that didn't happen (a login that failed,
  reported with a "✅");
- long outputs fill the context: 10 steps of 6,000 characters exceed the 16k
  `num_ctx` (see [risks](responsibility.md#3-how-our-choices-could-disrupt-a-system));
- the useful part of a test log (which test failed, where, why) is a few lines buried
  in hundreds.

### The alternative: parse test reports, and let the model explain

Almost every test framework can write a standard report:

- **Test results** in JUnit XML: `pytest --junitxml`, `ctest --output-junit`, the
  GoogleTest `--gtest_output=xml` option, `cargo nextest` and Jest through a reporter.
- **Coverage** in Cobertura XML: `coverage.xml`, `gcovr --xml`, `cargo llvm-cov
--cobertura`.

Instead of the model reading the log, a `test_report` tool would:

1. Run the command with the report option, through the existing `bash_tool` code.
2. Parse the XML with the standard library (`xml.etree.ElementTree`).
3. Return compact facts to the model: `{"passed": 41, "failed": 2, "failures":
[{"test": "test_parse_empty", "file": "tests/test_parser.py", "line": 18, "message":
"AssertionError: [] != None"}]}`.

The model no longer decides **whether** the tests pass, since the exit code and the
report already say so. It explains **why** they fail, and fixes them.

### What it handles better

| Constraint we named                                                                                                                 | Today                                                    | With reports                                                                                     |
| ----------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Trust in the answers ([UX](responsibility.md#4-the-users-experience-in-our-technical-choices))                                      | The verdict is the model's opinion                       | The verdict comes from the report. The model can't announce "everything passes" when `failed: 2` |
| Small model, chosen for the hardware ([decision 4](scope-and-decisions.md#4-a-3b-model-by-default-with-bigger-models-as-an-option)) | Has to find the needle in a raw log                      | Gets the failures already extracted. A 3B model is good enough to explain a given assertion      |
| Tokens and context (16k `num_ctx`)                                                                                                  | Up to 6,000 characters per step                          | A few hundred characters for a whole suite, failures included                                    |
| Latency (11 calls at most)                                                                                                          | Often one more step to read the file a failure points to | The file and line are in the observation, so there is one step less                              |

The generic `bash_tool` stays for what has no report: functional tests, GUI apps,
servers.

### Why it's doable

- No framework: JUnit XML and Cobertura are parsed with the standard library, in about
  a hundred lines.
- Nothing changes for the model or the hardware: the same local Ollama model, fewer
  tokens.
- It fits the existing architecture: one more `Tool`, registered in `registry.py`, with
  `safe = False` like `bash_tool` since it runs a command.
- Time: one or two days for one person, tests included. Our test fakes already cover
  tools that run commands.

---

## 2. Measure the agent from the first week, with scenario tests

### What we built

Our 490+ tests check the code: the controller, the tools, the session. They use fake
clients and never measure whether **the agent** succeeds at a testing task with a real
model. As a result:

- the budgets (5 steps then 10; 3 tool calls then 10; 2 per tool) were raised after
  failed real runs, not from measurements;
- the [benchmark](benchmark.md) compares models on public scores, and itself concludes
  that "the success of the agent loop is still a criterion to measure";
- each bug we found on a real model (invented refs, ignored schema, a fake success) was
  found by hand.

### The alternative: a scenario suite, run on local models

A folder of small reference projects, each with a known answer:

| Scenario          | Project                                 | Expected result                                                       |
| ----------------- | --------------------------------------- | --------------------------------------------------------------------- |
| Unit test failure | Python module with one known bug        | Reply names `test_parse_empty`; the fix makes `pytest` pass           |
| Coverage          | C project with Criterion                | Reply gives the coverage within 1 point of `gcovr`                    |
| Functional, web   | Small HTTP server with a login page     | The login succeeds with the right password and fails with a wrong one |
| Honesty           | A login form whose button doesn't exist | The reply reports a failure, never a success                          |

A Python script (no framework) runs Sensai's `Agent` on each scenario with each
installed model (`llama3.2`, `qwen3.5:9b`). It checks the result with a deterministic
check: exit code, a file's content, a word in the reply. It also records the
`prompt_eval_count`, `eval_count` and `total_duration` that `Response` already returns.

### What it handles better

- **Budgets, chunk size, model choice:** these become measured trade-offs. For example:
  "Qwen 9B succeeds at 7 out of 8 scenarios in 40 s, Llama 3B at 5 out of 8 in 15 s".
  We currently argue them from public scores.
- **Regressions:** a prompt change or a new tool that breaks the honesty scenario is
  seen at once, not at the next demo.
- **The benchmark becomes ours,** measured on our use case and our hardware, which is
  what the jury and our own [benchmark](benchmark.md) asked for.

### Why it's doable

- It uses the existing `Agent`, the local models already installed, and our own
  machines.
- It can run at night or before a release: it doesn't have to run in CI, which has no
  GPU.
- Writing the four scenarios and the script is about three days.

### The change in our organization

We split the work by feature: one person on RAG, one on tools, and so on. Each feature
was tested on its own, and the use case was only checked end to end at the end.

Starting over, **one person would own the scenario suite from the first week**. Each
feature's pull request would have to keep the scenarios passing, or add a scenario of
its own. The use case would then guide the work from the start, instead of being
written up at the end.

---

## 3. Smaller changes we would make right away

| Change                                               | Constraint it handles                                                                                                                               | Effort                                                                               |
| ---------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Change                                                       | Constraint it handles                                                                                                                                                                              | Effort                                                                               |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Ask for the Ollama server on first launch, instead of defaulting to our team's | Privacy: a new operator chooses their own server (their laptop or their company's) instead of inheriting ours ([limits](responsibility.md#sending-data-to-a-remote-server)) | A prompt at first launch, saved with the profile                                     |
| Redact passwords and tokens in the saved trace               | Secrets in `sensai.db`: we shouldn't store a secret we don't need, even on the operator's disk                                                                                                     | One function in `ReActController.transcript()`                                       |
| Budget the trajectory in tokens, not only in steps           | Context overflow beyond 16k                                                                                                                                                                        | The controller already knows each observation's length                               |

We wouldn't add session or profile deletion as a security feature. Sensai is
self-hosted, so the database is the operator's file: a developer deletes it, and a
company applies its own retention policy (see
[who is responsible for what](responsibility.md#who-is-responsible-for-what-sensai-is-a-self-hosted-tool)).

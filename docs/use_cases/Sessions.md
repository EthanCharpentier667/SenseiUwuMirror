# Sessions

Every conversation with Sensai is a session saved in SQLite. `/session` lists the
profile's sessions, switches back to an earlier one, starts a new one, renames or
deletes one. A new session is named by the model after its first exchange.

## Scenario

Camille spent the morning investigating the empty-cart regression with Sensai.
After lunch she starts a fresh session to draft the merge-request description,
then wants to go back to the morning's investigation to check which test failed,
without retyping its context. Malik later asks her to clean up the throwaway
sessions she opened while trying commands.

This feature belongs to the [Atelier Nova review scenario](../use-case.md#scenario-de-reference-camille-verifie-le-panier-datelier-nova).

## User stories

### US-SESS-01 — Resume an earlier investigation

**As Camille Moreau, the developer switching between tasks, I want to reopen an earlier session, so that the model continues it with its full history.**

Preconditions: the profile has at least one saved session.

| Acceptance criterion | Expected result |
| --- | --- |
| Picker | `/session` lists the profile's sessions, most recently used first, with their message count and last use, after a **+ New session** entry. |
| By name | `/session switch <name>` opens the session whose name matches exactly, or starts with the text typed (ignoring case). Tab completes the names. |
| Ambiguity | When several sessions match, the picker opens with only those. |
| Recap | Switching shows the session's name, size and age, then its last 3 exchanges. |
| Continuity | The next prompt is sent with the reopened session's history, summary and attached documents. |
| Isolation | Sessions of another profile can be neither listed nor opened, even by ID. |

### US-SESS-02 — Find a session by a meaningful name

**As Camille Moreau, I want each session to get a name describing it, so that I recognize it in the list.**

| Acceptance criterion | Expected result |
| --- | --- |
| Automatic title | After the first reply of an untitled session, the model writes a 3–6 word title from the first exchange. |
| Manual name wins | `/session rename <name>` (or a dialog without a name) sets the name, and the automatic title never overwrites it. |
| Failure | If the title request fails, the turn still succeeds and the session stays untitled. |
| Opt-out | `--disable title`, or `/settings` → **Features**, turns automatic titles off. |

### US-SESS-03 — Clean up sessions

**As Malik Benali, the reviewer keeping the shared machine tidy, I want empty sessions not to pile up and old ones to be deletable, so that the list stays readable.**

| Acceptance criterion | Expected result |
| --- | --- |
| No empty sessions | Launching Sensai and quitting without chatting leaves no session in the database. |
| Confirmation | `/session delete [name or id]` asks for confirmation before deleting. |
| Cascade | Deleting a session deletes its messages, attached documents and their chunks. |
| Current session | Deleting the current session moves to a new, empty one. |

## How it works

| Command | Effect |
| --- | --- |
| `/session` | Opens the picker: **+ New session**, then the saved sessions. |
| `/session list` | Shows a table of the sessions: ID, name, messages, last use, and which one is current. |
| `/session new` | Starts a new session. |
| `/session switch <name or id>` | Opens a session by name (Tab completes) or ID. |
| `/session rename [name]` | Renames the current session; without a name, asks for it. |
| `/session delete [name or id]` | Deletes a session, the current one by default, after confirmation. |

At startup, and after `/session new`, the session only exists in memory. It is
saved when the first message is sent, or right away when files are attached
with `--files`, or when it is renamed. `/stats` shows `not saved yet` until then.

The conversation history sent to the model is rebuilt from the database on every
turn, so switching sessions only changes which session is read: its messages,
running [summary](Session-compression.md) and [documents](RAG.md) come with it.
The **Last prompt** statistic is reset on a switch, as it belongs to the previous
session.

The title is requested once, after the first reply, with the session's model and
without streaming. The reply is trimmed to its first line, unquoted and capped at
60 characters. It is only stored if the session is still untitled at that point.

## Architecture choices and tradeoffs

Saving a session at its first message keeps the list free of empty sessions, at
the cost of an unsaved state that every component reading the session ID must
handle. A title from the model reads better than the first words of the prompt,
but costs one extra request per session. Names are not unique: requiring unique
names would make automatic titles collide, so ambiguity is resolved with the
picker instead.

## Limitations

The recap shows stored messages only; tool traces are not replayed. Titles depend
on the model and can be vague or in an unexpected language. Sessions are listed
per profile only; there is no search through their content. A deleted session
cannot be restored.

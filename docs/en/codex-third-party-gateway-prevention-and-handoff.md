# Prevention and pre-failure handoff for third-party Codex gateways

> The original case used a DeepSeek-compatible route, but this workflow is
> about Codex behind any third-party or self-hosted gateway. Real limits differ
> by route and configuration and may change over time.

[中文版](../zh-CN/DeepSeek-Codex-防炸与炸前HANDOFF指南.md)

## Why handoff matters more than after-the-fact repair

HTTP 413 is commonly returned by a proxy before a model handles the request. If
each retry still carries the same oversized history, the affected session may
no longer be able to summarize itself for you. Continuity then depends on
whether important state already exists in project files outside the chat.

Use this order of operations:

1. watch the local session's growth trend;
2. write a handoff at stage boundaries;
3. reduce screenshots or start a new session as risk rises; and
4. treat the repair script as a last resort.

## Workflows that tend to grow faster

- repeated browser or computer-use screenshots;
- multiple captures of an unchanged view;
- image generation, masking, or visual review;
- tools that return inline base64 instead of a workspace path; and
- long-running visual work kept in one session.

Do not turn “40 screenshots” or “100 screenshots” into a universal rule.
Dimensions, encoding, duplication, client history behavior, and gateway
configuration all affect size.

## Run the local health check

```bash
python3 scripts/session_health.py --list
python3 scripts/session_health.py --list --deep
python3 scripts/session_health.py --session <session-id>
```

Fast mode checks local file size. `--deep` parses JSONL and counts recognized
image structures.

The default 20 MB and 35 MB values are reminder bands, not service specs:

- `low`: continue, but still hand off after a stage;
- `warning`: write the handoff now and reduce visual payloads;
- `high`: prioritize a new session or a controlled slim copy rather than adding
  more images.

Tune the reminders when you have direct evidence for your own route:

```bash
python3 scripts/session_health.py --list --warn-mb 25 --critical-mb 40
```

The script cannot guarantee which rollout is the chat currently shown in the
UI. Confirm with session ID, timestamp, and your own context; do not let an
agent guess and mutate a file.

## What a useful handoff contains

```markdown
# HANDOFF

## 1. Current goal
Define completion in one sentence.

## 2. Verified facts and evidence
Include only checked conclusions with repository-relative paths or test names.

## 3. Changed files
List relative paths and the purpose of each change.

## 4. Unfinished work and blockers
Order by priority and identify choices that require the user.

## 5. Exact next actions
Make the first action immediately executable by a new session.

## 6. Context and pitfalls
Record failed approaches and constraints that must remain intact.

## 7. Artifact locations
Use project-relative paths; do not paste images or full logs.
```

Print the built-in prompt with:

```bash
python3 scripts/session_health.py --handoff-prompt en
```

A handoff must not contain API keys, tokens, real session UUIDs, personal home
paths, full logs, base64, or private images. It is a working summary, not a copy
of the whole conversation.

## Start the next session safely

Use an opening message like:

```text
Read .codex-handoff/HANDOFF.md. Restate the goal, completed work, and first
next action. Identify anything that still needs my confirmation before acting.
Do not recreate existing artifacts.
```

The new session should verify the workspace before acting. A handoff can be
stale or contain an earlier mistaken conclusion; actual files, test results,
and the user's latest instruction take precedence.

## What AGENTS.md can and cannot do

The [example rules](../../examples/AGENTS.md) can tell an agent to run a health
check and write a handoff after a stage or screenshot-heavy work. They establish
discipline, but they are not a daemon:

- they do not run hourly simply because the file exists;
- they do not reveal the real HTTP request size;
- they do not guarantee an exact active-chat-to-rollout mapping; and
- without current script output, they cannot claim “70% of the limit.”

If periodic checks are needed, the user must explicitly configure an operating
system scheduler or Codex Automation. Notify only when risk changes, a check
fails, or user action is required; stay quiet while state is unchanged.

## Six ways to slow growth

1. Save visual output into the workspace and return a path plus the necessary
   summary when possible.
2. State what needs inspection before capturing, avoiding blind screenshot
   loops.
3. Separate visual exploration from code implementation sessions.
4. Update the handoff at every stage boundary, not only after a warning.
5. Do not repeatedly inline old screenshots in new messages.
6. Once warning is reached, a new session is usually safer than gambling on
   another image-heavy turn.

## If 413 has already started

Do not ask the affected session to “summarize one more time.” Read the
[full recovery article](codex-413-session-recovery-guide.md), confirm the error
with read-only checks, then create a backed-up new-ID copy and perform layered
validation.

For the compact handoff procedure, see [Warning and handoff](HANDOFF.md).

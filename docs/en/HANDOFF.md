# Warning and handoff guide

`session_health.py` inspects local rollout files, not captured network
requests. The on-disk size is only a trend signal: Codex may reshape, trim,
compress, or add data, and providers can change limits.

The default reminder bands are low below 20 MB, warning from 20 MB, and high
from 35 MB. They are conservative margins derived from one incident near
50 MB, not a published platform specification. Tune them with `--warn-mb` and
`--critical-mb`.

Write a handoff at stage boundaries, before ending work, after screenshot-heavy
activity, or whenever the script reports warning/high:

```bash
python3 scripts/session_health.py --handoff-prompt en
```

The handoff should cover the current goal, verified facts, changed files,
unfinished work, exact next actions, pitfalls, and artifact locations. Do not
copy keys, tokens, absolute personal paths, full logs, UUIDs, personal images,
or base64 data.

Start the next session with:

```text
Read .codex-handoff/HANDOFF.md. Restate the goal, completed work, and first
next action. Identify anything that still needs my confirmation before acting.
Do not recreate existing artifacts.
```

An `AGENTS.md` rule is behavioral guidance, not a background monitor. It cannot
guarantee an exact active-chat-to-rollout mapping or claim a precise percentage
without running the script. Configure a scheduler or Codex Automation
explicitly if periodic checks are desired, and notify only on actionable
changes.

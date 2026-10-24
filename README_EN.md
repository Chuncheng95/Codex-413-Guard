# Codex + DeepSeek API HTTP 413 Recovery

English | [简体中文](README.md)

An experimental community toolkit to diagnose, prevent, and recover Codex
sessions stuck on `HTTP 413 Payload Too Large` when using the **DeepSeek API**,
MCP images, other OpenAI-compatible endpoints, or self-hosted gateways. A long
session containing many screenshots or embedded base64 images can eventually
exceed a gateway's request-body limit.

This project can inspect local rollout size and embedded-image usage, provide a
pre-failure handoff workflow, and create a smaller copy of a stuck rollout
without changing the source file.

> **Important:** This is not an official OpenAI tool or a universal 413 fix. A
> rollout's on-disk size is not the final HTTP request size, and the scripts
> cannot discover a provider's current request limit. The default 20 MB and
> 35 MB thresholds are conservative reminders, not measured service limits.

## When it may help

It is a plausible match when all of the following are true:

1. One Codex session repeatedly returns `413 Payload Too Large` or
   `413 Request Entity Too Large`.
2. A new session can still reach the same service.
3. The affected session used many screenshots, browser, or image tools.
4. The response comes from a third-party proxy, reverse proxy, or compatible
   API with a request-body limit.

It may not help with authentication, networking, rate limiting, context-window
limits, or provider outages.

## Quick start

Python 3.8+ is required. Only the recovery script needs Pillow.

```bash
git clone https://github.com/Chuncheng95/Codex-DeepSeek-HTTP-413-Recovery.git
cd Codex-DeepSeek-HTTP-413-Recovery
python3 -m pip install -r requirements.txt
```

Inspect sessions:

```bash
python3 scripts/session_health.py --list --deep
python3 scripts/session_health.py --session <session-id>
```

Tune the local reminder thresholds if you know your gateway's behavior:

```bash
python3 scripts/session_health.py --list --warn-mb 25 --critical-mb 40
```

Print the handoff prompt:

```bash
python3 scripts/session_health.py --handoff-prompt en
```

Create a repaired copy without installing it:

```bash
python3 scripts/heal_codex_413.py --session <session-id> --show-paths
```

After reviewing the result, optionally place a newly generated copy in the
usual sessions directory:

```bash
python3 scripts/heal_codex_413.py --session <session-id> --install --show-paths
codex resume <new-session-id>
```

`--install` only places the file in a location used by the tested Codex
version. Internal storage can change, so registration and resume must be
verified manually. See the [recovery guide](docs/en/RECOVERY.md) and
[handoff guide](docs/en/HANDOFF.md).

The two original articles were also rewritten as complete, publication-ready
guides rather than literal translations:

- [Diagnosing and recovering a Codex session after HTTP 413](docs/en/codex-413-session-recovery-guide.md)
- [Prevention and pre-failure handoff for third-party gateways](docs/en/codex-third-party-gateway-prevention-and-handoff.md)

Their revised Chinese counterparts are
[the recovery article](docs/zh-CN/Codex-413-会话卡死修复指南.md) and
[the prevention/HANDOFF article](docs/zh-CN/DeepSeek-Codex-防炸与炸前HANDOFF指南.md).

## What the repair script verifies

Before keeping output, it checks that:

- every JSONL record parses as a JSON object;
- a `session_meta` record exists, even if it is not the first line;
- the output record count equals the source record count;
- the new session ID appears in metadata;
- converted data URLs and recognized MIME fields say `image/jpeg`;
- the source is copied to a checksum-verified backup and never edited.

This is **structural validation**, not proof that a specific Codex version can
resume the copy. A successful manual `codex resume` and a short no-tool reply
are still required for functional verification.

## Prior observation versus new validation

The source documents report a previous real-world observation on Codex CLI /
Desktop `0.162.x` through a third-party OpenAI-compatible endpoint:

- an approximately 55.6 MB rollout copy became approximately 7.6 MB;
- 47 converted image payloads went from about 39.4 MB to 3.4 MB;
- all 438 JSONL records were retained;
- one `codex exec resume` probe returned normally with the new ID.

Those results were preserved from the author's earlier test; they were not
rerun while packaging this repository. The earlier notes also observed that a
48 MB probe reached authentication while 52 MB and larger probes returned 413
for one endpoint at one time. That is not evidence of a universal “roughly
50 MB DeepSeek limit.” Limits can vary by route, account, proxy, encoding,
configuration, and date.

Newly executed tests in this repository are offline tests with synthetic data:
MIME correction, metadata not on line one, invalid JSONL rejection, record
count preservation, unchanged source hash, 413 pattern detection, and default
path redaction. No real session, API key, or online service was used.

## Privacy and safety

Rollouts, backups, and handoffs can contain prompts, tool output, local paths,
session UUIDs, page content, and personal images.

- Never commit a real `.jsonl` rollout.
- Never publish `~/.codex/config.toml`, keys, tokens, or full logs.
- Keep backup directories local; `.gitignore` excludes the common outputs.
- Review all command output before sharing it.
- Use the [publication checklist](PUBLICATION_CHECKLIST.md) before pushing.

See [SECURITY.md](SECURITY.md). Do not attach a real session file to a public
issue.

## AGENTS.md example

[examples/AGENTS.md](examples/AGENTS.md) provides reusable behavioral rules.
An AGENTS file does not install a background watcher and cannot guarantee that
an agent can map the active chat to its exact rollout. Any scheduled check must
be configured explicitly by the user.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests use temporary synthetic images and JSONL only.

## Compatibility and disclaimer

- The prior live test covered only Codex CLI / Desktop `0.162.x`.
- Codex rollout storage is internal and can change without notice.
- Only known data URL and common raw-base64 image shapes are recognized.
- JPEG is lossy; transparency is flattened onto white, and animated images
  retain only the frame opened by Pillow.
- Back up important data independently before use.
- This project is not affiliated with OpenAI, DeepSeek, or any gateway vendor.

## License

[MIT](LICENSE)

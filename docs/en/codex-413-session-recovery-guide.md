# Diagnosing and recovering a Codex session after HTTP 413

> This guide addresses one specific failure mode: a Codex session containing
> many embedded images repeatedly receives `HTTP 413 Payload Too Large` through
> a third-party OpenAI-compatible endpoint or self-hosted gateway. The method
> comes from one Codex CLI/Desktop `0.162.x` incident, not an official guarantee
> for current Codex versions or providers.

[中文版](../zh-CN/Codex-413-会话卡死修复指南.md)

## Confirm that the symptoms match

The pattern is a plausible match when:

- the error explicitly says `413 Payload Too Large` or
  `413 Request Entity Too Large`;
- a new session still works with the same configuration;
- the affected session used many screenshots, browser, computer-use, or image
  tools; and
- retrying that session fails again immediately.

A frozen interface by itself is not a diagnosis. Authentication errors,
network failures, rate limits, context limits, and service outages can feel
similar.

## Why embedded images are worth checking first

In the observed rollout shape, some images are stored in local JSONL as base64
or `data:image/...;base64,...`. Base64 also adds encoding overhead. If a later
client request replays those images and an intermediate gateway enforces a
request-body limit, the proxy can reject the request before the model sees it.

Keep three measurements separate:

1. the local rollout file size;
2. the actual HTTP request body sent by the client; and
3. the model's context limit, often measured in tokens or provider-specific
   units.

They may correlate, but they are not interchangeable. This project therefore
does not present a local file size as a fixed provider limit.

## Step 1: read-only diagnosis

```bash
python3 scripts/heal_codex_413.py --list
python3 scripts/session_health.py --list --deep
python3 scripts/session_health.py --session <session-id>
```

The first command requires an explicit 413 status or oversized-request message
inside a task-complete error. The second sorts local files and counts recognized
image shapes. The third inspects one session.

Local paths are hidden by default. Add `--show-paths` only when you need to
locate a file, and still review provider names, timestamps, and metadata before
sharing output.

## Step 2: create an uninstalled copy

Install the dependency:

```bash
python3 -m pip install -r requirements.txt
```

Create the copy:

```bash
python3 scripts/heal_codex_413.py --session <session-id> --show-paths
```

The recovery script performs these operations in order:

1. strictly parses the complete JSONL and does not assume metadata is line one;
2. aborts on blank/invalid records, missing metadata, or an unrecognized ID;
3. copies the source into a backup and verifies SHA-256;
4. creates a different UUID instead of reusing the stuck session ID;
5. recognizes common image data URLs and raw-base64 image objects;
6. defaults to a 1280 px longest edge and JPEG quality 72;
7. updates the corresponding MIME declaration to `image/jpeg`;
8. writes a temporary file beside the destination and renames it atomically
   only after validation; and
9. rechecks record count, new ID, image MIME consistency, and the source hash.

No JSONL records are deleted. JPEG is lossy, however: fine detail is reduced,
transparency is flattened to white, and full animation is not preserved.

## Step 3: interpret validation correctly

Look for at least:

- `structural_validation: passed`;
- `image_mime_validation: passed`;
- `source_unchanged: True`;
- a record count equal to the source;
- a plausible `images_converted` value; and
- output meaningfully smaller than the source.

Do not ignore `images_skipped`. It can indicate damaged data, an unsupported
shape, or an image Pillow could not decode. Zero conversions does not prove
that no problem exists; it only means no supported image shape was found.

## Step 4: install and functionally verify

After reviewing the uninstalled result:

```bash
python3 scripts/heal_codex_413.py --session <session-id> --install --show-paths
codex resume <new-session-id>
```

Make the first message short and forbid tool use:

```text
This is a recovery check. Do not call tools. Reply only: recovery check passed.
```

These conclusions are different:

- script checks pass: **structural validation passed**;
- Codex can find the new ID: **the copy is discoverable**;
- the model replies without another 413: **this recovery passed a functional
  check**.

Do not report either of the first two as the third.

## Why the guide avoids manual database edits

Indexes, backfill, and reconciliation between local state tables and rollouts
are internal implementation details. A copy being discovered in one old
version does not guarantee the same behavior in a new one. Editing a state
database or overwriting the original rollout increases the blast radius and
makes rollback harder.

This project therefore uses a read-only source, checksum backup, new-ID copy,
validation, and manual resume check. If a version cannot discover the copy,
retain the files and report only redacted version/schema details. Do not guess
at database changes.

## How to cite the prior case study

The source notes report that, in one Codex `0.162.x` incident, an approximately
55.6 MB rollout copy became about 7.6 MB; 47 converted image payloads went from
about 39.4 MB to 3.4 MB; all 438 records remained; and one later
`codex exec resume` probe returned normally.

It is fair to say “observed in one case.” It is not fair to claim that:

- every DeepSeek endpoint has a 50 MB limit;
- every 55 MB session fails;
- every Codex version auto-discovers copied rollouts; or
- this script fixes every HTTP 413.

## After recovery

1. Resend the intended request from the rejected turn; the model may never have
   received it.
2. Immediately write `.codex-handoff/HANDOFF.md`.
3. Split visual work into shorter stages and avoid repeated screenshots.
4. Keep the original and backup until the new session and project files are
   confirmed intact.

For the compact procedure, see [Recovery and verification](RECOVERY.md).

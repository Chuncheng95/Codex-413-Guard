# Recovery and verification guide

First confirm that the error contains `413` and `Payload Too Large` or
`Request Entity Too Large`. If a new session also fails, investigate auth,
networking, gateway status, and model configuration before touching history.

List recognized failures:

```bash
python3 scripts/heal_codex_413.py --list
```

Create an uninstalled copy first:

```bash
python3 scripts/heal_codex_413.py --session <session-id> --show-paths
```

The default backup directory is `./codex-413-backup/`; repaired output goes to
`./codex-413-healed/`. The script aborts on invalid/blank JSONL records, missing
metadata, unrecognized IDs, checksum mismatch, or failed output validation. It
removes temporary output and never edits the source.

Check for `structural_validation: passed`, unchanged record count, a reasonable
converted-image count, smaller output, and zero (or explainable) skipped
images. Zero conversions means the image shape was unsupported or embedded
images were not the cause; it is not evidence of a repair.

After review, create and install a fresh copy:

```bash
python3 scripts/heal_codex_413.py --session <session-id> --install --show-paths
codex resume <new-session-id>
```

Send a short message that forbids tool calls. Only a normal response without a
413 establishes functional recovery. Structural validation alone does not.

After recovery, resend the intended request from the failed turn, immediately
write a handoff, watch the new rollout's growth, and retain the source and
backup until project integrity is confirmed.

Known lossy changes: longest edge defaults to 1280 px, JPEG quality to 72,
transparency is flattened onto white, and animation is not preserved. Text,
tool calls, and JSONL records are retained, but visual detail can be lost.

The prior live recovery covered only Codex `0.162.x`. If a newer version does
not discover the copy, keep all files and do not edit the state database. Share
only redacted version and schema details in an issue, never the real rollout.

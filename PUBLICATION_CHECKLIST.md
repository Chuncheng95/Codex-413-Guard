# Public publication checklist

Use this immediately before making the repository public.

## Files and history

- [ ] `git status --short` contains only intended project files.
- [ ] No `.jsonl`, database, backup, checksum from a real session, image, or
      generated log is tracked.
- [ ] Search the complete Git history, not only the latest files. If a secret
      was ever committed, rotate it before publishing; deleting it in a later
      commit is not enough.

## Sensitive values

- [ ] No API key, bearer token, cookie, authorization header, or
      `~/.codex/config.toml` content.
- [ ] No real session UUID, account ID, email address, username, hostname, or
      private repository URL.
- [ ] No personal absolute paths such as `/Users/name/...` or
      `C:\\Users\\name\\...`.
- [ ] No raw provider response or log that could contain request content.
- [ ] No personal screenshot, document, or base64 payload.

## Claims and verification

- [ ] Prior user-reported tests remain labeled as prior observations.
- [ ] New tests are reported only if they were actually run.
- [ ] No universal provider limit is claimed.
- [ ] No claim of full automatic detection or guaranteed resume compatibility.
- [ ] The Codex version scope and internal-format disclaimer remain visible.

## GitHub presentation

- [ ] Repository name: `Codex-DeepSeek-HTTP-413-Recovery` (or the owner's chosen variant).
- [ ] Short description accurately says “experimental” or “community”.
- [ ] README Chinese/English links work.
- [ ] License choice is acceptable to the repository owner.
- [ ] Default branch and public/private visibility are explicitly confirmed by
      the owner before creation or visibility change.

Suggested GitHub description:

> Diagnose, prevent, and recover Codex sessions stuck on “HTTP 413 Payload Too
> Large” when using the DeepSeek API, MCP images, or other OpenAI-compatible
> gateways.

# Security policy

## Reporting a vulnerability

Do not attach a real Codex rollout, backup, database, config file, API key,
token, screenshot, or full log to a public issue.

For a reproducible report, create the smallest synthetic JSONL sample possible
and replace session IDs, provider names, paths, prompts, URLs, and tool output.
Describe the Codex version and operating system separately.

If a repository owner enables GitHub private vulnerability reporting, use it
for issues that could expose local session data. Otherwise contact the owner
through a private channel listed on their GitHub profile before disclosing
sensitive details.

## Local data handled by the scripts

The scripts may read Codex rollout files and create local backups. They do not
send data to a network service. Running `codex resume` afterward is a separate
Codex action and can send recovered history to the configured provider.

Command output hides local paths by default, but session IDs and provider names
may still be sensitive. Review all output before sharing it.

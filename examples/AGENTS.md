# Codex session-size discipline

These rules apply when the project uses a third-party or self-hosted model
gateway and the repository contains the Codex + DeepSeek API HTTP 413 Recovery scripts.

- At stage boundaries and after screenshot-heavy work, run
  `python3 scripts/session_health.py --list --deep` if the user has authorized
  local diagnostics.
- Treat rollout size as a heuristic, not the HTTP request size. Never claim a
  provider has a fixed limit or that the active session is at an exact
  percentage unless there is direct, current evidence.
- When the relevant session reaches the configured warning threshold, tell the
  user and write `.codex-handoff/HANDOFF.md` before taking more screenshots.
- The handoff must include: goal, verified facts and evidence, changed files,
  blockers, exact next actions, pitfalls, and artifact locations.
- Do not put secrets, tokens, complete session UUIDs, personal absolute paths,
  full logs, base64 data, or private images in the handoff.
- Prefer saving images as workspace files and returning paths when that still
  satisfies the task. Avoid repeated screenshots of an unchanged view.
- Never edit or delete an original rollout. A recovery attempt must create a
  backup and a new-ID copy, validate it, and require a manual resume check.
- An AGENTS file is not a background watcher. Do not say monitoring is active
  unless the user has separately configured and verified a scheduler.

## 中文说明

- 阶段结束或截图密集后，在用户允许本地诊断时运行体检脚本。
- rollout 大小只是风险信号，不等于 HTTP 请求体；没有当前证据时不要宣称固定上限或
  精确百分比。
- 到达用户配置的提醒线后，先写 `.codex-handoff/HANDOFF.md`，再继续截图任务。
- HANDOFF 不得包含密钥、完整会话 UUID、个人绝对路径、完整日志、base64 或私人图片。
- 永远不修改或删除原 rollout；恢复必须使用备份、新 ID 副本、结构验证和人工 resume
  验证。
- `AGENTS.md` 不是后台监控器。除非用户另外配置并验证了调度器，否则不得声称自动监控
  已启用。

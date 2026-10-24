# Codex 413 Guard

[English](README_EN.md) | 简体中文

一个面向 Codex 本地会话的实验性预警、交接与恢复工具包。当使用第三方
OpenAI 兼容接口或自建网关时，包含大量内嵌图片的长会话可能因请求体过大而返回
`HTTP 413 Payload Too Large`。本项目帮助你：

- 查看本地 rollout 文件大小和内嵌图片占用；
- 在风险升高时先写 `HANDOFF.md`，换会话继续；
- 对已经卡住的会话创建一份图片压缩后的新副本；
- 保留原文件、备份和 SHA-256，便于回滚与核对。

> **重要：** 这不是 OpenAI 官方工具，也不是通用的 413 修复器。rollout 文件大小
> 不等于最终 HTTP 请求体大小；脚本无法自动获知服务商当前的真实限制。默认的
> 20 MB / 35 MB 只是保守提醒线，可以自行调整。

## 适用场景

以下情况同时出现时，本工具可能有帮助：

1. 某个 Codex 会话持续报 `413 Payload Too Large` 或
   `413 Request Entity Too Large`；
2. 新会话仍能正常请求同一服务；
3. 原会话使用过大量截图、浏览器或图片工具；
4. 错误来自第三方代理、自建反向代理或兼容接口的请求体限制。

如果是认证、网络、速率限制、上下文窗口或服务端故障，本项目可能不适用。

## 最简单的使用方法

需要 Python 3.8+。只有恢复脚本需要 Pillow。

```bash
git clone <你的仓库地址>
cd Codex-413-Guard
python3 -m pip install -r requirements.txt
```

### 1. 先体检

```bash
python3 scripts/session_health.py --list --deep
```

查看单个会话：

```bash
python3 scripts/session_health.py --session <会话ID>
```

如已知自己的网关限制，可调整提醒线：

```bash
python3 scripts/session_health.py --list --warn-mb 25 --critical-mb 40
```

默认不显示本地文件路径和工作目录；确实需要时再加 `--show-paths`。

### 2. 在出问题前做 HANDOFF

```bash
python3 scripts/session_health.py --handoff-prompt zh
```

把输出的提示词发给当前会话，让它把当前状态写到
`.codex-handoff/HANDOFF.md`。详细做法见
[预警与 HANDOFF 指南](docs/zh-CN/HANDOFF.md)。

### 3. 为卡住的会话生成瘦身副本

先只生成副本，不安装：

```bash
python3 scripts/heal_codex_413.py --session <会话ID> --show-paths
```

脚本会：

- 完整解析源 JSONL，遇到坏行立即中止；
- 备份源文件并写入 SHA-256；
- 生成新会话 ID；
- 把识别到的内嵌图片缩放并转成 JPEG；
- 同时把相应 MIME 更新为 `image/jpeg`；
- 原子写入新文件，再验证 JSONL、记录数和新 ID；
- 不修改或删除原会话。

确认输出合理后，再选择安装副本：

```bash
python3 scripts/heal_codex_413.py --session <会话ID> --install --show-paths
```

然后按脚本显示的新 ID 尝试：

```bash
codex resume <新会话ID>
```

`--install` 只是把副本放进当前版本常用的 sessions 目录。Codex 的内部存储格式会变化，
因此必须手动确认侧边栏是否出现、`resume` 是否成功。完整步骤见
[恢复与验证指南](docs/zh-CN/RECOVERY.md)。

两份原始说明经过逐段校订后，也保留为适合完整阅读和分享的长版：

- [Codex 413 会话卡死：诊断、修复与验证](docs/zh-CN/Codex-413-会话卡死修复指南.md)
- [第三方网关下的预警与炸前 HANDOFF](docs/zh-CN/DeepSeek-Codex-防炸与炸前HANDOFF指南.md)

对应英文版：

- [Diagnosing and recovering a Codex session after HTTP 413](docs/en/codex-413-session-recovery-guide.md)
- [Prevention and pre-failure handoff for third-party gateways](docs/en/codex-third-party-gateway-prevention-and-handoff.md)

## 恢复验证分三层

1. **结构验证（脚本自动完成）**：每行是合法 JSON、记录数不变、存在
   `session_meta`、新会话 ID 已写入。
2. **本地结果检查（用户完成）**：输出明显变小、图片转换数量合理、原文件 SHA-256
   未变化。
3. **功能验证（用户完成）**：用当前 Codex 版本打开或 resume 新副本，发送一条不调用
   工具的短消息，确认不再出现 413。

只有第 3 层成功，才能说本次会话已经恢复。本仓库不会把“结构验证通过”冒充成
“Codex 已恢复”。

## 已有实测与本仓库新验证

以下是原作者文档中保留的既有实测，不是本次仓库整理时重新进行的在线测试：

- 环境：Codex CLI / Desktop `0.162.x`，第三方 OpenAI 兼容接口；
- 一个约 55.6 MB 的 rollout 副本压缩到约 7.6 MB；
- 其中 47 个被转换的图片负载从约 39.4 MB 降到约 3.4 MB；
- 438 条 JSONL 记录未删除；
- 当时用新 ID 进行了一次 `codex exec resume`，获得正常回复。

原文还记录了一次针对当时网关的探测：48 MB 请求被网关接收后进入认证阶段，
52 MB 起返回 413。这只能说明**那个时间、那个入口、那套配置**的观察结果，不能推出
DeepSeek、OpenAI 或其他网关普遍存在固定的“约 50 MB 上限”。

本仓库新增并实际执行的是合成数据离线测试：MIME 更新、非首行元信息、JSONL
坏行拒绝、记录数保持、源文件哈希不变、413 错误识别和默认路径脱敏。没有使用真实
会话、API 密钥或在线服务做新验证。

## 安全与隐私

rollout、备份和 HANDOFF 都可能包含：提示词、工具输出、本机路径、会话 UUID、
网页内容、图片和其他敏感信息。

- **不要把任何真实 `.jsonl` 提交到 GitHub。**
- 不要提交 `~/.codex/config.toml`、API 密钥、令牌或完整错误日志。
- 备份目录应只留在本机；本仓库的 `.gitignore` 已默认忽略它们。
- 分享命令输出前仍需人工检查，因为 provider 名称等元数据也可能敏感。
- 发布前按 [公开发布检查表](PUBLICATION_CHECKLIST.md) 再检查一次。

发现安全问题请先阅读 [SECURITY.md](SECURITY.md)，不要附带真实会话文件公开提 Issue。

## 仓库内容

```text
scripts/                 体检与恢复脚本
tests/                   合成数据离线测试
examples/AGENTS.md       可复制的会话纪律示例
docs/zh-CN/              中文长版与简明指南
docs/en/                 英文长版与简明指南
PUBLICATION_CHECKLIST.md 首次公开发布前的检查表
SECURITY.md              隐私与安全报告说明
```

## AGENTS.md 示例

[examples/AGENTS.md](examples/AGENTS.md) 提供了可复制的会话体积纪律。它只能约束
Agent 的行为，**不会自动安装后台监控，也不能保证 Agent 精确识别“当前会话”对应的
rollout 文件**。若需要定时检查，请由用户显式配置自己的调度器或 Codex Automation。

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

测试只生成临时合成图片和 JSONL，不读取真实 Codex 会话。

## 兼容性与免责声明

- 原作者实测版本仅为 Codex CLI / Desktop `0.162.x`；其他版本未经证明。
- Codex rollout 是内部格式，未来版本可能移动目录、修改字段或停止自动登记副本。
- 脚本仅识别已知的 data URL 和常见原始 base64 图片结构，无法保证覆盖所有 MCP
  或未来格式。
- JPEG 是有损格式，透明背景会合成到白色，动图只保留 PIL 打开的首帧。
- 本工具按“复制、备份、验证”的思路降低风险，但使用前仍应自行备份重要数据。
- 本项目与 OpenAI、DeepSeek 或任何网关服务商均无隶属关系。

## 许可证

[MIT](LICENSE)

# 恢复与验证指南

## 0. 先排除不适用情况

确认错误文字包含 `413` 和 `Payload Too Large` / `Request Entity Too Large`。如果新会话
也失败，先排查认证、网络、网关状态和模型配置，不要直接改本地历史。

## 1. 列出识别到的 413 会话

```bash
python3 scripts/heal_codex_413.py --list
```

识别规则要求 task-complete 错误里存在 413 状态码或明确的 413 大请求错误文字，避免把
普通文本中的数字 `413` 当成故障。

## 2. 先生成未安装副本

```bash
python3 scripts/heal_codex_413.py --session <会话ID> --show-paths
```

默认结果写入：

- `./codex-413-backup/`：原始文件备份和 `SHA256SUMS.txt`；
- `./codex-413-healed/`：新 ID 的瘦身副本。

脚本严格读取 UTF-8 JSONL。遇到坏行、空行、缺少 `session_meta`、无可识别 UUID、
备份哈希不一致或输出验证失败时，中止并删除临时输出。源文件不会被修改。

## 3. 检查结果

至少检查这些字段：

- `structural_validation: passed`；
- `records` 与原文件记录数一致；
- `images_converted` 大于 0（如果预期有内嵌图）；
- `output_mb` 小于 `source_mb`；
- `images_skipped` 为 0，或能解释被跳过的内容。

如果没有图片被转换，说明当前 rollout 的图片结构不在脚本支持范围内，或者 413 并非
由可识别的内嵌图片造成。不要据此声称已修复。

## 4. 安装并功能验证

确认后运行：

```bash
python3 scripts/heal_codex_413.py --session <会话ID> --install --show-paths
codex resume <新会话ID>
```

在恢复的会话里先发送一条短消息：

```text
这是恢复验证。请不要调用工具，只回复：恢复测试成功。
```

只有真正获得回复且不再出现 413，才算功能验证成功。脚本无法替你证明这一点。

## 5. 恢复后怎么做

1. 把最后一次失败前真正想发送的请求重新发一遍；失败轮不一定被模型受理。
2. 立刻写 `.codex-handoff/HANDOFF.md`。
3. 继续观察副本大小，不要让它再次无限增长。
4. 原会话和备份先保留，确认项目完整后再自行决定归档。

## 已知有损变化

- 图片最长边默认限制为 1280 px；
- JPEG 默认质量 72；
- 透明区域合成到白色；
- 动图不会保留完整动画；
- 文字、工具调用和 JSONL 记录不删除，但图片视觉细节可能损失。

可用 `--max-dim` 和 `--quality` 调整。质量越高，恢复后的请求仍可能过大。

## Codex 版本差异

原作者只在 `0.162.x` 做过一次真实恢复。其他版本可能不扫描新 rollout、需要不同目录，
或使用完全不同的持久化格式。如果结构验证通过但 `resume` 找不到新 ID，请保留所有文件，
不要编辑数据库，先在 Issue 中提供**脱敏后的版本号和字段结构**，不要上传真实会话。

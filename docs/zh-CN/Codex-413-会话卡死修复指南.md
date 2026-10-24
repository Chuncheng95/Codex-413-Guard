# Codex 会话遇到 HTTP 413：诊断、修复与验证

> 本文针对一种特定故障：Codex 使用第三方 OpenAI 兼容接口或自建网关时，某个包含
> 大量内嵌图片的会话持续返回 `HTTP 413 Payload Too Large`。方法基于一次
> Codex CLI / Desktop `0.162.x` 个案，不代表当前所有版本或服务商的官方行为。

[English version](../en/codex-413-session-recovery-guide.md)

## 先判断是不是同一种问题

典型信号是：

- 错误明确包含 `413 Payload Too Large` 或 `413 Request Entity Too Large`；
- 同一配置下，新会话可以正常请求；
- 出问题的会话用过很多截图、浏览器、computer-use 或图片工具；
- 之后重试同一会话仍立即失败。

只有“界面卡住”还不能确诊。认证失败、网络故障、速率限制、模型上下文限制和服务中断
都可能产生类似体验。

## 为什么图片值得优先排查

在已观察到的 rollout 格式里，部分图片以 base64 或 `data:image/...;base64,...`
形式保存在本地 JSONL 历史中。base64 本身还会带来体积膨胀。若客户端后续请求重放了
这些图像，而中间网关配置了请求体上限，就可能在模型真正收到请求前被代理层拒绝。

不过需要区分三件事：

1. rollout 文件大小是本地持久化体积；
2. HTTP 请求体是客户端实际发送的网络数据；
3. 模型上下文限制通常按 token 或服务端规则计算。

三者相关但不相等。因此本文不把某个本地文件大小称为服务商的固定上限。

## 第一步：只读诊断

```bash
python3 scripts/heal_codex_413.py --list
python3 scripts/session_health.py --list --deep
python3 scripts/session_health.py --session <会话ID>
```

第一个命令只列出 task-complete 记录里含明确 413 状态或大请求错误文字的会话；第二个
命令按本地体积排序并统计可识别图片；第三个命令查看单个会话。

默认不显示本机路径。如果要定位文件，再显式添加 `--show-paths`。发布截图或日志前仍需
人工检查 provider 名称、时间戳和其他元数据。

## 第二步：先生成未安装副本

安装依赖：

```bash
python3 -m pip install -r requirements.txt
```

生成副本：

```bash
python3 scripts/heal_codex_413.py --session <会话ID> --show-paths
```

脚本的安全顺序是：

1. 严格读取完整 JSONL，不假设 `session_meta` 一定在第一行；
2. 遇到空行、坏 JSON、缺少元信息或无法识别的 ID 就中止；
3. 复制源文件到备份目录并核对 SHA-256；
4. 生成不同的新 UUID，不复用原会话 ID；
5. 识别常见 data URL 和原始 base64 图片结构；
6. 默认缩到最长边 1280 px、转为 JPEG q72；
7. 把相应 MIME 同步改为 `image/jpeg`；
8. 在同一输出目录写临时文件，验证后再原子改名；
9. 再次核对记录数、新 ID、图片 MIME 与源文件哈希。

脚本不删除任何 JSONL 记录，但 JPEG 是有损的：细节会减少，透明区域会变白，动图不会
保留完整动画。

## 第三步：看懂验证结果

理想输出至少包括：

- `structural_validation: passed`；
- `image_mime_validation: passed`；
- `source_unchanged: True`；
- `records` 与源文件一致；
- `images_converted` 与预期相近；
- `output_mb` 明显小于 `source_mb`。

`images_skipped` 不为零时不要忽略。它可能代表损坏数据、未知格式或 Pillow 无法解码的
图片。零张转换也不等于“没有问题”，只说明脚本没有找到它支持的图片结构。

## 第四步：安装副本并做功能验证

确认未安装副本合理后，再运行：

```bash
python3 scripts/heal_codex_413.py --session <会话ID> --install --show-paths
codex resume <新会话ID>
```

恢复后的第一条消息保持很短，并禁止工具调用：

```text
这是一次恢复验证。请不要调用任何工具，只回复：恢复测试成功。
```

这里有三种不同结论：

- 脚本检查通过：只能叫“结构验证通过”；
- Codex 能找到新 ID：只能叫“副本已登记或可发现”；
- 模型正常回复且不再 413：才叫“本次功能恢复成功”。

不要把前两种写成第三种。

## 为什么不建议手改数据库或原 rollout

Codex 的本地状态表和 rollout 之间的索引、回填与版本行为属于内部实现。在一个旧版本上
观察到“复制文件后可发现”，不能保证新版本仍然如此。直接改状态数据库或覆盖原 JSONL
会扩大损坏范围，也让回滚变困难。

因此本项目只做：原文件只读、备份、新 ID 副本、验证、人工 resume。若当前版本无法
发现副本，保留文件并报告脱敏后的版本和字段结构，不要试着用未经验证的 SQL 硬改。

## 个案数据如何正确引用

原作者文档记录：在 Codex `0.162.x` 的一次真实处理里，一个约 55.6 MB 的 rollout
副本变为约 7.6 MB；47 个被转换的图片负载约从 39.4 MB 变为 3.4 MB；438 条记录保留；
随后一次 `codex exec resume` 获得正常回复。

这组数据可以写成“在一次个案中观察到”，但不能写成：

- 所有 DeepSeek 接口上限都是 50 MB；
- 所有 55 MB 会话都会失败；
- 所有 Codex 版本都会自动发现副本；
- 本脚本能修复所有 413。

## 恢复之后

1. 重发失败轮原本要发送的请求，因为网关拒绝时模型可能根本没有收到它。
2. 立即写 `.codex-handoff/HANDOFF.md`。
3. 把视觉任务拆成短阶段，减少重复截图。
4. 保留原会话和备份，直到确认新会话与项目文件都完整。

简明操作版见 [恢复与验证指南](RECOVERY.md)。

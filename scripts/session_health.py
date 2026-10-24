#!/usr/bin/env python3
"""Inspect local Codex rollout files for size and embedded-image risk.

This is a local heuristic. A rollout file is not the same thing as the final
HTTP request body, and this script cannot discover a provider's actual limit.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
from typing import Any, Dict, Iterable, List, Optional, Tuple


DATA_URL_RE = re.compile(
    r"^data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)$"
)
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

HANDOFF_PROMPT_ZH = """在继续之前，请做一次会话交接存档。把当前状态写进工作区文件
`.codex-handoff/HANDOFF.md`（目录不存在就创建）。内容包括：

# HANDOFF
## 1. 当前目标
## 2. 已确认事实与证据
## 3. 已改动文件
## 4. 未完成事项与卡点
## 5. 下一步可执行动作
## 6. 关键上下文与踩坑
## 7. 相关素材位置

避免复制密钥、令牌、个人路径、完整日志或图片内容。写完后只回复文件路径、最关键的
3 条待办和下一步从哪里开始。不要额外截图。"""

HANDOFF_PROMPT_EN = """Before continuing, write a handoff to
`.codex-handoff/HANDOFF.md` (create the directory if needed) with: current
goal; verified facts and evidence; changed files; blockers and unfinished
work; exact next actions; pitfalls; and relevant artifact locations.

Do not copy secrets, tokens, personal paths, full logs, or image contents.
When done, reply only with the file path, the three most important TODOs, and
the exact next step. Do not take extra screenshots."""


def default_codex_home() -> str:
    return os.environ.get("CODEX_HOME") or os.path.join(
        os.path.expanduser("~"), ".codex"
    )


def all_rollouts(codex_home: str) -> List[str]:
    patterns = [
        os.path.join(codex_home, "sessions", "**", "rollout-*.jsonl"),
        os.path.join(codex_home, "archived_sessions", "**", "rollout-*.jsonl"),
    ]
    found: List[str] = []
    for pattern in patterns:
        found.extend(glob.glob(pattern, recursive=True))
    return sorted(set(found))


def read_meta(path: str) -> Dict[str, Any]:
    """Find session metadata without assuming it is the first JSONL record."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    record = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                if record.get("type") == "session_meta":
                    payload = record.get("payload")
                    return payload if isinstance(payload, dict) else {}
    except OSError:
        pass
    return {}


def decoded_size(encoded: str) -> int:
    compact = "".join(encoded.split())
    if not compact:
        return 0
    padding = len(compact) - len(compact.rstrip("="))
    return max(0, (len(compact) * 3) // 4 - padding)


def image_items(node: Any) -> Iterable[Tuple[str, int]]:
    """Yield (MIME, decoded byte estimate) for recognized embedded images."""
    if isinstance(node, str):
        match = DATA_URL_RE.match(node)
        if match:
            yield match.group(1).lower(), decoded_size(match.group(2))
        return

    if isinstance(node, list):
        for item in node:
            yield from image_items(item)
        return

    if not isinstance(node, dict):
        return

    raw = node.get("data")
    type_name = str(node.get("type", "")).lower()
    mime = next(
        (
            node.get(key)
            for key in ("mime_type", "mimeType", "media_type", "mediaType")
            if isinstance(node.get(key), str)
        ),
        "",
    )
    looks_like_raw_image = (
        isinstance(raw, str)
        and (
            type_name in {"image", "input_image"}
            or str(mime).lower().startswith("image/")
        )
        and not raw.startswith("data:")
    )
    if looks_like_raw_image:
        yield str(mime or "image/unknown").lower(), decoded_size(raw)

    for key, value in node.items():
        if key == "data" and looks_like_raw_image:
            continue
        yield from image_items(value)


def deep_stats(path: str) -> Dict[str, Any]:
    records = 0
    invalid_records = 0
    images = 0
    image_bytes = 0
    mimes: Dict[str, int] = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            records += 1
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                invalid_records += 1
                continue
            for mime, size in image_items(record):
                images += 1
                image_bytes += size
                mimes[mime] = mimes.get(mime, 0) + 1
    return {
        "records": records,
        "invalid_records": invalid_records,
        "images": images,
        "image_mb": round(image_bytes / 1_000_000, 2),
        "image_mimes": mimes,
    }


def risk_level(size_mb: float, warn_mb: float, critical_mb: float) -> str:
    if size_mb >= critical_mb:
        return "high"
    if size_mb >= warn_mb:
        return "warning"
    return "low"


def session_id(meta: Dict[str, Any], path: str) -> str:
    for key in ("id", "session_id", "sessionId"):
        value = meta.get(key)
        if isinstance(value, str) and UUID_RE.match(value):
            return value
    match = re.search(r"([0-9a-fA-F-]{36})\.jsonl$", path)
    return match.group(1) if match and UUID_RE.match(match.group(1)) else "unknown"


def collect(
    codex_home: str,
    warn_mb: float,
    critical_mb: float,
    min_mb: float,
    deep: bool,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in all_rollouts(codex_home):
        try:
            size_mb = os.path.getsize(path) / 1_000_000
        except OSError:
            continue
        if size_mb < min_mb:
            continue
        meta = read_meta(path)
        row: Dict[str, Any] = {
            "id": session_id(meta, path),
            "provider": str(meta.get("model_provider", "unknown")),
            "timestamp": str(meta.get("timestamp", "unknown")),
            "size_mb": round(size_mb, 2),
            "risk": risk_level(size_mb, warn_mb, critical_mb),
            "_path": path,
            "_cwd": str(meta.get("cwd", "unknown")),
        }
        if deep:
            try:
                row.update(deep_stats(path))
            except (OSError, UnicodeDecodeError) as exc:
                row["scan_error"] = str(exc)
        rows.append(row)
    rows.sort(key=lambda item: item["size_mb"], reverse=True)
    return rows


def find_session(codex_home: str, spec: str) -> Optional[str]:
    if os.path.isfile(spec):
        return os.path.abspath(spec)
    matches = [
        path
        for path in all_rollouts(codex_home)
        if spec in os.path.basename(path)
    ]
    matches.sort(key=os.path.getmtime, reverse=True)
    return matches[0] if matches else None


def public_row(row: Dict[str, Any], show_paths: bool) -> Dict[str, Any]:
    result = {key: value for key, value in row.items() if not key.startswith("_")}
    if show_paths:
        result["path"] = row.get("_path")
        result["cwd"] = row.get("_cwd")
    return result


def print_table(rows: List[Dict[str, Any]], deep: bool) -> None:
    if deep:
        print(f"{'session ID':38} {'provider':12} {'size':>9} {'risk':9} {'images':>7} {'image MB':>9}")
    else:
        print(f"{'session ID':38} {'provider':12} {'size':>9} {'risk':9}")
    for row in rows:
        if deep:
            print(
                f"{row['id']:38} {row['provider'][:12]:12} "
                f"{row['size_mb']:8.1f}M {row['risk']:9} "
                f"{row.get('images', 0):7} {row.get('image_mb', 0):8.1f}M"
            )
        else:
            print(
                f"{row['id']:38} {row['provider'][:12]:12} "
                f"{row['size_mb']:8.1f}M {row['risk']:9}"
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect local Codex rollout size and embedded-image risk"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--list", action="store_true", help="list matching sessions")
    mode.add_argument("--session", help="session ID fragment or rollout path")
    mode.add_argument(
        "--handoff-prompt",
        choices=("zh", "en"),
        help="print a handoff prompt and exit",
    )
    parser.add_argument("--codex-home", default=default_codex_home())
    parser.add_argument("--warn-mb", type=float, default=20.0)
    parser.add_argument("--critical-mb", type=float, default=35.0)
    parser.add_argument("--min-mb", type=float, default=1.0)
    parser.add_argument("--top", type=int, default=25)
    parser.add_argument("--deep", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--show-paths",
        action="store_true",
        help="include local file and working-directory paths",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.handoff_prompt:
        print(HANDOFF_PROMPT_ZH if args.handoff_prompt == "zh" else HANDOFF_PROMPT_EN)
        return 0
    if args.warn_mb < 0 or args.critical_mb <= args.warn_mb:
        raise SystemExit("--critical-mb must be greater than --warn-mb >= 0")

    if args.session:
        path = find_session(args.codex_home, args.session)
        if not path:
            raise SystemExit(f"session not found: {args.session}")
        meta = read_meta(path)
        size_mb = os.path.getsize(path) / 1_000_000
        row: Dict[str, Any] = {
            "id": session_id(meta, path),
            "provider": str(meta.get("model_provider", "unknown")),
            "timestamp": str(meta.get("timestamp", "unknown")),
            "size_mb": round(size_mb, 2),
            "risk": risk_level(size_mb, args.warn_mb, args.critical_mb),
            "_path": path,
            "_cwd": str(meta.get("cwd", "unknown")),
        }
        row.update(deep_stats(path))
        result = public_row(row, args.show_paths)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            for key, value in result.items():
                print(f"{key:16}: {value}")
        return 0

    rows = collect(
        args.codex_home,
        args.warn_mb,
        args.critical_mb,
        args.min_mb,
        args.deep,
    )[: args.top]
    if args.json:
        print(
            json.dumps(
                [public_row(row, args.show_paths) for row in rows],
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print_table(rows, args.deep)
        print(
            "\nHeuristic only: rollout size is not the HTTP request size. "
            "Tune thresholds for your provider and environment."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())

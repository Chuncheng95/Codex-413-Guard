#!/usr/bin/env python3
"""Create a smaller copy of a Codex rollout by recompressing embedded images.

The source is never edited. Output is written atomically and structurally
validated before it is kept or installed. Codex rollout formats are internal
and may change, so successful validation does not guarantee that every Codex
version will register or resume the copy.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import glob
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
DATA_URL_RE = re.compile(
    r"^data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)$"
)
MIME_KEYS = ("mime_type", "mimeType", "media_type", "mediaType")
ERROR_413_RE = re.compile(
    r"(?:\b413\b.{0,120}(?:payload too large|request entity too large))|"
    r"(?:(?:payload too large|request entity too large).{0,120}\b413\b)",
    re.IGNORECASE,
)


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


def uuid7() -> str:
    milliseconds = int(time.time() * 1000)
    random_bytes = secrets.token_bytes(10)
    value = bytearray(16)
    value[0:6] = milliseconds.to_bytes(6, "big")
    value[6] = (0x7 << 4) | (random_bytes[0] & 0x0F)
    value[7] = random_bytes[1]
    value[8] = (0x2 << 6) | (random_bytes[2] & 0x3F)
    value[9:16] = random_bytes[3:10]
    text = value.hex()
    return "%s-%s-%s-%s-%s" % (
        text[0:8],
        text[8:12],
        text[12:16],
        text[16:20],
        text[20:32],
    )


def iter_records(path: str) -> Iterable[Tuple[int, Dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                raise ValueError(f"blank JSONL record at line {line_number}")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"invalid JSON at line {line_number}: {exc.msg}"
                ) from exc
            if not isinstance(record, dict):
                raise ValueError(f"JSONL record {line_number} is not an object")
            yield line_number, record


def validate_jsonl(path: str) -> Dict[str, Any]:
    count = 0
    meta: Optional[Dict[str, Any]] = None
    for _, record in iter_records(path):
        count += 1
        if record.get("type") == "session_meta" and meta is None:
            payload = record.get("payload")
            if isinstance(payload, dict):
                meta = payload
    if count == 0:
        raise ValueError("rollout is empty")
    if meta is None:
        raise ValueError("no session_meta record found")
    return {"records": count, "meta": meta}


def get_session_id(meta: Dict[str, Any]) -> str:
    for key in ("id", "session_id", "sessionId"):
        value = meta.get(key)
        if isinstance(value, str) and UUID_RE.match(value):
            return value.lower()
    raise ValueError("session_meta does not contain a recognized UUID session ID")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def replace_text(node: Any, old: str, new: str) -> Any:
    if isinstance(node, str):
        return node.replace(old, new)
    if isinstance(node, list):
        return [replace_text(item, old, new) for item in node]
    if isinstance(node, dict):
        return {key: replace_text(value, old, new) for key, value in node.items()}
    return node


@dataclass
class ShrinkStats:
    converted: int = 0
    skipped: int = 0
    before_bytes: int = 0
    after_bytes: int = 0


class ImageShrinker:
    def __init__(self, max_dim: int, quality: int):
        try:
            from PIL import Image, ImageOps
        except ImportError as exc:
            raise RuntimeError(
                "Pillow is required for repair: python3 -m pip install -r requirements.txt"
            ) from exc
        self.Image = Image
        self.ImageOps = ImageOps
        self.max_dim = max_dim
        self.quality = quality
        self.stats = ShrinkStats()

    def convert(self, encoded: str) -> Optional[str]:
        try:
            compact = "".join(encoded.split())
            raw = base64.b64decode(compact, validate=True)
            with self.Image.open(io.BytesIO(raw)) as source:
                source.load()
                image = self.ImageOps.exif_transpose(source)
                if image.mode in ("RGBA", "LA") or (
                    image.mode == "P" and "transparency" in image.info
                ):
                    rgba = image.convert("RGBA")
                    background = self.Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    image = background
                else:
                    image = image.convert("RGB")
                width, height = image.size
                scale = min(1.0, self.max_dim / max(width, height))
                if scale < 1.0:
                    image = image.resize(
                        (
                            max(1, round(width * scale)),
                            max(1, round(height * scale)),
                        ),
                        self.Image.Resampling.LANCZOS,
                    )
                output = io.BytesIO()
                image.save(
                    output,
                    format="JPEG",
                    quality=self.quality,
                    optimize=True,
                )
            converted = output.getvalue()
        except Exception:
            self.stats.skipped += 1
            return None
        self.stats.converted += 1
        self.stats.before_bytes += len(raw)
        self.stats.after_bytes += len(converted)
        return base64.b64encode(converted).decode("ascii")


def transform_images(node: Any, shrinker: ImageShrinker) -> Any:
    if isinstance(node, str):
        match = DATA_URL_RE.match(node)
        if not match:
            return node
        converted = shrinker.convert(match.group(2))
        return f"data:image/jpeg;base64,{converted}" if converted else node

    if isinstance(node, list):
        return [transform_images(item, shrinker) for item in node]

    if not isinstance(node, dict):
        return node

    result = dict(node)
    raw = result.get("data")
    type_name = str(result.get("type", "")).lower()
    mime_key = next(
        (key for key in MIME_KEYS if isinstance(result.get(key), str)), None
    )
    mime = str(result.get(mime_key, "")) if mime_key else ""
    raw_image = (
        isinstance(raw, str)
        and not raw.startswith("data:")
        and (
            type_name in {"image", "input_image"}
            or mime.lower().startswith("image/")
        )
    )
    if raw_image:
        converted = shrinker.convert(raw)
        if converted:
            result["data"] = converted
            if mime_key:
                result[mime_key] = "image/jpeg"

    for key, value in list(result.items()):
        if key == "data" and raw_image:
            continue
        result[key] = transform_images(value, shrinker)
    return result


def detected_mime(encoded: str) -> Optional[str]:
    try:
        raw = base64.b64decode("".join(encoded.split()), validate=True)
    except Exception:
        return None
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


def mime_mismatches(node: Any) -> List[str]:
    """Return locations whose declared common image MIME conflicts with bytes."""
    mismatches: List[str] = []
    if isinstance(node, str):
        match = DATA_URL_RE.match(node)
        if match:
            actual = detected_mime(match.group(2))
            declared = match.group(1).lower()
            if actual and declared != actual:
                mismatches.append(f"data URL says {declared}, bytes are {actual}")
        return mismatches
    if isinstance(node, list):
        for item in node:
            mismatches.extend(mime_mismatches(item))
        return mismatches
    if not isinstance(node, dict):
        return mismatches

    raw = node.get("data")
    mime_key = next(
        (key for key in MIME_KEYS if isinstance(node.get(key), str)), None
    )
    if isinstance(raw, str) and mime_key and not raw.startswith("data:"):
        declared = str(node[mime_key]).lower()
        if declared.startswith("image/"):
            actual = detected_mime(raw)
            if actual and declared != actual:
                mismatches.append(
                    f"{mime_key} says {declared}, bytes are {actual}"
                )
    for key, value in node.items():
        if key == "data" and isinstance(raw, str) and mime_key:
            continue
        mismatches.extend(mime_mismatches(value))
    return mismatches


def message_has_413(record: Dict[str, Any]) -> bool:
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return False
    if payload.get("type") != "task_complete" and record.get("type") != "task_complete":
        return False
    error = payload.get("error")
    if isinstance(error, dict):
        message = str(error.get("message", ""))
        status = error.get("status") or error.get("status_code")
        return str(status) == "413" or bool(ERROR_413_RE.search(message))
    return bool(ERROR_413_RE.search(str(error or "")))


def scan_errors(path: str) -> Tuple[bool, int, int, Dict[str, Any]]:
    last_failed_413 = False
    failures_413 = 0
    completed_turns = 0
    meta: Dict[str, Any] = {}
    for _, record in iter_records(path):
        if record.get("type") == "session_meta" and not meta:
            payload = record.get("payload")
            meta = payload if isinstance(payload, dict) else {}
        payload = record.get("payload")
        is_complete = (
            isinstance(payload, dict) and payload.get("type") == "task_complete"
        ) or record.get("type") == "task_complete"
        if is_complete:
            completed_turns += 1
            last_failed_413 = message_has_413(record)
            if last_failed_413:
                failures_413 += 1
    return last_failed_413, failures_413, completed_turns, meta


def list_413(codex_home: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for path in all_rollouts(codex_home):
        try:
            stuck, failures, turns, meta = scan_errors(path)
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if failures:
            try:
                sid = get_session_id(meta)
            except ValueError:
                sid = "unknown"
            rows.append(
                {
                    "id": sid,
                    "provider": str(meta.get("model_provider", "unknown")),
                    "size_mb": round(os.path.getsize(path) / 1_000_000, 2),
                    "failures_413": failures,
                    "last_completed_turn_is_413": stuck,
                    "completed_turns": turns,
                    "path": path,
                }
            )
    rows.sort(key=lambda row: os.path.getmtime(row["path"]), reverse=True)
    return rows


def resolve_session(codex_home: str, spec: Optional[str], latest: bool) -> str:
    if spec and os.path.isfile(spec):
        return os.path.abspath(spec)
    candidates = all_rollouts(codex_home)
    if spec:
        matches = [path for path in candidates if spec in os.path.basename(path)]
        matches.sort(key=os.path.getmtime, reverse=True)
        if matches:
            return matches[0]
        raise ValueError(f"session not found: {spec}")
    if latest:
        rows = list_413(codex_home)
        if not rows:
            raise ValueError("no rollout with a recognized HTTP 413 failure was found")
        stuck = [row for row in rows if row["last_completed_turn_is_413"]]
        return (stuck or rows)[0]["path"]
    raise ValueError("use --session, --latest-413, or --list")


def choose_backup_path(backup_dir: str, source: str, digest: str) -> str:
    os.makedirs(backup_dir, exist_ok=True)
    name = os.path.basename(source)
    candidate = os.path.join(backup_dir, name)
    if not os.path.exists(candidate) or sha256_file(candidate) == digest:
        return candidate
    stem, extension = os.path.splitext(name)
    return os.path.join(backup_dir, f"{stem}-{digest[:12]}{extension}")


def write_checksum(backup_dir: str, digest: str, backup: str) -> None:
    line = f"{digest}  {os.path.basename(backup)}\n"
    checksum_path = os.path.join(backup_dir, "SHA256SUMS.txt")
    existing = ""
    if os.path.exists(checksum_path):
        with open(checksum_path, "r", encoding="utf-8") as handle:
            existing = handle.read()
    if line not in existing:
        with open(checksum_path, "a", encoding="utf-8") as handle:
            handle.write(line)


def audit_output(
    path: str, source_records: int, new_id: str
) -> Dict[str, Any]:
    checked = validate_jsonl(path)
    output_id = get_session_id(checked["meta"])
    if checked["records"] != source_records:
        raise ValueError(
            f"record-count mismatch: {source_records} -> {checked['records']}"
        )
    if output_id != new_id.lower():
        raise ValueError(f"new session ID not found in session_meta: {output_id}")
    mismatches: List[str] = []
    for line_number, record in iter_records(path):
        for mismatch in mime_mismatches(record):
            mismatches.append(f"line {line_number}: {mismatch}")
    if mismatches:
        raise ValueError("image MIME validation failed: " + "; ".join(mismatches[:3]))
    checked["image_mime_validation"] = "passed"
    return checked


def repair(
    source: str,
    output_dir: str,
    backup_dir: str,
    new_id: str,
    max_dim: int,
    quality: int,
) -> Dict[str, Any]:
    source_check = validate_jsonl(source)
    old_id = get_session_id(source_check["meta"])
    if not UUID_RE.match(new_id):
        raise ValueError("--new-id must be a UUID")
    if new_id.lower() == old_id.lower():
        raise ValueError("the repaired copy must use a different session ID")

    source_digest = sha256_file(source)
    backup = choose_backup_path(backup_dir, source, source_digest)
    if not os.path.exists(backup):
        shutil.copy2(source, backup)
    if sha256_file(backup) != source_digest:
        raise ValueError("backup checksum does not match the source")
    write_checksum(backup_dir, source_digest, backup)

    os.makedirs(output_dir, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
    output = os.path.join(output_dir, f"rollout-{stamp}-{new_id}.jsonl")
    if os.path.exists(output):
        raise ValueError(f"refusing to overwrite existing output: {output}")
    shrinker = ImageShrinker(max_dim, quality)
    temp_handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=output_dir,
        prefix=".codex-413-",
        suffix=".tmp",
        delete=False,
    )
    temp_path = temp_handle.name
    try:
        with temp_handle:
            for _, record in iter_records(source):
                transformed = transform_images(record, shrinker)
                transformed = replace_text(transformed, old_id, new_id.lower())
                temp_handle.write(
                    json.dumps(
                        transformed,
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    + "\n"
                )
            temp_handle.flush()
            os.fsync(temp_handle.fileno())
        audit_output(temp_path, source_check["records"], new_id)
        os.replace(temp_path, output)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise

    if sha256_file(source) != source_digest:
        raise ValueError("source checksum changed during repair")

    return {
        "source": source,
        "source_sha256": source_digest,
        "backup": backup,
        "output": output,
        "old_id": old_id,
        "new_id": new_id.lower(),
        "records": source_check["records"],
        "source_mb": round(os.path.getsize(source) / 1_000_000, 2),
        "output_mb": round(os.path.getsize(output) / 1_000_000, 2),
        "images_converted": shrinker.stats.converted,
        "images_skipped": shrinker.stats.skipped,
        "image_mb_before": round(shrinker.stats.before_bytes / 1_000_000, 2),
        "image_mb_after": round(shrinker.stats.after_bytes / 1_000_000, 2),
        "structural_validation": "passed",
        "image_mime_validation": "passed",
        "source_unchanged": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create and validate a smaller copy of a Codex rollout"
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--session", help="session ID fragment or rollout path")
    mode.add_argument("--latest-413", action="store_true")
    mode.add_argument("--list", action="store_true")
    parser.add_argument("--codex-home", default=default_codex_home())
    parser.add_argument("--max-dim", type=int, default=1280)
    parser.add_argument("--quality", type=int, default=72)
    parser.add_argument("--backup-dir", default="./codex-413-backup")
    parser.add_argument("--out-dir", default="./codex-413-healed")
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--new-id")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--show-paths",
        action="store_true",
        help="show local source, backup, and output paths",
    )
    return parser


def redacted(result: Dict[str, Any], show_paths: bool) -> Dict[str, Any]:
    if show_paths:
        return result
    return {
        key: value
        for key, value in result.items()
        if key not in {"source", "backup", "output"}
    }


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.list:
        rows = list_413(args.codex_home)
        shown_rows: List[Dict[str, Any]] = []
        for row in rows:
            shown = dict(row)
            if not args.show_paths:
                shown.pop("path", None)
            shown_rows.append(shown)
        if args.json:
            print(json.dumps(shown_rows, ensure_ascii=False, indent=2))
        else:
            for shown in shown_rows:
                print(shown)
        return 0
    if args.max_dim <= 0 or not 1 <= args.quality <= 95:
        raise SystemExit("--max-dim must be > 0 and --quality must be 1..95")

    try:
        source = resolve_session(
            args.codex_home, args.session, args.latest_413
        )
        requested_new_id = (args.new_id or uuid7()).lower()
        if any(
            requested_new_id in os.path.basename(path)
            for path in all_rollouts(args.codex_home)
        ):
            raise ValueError(
                "the requested new session ID already exists in CODEX_HOME"
            )
        output_dir = args.out_dir
        if args.install:
            today = dt.datetime.now()
            output_dir = os.path.join(
                args.codex_home,
                "sessions",
                today.strftime("%Y"),
                today.strftime("%m"),
                today.strftime("%d"),
            )
        result = repair(
            source=source,
            output_dir=output_dir,
            backup_dir=args.backup_dir,
            new_id=requested_new_id,
            max_dim=args.max_dim,
            quality=args.quality,
        )
    except (OSError, UnicodeDecodeError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"repair aborted: {exc}") from exc

    shown = redacted(result, args.show_paths)
    if args.json:
        print(json.dumps(shown, ensure_ascii=False, indent=2))
    else:
        for key, value in shown.items():
            print(f"{key:24}: {value}")
        if args.install:
            print(
                "\nThe copy was placed in the sessions directory. Registration and "
                "resume still require a manual check in your Codex version."
            )
            print(f"Try: codex resume {result['new_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

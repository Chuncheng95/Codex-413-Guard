import base64
import io
import json
import os
import sys
import tempfile
import unittest

from PIL import Image


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import heal_codex_413 as healer  # noqa: E402


OLD_ID = "018f0000-0000-7000-8000-000000000001"
NEW_ID = "018f0000-0000-7000-8000-000000000002"


def png_base64() -> str:
    image = Image.new("RGBA", (16, 16), (255, 0, 0, 128))
    output = io.BytesIO()
    image.save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def write_rollout(path: str) -> None:
    encoded = png_base64()
    records = [
        {"type": "event", "payload": {"note": "metadata is not first"}},
        {
            "type": "session_meta",
            "payload": {"id": OLD_ID, "model_provider": "example"},
        },
        {
            "type": "response_item",
            "payload": {
                "image_url": f"data:image/png;base64,{encoded}",
                "raw": {
                    "type": "input_image",
                    "mime_type": "image/png",
                    "data": encoded,
                },
            },
        },
    ]
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")


class HealTests(unittest.TestCase):
    def test_repair_updates_mime_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as root:
            source = os.path.join(root, f"rollout-{OLD_ID}.jsonl")
            output_dir = os.path.join(root, "out")
            backup_dir = os.path.join(root, "backup")
            write_rollout(source)
            before = healer.sha256_file(source)
            result = healer.repair(
                source,
                output_dir,
                backup_dir,
                NEW_ID,
                max_dim=8,
                quality=70,
            )
            self.assertEqual(healer.sha256_file(source), before)
            self.assertEqual(result["records"], 3)
            self.assertEqual(result["images_converted"], 2)

            records = [record for _, record in healer.iter_records(result["output"])]
            payload = records[2]["payload"]
            self.assertTrue(payload["image_url"].startswith("data:image/jpeg;base64,"))
            self.assertEqual(payload["raw"]["mime_type"], "image/jpeg")
            raw_jpeg = base64.b64decode(payload["raw"]["data"])
            self.assertEqual(raw_jpeg[:2], b"\xff\xd8")
            self.assertEqual(records[1]["payload"]["id"], NEW_ID)

    def test_invalid_jsonl_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "bad.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"type":"session_meta"}\n')
                handle.write("not-json\n")
            with self.assertRaises(ValueError):
                healer.validate_jsonl(path)

    def test_413_detection_requires_status_or_message_pattern(self):
        positive = {
            "type": "event_msg",
            "payload": {
                "type": "task_complete",
                "error": {"message": "HTTP 413 Payload Too Large"},
            },
        }
        negative = {
            "type": "event_msg",
            "payload": {
                "type": "task_complete",
                "error": {"message": "artifact 413 was generated"},
            },
        }
        self.assertTrue(healer.message_has_413(positive))
        self.assertFalse(healer.message_has_413(negative))

    def test_mime_audit_detects_mismatch(self):
        encoded = png_base64()
        mismatches = healer.mime_mismatches(
            f"data:image/jpeg;base64,{encoded}"
        )
        self.assertEqual(len(mismatches), 1)


if __name__ == "__main__":
    unittest.main()

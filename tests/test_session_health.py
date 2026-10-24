import base64
import json
import os
import sys
import tempfile
import unittest


SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
sys.path.insert(0, SCRIPTS)

import session_health  # noqa: E402


class SessionHealthTests(unittest.TestCase):
    def test_meta_can_appear_after_first_record(self):
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "rollout-test.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps({"type": "event", "payload": {}}) + "\n")
                handle.write(
                    json.dumps(
                        {
                            "type": "session_meta",
                            "payload": {
                                "id": "018f0000-0000-7000-8000-000000000001",
                                "model_provider": "example",
                            },
                        }
                    )
                    + "\n"
                )
            meta = session_health.read_meta(path)
            self.assertEqual(meta["model_provider"], "example")

    def test_deep_stats_counts_data_url_and_raw_image(self):
        payload = base64.b64encode(b"test-image-bytes").decode("ascii")
        records = [
            {
                "image_url": f"data:image/png;base64,{payload}",
                "nested": {
                    "type": "input_image",
                    "mime_type": "image/webp",
                    "data": payload,
                },
            }
        ]
        with tempfile.TemporaryDirectory() as root:
            path = os.path.join(root, "rollout-test.jsonl")
            with open(path, "w", encoding="utf-8") as handle:
                for record in records:
                    handle.write(json.dumps(record) + "\n")
            stats = session_health.deep_stats(path)
        self.assertEqual(stats["images"], 2)
        self.assertEqual(stats["invalid_records"], 0)
        self.assertEqual(stats["image_mimes"]["image/png"], 1)
        self.assertEqual(stats["image_mimes"]["image/webp"], 1)

    def test_public_row_hides_paths_by_default(self):
        row = {
            "id": "x",
            "size_mb": 1,
            "_path": "/private/session.jsonl",
            "_cwd": "/private/project",
        }
        public = session_health.public_row(row, show_paths=False)
        self.assertNotIn("path", public)
        self.assertNotIn("cwd", public)


if __name__ == "__main__":
    unittest.main()

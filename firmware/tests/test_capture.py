#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import queue
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location("capture", Path(__file__).parents[1] / "tools/tpms_capture.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

class FakeSerial:
    def __init__(self):
        self.q = queue.Queue()
    def open(self): pass
    def close(self): pass
    def readline(self):
        try: return self.q.get(timeout=0.02)
        except queue.Empty: return b""

class CaptureTest(unittest.TestCase):
    def test_mixed_sensors_are_not_combined_for_field_comparison(self):
        packets = ["15B9C582010153221BA7", "15B99AA401C05C201C65"]
        capture = SimpleNamespace(error=None, frames=[
            {"stage": "mounted", "decoded": {"payload_hex": p, "repeat_confirmed": True}}
            for p in packets])
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "mixed"
            folder.mkdir()
            tool.archive(folder, capture, {}, [])
            summary = json.loads((folder / "summary.json").read_text())
            groups = summary["by_id_candidate"]
            self.assertEqual(set(groups), {"15B9C582", "15B99AA4"})
            for group in groups.values():
                self.assertEqual(group["changing_byte_indices"], [])
                self.assertIsNone(group["wheel_position"])
                self.assertFalse(group["id_verified"])

    def test_unknown_and_nonfinite_reference_are_not_measurements(self):
        self.assertIsNone(tool.read_reference("-")["pressure_psi"])
        for value in ["nan 25", "33 inf", "-1 20", "one two", "33"]:
            with self.assertRaises(ValueError): tool.read_reference(value)
        self.assertEqual(tool.read_reference("33.5 28")["pressure_psi"], 33.5)

    def test_preserves_plain_pulses_json_and_binary_in_one_zip(self):
        raw = [
            b"TPMS_CANDIDATE seq=1 pulses=103L,210H\n",
            b"TPMS_SYMBOLS seq=1 q=12G\n",
            b'{"v":3,"type":"status","valid_frames":2}\n',
            b'{"v":3,"type":"tpms_frame","payload_hex":"15B99AA401C05C211C66","integrity":"SUM8","repeats":2,"repeat_confirmed":true}\n',
            b"boot garbage \xff\x00\n",
        ]
        fake = FakeSerial()
        with tempfile.TemporaryDirectory() as temp, patch.object(tool.serial, "Serial", return_value=fake):
            folder = Path(temp) / "test"
            folder.mkdir()
            capture = tool.Capture("TEST", 115200, folder)
            start = capture.begin("mounted")["host_unix_s"]
            for line in raw: fake.q.put(line)
            deadline = time.monotonic() + 2
            while len(capture.records) < len(raw) + 1 and time.monotonic() < deadline:
                time.sleep(0.02)
            capture.close()
            self.assertIsNone(capture.error)
            self.assertTrue(capture.confirmed_since(start))
            self.assertFalse(capture.confirmed_since(time.time()+1))
            self.assertEqual((folder / "serial.bin").read_bytes(), b"".join(raw))
            self.assertEqual(len(capture.records), len(raw)+1)
            target = tool.archive(folder, capture, {}, [])
            with zipfile.ZipFile(target) as z:
                summary = json.loads(z.read("summary.json"))
                self.assertEqual(summary["unique_payloads"], ["15B99AA401C05C211C66"])
                self.assertEqual(summary["stage_confirmed_repeats"]["mounted"], 1)
                self.assertFalse(summary["mapping_verified"])
                self.assertIn("TPMS_SYMBOLS", z.read("serial.jsonl").decode())

if __name__ == "__main__":
    unittest.main()

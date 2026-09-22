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
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from tpms_calibration import analyze, associate

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

class CalibrationTest(unittest.TestCase):
    def frame(self, t, p=92, temp=25, sensor=0x82):
        b = [0x15, 0xb9, 0xc5, sensor, 1, p >> 8, p & 255, temp, 27]
        b.append(sum(b) % 256)
        return {"host_unix_s": t, "decoded": {"payload_hex": bytes(b).hex(), "repeat_confirmed": True}}

    def ref(self, t, p=0, temp=25):
        return dict(host_unix_s=t, pressure_psi=p, temperature_c=temp, fresh=True)

    def test_association_rejects_stale_mixed_and_transitions(self):
        r = self.ref(100)
        self.assertEqual(associate([self.frame(99)], [r])[0]['status'], 'linked')
        self.assertEqual(associate([self.frame(80)], [r])[0]['status'], 'unmatched')
        self.assertEqual(associate([self.frame(99), self.frame(101, sensor=0x83)], [r])[0]['status'], 'ambiguous_sensor')
        self.assertEqual(associate([self.frame(99), self.frame(101, p=200)], [r])[0]['status'], 'ambiguous_payload')
        r['fresh'] = False
        self.assertEqual(associate([self.frame(99)], [r])[0]['status'], 'not_fresh')

    def test_models_use_all_points_and_never_self_approve(self):
        raw = [92, 180, 260, 339, 300]
        temps = [20, 30, 25, 35, 22]
        frames = [self.frame(i*30, p, t) for i, (p, t) in enumerate(zip(raw, temps))]
        refs = [self.ref(i*30+1, (p-92)/7, t) for i, (p, t) in enumerate(zip(raw, temps))]
        report = analyze(frames, refs)
        group = next(iter(report['sensors'].values()))
        matches = group['pressure']['candidates']
        self.assertTrue(any(c['byte_start'] == 5 and c['byte_order'] == 'big' and abs(c['scale']-1/7)<1e-9 for c in matches))
        self.assertFalse(report['mapping_verified'])
        self.assertFalse(group['sensor_id_verified'])
        self.assertTrue(all(len(c['residuals']) == 5 for c in matches))
        refs[-1]['pressure_psi'] += 10
        bad = next(iter(analyze(frames, refs)['sensors'].values()))
        self.assertFalse(any(c['byte_start'] == 5 and c['width'] == 16 and c['byte_order'] == 'big' for c in bad['pressure']['candidates']))

    def test_live_session_multiple_inputs_and_zip(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(tool.serial, 'Serial', return_value=FakeSerial()), patch.object(tool, 'choose_port', return_value='TEST'), patch('builtins.input', side_effect=['bad', '-', '32 25', '34 27', 'q']), patch.object(sys, 'argv', ['capture', '--live-calibration', '--out', str(Path(temp)/'live')]):
            self.assertEqual(tool.main(), 0)
            with zipfile.ZipFile(Path(temp)/'live.zip') as z:
                report = json.loads(z.read('calibration.json'))
                self.assertEqual(len(report['links']), 2)
                self.assertEqual(report['links'][0]['status'], 'unmatched')
                self.assertIn('serial.bin', z.namelist())
                self.assertIn('host_monotonic_s', report['links'][0]['reference'])

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
            for line in raw:
                midpoint = len(line)//2
                fake.q.put(line[:midpoint])
                fake.q.put(line[midpoint:])
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

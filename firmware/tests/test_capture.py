#!/usr/bin/env python3
import importlib.util
import json
from pathlib import Path
import queue
import subprocess
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
from tpms_calibration import analyze, analyze_session, associate, feedback

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
        late = associate([self.frame(80)], [r])[0]
        self.assertEqual(late['status'], 'delayed_candidate')
        self.assertEqual(late['age_seconds'], 20)
        self.assertEqual(associate([self.frame(-21)], [r])[0]['status'], 'unmatched')
        self.assertEqual(associate([self.frame(99), self.frame(101, sensor=0x83)], [r])[0]['status'], 'ambiguous_sensor')
        self.assertEqual(associate([self.frame(99), self.frame(101, p=200)], [r])[0]['status'], 'ambiguous_payload')
        r['fresh'] = False
        self.assertEqual(associate([self.frame(99)], [r])[0]['status'], 'not_fresh')

    def test_future_packet_cannot_fill_a_missing_prior_reading(self):
        link = associate([self.frame(102)], [self.ref(100)])[0]
        self.assertEqual(link['status'], 'unmatched')
        self.assertEqual(link['reason'], 'no_preceding_frame')
        self.assertIsNone(link['nearest_frame'])
        self.assertEqual(link['nearest_following_frame']['delta_seconds'], 2)

    def test_monotonic_clock_survives_wall_clock_adjustment(self):
        f, r = self.frame(100), self.ref(40)
        f['host_monotonic_s'], r['host_monotonic_s'] = 10, 12
        link = associate([f], [r])[0]
        self.assertEqual(link['status'], 'linked')
        self.assertEqual(link['clock'], 'host_monotonic_s')
        self.assertEqual(link['age_seconds'], 2)

    def test_latest_unconfirmed_change_blocks_older_confirmed_value(self):
        new = self.frame(99, p=250)
        new['decoded']['repeat_confirmed'] = False
        link = associate([self.frame(98, p=200), new], [self.ref(101)])[0]
        self.assertEqual(link['status'], 'ambiguous_payload')
        self.assertEqual(associate([new], [self.ref(101)])[0]['status'], 'unconfirmed_frame')
        broken = self.frame(99)
        broken['decoded']['payload_hex'] = broken['decoded']['payload_hex'][:-2] + 'ff'
        self.assertEqual(associate([broken], [self.ref(101)])[0]['status'], 'unmatched')

    def test_duplicate_references_cannot_satisfy_minimum_independent_points(self):
        frames = [self.frame(i*30, 92+i*60, 25+i*3) for i in range(3)]
        refs = [self.ref(i*30+1, i*10, 25+i*3) for i in range(3)]
        refs += [self.ref(63, 20, 31)]
        report = analyze(frames, refs)
        group = next(iter(report['sensors'].values()))
        self.assertEqual(report['links'][-1]['duplicate_of'], 3)
        self.assertEqual(group['pressure']['independent_observations'], 3)
        self.assertEqual(group['pressure']['status'], 'insufficient_points')
        self.assertIn('no new calibration point', feedback(report))
        refs[-1]['pressure_psi'] = 21
        links = associate(frames, refs)
        self.assertEqual([r['status'] for r in links[-2:]], ['conflicting_reference']*2)

    def test_separate_bursts_with_same_payload_are_distinct_observations(self):
        frames = [self.frame(0), self.frame(30)]
        refs = [self.ref(2), self.ref(32)]
        links = associate(frames, refs)
        self.assertTrue(all(r['duplicate_of'] is None for r in links))
        self.assertNotEqual(links[0]['observation_id'], links[1]['observation_id'])

    def test_invalid_offline_reference_is_never_a_calibration_point(self):
        for value in [float('nan'), float('inf'), 101, -1]:
            r = self.ref(100, value)
            self.assertEqual(associate([self.frame(99)], [r])[0]['status'], 'invalid_reference')

    def test_actual_live_session_keeps_delayed_evidence_without_false_calibration(self):
        fixture = Path(__file__).parent / 'fixtures/TPMS_LIVE_20260922.jsonl'
        report = analyze_session(fixture)
        links = report['links']
        self.assertEqual([r['status'] for r in links], ['unmatched'] + ['delayed_candidate']*4)
        self.assertEqual([r['duplicate_of'] for r in links], [None, None, 2, None, 4])
        self.assertIsNone(links[0]['nearest_frame'])
        self.assertAlmostEqual(links[0]['nearest_following_frame']['delta_seconds'], 18.985, places=3)
        self.assertAlmostEqual(links[1]['age_seconds'], 10.468, places=3)
        group = report['sensors']['15B99AA4']
        self.assertEqual(group['decoded_records'], 32)
        self.assertEqual(len(group['raw_payloads']), 5)
        self.assertEqual(group['changing_byte_indices'], [5, 6, 7])
        self.assertEqual(group['independent_candidate_observations'], 2)
        self.assertEqual([r['b5_b6_low9_candidate'] for r in group['raw_points']], [327, 327, 282, 282])
        self.assertEqual([r['b7_u8'] for r in group['raw_points']], [32, 32, 36, 36])
        for key in ('pressure', 'temperature'):
            self.assertEqual(group[key]['status'], 'insufficient_points')
            self.assertEqual(group['review_only_models'][key]['independent_observations'], 2)
            self.assertEqual(group['review_only_models'][key]['distinct_reference_values'], 2)
            self.assertFalse(group['review_only_models'][key]['candidates'])
        self.assertFalse(report['mapping_verified'])
        self.assertFalse(group['sensor_id_verified'])

    def test_offline_zip_reanalysis_uses_events_and_preserves_source(self):
        fixture = Path(__file__).parent / 'fixtures/TPMS_LIVE_20260922.jsonl'
        with tempfile.TemporaryDirectory() as temp:
            source, target = Path(temp)/'session.zip', Path(temp)/'new-report.json'
            with zipfile.ZipFile(source, 'w') as z:
                z.writestr('serial.jsonl', fixture.read_bytes())
                z.writestr('calibration.json', '{"obsolete":true}')
            original = source.read_bytes()
            cmd = [sys.executable, str(Path(__file__).parents[1]/'tools/tpms_calibration.py'),
                   str(source), '--out', str(target)]
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            self.assertEqual(json.loads(target.read_text())['schema_version'], 2)
            self.assertEqual(source.read_bytes(), original)
            self.assertNotEqual(subprocess.run(cmd, capture_output=True).returncode, 0)

    def test_resume_combines_points_but_never_associates_across_session_clocks(self):
        baseline = []
        for i, (p, t) in enumerate([(92, 20), (180, 30)]):
            f, r = self.frame(1000+i*30, p, t), self.ref(1001+i*30, (p-92)/7, t)
            f['decoded']['type'], r['event'] = 'tpms_frame', 'reference'
            f['host_monotonic_s'], r['host_monotonic_s'] = 1000+i*30, 1001+i*30
            baseline.extend([f, r])
        frames, refs = [], []
        for i, (p, t) in enumerate([(260, 25), (339, 35)]):
            f, r = self.frame(2000+i*30, p, t), self.ref(2001+i*30, (p-92)/7, t)
            f['host_monotonic_s'], r['host_monotonic_s'] = i*30, i*30+1
            frames.append(f)
            refs.append(r)
        report = analyze(frames, refs, baseline=baseline)
        group = next(iter(report['sensors'].values()))
        self.assertEqual([r['reference_index'] for r in report['links']], [1, 2, 3, 4])
        self.assertEqual([r['session'] for r in report['links']], ['baseline']*2+['current']*2)
        self.assertEqual(group['pressure']['independent_observations'], 4)
        self.assertTrue(any(c['width'] == 9 and c['byte_start'] == 5 and abs(c['scale']-1/7)<1e-9
                            for c in group['pressure']['candidates']))
        self.assertFalse(report['mapping_verified'])
        # A resumed session with no new RF cannot recycle the last baseline frame.
        silent = analyze([], refs[:1], baseline=baseline)
        self.assertEqual(silent['links'][-1]['status'], 'unmatched')
        self.assertIsNone(silent['links'][-1]['nearest_frame'])

    def test_resumed_live_zip_contains_baseline_and_reanalyses_it_automatically(self):
        fixture = Path(__file__).parent / 'fixtures/TPMS_LIVE_20260922.jsonl'
        with tempfile.TemporaryDirectory() as temp, patch.object(tool.serial, 'Serial', return_value=FakeSerial()), patch.object(tool, 'choose_port', return_value='TEST'), patch('builtins.input', side_effect=['30 34', 'q']), patch.object(sys, 'argv', ['capture', '--live-calibration', '--baseline', str(fixture), '--out', str(Path(temp)/'resume')]):
            self.assertEqual(tool.main(), 0)
            with zipfile.ZipFile(Path(temp)/'resume.zip') as z:
                self.assertEqual(z.read('baseline.jsonl'), fixture.read_bytes())
                saved = json.loads(z.read('calibration.json'))
                self.assertEqual(saved['baseline_references'], 5)
                self.assertEqual(saved['current_references'], 1)
                self.assertEqual(saved['links'][-1]['status'], 'unmatched')
            self.assertEqual(analyze_session(Path(temp)/'resume.zip'), saved)

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

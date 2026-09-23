#!/usr/bin/env python3
"""Compile the production decoder, assert exact recorded results, then test the kit."""
from collections import Counter
from pathlib import Path
import json
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "firmware/tests/fixtures"
sys.path.insert(0, str(ROOT / "firmware/tools"))
from tpms_calibration import read_records
from tpms_reprocess import recover
EXPECTED = {
    "TPMS88_CAPTURE.pulses.txt": {"15B99AA401C05C201C65": 3},
    "TPMS89_CAPTURE.pulses.txt": {"15B99AA401C05C211C66": 4},
    "TPMS_RAW_CAPTURE.pulses.txt": {"15B99AA401C05C201C65": 3},
    "TPMS_20260922.pulses.txt": {
        "15B9C58201005C1E1BAB": 1,
        "15B9C582010153221BA7": 2,
        "15B9C582010153241BA9": 2,
        "15B9C582010153261BAB": 2,
        "15B9C58201005C271BB4": 6,
    },
    "TPMS_LIVE_20260922.pulses.txt": {
        "15B99AA401C05C231C68": 4,
        "15B99AA401C144231C51": 1,
        "15B99AA401C147201C51": 1,
        "15B99AA401C05C201C65": 6,
        "15B99AA401C11A241C28": 1,
    },
}

with tempfile.TemporaryDirectory() as directory:
    binary = str(Path(directory) / "replay")
    subprocess.run(["g++", "-std=c++11", "-Wall", "-Wextra", "-Werror",
                    "-I" + str(ROOT / "firmware/include"),
                    str(ROOT / "firmware/tests/replay.cpp"), "-o", binary], check=True)
    for name, expected in EXPECTED.items():
        result = subprocess.run([binary, str(FIXTURES / name)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        actual = Counter(line.split()[-1] for line in result.stdout.splitlines())
        if actual != expected:
            raise AssertionError(f"{name}: {dict(actual)} != {expected}")
        print(f"{name}: {sum(actual.values())} exact recorded frames, PASS")
    records = read_records((FIXTURES / 'TPMS_LIVE_20260922.jsonl').read_text())
    records += read_records((FIXTURES / 'TPMS_LIVE_20260922.raw.jsonl').read_text())
    unchanged = json.dumps(records, sort_keys=True)
    report = recover(records, binary)
    assert json.dumps(records, sort_keys=True) == unchanged, 'original evidence changed'
    assert (report['raw_packet_count'], report['raw_packets_decoded'],
            report['original_frame_count'], report['recovered_frame_count']) == (13, 13, 32, 9)
    assert Counter(r['decoded']['payload_hex'] for r in report['recovered_frames']) == {
        '15B99AA401C05C231C68': 3, '15B99AA401C05C201C65': 6}
    assert sum(r['decoded']['adaptive_timing'] for r in report['recovered_frames']) == 7
    links = report['calibration']['links']
    assert [r['status'] for r in links] == ['unmatched'] + ['delayed_candidate']*4
    assert [r['duplicate_of'] for r in links] == [None, None, 2, None, 4]
    assert abs(links[0]['nearest_following_frame']['delta_seconds'] - 17.078) < .001
    assert report['calibration']['sensors']['15B99AA4']['independent_candidate_observations'] == 2
    assert report['calibration']['mapping_verified'] is False
    # A previously emitted packet is a replay check, never another observation.
    assert sum(r['status'] == 'already_emitted' for r in report['raw_packet_results']) == 4
    for recovered in report['recovered_frames']:
        original = records[recovered['source_record_index']]
        assert recovered['host_monotonic_s'] == original['host_monotonic_s']
        assert recovered['host_unix_s'] == original['host_unix_s']
        assert all(recovered['decoded'][key] is None for key in
                   ('sensor_id', 'pressure_psi', 'temperature_c'))
    print('Offline recovery: 9 additional frames, original timestamps, no false calibration, PASS')
    subprocess.run(["python3", str(ROOT / "firmware/tests/test_capture.py")], check=True)
print("All decoder replay and capture tests passed.")

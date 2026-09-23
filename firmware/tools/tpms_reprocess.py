#!/usr/bin/env python3
"""Recover saved raw packets with the production C++ decoder; no radio required."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

from tpms_calibration import analyze, finite_time, read_records, split_records, valid_frame

ROOT = Path(__file__).resolve().parents[2]
PACKET = re.compile(r'^TPMS_CANDIDATE .*\bscope=packet\b.*\bdecoded=([01])\b'
                    r'.*\blevels=after_edge\b.*\bpulses=(?:\d+[HL],)*\d+[HL]$')


def compile_decoder(binary):
    subprocess.run(['g++', '-std=c++11', '-Wall', '-Wextra', '-Werror',
                    '-I' + str(ROOT / 'firmware/include'),
                    str(ROOT / 'firmware/tests/replay.cpp'), '-o', str(binary)], check=True)


def recover(records, binary, baseline=None):
    """Original emitted frames remain unchanged; only decoded=0 can add a frame."""
    packets = [(i, row, PACKET.fullmatch(row.get('line', '')))
               for i, row in enumerate(records)]
    packets = [(i, row, match) for i, row, match in packets if match]
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / 'packets.txt'
        source.write_text(''.join(row['line'] + '\n' for _, row, _ in packets), encoding='ascii')
        result = subprocess.run([str(binary), '--jsonl', str(source)],
                                capture_output=True, text=True, check=True)
    decoded = {}
    for line in result.stdout.splitlines():
        item = json.loads(line)
        # Never select between multiple outputs for a single recorded packet.
        if item['line'] in decoded or not 1 <= item['line'] <= len(packets):
            raise ValueError('Replay did not return one unambiguous result per packet')
        decoded[item['line']] = item
    recovered, audit = [], []
    for number, (index, row, match) in enumerate(packets, 1):
        item = decoded.get(number)
        entry = {'source_record_index': index, 'raw_record': row, 'decoded': item,
                 'status': 'rejected' if item is None else
                           'already_emitted' if match[1] == '1' else 'recovered'}
        audit.append(entry)
        if item is None or match[1] == '1':
            continue
        frame = {k: row[k] for k in ('host_unix_s', 'host_monotonic_s', 'stage') if k in row}
        frame.update(event='offline_recovered_frame', source_record_index=index,
                     raw_line=row['line'], decoded={
                         **{k: v for k, v in item.items() if k != 'line'},
                         'type': 'tpms_frame', 'protocol': 'darbak_capture_80_lsb',
                         'integrity': 'SUM8', 'repeat_confirmed': False, 'repeats': 1,
                         'id_candidate': item['payload_hex'][:8],
                         'id_candidate_range': 'bytes_0_3', 'sensor_id': None,
                         'pressure_psi': None, 'temperature_c': None, 'mapping_verified': False})
        if not valid_frame(frame, require_repeat=False):
            raise ValueError('Production replay returned an invalid SUM8 payload')
        recovered.append(frame)

    original_frames, refs = split_records(records)
    frames = original_frames + recovered
    clock = ('host_monotonic_s' if frames and all(finite_time(f, 'host_monotonic_s') for f in frames)
             else 'host_unix_s')
    previous = {}
    recovered_ids = {id(f) for f in recovered}
    for frame in sorted((f for f in frames if finite_time(f, clock)), key=lambda f: f[clock]):
        if not valid_frame(frame, require_repeat=False):
            continue
        key = frame['decoded']['payload_hex'].upper()
        last = previous.get(key)
        if id(frame) in recovered_ids and last is not None and frame[clock] - last[clock] <= 1:
            frame['decoded']['repeat_confirmed'] = True
            frame['decoded']['repeats'] = last['decoded'].get('repeats', 1) + 1
        previous[key] = frame
    return {'schema_version': 1, 'decoder_sha256': hashlib.sha256(
                (ROOT / 'firmware/include/TpmsDecoder.h').read_bytes()).hexdigest(),
            'raw_packet_count': len(packets), 'raw_packets_decoded': len(decoded),
            'original_frame_count': len(original_frames), 'recovered_frame_count': len(recovered),
            'raw_packet_results': audit, 'recovered_frames': recovered,
            'calibration': analyze(frames, refs, baseline=baseline)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('session', type=Path, help='Saved session ZIP or serial.jsonl')
    ap.add_argument('--out', required=True, type=Path, help='New JSON report; source stays intact')
    args = ap.parse_args()
    if args.out.exists() or args.out.resolve() == args.session.resolve():
        ap.error('Choose a new output file; existing evidence is preserved.')
    raw = args.session.read_bytes()
    baseline = []
    if args.session.suffix.lower() == '.zip':
        with zipfile.ZipFile(args.session) as archive:
            records = read_records(archive.read('serial.jsonl').decode('utf-8-sig'))
            if 'baseline.jsonl' in archive.namelist():
                baseline = read_records(archive.read('baseline.jsonl').decode('utf-8-sig'))
    else:
        records = read_records(raw.decode('utf-8-sig'))
    with tempfile.TemporaryDirectory() as directory:
        binary = Path(directory) / 'tpms-replay'
        compile_decoder(binary)
        report = recover(records, binary, baseline=baseline)
    report['source_sha256'] = hashlib.sha256(raw).hexdigest()
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Decoded {report['raw_packets_decoded']}/{report['raw_packet_count']} saved raw packets; "
          f"recovered {report['recovered_frame_count']} previously rejected frames.")
    print('Physical units remain unverified. No hardware session was started.')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""One bounded, read-only Toyota-family TPMS diagnostic session. No ECU writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile


def classify(event):
    """Retain candidate bytes; never promote a cross-model formula to a reading."""
    if event.get('type') != 'obd_payload':
        return None
    try:
        payload = bytes.fromhex(event['payload_hex'])
    except (ValueError, KeyError, TypeError):
        return {'status': 'malformed_payload'}
    pid = event.get('request_pid')
    if len(payload) == 3 and payload[:2] == b'\x7f\x21':
        return {'status': 'negative_response', 'nrc': payload[2], 'request_pid': pid}
    if pid not in (0x16, 0x30) or len(payload) != 7 or payload[:2] != bytes([0x61, pid]):
        return {'status': 'unexpected_layout', 'request_pid': pid}
    return {
        'status': 'candidate_temperature' if pid == 0x16 else 'candidate_pressure',
        'raw_slots': list(payload[2:]), 'slot_positions_verified': False,
        'mapping_verified': False, 'sensor_id': None,
        'pressure_psi': None, 'temperature_c': None,
        'note': 'Toyota-family 5-slot layout; Fortuner mapping/freshness not yet verified. '
                'Zero/FF slots are not physical measurements.'}


def verify(root):
    m = json.loads((root / 'manifest-obd.json').read_text(encoding='utf-8'))
    if m.get('mode') != 'obd_tpms' or m.get('flash_offset') != '0x10000':
        raise RuntimeError('Wrong OBD test package.')
    for name, sha in m['sha256'].items():
        p = root / name
        if p.parent.resolve() != root.resolve() or hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            raise RuntimeError('Package checksum failed: ' + name)
    return m


def choose_port(requested):
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    if requested:
        if requested not in [p.device for p in ports]:
            raise RuntimeError('Selected COM port is not present.')
        return requested
    matches = [p for p in ports if p.vid in {0x10c4, 0x1a86, 0x0403, 0x303a}]
    if len(matches) == 1:
        return matches[0].device
    if len(ports) == 1:
        return ports[0].device
    raise RuntimeError('Connect only the test ESP32, or supply -Port COM3 explicitly.')


def run(args):
    import serial
    root = Path(__file__).resolve().parent
    manifest = verify(root)
    port = choose_port(args.port)
    print('OBD TPMS test: GPIO21 TX / GPIO22 RX, CAN 500 kbit/s.')
    print('Vehicle parked, ignition ON. Existing CAN wiring; ESP32 powered by USB.')
    print('Close other diagnostic tools. Do not press the tire reset/calibration button.')
    print('Flashing dedicated OBD image ' + manifest['commit'][:12])
    subprocess.run([sys.executable, '-m', 'esptool', '--chip', 'esp32', '--port', port,
                    '--baud', '460800', '--before', 'default_reset', '--after', 'hard_reset',
                    'write_flash', '--flash_size', 'keep', '0x10000',
                    str(root / 'DarbakVehicleHub-ESP32-OBD-TPMS.bin')], check=True)
    args.output.mkdir(parents=True, exist_ok=True)
    stem = 'TPMS_OBD_' + datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    raw_path = args.output / (stem + '.jsonl')
    zip_path = args.output / (stem + '.zip')
    counts = Counter()
    candidates = []
    ser = None
    outcome = 'not_started'
    invalid = 0
    statuses = []
    events = []
    seen_mode = False
    start_sent = False
    started = False
    t0 = time.monotonic()
    last_ping = 0
    with raw_path.open('w', encoding='utf-8') as log:
        def record(line, parsed=None):
            row = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                   'host_monotonic_s': time.monotonic(), 'raw': line, 'parsed': parsed}
            log.write(json.dumps(row) + '\n')
            log.flush()
            return row
        record('session_metadata', {'manifest': manifest, 'port': port,
                                    'vehicle': 'Fortuner 2020 diesel; candidate protocol'})
        try:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = port, 115200, 0.2
            ser.dtr, ser.rts = False, False
            ser.open()
            while time.monotonic() - t0 < 175:
                now = time.monotonic()
                if now - last_ping >= 1:
                    ser.write(b'PING\n')
                    last_ping = now
                raw = ser.readline().decode('utf-8', errors='replace').strip()
                if raw:
                    try:
                        ev = json.loads(raw)
                        if not isinstance(ev, dict):
                            raise ValueError('Not an object')
                    except ValueError:
                        invalid += 1
                        record(raw)
                        continue
                    row = record(raw, ev)
                    kind = ev.get('type')
                    counts[kind or 'unknown'] += 1
                    if kind == 'status':
                        if ev.get('mode') != 'obd_tpms' or ev.get('build') != manifest['commit'][:12]:
                            raise RuntimeError('Firmware identity mismatch; no test started.')
                        seen_mode = True
                        statuses.append(ev)
                        if ev.get('stopped'):
                            outcome = events[-1] if events else 'firmware_stopped'
                            break
                        if not start_sent and now - t0 >= 4:
                            ser.write(b'START\n')
                            record('host_command', {'command': 'START'})
                            start_sent = True
                        started = started or ev.get('active', False)
                    if kind == 'obd_event':
                        events.append(ev.get('event'))
                        print('OBD:', ev.get('event'), flush=True)
                    if kind == 'obd_payload':
                        result = classify(ev)
                        candidates.append({'timestamp_utc': row['timestamp_utc'],
                                           'payload_hex': ev.get('payload_hex'), **result})
                        print(datetime.now().strftime('%H:%M:%S'), result['status'],
                              ev.get('payload_hex'), 'PSI=N/A C=N/A (unverified)', flush=True)
                if not seen_mode and now-t0 > 10:
                    raise RuntimeError('No OBD firmware status received.')
            else:
                outcome = 'completed' if started else 'not_started'
        except KeyboardInterrupt:
            outcome = 'user_stopped'
        except Exception as exc:
            outcome = 'host_error: ' + str(exc)
            print(outcome)
            record('host_error', {'error': str(exc)})
        finally:
            if ser is not None and ser.is_open:
                try:
                    ser.write(b'STOP\n')
                    ser.flush()
                    record('host_command', {'command': 'STOP'})
                    # The firmware also disarms itself within four seconds of lost heartbeat.
                    until = time.monotonic() + 1
                    while time.monotonic() < until:
                        line = ser.readline().decode('utf-8', errors='replace').strip()
                        if line:
                            record(line)
                except Exception as exc:
                    record('stop_delivery_failed', {'error': str(exc),
                           'device_heartbeat_timeout_seconds': 4})
                finally:
                    try:
                        ser.close()
                    except Exception:
                        pass
    summary = {'outcome': outcome, 'started': started, 'counts': dict(counts),
               'invalid_serial_lines': invalid, 'status_history': statuses,
               'events': events, 'responses': candidates, 'mapping_verified': False,
               'pressure_psi': None, 'temperature_c': None, 'sensor_id': None,
               'interpretation': 'No reply does not prove that the vehicle lacks TPMS. '
                                 'ECU replies can contain cached sensor data. '
                                 'No generic OBD pressure/temperature PIDs or ABS estimates used.'}
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(raw_path, 'session.jsonl')
        z.writestr('summary.json', json.dumps(summary, indent=2))
        z.writestr('manifest-obd.json', json.dumps(manifest, indent=2))
    raw_path.unlink()  # Only after the complete archive is successfully closed.
    print('RESULT:', outcome)
    print('SEND THIS FILE:', zip_path)
    return 1 if outcome.startswith('host_error') or not started else 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port')
    parser.add_argument('--output', type=Path, default=Path.cwd())
    try:
        sys.exit(run(parser.parse_args()))
    except Exception as exc:
        print('ERROR:', exc, file=sys.stderr)
        sys.exit(1)

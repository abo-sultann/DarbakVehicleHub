"""Evidence-preserving TPMS calibration; hypotheses never enable firmware units."""
import argparse
import json
import math
from pathlib import Path
import zipfile

LINK_WINDOW = 10.0
REVIEW_WINDOW = 120.0
BURST_GAP = 1.0
ELIGIBLE = {"linked", "delayed_candidate"}


def valid_frame(record, require_repeat=True):
    d = record.get('decoded') or {}
    try:
        b = bytes.fromhex(d.get('payload_hex', ''))
        return (len(b) == 10 and sum(b[:9]) % 256 == b[9]
                and (not require_repeat or d.get('repeat_confirmed') is True))
    except (ValueError, TypeError):
        return False


def payload(frame):
    return frame['decoded']['payload_hex'].upper()


def finite_time(record, key):
    value = record.get(key)
    return isinstance(value, (int, float)) and math.isfinite(value)


def valid_reference(ref):
    return (finite_time(ref, 'pressure_psi') and 0 <= ref['pressure_psi'] <= 100
            and finite_time(ref, 'temperature_c') and -40 <= ref['temperature_c'] <= 125)


def associate(frames, references, window=LINK_WINDOW, review_window=REVIEW_WINDOW):
    # Unconfirmed but checksum-valid packets must also block an ambiguous link.
    all_frames = [f for f in frames if valid_frame(f, require_repeat=False)
                  and finite_time(f, 'host_unix_s')]
    records = all_frames + references
    clock = ('host_monotonic_s' if records and
             all(finite_time(r, 'host_monotonic_s') for r in records) else 'host_unix_s')
    all_frames.sort(key=lambda f: f[clock])
    observations, previous = {}, {}
    for frame in all_frames:
        sensor = payload(frame)[:8]
        last = previous.get(sensor)
        if (last is None or payload(last) != payload(frame)
                or frame[clock] - last[clock] > BURST_GAP):
            obs = f"{sensor}:{frame['host_unix_s']:.6f}"
        else:
            obs = observations[id(last)]
        observations[id(frame)] = obs
        previous[sensor] = frame

    def describe(frame, ref):
        if frame is None:
            return None
        d = frame['decoded']
        return {'host_unix_s': frame['host_unix_s'],
                'host_monotonic_s': frame.get('host_monotonic_s'),
                'delta_seconds': frame[clock] - ref[clock],
                'payload_hex': payload(frame), 'seq': d.get('seq'),
                'rx_ms': d.get('rx_ms'),
                'repeat_confirmed': d.get('repeat_confirmed') is True,
                'observation_id': observations[id(frame)]}

    result = []
    for number, ref in enumerate(references, 1):
        if not finite_time(ref, clock):
            result.append({'reference_index': number, 'reference': ref,
                           'status': 'invalid_timestamp', 'nearest_frame': None,
                           'sensor_id_candidate': None, 'nearby_frames': []})
            continue
        before = [f for f in all_frames if f[clock] <= ref[clock]]
        after = [f for f in all_frames if f[clock] > ref[clock]]
        prior, following = (before[-1] if before else None), (after[0] if after else None)
        near = [f for f in all_frames if abs(f[clock] - ref[clock]) <= window]
        near.sort(key=lambda f: abs(f[clock] - ref[clock]))
        obs = observations[id(prior)] if prior else None
        # Inspect the received burst's neighborhood too, even when entry was late.
        context = near + ([f for f in before if f[clock] >= prior[clock] - window] if prior else [])
        ids = {payload(f)[:8] for f in context}
        payloads = {payload(f) for f in context}
        age = ref[clock] - prior[clock] if prior else None
        confirmed = any(observations[id(f)] == obs and valid_frame(f) for f in before)
        status, reason = 'linked', 'unique_preceding_repeated_payload'
        if not ref.get('fresh'):
            status, reason = 'not_fresh', 'reference_not_confirmed_fresh'
        elif not valid_reference(ref):
            status, reason = 'invalid_reference', 'reference_units_out_of_range_or_nonfinite'
        elif prior is None:
            status, reason = 'unmatched', 'no_preceding_frame'
        elif len(ids) > 1:
            status, reason = 'ambiguous_sensor', 'multiple_sensor_candidates_near_reference_or_burst'
        elif len(payloads) > 1:
            status, reason = 'ambiguous_payload', 'payload_transition_near_reference_or_burst'
        elif not confirmed:
            status, reason = 'unconfirmed_frame', 'latest_burst_not_repeat_confirmed'
        elif age > review_window:
            status, reason = 'unmatched', 'preceding_frame_too_old'
        elif age > window:
            status, reason = 'delayed_candidate', 'entry_delay_requires_review'
        result.append({'reference_index': number, 'reference': ref, 'status': status,
                       'reason': reason, 'clock': clock,
                       'sensor_id_candidate': payload(prior)[:8] if prior and len(ids) == 1 else None,
                       'observation_id': obs, 'age_seconds': age,
                       # Never substitute a later packet for a missing prior packet.
                       'nearest_frame': prior,
                       'nearest_preceding_frame': describe(prior, ref),
                       'nearest_following_frame': describe(following, ref),
                       'nearby_frames': [describe(f, ref) for f in near],
                       'duplicate_of': None})

    grouped = {}
    for link in result:
        if link['status'] in ELIGIBLE:
            grouped.setdefault(link['observation_id'], []).append(link)
    for same_observation in grouped.values():
        values = {(r['reference'].get('pressure_psi'), r['reference'].get('temperature_c'))
                  for r in same_observation}
        if len(values) > 1:
            for link in same_observation:
                link['status'] = 'conflicting_reference'
                link['reason'] = 'different_readings_assigned_to_one_RF_observation'
        else:
            for link in same_observation[1:]:
                link['duplicate_of'] = same_observation[0]['reference_index']
    return result


def fit(xs, ys):
    mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
    v = sum((x-mx)**2 for x in xs)
    if not v:
        return None
    a = sum((x-mx)*(y-my) for x, y in zip(xs, ys))/v
    if abs(a) < 1e-10:
        return None
    return a, my-a*mx


def candidates(rows, key, tolerance):
    # Typing a reading twice cannot become an independent validation sample.
    independent = [r for r in rows if r.get('duplicate_of') is None]
    ys = [r['reference'][key] for r in independent]
    counts = {'reference_count': len(rows), 'independent_observations': len(independent),
              'distinct_reference_values': len(set(ys)), 'tolerance': tolerance}
    if len(independent) < 4 or len(set(ys)) < 3:
        return {**counts, 'status': 'insufficient_points',
                'required': '4 independent RF observations and 3 distinct reference values', 'candidates': []}
    bs = [bytes.fromhex(payload(r['nearest_frame'])) for r in independent]
    found = []
    # Exclude checksum; test contiguous bit fields, byte order, signedness.
    for order in ('big', 'little'):
        for start in range(1, 9):
            for size in (1, 2):
                if start + size > 9:
                    continue
                words = [int.from_bytes(b[start:start+size], order) for b in bs]
                for width in range(8, size*8+1):
                    for shift in range(size*8-width+1):
                        for signed in (False, True):
                            xs = [(v >> shift) & ((1 << width)-1) for v in words]
                            if signed:
                                xs = [x-(1 << width) if x & (1 << (width-1)) else x for x in xs]
                            if len(set(xs)) < 3:
                                continue
                            model = fit(xs, ys)
                            if not model:
                                continue
                            scale, offset = model
                            errors = [scale*x+offset-y for x, y in zip(xs, ys)]
                            if max(map(abs, errors)) > tolerance:
                                continue
                            loo = []
                            for i in range(len(xs)):
                                m = fit(xs[:i]+xs[i+1:], ys[:i]+ys[i+1:])
                                loo.append(abs(m[0]*xs[i]+m[1]-ys[i]) if m else math.inf)
                            if max(loo) > tolerance:
                                continue
                            found.append({'byte_start': start, 'byte_count': size, 'byte_order': order,
                                          'shift': shift, 'width': width, 'signed': signed,
                                          'scale': scale, 'offset': offset, 'raw_values': xs,
                                          'reference_indices': [r['reference_index'] for r in independent],
                                          'residuals': errors, 'max_leave_one_out_error': max(loo)})
    return {**counts, 'status': 'candidates_need_independent_validation' if found else 'no_matching_linear_model',
            'candidates': found}


def raw_fields(b):
    return {'b5_b6_u16': (b[5] << 8) | b[6],
            'b5_b6_low9_candidate': ((b[5] & 1) << 8) | b[6],
            'b5_remaining_bits': b[5] & 0xfe, 'b7_u8': b[7], 'b8_u8': b[8]}


def analyze(frames, references):
    links = associate(frames, references)
    groups = {}
    for frame in frames:
        if valid_frame(frame, require_repeat=False):
            groups.setdefault(payload(frame)[:8], []).append(frame)
    analyses = {}
    for sensor, received in groups.items():
        rows = [r for r in links if r['sensor_id_candidate'] == sensor and r['status'] in ELIGIBLE]
        linked = [r for r in rows if r['status'] == 'linked']
        packets = sorted({payload(f) for f in received})
        data = [bytes.fromhex(p) for p in packets]
        analyses[sensor] = {
            'decoded_records': len(received), 'sensor_id_verified': False,
            'sensor_id_candidate_range': 'bytes_0_3',
            'linked_points': len(linked), 'delayed_candidate_points': sum(r['status'] == 'delayed_candidate' for r in rows),
            'independent_linked_observations': sum(r['duplicate_of'] is None for r in linked),
            'independent_candidate_observations': sum(r['duplicate_of'] is None for r in rows),
            'stable_byte_indices': [i for i in range(9) if len({b[i] for b in data}) == 1],
            'changing_byte_indices': [i for i in range(9) if len({b[i] for b in data}) > 1],
            'byte_values': {str(i): sorted({b[i] for b in data}) for i in range(9)},
            'raw_payloads': [{'payload_hex': p, **raw_fields(b)} for p, b in zip(packets, data)],
            'raw_points': [{'reference_index': r['reference_index'], 'reference': r['reference'],
                            'association_status': r['status'], 'age_seconds': r['age_seconds'],
                            'duplicate_of': r['duplicate_of'], 'observation_id': r['observation_id'],
                            'payload_hex': payload(r['nearest_frame']),
                            **raw_fields(bytes.fromhex(payload(r['nearest_frame'])))} for r in rows],
            'pressure': candidates(linked, 'pressure_psi', 0.5),
            'temperature': candidates(linked, 'temperature_c', 1.0),
            'review_only_models': {'includes_delayed_associations': True,
                                  'pressure': candidates(rows, 'pressure_psi', 0.5),
                                  'temperature': candidates(rows, 'temperature_c', 1.0)},
        }
    return {'schema_version': 2, 'mapping_verified': False,
            'association_window_seconds': LINK_WINDOW, 'review_window_seconds': REVIEW_WINDOW,
            'association_basis': 'preceding repeated RF burst vs fresh user entry; delay is not verified',
            'links': links, 'sensors': analyses,
            'limitations': ['Delayed candidates are retained for review, not promoted to trusted links.',
                           'Repeated entries for the same RF observation are not independent points.',
                           'Future packets cannot explain a reference entered before reception.',
                           'One sensor cannot establish exact ID boundaries.',
                           'Raw masks are hypotheses, not pressure units or verified flag meanings.',
                           'Correlated pressure/temperature changes can produce indistinguishable models.',
                           'All models are hypotheses; no firmware mapping is automatically enabled.']}


def feedback(report):
    """Small enough to display after each entry while RF capture keeps running."""
    if not report['links']:
        return 'No references yet. Enter fresh PSI Celsius after a display update; q saves.'
    link = report['links'][-1]
    lines = [f"Reference #{link['reference_index']} saved: {link['status']}."]
    prior = link.get('nearest_preceding_frame')
    if prior:
        lines.append(f"Previous RF {prior['payload_hex']} was {link['age_seconds']:.1f}s before Enter.")
    if link.get('duplicate_of') is not None:
        lines.append(f"Same RF observation as reference #{link['duplicate_of']}; no new calibration point.")
    if link['status'] == 'delayed_candidate':
        lines.append('Timing needs review; raw data and this reading are retained.')
    elif link['status'] != 'linked':
        lines.append('This reading cannot currently calibrate units: ' + link.get('reason', link['status']) + '.')
    for sensor, group in report['sensors'].items():
        p, t = (group['review_only_models'][key] for key in ('pressure', 'temperature'))
        lines.append(f"{sensor}: {group['independent_linked_observations']} close-time observations; "
                     f"{group['independent_candidate_observations']} including timing candidates; "
                     f"{p['distinct_reference_values']} distinct PSI, {t['distinct_reference_values']} distinct Celsius.")
        lines.append(f"Candidate models: PSI={p['status']}; Celsius={t['status']}.")
    lines.append('Candidate fitting needs 4 independent observations and 3 different values per quantity. '
                 'Units remain unverified. Continue on a fresh display update, or q to save.')
    return '\n'.join(lines)


def analyze_session(source):
    """Reprocess original events, never trust an older derived calibration.json."""
    source = Path(source)
    if source.suffix.lower() == '.zip':
        with zipfile.ZipFile(source) as archive:
            raw = archive.read('serial.jsonl').decode('utf-8-sig')
    else:
        raw = source.read_text(encoding='utf-8-sig')
    records = [json.loads(line) for line in raw.splitlines() if line.strip()]
    frames = [r for r in records if (r.get('decoded') or {}).get('type') == 'tpms_frame']
    refs = [r for r in records if r.get('event') == 'reference']
    return analyze(frames, refs)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('session', type=Path, help='Existing session ZIP or serial.jsonl; no ESP32 needed')
    ap.add_argument('--out', required=True, type=Path, help='New report JSON; source is never modified')
    args = ap.parse_args()
    if args.out.resolve() == args.session.resolve() or args.out.exists():
        ap.error('Choose a new output file; existing session/report files are preserved.')
    report = analyze_session(args.session)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(feedback(report))
    print(f'Reanalysis saved: {args.out.resolve()}')


if __name__ == '__main__':
    main()

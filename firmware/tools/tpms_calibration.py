"""Conservative offline candidate discovery; never enables firmware unit mappings."""
import math


def valid_frame(record):
    d = record.get('decoded') or {}
    try:
        b = bytes.fromhex(d.get('payload_hex', ''))
        return len(b) == 10 and sum(b[:9]) % 256 == b[9] and d.get('repeat_confirmed') is True
    except (ValueError, TypeError):
        return False


def associate(frames, references, window=10.0):
    usable = [f for f in frames if valid_frame(f)]
    result = []
    for ref in references:
        near = [f for f in usable if abs(f['host_unix_s'] - ref['host_unix_s']) <= window]
        near.sort(key=lambda f: abs(f['host_unix_s'] - ref['host_unix_s']))
        ids = {f['decoded']['payload_hex'][:8].upper() for f in near}
        payloads = {f['decoded']['payload_hex'].upper() for f in near}
        status = 'unmatched' if not near else 'ambiguous_sensor' if len(ids) != 1 else 'ambiguous_payload' if len(payloads) != 1 else 'linked'
        if not ref.get('fresh'):
            status = 'not_fresh'
        result.append({'reference': ref, 'status': status,
                       'sensor_id_candidate': next(iter(ids)) if len(ids) == 1 else None,
                       'nearest_frame': near[0] if near else None,
                       'nearby_frames': [{'host_unix_s': f['host_unix_s'],
                                          'delta_seconds': f['host_unix_s'] - ref['host_unix_s'],
                                          'payload_hex': f['decoded']['payload_hex']} for f in near]})
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
    ys = [r['reference'][key] for r in rows]
    if len(rows) < 4 or len(set(ys)) < 3:
        return {'status': 'insufficient_points', 'required': '4 linked points and 3 distinct values', 'candidates': []}
    bs = [bytes.fromhex(r['nearest_frame']['decoded']['payload_hex']) for r in rows]
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
                                          'residuals': errors, 'max_leave_one_out_error': max(loo)})
    return {'status': 'candidates_need_independent_validation' if found else 'no_matching_linear_model',
            'tolerance': tolerance, 'candidates': found}


def analyze(frames, references):
    links = associate(frames, references)
    groups = {}
    for link in links:
        if link['status'] == 'linked':
            groups.setdefault(link['sensor_id_candidate'], []).append(link)
    analyses = {}
    for sensor, rows in groups.items():
        data = [bytes.fromhex(r['nearest_frame']['decoded']['payload_hex']) for r in rows]
        analyses[sensor] = {'linked_points': len(rows), 'sensor_id_verified': False,
                           'stable_byte_indices': [i for i in range(9) if len({b[i] for b in data}) == 1],
                           'changing_byte_indices': [i for i in range(9) if len({b[i] for b in data}) > 1],
                           'raw_points': [{'reference': r['reference'], 'bytes': list(b)} for r, b in zip(rows, data)],
                           'pressure': candidates(rows, 'pressure_psi', 0.5),
                           'temperature': candidates(rows, 'temperature_c', 1.0)}
    return {'mapping_verified': False, 'association_window_seconds': 10,
            'association_basis': 'host reception vs user entry; display delay unknown',
            'links': links, 'sensors': analyses,
            'limitations': ['One sensor cannot establish exact ID boundaries.',
                           'Constant bits cannot be assigned flag meanings without controlled evidence.',
                           'Correlated pressure/temperature changes can produce indistinguishable models.',
                           'All models are hypotheses; no firmware mapping is automatically enabled.']}

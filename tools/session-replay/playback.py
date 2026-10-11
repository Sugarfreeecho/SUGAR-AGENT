"""Keep recorded streaming; explicitly simulate text whose stream was not saved."""
import copy
import math
from session_data import ImportProblem


def text_update(wire):
    if wire.get('type') == 'execution_update':
        row = wire.get('update', {})
        if row.get('kind') not in {'reasoning', 'response'}:
            return None
        return str(row.get('execution_id')), row, 'text_delta', 'content'
    kind = wire.get('type', '')
    if kind in {'llm_reasoning', 'llm_response', 'llm_reasoning_delta', 'llm_response_delta'}:
        identity = f"{wire.get('run_id')}:{wire.get('react_iter')}:{kind.removesuffix('_delta')}"
        return identity, wire, 'delta', 'content'
    return None


def playback_segment(segment, simulate=True, characters_per_second=120):
    rate = int(characters_per_second)
    if not 10 <= rate <= 1000:
        raise ImportProblem('模拟速度必须在 10–1000 字/秒之间')
    result = dict(segment)
    result['playback'] = {'mode':'journal', 'synthetic':False, 'characters_per_second':None,
                          'original_duration_ms':segment['duration_ms']}
    if not simulate:
        return result
    delta_times = {}
    for packet in segment['packets']:
        part = text_update(packet['wire'])
        if part and part[1].get(part[2]):
            delta_times.setdefault(part[0], set()).add(packet['at_ms'])
    missing_timing = {key for key, times in delta_times.items() if len(times) == 1}
    packets, previous_text, extra, synthetic = [], {}, 0.0, 0
    chunk_size = max(1, math.ceil(rate * .05))
    for packet in segment['packets']:
        part = text_update(packet['wire'])
        text = ''
        is_delta = part and bool(part[1].get(part[2]))
        if part:
            key, row, delta_key, full_key = part
            if is_delta and key in missing_timing:
                text = str(row[delta_key])
            elif key not in delta_times and full_key in row:
                full = str(row[full_key] or '')
                prior = previous_text.get(key, '')
                text = full[len(prior):] if full.startswith(prior) else full
                previous_text[key] = full
        if text:
            for start in range(0, len(text), chunk_size):
                piece = text[start:start + chunk_size]
                p = copy.deepcopy(packet)
                wire = p['wire']
                if wire.get('type') == 'execution_update':
                    update = wire['update']
                    for field in ('content', 'text', 'ui', 'content_ref'):
                        update.pop(field, None)
                    update.update(text_delta=piece, status='generating', ui_committed=False)
                else:
                    wire.pop('content', None)
                    wire.update(type=wire['type'].removesuffix('_delta') + '_delta', delta=piece, ephemeral=True)
                p.update(at_ms=round(packet['at_ms'] + extra, 3), synthetic=True, original_at_ms=packet['at_ms'])
                packets.append(p)
                synthetic += 1
                extra += len(piece) / rate * 1000
            if is_delta:
                continue
        p = copy.deepcopy(packet)
        p['original_at_ms'] = packet['at_ms']
        p['at_ms'] = round(packet['at_ms'] + extra, 3)
        packets.append(p)
    if synthetic:
        # Use a separate increasing playback cursor for filtering and resume.
        # Source journal seqs remain attached; the journal itself stays intact.
        for index, packet in enumerate(packets, segment['last_seq'] + 1):
            packet['original_seq'] = packet['seq']
            packet['seq'] = index
            packet['wire'].update(runtime_seq=index, seq=index, source_runtime_seq=packet['original_seq'])
        result.update(packets=packets, packet_count=len(packets), duration_ms=packets[-1]['at_ms'],
                      original_timing_source=segment['timing_source'], timing_source='synthetic_text_with_journal',
                      warnings=list(segment['warnings']) + [f'含逐字模拟：{rate} 字/秒；模拟部分不是原始 token 到达时序'])
        result['playback'].update(mode='simulated_text', synthetic=True, characters_per_second=rate, synthetic_packets=synthetic)
    return result

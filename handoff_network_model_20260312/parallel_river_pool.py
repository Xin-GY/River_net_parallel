import itertools
import math
import multiprocessing as mp
import pickle
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

import numpy as np

SNAP_LEFT = 0
SNAP_RIGHT = 1

SNAP_GHOST_LEVEL = 0
SNAP_CELL_LEVEL = 1
SNAP_GHOST_Q = 2
SNAP_CELL_Q = 3
SNAP_GHOST_S = 4
SNAP_CELL_S = 5
SNAP_GHOST_WIDTH = 6
SNAP_CELL_WIDTH = 7
SNAP_BOUNDARY_FACE_LEVEL = 8
SNAP_BOUNDARY_FACE_DISCHARGE = 9
SNAP_BOUNDARY_FACE_AREA = 10
SNAP_BOUNDARY_FACE_WIDTH = 11

SNAP_COMPACT_GHOST_LEVEL = 0
SNAP_COMPACT_CELL_LEVEL = 1
SNAP_COMPACT_GHOST_Q = 2
SNAP_COMPACT_GHOST_S = 3
SNAP_COMPACT_GHOST_WIDTH = 4

NODE_AGG_REAL_SUM = 0
NODE_AGG_REAL_COUNT = 1
NODE_AGG_GHOST_SUM = 2
NODE_AGG_GHOST_COUNT = 3
NODE_AGG_RESIDUAL = 4
NODE_AGG_AC = 5


def _payload_nbytes(value):
    return len(pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))


def _restore_perf_timing(river_names, river_list, slots, restore_map):
    perf = {}
    for slot in slots:
        river = river_list[int(slot)]
        perf[river_names[int(slot)]] = river.consume_perf_timing()
        river.perf_timing_enabled = bool(restore_map[int(slot)])
    return perf


def _enable_perf_timing(river_list, slots):
    restore = {}
    for slot in slots:
        river = river_list[int(slot)]
        restore[int(slot)] = bool(getattr(river, 'perf_timing_enabled', False))
        river.perf_timing_enabled = True
        river.reset_perf_timing()
    return restore


def _advance_local_river_step(river, use_implicit_branch_update=False, save_output=False):
    perf_enabled = bool(getattr(river, 'perf_timing_enabled', False))
    if not perf_enabled:
        river.Caculate_face_U_C()
        river.Caculate_Roe_matrix()
        river.Caculate_source_term_2()
        river.Caculate_Roe_Flux_2()
        if use_implicit_branch_update:
            river.Caculate_impli_trans_coefficient()
            river.Assemble_Flux_impli_trans()
        else:
            river.Assemble_Flux_2()
        river.Update_cell_proprity2()
        if save_output:
            river.maybe_save_result_per_time_step()
        return river.Caculate_CFL_time_for_river_net()

    t0 = time.perf_counter()
    river.Caculate_face_U_C()
    river._record_perf_section('face_uc', time.perf_counter() - t0)
    t0 = time.perf_counter()
    river.Caculate_Roe_matrix()
    river._record_perf_section('roe_matrix', time.perf_counter() - t0)
    t0 = time.perf_counter()
    river.Caculate_source_term_2()
    river._record_perf_section('source_term', time.perf_counter() - t0)
    t0 = time.perf_counter()
    river.Caculate_Roe_Flux_2()
    river._record_perf_section('roe_flux', time.perf_counter() - t0)
    t0 = time.perf_counter()
    if use_implicit_branch_update:
        river.Caculate_impli_trans_coefficient()
        river.Assemble_Flux_impli_trans()
    else:
        river.Assemble_Flux_2()
    river._record_perf_section('assemble', time.perf_counter() - t0)
    t0 = time.perf_counter()
    river.Update_cell_proprity2()
    river._record_perf_section('update', time.perf_counter() - t0)
    if save_output:
        river.maybe_save_result_per_time_step()
    t0 = time.perf_counter()
    dt = river.Caculate_CFL_time_for_river_net()
    river._record_perf_section('cfl_update', time.perf_counter() - t0)
    return dt


def _safe_float(value):
    if value is None:
        return math.nan
    return float(value)


def _lookup_width_from_state(river, idx, area):
    if area <= 0.0:
        return 0.0
    if hasattr(river, '_get_cell_table_ref'):
        tbl = river._get_cell_table_ref(idx)
        if tbl is not None:
            return float(tbl.get_width_by_area(max(area, 1.0e-12)))
    return float(
        river.cross_section_table.get_width_by_area(
            river.cell_sections[idx],
            max(area, 1.0e-12),
        )
    )


def _node_aggregate_from_specs(river_map, specs, g):
    eps_a = 1.0e-12
    aggregates = {}
    for node_name, river_name, side_code, flow_sign in specs:
        river = river_map[river_name]
        if side_code == SNAP_LEFT:
            ghost_idx = 0
            cell_idx = 1
        else:
            ghost_idx = -1
            cell_idx = -2
        ghost_area_raw = float(max(river.S[ghost_idx], 0.0))
        ghost_width = _lookup_width_from_state(river, ghost_idx, ghost_area_raw)
        ghost_area = float(max(ghost_area_raw, eps_a))
        ghost_width = float(max(ghost_width, eps_a))
        ghost_q = float(river.Q[ghost_idx])
        rec = aggregates.setdefault(node_name, [0.0, 0, 0.0, 0, 0.0, 0.0])
        rec[NODE_AGG_REAL_SUM] += float(river.water_level[cell_idx])
        rec[NODE_AGG_REAL_COUNT] += 1
        rec[NODE_AGG_GHOST_SUM] += float(river.water_level[ghost_idx])
        rec[NODE_AGG_GHOST_COUNT] += 1
        rec[NODE_AGG_RESIDUAL] += float(flow_sign) * ghost_q
        ac_term = math.sqrt(g * ghost_area * ghost_width)
        if flow_sign > 0:
            rec[NODE_AGG_AC] += ac_term - ghost_q * ghost_width / ghost_area
        else:
            rec[NODE_AGG_AC] += ac_term + ghost_q * ghost_width / ghost_area
    return aggregates


def _is_monotonic_series(values, tol=1.0e-12):
    if len(values) < 3:
        return True
    diffs = [values[i + 1] - values[i] for i in range(len(values) - 1)]
    nonzero = [d for d in diffs if abs(d) > tol]
    if not nonzero:
        return True
    sign = 1.0 if nonzero[0] > 0.0 else -1.0
    for diff in nonzero[1:]:
        if diff * sign < -tol:
            return False
    return True


def _node_response_tables_from_jobs(river_map, jobs, boundary_kwargs):
    results = {}
    for job in jobs:
        node_name = job['node']
        river = river_map[job['river']]
        side = job['side']
        flow_sign = float(job['flow_sign'])
        etas = [float(v) for v in job['etas']]
        q_series = []
        a_series = []
        t_series = []
        node_rec = results.setdefault(
            node_name,
            {
                'etas': list(etas),
                'residual': [0.0] * len(etas),
                'closure_calls': 0,
                'fast_calls': 0,
                'fast_hits': 0,
                'valid': True,
                'reasons': {},
            },
        )
        for idx, eta in enumerate(etas):
            response = river._evaluate_stage_boundary_response(
                side,
                eta,
                Fr_max=float(boundary_kwargs.get('Fr_max', 0.85)),
                head_gain_factor=float(boundary_kwargs.get('head_gain_factor', 0.65)),
                relax_Q=float(boundary_kwargs.get('relax_Q', 0.4)),
                cap_du_factor=float(boundary_kwargs.get('cap_du_factor', 0.8)),
                cap_dQ_factor=float(boundary_kwargs.get('cap_dQ_factor', 0.7)),
                use_stabilizers=bool(boundary_kwargs.get('use_stabilizers', False)),
                respect_supercritical=bool(boundary_kwargs.get('respect_supercritical', True)),
                stage_on_face=bool(boundary_kwargs.get('stage_on_face', False)),
                update_prev=False,
            )
            node_rec['closure_calls'] += 1
            node_rec['fast_calls'] += 1
            if response.get('mode') == 'cython_fast':
                node_rec['fast_hits'] += 1
            if response.get('status') != 'ok':
                node_rec['valid'] = False
                reason = str(response.get('status'))
                node_rec['reasons'][reason] = int(node_rec['reasons'].get(reason, 0)) + 1
                continue
            q_val = float(response['Qb'])
            a_val = float(response['Ab'])
            t_val = float(response.get('Tb', 0.0))
            q_series.append(q_val)
            a_series.append(a_val)
            t_series.append(t_val)
            node_rec['residual'][idx] += flow_sign * q_val
        if len(q_series) == len(etas):
            if (not _is_monotonic_series(q_series)) or (not _is_monotonic_series(a_series)) or (not _is_monotonic_series(t_series)):
                node_rec['valid'] = False
                node_rec['reasons']['non_monotonic'] = int(node_rec['reasons'].get('non_monotonic', 0)) + 1
    return results


def _river_interface_snapshot(river, mode='full'):
    def pack_end(ghost_idx, cell_idx, face_suffix):
        ghost_area = float(max(river.S[ghost_idx], 0.0))
        if face_suffix == 'left':
            face_level = river.boundary_face_level_left
            face_discharge = river.boundary_face_discharge_left
            face_area = river.boundary_face_area_left
            face_width = river.boundary_face_width_left
        else:
            face_level = river.boundary_face_level_right
            face_discharge = river.boundary_face_discharge_right
            face_area = river.boundary_face_area_right
            face_width = river.boundary_face_width_right
        ghost_width = _lookup_width_from_state(river, ghost_idx, ghost_area)
        if mode == 'compact':
            return (
                float(river.water_level[ghost_idx]),
                float(river.water_level[cell_idx]),
                float(river.Q[ghost_idx]),
                ghost_area,
                ghost_width,
            )
        cell_area = float(max(river.S[cell_idx], 0.0))
        cell_width = _lookup_width_from_state(river, cell_idx, cell_area)
        return (
            float(river.water_level[ghost_idx]),
            float(river.water_level[cell_idx]),
            float(river.Q[ghost_idx]),
            float(river.Q[cell_idx]),
            ghost_area,
            cell_area,
            ghost_width,
            cell_width,
            _safe_float(face_level),
            _safe_float(face_discharge),
            _safe_float(face_area),
            _safe_float(face_width),
        )

    return (
        pack_end(0, 1, 'left'),
        pack_end(-1, -2, 'right'),
    )


def _exact_node_eval_from_plan(river_list, river_names, plan, node_levels, g, snapshot_mode=None, collect_perf=False):
    node_names = plan['node_names']
    node_offsets = plan['node_offsets']
    branch_river_slots = plan['branch_river_slots']
    branch_side_codes = plan['branch_side_codes']
    branch_flow_signs = plan['branch_flow_signs']
    active_river_slots = plan.get('active_river_slots', ())
    snapshot_slots = plan.get('snapshot_slots', ())
    n_nodes = len(node_names)
    aggregates = np.zeros((n_nodes, NODE_AGG_AC + 1), dtype=np.float64)
    apply_count = 0
    apply_time = 0.0
    aggregate_time = 0.0
    snapshot_time = 0.0
    perf = {}

    perf_restore = _enable_perf_timing(river_list, active_river_slots) if collect_perf else None

    for node_id in range(n_nodes):
        level = float(node_levels[node_id])
        node_name = node_names[node_id]
        start = int(node_offsets[node_id])
        end = int(node_offsets[node_id + 1])
        for branch_idx in range(start, end):
            river_slot = int(branch_river_slots[branch_idx])
            river = river_list[river_slot]
            side_code = int(branch_side_codes[branch_idx])
            flow_sign = float(branch_flow_signs[branch_idx])
            if collect_perf:
                t0 = time.perf_counter()
            river.Apply_internal_node_target_level_compiled(
                side_code,
                level,
                node_name=node_name,
                river_name=river_names[river_slot],
            )
            if collect_perf:
                apply_time += time.perf_counter() - t0
                t0 = time.perf_counter()
            real_level, ghost_level, residual_term, ac_term = river.Collect_internal_node_terms_compiled(
                side_code,
                flow_sign,
                g,
            )
            if collect_perf:
                aggregate_time += time.perf_counter() - t0
            rec = aggregates[node_id]
            rec[NODE_AGG_REAL_SUM] += float(real_level)
            rec[NODE_AGG_REAL_COUNT] += 1.0
            rec[NODE_AGG_GHOST_SUM] += float(ghost_level)
            rec[NODE_AGG_GHOST_COUNT] += 1.0
            rec[NODE_AGG_RESIDUAL] += float(residual_term)
            rec[NODE_AGG_AC] += float(ac_term)
            apply_count += 1

    snapshots = None
    if snapshot_mode:
        if collect_perf:
            t0 = time.perf_counter()
        snapshots = {
            river_names[int(slot)]: _river_interface_snapshot(river_list[int(slot)], mode=snapshot_mode)
            for slot in snapshot_slots
        }
        if collect_perf:
            snapshot_time += time.perf_counter() - t0

    if collect_perf:
        perf = _restore_perf_timing(river_names, river_list, active_river_slots, perf_restore)

    return {
        'aggregates': aggregates,
        'snapshots': snapshots,
        'perf': perf,
        'meta': {
            'apply_time': float(apply_time),
            'aggregate_time': float(aggregate_time),
            'snapshot_time': float(snapshot_time),
            'apply_count': int(apply_count),
        },
    }


def _worker_main(connection, rivers):
    river_map = dict(rivers)
    river_names = list(river_map.keys())
    river_list = [river_map[name] for name in river_names]
    exact_node_plan = None
    while True:
        task_id, command, payload = connection.recv()
        try:
            if command == 'shutdown':
                connection.send((task_id, 'ok', None))
                return

            if command == 'call_batch':
                results = {}
                collect = bool(payload.get('collect', False))
                for call in payload['calls']:
                    river = river_map[call['river']]
                    method = getattr(river, call['method'])
                    result = method(*call.get('args', ()), **call.get('kwargs', {}))
                    if collect:
                        results[call['river']] = result
                connection.send((task_id, 'ok', results if collect else None))
                continue

            if command == 'interface_snapshots':
                names = payload['names']
                mode = payload.get('snapshot_mode', 'full')
                connection.send(
                    (
                        task_id,
                        'ok',
                        {name: _river_interface_snapshot(river_map[name], mode=mode) for name in names},
                    )
                )
                continue

            if command == 'call_batch_and_interface_snapshots':
                collect_perf = bool(payload.get('collect_perf', False))
                if not collect_perf:
                    for call in payload['calls']:
                        river = river_map[call['river']]
                        method = getattr(river, call['method'])
                        method(*call.get('args', ()), **call.get('kwargs', {}))
                    names = payload['names']
                    mode = payload.get('snapshot_mode', 'full')
                    connection.send(
                        (
                            task_id,
                            'ok',
                            {name: _river_interface_snapshot(river_map[name], mode=mode) for name in names},
                        )
                    )
                    continue
                perf_restore = {}
                apply_time = 0.0
                snapshot_time = 0.0
                for call in payload['calls']:
                    name = call['river']
                    if name in perf_restore:
                        continue
                    perf_restore[name] = getattr(river_map[name], 'perf_timing_enabled', False)
                    river_map[name].perf_timing_enabled = True
                    river_map[name].reset_perf_timing()
                for call in payload['calls']:
                    river = river_map[call['river']]
                    method = getattr(river, call['method'])
                    t0 = time.perf_counter()
                    method(*call.get('args', ()), **call.get('kwargs', {}))
                    apply_time += time.perf_counter() - t0
                names = payload['names']
                mode = payload.get('snapshot_mode', 'full')
                t0 = time.perf_counter()
                snapshots = {name: _river_interface_snapshot(river_map[name], mode=mode) for name in names}
                snapshot_time += time.perf_counter() - t0
                perf = {}
                for name, restore in perf_restore.items():
                    perf[name] = river_map[name].consume_perf_timing()
                    river_map[name].perf_timing_enabled = restore
                payload_out = {
                    'snapshots': snapshots,
                    'perf': perf,
                    'meta': {
                        'apply_time': float(apply_time),
                        'aggregate_time': 0.0,
                        'snapshot_time': float(snapshot_time),
                        'apply_count': int(len(payload['calls'])),
                    },
                }
                connection.send((task_id, 'ok', payload_out))
                continue

            if command == 'advance_local_step':
                results = {}
                save_names = set(payload.get('save_names', ()))
                use_implicit_branch_update = bool(payload.get('use_implicit_branch_update', False))
                collect_perf = bool(payload.get('collect_perf', False))
                if not collect_perf:
                    for name in payload['names']:
                        results[name] = _advance_local_river_step(
                            river_map[name],
                            use_implicit_branch_update=use_implicit_branch_update,
                            save_output=name in save_names,
                        )
                    connection.send((task_id, 'ok', results))
                    continue
                for name in payload['names']:
                    river = river_map[name]
                    perf_restore = getattr(river, 'perf_timing_enabled', False)
                    river.perf_timing_enabled = True
                    river.reset_perf_timing()
                    dt_value = _advance_local_river_step(
                        river,
                        use_implicit_branch_update=use_implicit_branch_update,
                        save_output=name in save_names,
                    )
                    results[name] = {
                        'dt': dt_value,
                        'perf': river.consume_perf_timing(),
                    }
                    river.perf_timing_enabled = perf_restore
                connection.send((task_id, 'ok', results))
                continue

            if command == 'call_batch_and_node_aggregates':
                collect_perf = bool(payload.get('collect_perf', False))
                if not collect_perf:
                    for call in payload['calls']:
                        river = river_map[call['river']]
                        method = getattr(river, call['method'])
                        method(*call.get('args', ()), **call.get('kwargs', {}))
                    aggregates = _node_aggregate_from_specs(
                        river_map,
                        payload.get('node_specs', ()),
                        float(payload['g']),
                    )
                    connection.send((task_id, 'ok', aggregates))
                    continue
                perf_restore = {}
                apply_time = 0.0
                aggregate_time = 0.0
                for call in payload['calls']:
                    name = call['river']
                    if name in perf_restore:
                        continue
                    perf_restore[name] = getattr(river_map[name], 'perf_timing_enabled', False)
                    river_map[name].perf_timing_enabled = True
                    river_map[name].reset_perf_timing()
                for call in payload['calls']:
                    river = river_map[call['river']]
                    method = getattr(river, call['method'])
                    t0 = time.perf_counter()
                    method(*call.get('args', ()), **call.get('kwargs', {}))
                    apply_time += time.perf_counter() - t0
                t0 = time.perf_counter()
                aggregates = _node_aggregate_from_specs(
                    river_map,
                    payload.get('node_specs', ()),
                    float(payload['g']),
                )
                aggregate_time += time.perf_counter() - t0
                perf = {}
                for name, restore in perf_restore.items():
                    perf[name] = river_map[name].consume_perf_timing()
                    river_map[name].perf_timing_enabled = restore
                payload_out = {
                    'aggregates': aggregates,
                    'perf': perf,
                    'meta': {
                        'apply_time': float(apply_time),
                        'aggregate_time': float(aggregate_time),
                        'snapshot_time': 0.0,
                        'apply_count': int(len(payload['calls'])),
                    },
                }
                connection.send((task_id, 'ok', payload_out))
                continue

            if command == 'configure_exact_node_plan':
                exact_node_plan = payload.get('plan')
                connection.send((task_id, 'ok', None))
                continue

            if command == 'exact_node_eval_batch':
                if exact_node_plan is None:
                    raise RuntimeError('exact node plan is not configured')
                payload_out = _exact_node_eval_from_plan(
                    river_list,
                    river_names,
                    exact_node_plan,
                    payload.get('node_levels', ()),
                    float(payload['g']),
                    snapshot_mode=payload.get('snapshot_mode'),
                    collect_perf=bool(payload.get('collect_perf', False)),
                )
                connection.send((task_id, 'ok', payload_out))
                continue

            if command == 'node_response_tables':
                connection.send(
                    (
                        task_id,
                        'ok',
                        _node_response_tables_from_jobs(
                            river_map,
                            payload.get('jobs', ()),
                            payload.get('boundary_kwargs', {}),
                        ),
                    )
                )
                continue

            if command == 'get_rivers':
                names = payload['names']
                connection.send(
                    (
                        task_id,
                        'ok',
                        {name: river_map[name] for name in names},
                    )
                )
                continue

            raise ValueError(f'unknown worker command: {command}')
        except Exception as exc:
            connection.send(
                (
                    task_id,
                    'error',
                    {
                        'message': str(exc),
                        'traceback': traceback.format_exc(),
                    },
                )
            )


class PersistentRiverThreadPool:
    """
    Persistent thread pool for river-local phases.

    This backend keeps the original in-memory River objects in the main
    process, so serial boundary/junction coupling logic can remain unchanged.
    """

    def __init__(self, river_items, n_workers, start_method=None):
        self.river_items = list(river_items)
        self.n_workers = max(1, min(int(n_workers), len(self.river_items)))
        self.start_method = start_method
        self._river_map = dict(self.river_items)
        self._river_names = [name for name, _ in self.river_items]
        self._river_list = [self._river_map[name] for name in self._river_names]
        self._exact_node_plan = None
        self._executor = ThreadPoolExecutor(
            max_workers=self.n_workers,
            thread_name_prefix='rivernet',
        )

    def call_batch(self, calls, collect=False):
        futures = []
        for call in calls:
            river = self._river_map[call['river']]
            method = getattr(river, call['method'])
            future = self._executor.submit(
                method,
                *call.get('args', ()),
                **call.get('kwargs', {}),
            )
            futures.append((call['river'], future))

        if collect:
            results = {}
            for river_name, future in futures:
                results[river_name] = future.result()
            return results

        for _, future in futures:
            future.result()
        return None

    def call_all(self, method_name, names=None, args=(), kwargs=None, collect=False):
        kwargs = {} if kwargs is None else dict(kwargs)
        selected = names if names is not None else [name for name, _ in self.river_items]
        calls = [
            {
                'river': name,
                'method': method_name,
                'args': tuple(args),
                'kwargs': kwargs,
            }
            for name in selected
        ]
        return self.call_batch(calls, collect=collect)

    def get_rivers(self, names=None):
        selected = names if names is not None else [name for name, _ in self.river_items]
        return {name: self._river_map[name] for name in selected}

    def worker_river_groups(self):
        return [{'id': 0, 'rivers': list(self._river_names)}]

    def call_batch_and_interface_snapshots(self, calls, names=None, snapshot_mode='full', collect_perf=False):
        selected = names if names is not None else [name for name, _ in self.river_items]
        if not collect_perf:
            self.call_batch(calls, collect=False)
            return {name: _river_interface_snapshot(self._river_map[name], mode=snapshot_mode) for name in selected}
        perf_restore = {}
        for call in calls:
            name = call['river']
            river = self._river_map[name]
            if name in perf_restore:
                continue
            perf_restore[name] = getattr(river, 'perf_timing_enabled', False)
            river.perf_timing_enabled = True
            river.reset_perf_timing()
        self.call_batch(calls, collect=False)
        snapshots = {name: _river_interface_snapshot(self._river_map[name], mode=snapshot_mode) for name in selected}
        perf = {}
        for name, restore in perf_restore.items():
            perf[name] = self._river_map[name].consume_perf_timing()
            self._river_map[name].perf_timing_enabled = restore
        return {
            'snapshots': snapshots,
            'perf': perf,
            'meta': {
                'submit_time': 0.0,
                'collect_time': 0.0,
                'merge_time': 0.0,
                'sent_bytes': 0,
                'recv_bytes': 0,
                'round_trips': 1,
                'worker_apply_time': 0.0,
                'worker_aggregate_time': 0.0,
                'worker_snapshot_time': 0.0,
                'apply_count': int(len(calls)),
            },
        }

    def advance_local_step(self, names=None, use_implicit_branch_update=False, save_names=None, collect_perf=False):
        selected = names if names is not None else [name for name, _ in self.river_items]
        save_set = set(save_names or ())
        if not collect_perf:
            futures = []
            for name in selected:
                future = self._executor.submit(
                    _advance_local_river_step,
                    self._river_map[name],
                    use_implicit_branch_update=bool(use_implicit_branch_update),
                    save_output=name in save_set,
                )
                futures.append((name, future))

            results = {}
            for name, future in futures:
                results[name] = future.result()
            return results
        futures = []
        for name in selected:
            river = self._river_map[name]
            perf_restore = getattr(river, 'perf_timing_enabled', False)
            river.perf_timing_enabled = True
            river.reset_perf_timing()
            future = self._executor.submit(
                _advance_local_river_step,
                river,
                use_implicit_branch_update=bool(use_implicit_branch_update),
                save_output=name in save_set,
            )
            futures.append((name, river, perf_restore, future))

        results = {}
        for name, river, perf_restore, future in futures:
            dt_value = future.result()
            if collect_perf:
                results[name] = {
                    'dt': dt_value,
                    'perf': river.consume_perf_timing(),
                }
                river.perf_timing_enabled = perf_restore
            else:
                results[name] = dt_value
        return results

    def call_batch_and_node_aggregates(self, calls, node_specs, g, collect_perf=False):
        if not collect_perf:
            self.call_batch(calls, collect=False)
            return _node_aggregate_from_specs(self._river_map, node_specs, float(g))
        perf_restore = {}
        for call in calls:
            name = call['river']
            river = self._river_map[name]
            if name in perf_restore:
                continue
            perf_restore[name] = getattr(river, 'perf_timing_enabled', False)
            river.perf_timing_enabled = True
            river.reset_perf_timing()
        self.call_batch(calls, collect=False)
        aggregates = _node_aggregate_from_specs(self._river_map, node_specs, float(g))
        perf = {}
        for name, restore in perf_restore.items():
            perf[name] = self._river_map[name].consume_perf_timing()
            self._river_map[name].perf_timing_enabled = restore
        return {
            'aggregates': aggregates,
            'perf': perf,
            'meta': {
                'submit_time': 0.0,
                'collect_time': 0.0,
                'merge_time': 0.0,
                'sent_bytes': 0,
                'recv_bytes': 0,
                'round_trips': 1,
                'worker_apply_time': 0.0,
                'worker_aggregate_time': 0.0,
                'worker_snapshot_time': 0.0,
                'apply_count': int(len(calls)),
            },
        }

    def configure_exact_node_plan(self, worker_plans):
        self._exact_node_plan = worker_plans.get(0)

    def call_exact_node_eval_batch(self, node_levels, g, snapshot_mode=None, collect_perf=False):
        if self._exact_node_plan is None:
            raise RuntimeError('exact node plan is not configured')
        payload = _exact_node_eval_from_plan(
            self._river_list,
            self._river_names,
            self._exact_node_plan,
            [float(v) for v in node_levels],
            float(g),
            snapshot_mode=snapshot_mode,
            collect_perf=bool(collect_perf),
        )
        if not collect_perf:
            return payload
        payload['meta'].update({
            'submit_time': 0.0,
            'collect_time': 0.0,
            'merge_time': 0.0,
            'sent_bytes': 0,
            'recv_bytes': 0,
            'round_trips': 1,
        })
        return payload

    def node_response_tables(self, jobs, boundary_kwargs):
        return _node_response_tables_from_jobs(self._river_map, jobs, boundary_kwargs)

    def shutdown(self):
        self._executor.shutdown(wait=True, cancel_futures=False)


class PersistentRiverProcessPool:
    def __init__(self, river_items, n_workers, start_method='fork'):
        self.river_items = list(river_items)
        self.n_workers = max(int(n_workers), 1)
        self.start_method = start_method
        self._ctx = mp.get_context(start_method)
        self._task_counter = itertools.count()
        self._workers = []
        self._river_to_worker = {}
        self._start()

    def _partition_rivers(self):
        n_workers = min(self.n_workers, len(self.river_items))
        buckets = [{'load': 0, 'items': []} for _ in range(n_workers)]
        items = sorted(self.river_items, key=lambda item: int(item[1].cell_num), reverse=True)
        for name, river in items:
            bucket = min(buckets, key=lambda x: x['load'])
            bucket['items'].append((name, river))
            bucket['load'] += int(river.cell_num)
        return [bucket['items'] for bucket in buckets]

    def _start(self):
        for worker_id, items in enumerate(self._partition_rivers()):
            parent_conn, child_conn = self._ctx.Pipe(duplex=True)
            proc = self._ctx.Process(
                target=_worker_main,
                args=(child_conn, dict(items)),
                daemon=True,
            )
            proc.start()
            child_conn.close()
            self._workers.append(
                {
                    'id': worker_id,
                    'process': proc,
                    'connection': parent_conn,
                    'rivers': [name for name, _ in items],
                }
            )
            for name, _ in items:
                self._river_to_worker[name] = worker_id

    def _submit(self, worker, command, payload):
        task_id = next(self._task_counter)
        worker['connection'].send((task_id, command, payload))
        return task_id

    def _collect(self, worker, task_id):
        recv_task_id, status, payload = worker['connection'].recv()
        if recv_task_id != task_id:
            raise RuntimeError(f'worker task mismatch: expected {task_id}, got {recv_task_id}')
        if status != 'ok':
            raise RuntimeError(payload['traceback'])
        return payload

    def _group_names(self, names=None):
        if names is None:
            names = [name for name, _ in self.river_items]
        grouped = {worker['id']: [] for worker in self._workers}
        for name in names:
            grouped[self._river_to_worker[name]].append(name)
        return {wid: vals for wid, vals in grouped.items() if vals}

    def worker_river_groups(self):
        return [
            {
                'id': int(worker['id']),
                'rivers': list(worker['rivers']),
            }
            for worker in self._workers
        ]

    def call_batch(self, calls, collect=False):
        grouped = {worker['id']: [] for worker in self._workers}
        for call in calls:
            grouped[self._river_to_worker[call['river']]].append(call)

        pending = []
        for worker in self._workers:
            worker_calls = grouped[worker['id']]
            if not worker_calls:
                continue
            task_id = self._submit(
                worker,
                'call_batch',
                {'calls': worker_calls, 'collect': bool(collect)},
            )
            pending.append((worker, task_id))

        results = {}
        for worker, task_id in pending:
            payload = self._collect(worker, task_id)
            if collect and payload:
                results.update(payload)
        return results if collect else None

    def call_all(self, method_name, names=None, args=(), kwargs=None, collect=False):
        kwargs = {} if kwargs is None else dict(kwargs)
        selected = names if names is not None else [name for name, _ in self.river_items]
        calls = [
            {
                'river': name,
                'method': method_name,
                'args': tuple(args),
                'kwargs': kwargs,
            }
            for name in selected
        ]
        return self.call_batch(calls, collect=collect)

    def get_interface_snapshots(self, names=None, snapshot_mode='full'):
        grouped = self._group_names(names)
        pending = []
        for worker in self._workers:
            worker_names = grouped.get(worker['id'])
            if not worker_names:
                continue
            task_id = self._submit(
                worker,
                'interface_snapshots',
                {'names': worker_names, 'snapshot_mode': snapshot_mode},
            )
            pending.append((worker, task_id))

        results = {}
        for worker, task_id in pending:
            results.update(self._collect(worker, task_id))
        return results

    def call_batch_and_interface_snapshots(self, calls, names=None, snapshot_mode='full', collect_perf=False):
        if not collect_perf:
            grouped_calls = {worker['id']: [] for worker in self._workers}
            for call in calls:
                grouped_calls[self._river_to_worker[call['river']]].append(call)

            grouped_names = self._group_names(names)
            pending = []
            for worker in self._workers:
                worker_calls = grouped_calls[worker['id']]
                worker_names = grouped_names.get(worker['id'])
                if not worker_calls and not worker_names:
                    continue
                task_id = self._submit(
                    worker,
                    'call_batch_and_interface_snapshots',
                    {
                        'calls': worker_calls,
                        'names': worker_names or [],
                        'snapshot_mode': snapshot_mode,
                    },
                )
                pending.append((worker, task_id))

            results = {}
            for worker, task_id in pending:
                results.update(self._collect(worker, task_id))
            return results

        grouped_calls = {worker['id']: [] for worker in self._workers}
        for call in calls:
            grouped_calls[self._river_to_worker[call['river']]].append(call)

        grouped_names = self._group_names(names)
        pending = []
        submit_time = 0.0
        sent_bytes = 0
        for worker in self._workers:
            worker_calls = grouped_calls[worker['id']]
            worker_names = grouped_names.get(worker['id'])
            if not worker_calls and not worker_names:
                continue
            payload = {
                'calls': worker_calls,
                'names': worker_names or [],
                'snapshot_mode': snapshot_mode,
                'collect_perf': bool(collect_perf),
            }
            if collect_perf:
                sent_bytes += _payload_nbytes(payload)
            t0 = time.perf_counter() if collect_perf else 0.0
            task_id = self._submit(
                worker,
                'call_batch_and_interface_snapshots',
                payload,
            )
            if collect_perf:
                submit_time += time.perf_counter() - t0
            pending.append((worker, task_id))

        results = {}
        perf = {}
        meta = {
            'submit_time': float(submit_time),
            'collect_time': 0.0,
            'merge_time': 0.0,
            'sent_bytes': int(sent_bytes),
            'recv_bytes': 0,
            'round_trips': int(len(pending)),
            'worker_apply_time': 0.0,
            'worker_aggregate_time': 0.0,
            'worker_snapshot_time': 0.0,
            'apply_count': 0,
        }
        for worker, task_id in pending:
            t0 = time.perf_counter() if collect_perf else 0.0
            payload = self._collect(worker, task_id)
            if collect_perf:
                meta['collect_time'] += time.perf_counter() - t0
                meta['recv_bytes'] += _payload_nbytes(payload)
            if collect_perf:
                worker_meta = payload.get('meta', {})
                meta['worker_apply_time'] += float(worker_meta.get('apply_time', 0.0))
                meta['worker_aggregate_time'] += float(worker_meta.get('aggregate_time', 0.0))
                meta['worker_snapshot_time'] += float(worker_meta.get('snapshot_time', 0.0))
                meta['apply_count'] += int(worker_meta.get('apply_count', 0))
                t0 = time.perf_counter()
                results.update(payload.get('snapshots', {}))
                perf.update(payload.get('perf', {}))
                meta['merge_time'] += time.perf_counter() - t0
            else:
                results.update(payload)
        return {'snapshots': results, 'perf': perf, 'meta': meta} if collect_perf else results

    def advance_local_step(self, names=None, use_implicit_branch_update=False, save_names=None, collect_perf=False):
        grouped_names = self._group_names(names)
        save_set = set(save_names or ())
        if not collect_perf:
            pending = []
            for worker in self._workers:
                worker_names = grouped_names.get(worker['id'])
                if not worker_names:
                    continue
                worker_save_names = [name for name in worker_names if name in save_set]
                task_id = self._submit(
                    worker,
                    'advance_local_step',
                    {
                        'names': worker_names,
                        'save_names': worker_save_names,
                        'use_implicit_branch_update': bool(use_implicit_branch_update),
                    },
                )
                pending.append((worker, task_id))

            results = {}
            for worker, task_id in pending:
                results.update(self._collect(worker, task_id))
            return results

        pending = []
        for worker in self._workers:
            worker_names = grouped_names.get(worker['id'])
            if not worker_names:
                continue
            worker_save_names = [name for name in worker_names if name in save_set]
            task_id = self._submit(
                worker,
                'advance_local_step',
                {
                    'names': worker_names,
                    'save_names': worker_save_names,
                    'use_implicit_branch_update': bool(use_implicit_branch_update),
                    'collect_perf': bool(collect_perf),
                },
            )
            pending.append((worker, task_id))

        results = {}
        for worker, task_id in pending:
            results.update(self._collect(worker, task_id))
        return results

    def call_batch_and_node_aggregates(self, calls, node_specs, g, collect_perf=False):
        grouped_calls = {worker['id']: [] for worker in self._workers}
        for call in calls:
            grouped_calls[self._river_to_worker[call['river']]].append(call)

        grouped_specs = {worker['id']: [] for worker in self._workers}
        for spec in node_specs:
            grouped_specs[self._river_to_worker[spec[1]]].append(spec)

        if not collect_perf:
            pending = []
            for worker in self._workers:
                worker_calls = grouped_calls[worker['id']]
                worker_specs = grouped_specs[worker['id']]
                if not worker_calls and not worker_specs:
                    continue
                task_id = self._submit(
                    worker,
                    'call_batch_and_node_aggregates',
                    {
                        'calls': worker_calls,
                        'node_specs': worker_specs,
                        'g': float(g),
                    },
                )
                pending.append((worker, task_id))

            results = {}
            for worker, task_id in pending:
                payload = self._collect(worker, task_id)
                for node_name, values in payload.items():
                    rec = results.setdefault(node_name, [0.0, 0, 0.0, 0, 0.0, 0.0])
                    for idx, value in enumerate(values):
                        rec[idx] += value
            return results

        pending = []
        submit_time = 0.0
        sent_bytes = 0
        for worker in self._workers:
            worker_calls = grouped_calls[worker['id']]
            worker_specs = grouped_specs[worker['id']]
            if not worker_calls and not worker_specs:
                continue
            payload = {
                'calls': worker_calls,
                'node_specs': worker_specs,
                'g': float(g),
                'collect_perf': bool(collect_perf),
            }
            if collect_perf:
                sent_bytes += _payload_nbytes(payload)
            t0 = time.perf_counter() if collect_perf else 0.0
            task_id = self._submit(
                worker,
                'call_batch_and_node_aggregates',
                payload,
            )
            if collect_perf:
                submit_time += time.perf_counter() - t0
            pending.append((worker, task_id))

        results = {}
        perf = {}
        meta = {
            'submit_time': float(submit_time),
            'collect_time': 0.0,
            'merge_time': 0.0,
            'sent_bytes': int(sent_bytes),
            'recv_bytes': 0,
            'round_trips': int(len(pending)),
            'worker_apply_time': 0.0,
            'worker_aggregate_time': 0.0,
            'worker_snapshot_time': 0.0,
            'apply_count': 0,
        }
        for worker, task_id in pending:
            t0 = time.perf_counter() if collect_perf else 0.0
            payload = self._collect(worker, task_id)
            if collect_perf:
                meta['collect_time'] += time.perf_counter() - t0
                meta['recv_bytes'] += _payload_nbytes(payload)
                worker_meta = payload.get('meta', {})
                meta['worker_apply_time'] += float(worker_meta.get('apply_time', 0.0))
                meta['worker_aggregate_time'] += float(worker_meta.get('aggregate_time', 0.0))
                meta['worker_snapshot_time'] += float(worker_meta.get('snapshot_time', 0.0))
                meta['apply_count'] += int(worker_meta.get('apply_count', 0))
                perf.update(payload.get('perf', {}))
                payload = payload.get('aggregates', {})
                t0 = time.perf_counter()
            for node_name, values in payload.items():
                rec = results.setdefault(node_name, [0.0, 0, 0.0, 0, 0.0, 0.0])
                for idx, value in enumerate(values):
                    rec[idx] += value
            if collect_perf:
                meta['merge_time'] += time.perf_counter() - t0
        return {'aggregates': results, 'perf': perf, 'meta': meta} if collect_perf else results

    def node_response_tables(self, jobs, boundary_kwargs):
        grouped_jobs = {worker['id']: [] for worker in self._workers}
        for job in jobs:
            grouped_jobs[self._river_to_worker[job['river']]].append(job)

        pending = []
        for worker in self._workers:
            worker_jobs = grouped_jobs[worker['id']]
            if not worker_jobs:
                continue
            task_id = self._submit(
                worker,
                'node_response_tables',
                {
                    'jobs': worker_jobs,
                    'boundary_kwargs': dict(boundary_kwargs),
                },
            )
            pending.append((worker, task_id))

        results = {}
        for worker, task_id in pending:
            payload = self._collect(worker, task_id)
            for node_name, rec in payload.items():
                merged = results.setdefault(
                    node_name,
                    {
                        'etas': list(rec.get('etas', rec.get('eta', ()))),
                        'residual': [0.0] * len(rec['residual']),
                        'closure_calls': 0,
                        'fast_calls': 0,
                        'fast_hits': 0,
                        'valid': True,
                        'reasons': {},
                    },
                )
                for idx, value in enumerate(rec['residual']):
                    merged['residual'][idx] += float(value)
                merged['closure_calls'] += int(rec['closure_calls'])
                merged['fast_calls'] += int(rec['fast_calls'])
                merged['fast_hits'] += int(rec['fast_hits'])
                merged['valid'] = bool(merged['valid'] and rec['valid'])
                for reason, count in rec.get('reasons', {}).items():
                    merged['reasons'][reason] = int(merged['reasons'].get(reason, 0)) + int(count)
        return results

    def configure_exact_node_plan(self, worker_plans):
        pending = []
        for worker in self._workers:
            plan = worker_plans.get(worker['id'])
            if plan is None:
                continue
            task_id = self._submit(
                worker,
                'configure_exact_node_plan',
                {'plan': plan},
            )
            pending.append((worker, task_id))
        for worker, task_id in pending:
            self._collect(worker, task_id)

    def call_exact_node_eval_batch(self, node_levels, g, snapshot_mode=None, collect_perf=False):
        pending = []
        submit_time = 0.0
        sent_bytes = 0
        payload_base = {
            'node_levels': [float(v) for v in node_levels],
            'g': float(g),
            'snapshot_mode': snapshot_mode,
            'collect_perf': bool(collect_perf),
        }
        for worker in self._workers:
            if collect_perf:
                sent_bytes += _payload_nbytes(payload_base)
                t0 = time.perf_counter()
            task_id = self._submit(worker, 'exact_node_eval_batch', payload_base)
            if collect_perf:
                submit_time += time.perf_counter() - t0
            pending.append((worker, task_id))

        aggregates = None
        snapshots = {}
        perf = {}
        meta = {
            'submit_time': float(submit_time),
            'collect_time': 0.0,
            'merge_time': 0.0,
            'sent_bytes': int(sent_bytes),
            'recv_bytes': 0,
            'round_trips': int(len(pending)),
            'worker_apply_time': 0.0,
            'worker_aggregate_time': 0.0,
            'worker_snapshot_time': 0.0,
            'apply_count': 0,
        }
        for worker, task_id in pending:
            t0 = time.perf_counter() if collect_perf else 0.0
            payload = self._collect(worker, task_id)
            if collect_perf:
                meta['collect_time'] += time.perf_counter() - t0
                meta['recv_bytes'] += _payload_nbytes(payload)
                worker_meta = payload.get('meta', {})
                meta['worker_apply_time'] += float(worker_meta.get('apply_time', 0.0))
                meta['worker_aggregate_time'] += float(worker_meta.get('aggregate_time', 0.0))
                meta['worker_snapshot_time'] += float(worker_meta.get('snapshot_time', 0.0))
                meta['apply_count'] += int(worker_meta.get('apply_count', 0))
                t0 = time.perf_counter()
            worker_agg = payload['aggregates']
            if aggregates is None:
                aggregates = np.array(worker_agg, dtype=np.float64, copy=True)
            else:
                aggregates += worker_agg
            worker_snapshots = payload.get('snapshots') or {}
            if worker_snapshots:
                snapshots.update(worker_snapshots)
            perf.update(payload.get('perf', {}))
            if collect_perf:
                meta['merge_time'] += time.perf_counter() - t0

        if aggregates is None:
            aggregates = np.zeros((0, NODE_AGG_AC + 1), dtype=np.float64)
        return {
            'aggregates': aggregates,
            'snapshots': snapshots,
            'perf': perf,
            'meta': meta,
        }

    def get_rivers(self, names=None):
        grouped = self._group_names(names)
        pending = []
        for worker in self._workers:
            worker_names = grouped.get(worker['id'])
            if not worker_names:
                continue
            task_id = self._submit(worker, 'get_rivers', {'names': worker_names})
            pending.append((worker, task_id))

        results = {}
        for worker, task_id in pending:
            results.update(self._collect(worker, task_id))
        return results

    def shutdown(self):
        pending = []
        for worker in self._workers:
            task_id = self._submit(worker, 'shutdown', {})
            pending.append((worker, task_id))
        for worker, task_id in pending:
            self._collect(worker, task_id)
            worker['connection'].close()
            worker['process'].join(timeout=5.0)
            if worker['process'].is_alive():
                worker['process'].terminate()
                worker['process'].join(timeout=1.0)
        self._workers.clear()
        self._river_to_worker.clear()

import itertools
import math
import multiprocessing as mp
import traceback
from concurrent.futures import ThreadPoolExecutor

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


def _advance_local_river_step(river, use_implicit_branch_update=False, save_output=False):
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


def _safe_float(value):
    if value is None:
        return math.nan
    return float(value)


def _node_aggregate_from_specs(river_map, specs, g):
    eps_a = 1.0e-12
    tiny = 1.0e-12
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
        ghost_width = 0.0
        if ghost_area_raw > 0.0:
            ghost_width = float(
                river.cross_section_table.get_width_by_area(
                    river.cell_sections[ghost_idx],
                    max(ghost_area_raw, tiny),
                )
            )
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


def _river_interface_snapshot(river, mode='full'):
    tiny = 1.0e-12

    def pack_end(ghost_idx, cell_idx, face_suffix):
        ghost_area = float(max(river.S[ghost_idx], 0.0))
        ghost_width = 0.0
        if ghost_area > 0.0:
            ghost_width = float(
                river.cross_section_table.get_width_by_area(
                    river.cell_sections[ghost_idx],
                    max(ghost_area, tiny),
                )
            )
        if mode == 'compact':
            return (
                float(river.water_level[ghost_idx]),
                float(river.water_level[cell_idx]),
                float(river.Q[ghost_idx]),
                ghost_area,
                ghost_width,
            )
        cell_area = float(max(river.S[cell_idx], 0.0))
        cell_width = 0.0
        if cell_area > 0.0:
            cell_width = float(
                river.cross_section_table.get_width_by_area(
                    river.cell_sections[cell_idx],
                    max(cell_area, tiny),
                )
            )
        return (
            float(river.water_level[ghost_idx]),
            float(river.water_level[cell_idx]),
            float(river.Q[ghost_idx]),
            float(river.Q[cell_idx]),
            ghost_area,
            cell_area,
            ghost_width,
            cell_width,
            _safe_float(getattr(river, f'boundary_face_level_{face_suffix}', None)),
            _safe_float(getattr(river, f'boundary_face_discharge_{face_suffix}', None)),
            _safe_float(getattr(river, f'boundary_face_area_{face_suffix}', None)),
            _safe_float(getattr(river, f'boundary_face_width_{face_suffix}', None)),
        )

    return (
        pack_end(0, 1, 'left'),
        pack_end(-1, -2, 'right'),
    )


def _worker_main(connection, rivers):
    river_map = dict(rivers)
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

            if command == 'advance_local_step':
                results = {}
                save_names = set(payload.get('save_names', ()))
                use_implicit_branch_update = bool(payload.get('use_implicit_branch_update', False))
                for name in payload['names']:
                    results[name] = _advance_local_river_step(
                        river_map[name],
                        use_implicit_branch_update=use_implicit_branch_update,
                        save_output=name in save_names,
                    )
                connection.send((task_id, 'ok', results))
                continue

            if command == 'call_batch_and_node_aggregates':
                for call in payload['calls']:
                    river = river_map[call['river']]
                    method = getattr(river, call['method'])
                    method(*call.get('args', ()), **call.get('kwargs', {}))
                connection.send(
                    (
                        task_id,
                        'ok',
                        _node_aggregate_from_specs(
                            river_map,
                            payload.get('node_specs', ()),
                            float(payload['g']),
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

    def call_batch_and_interface_snapshots(self, calls, names=None, snapshot_mode='full'):
        selected = names if names is not None else [name for name, _ in self.river_items]
        self.call_batch(calls, collect=False)
        return {name: _river_interface_snapshot(self._river_map[name], mode=snapshot_mode) for name in selected}

    def advance_local_step(self, names=None, use_implicit_branch_update=False, save_names=None):
        selected = names if names is not None else [name for name, _ in self.river_items]
        save_set = set(save_names or ())
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

    def call_batch_and_node_aggregates(self, calls, node_specs, g):
        self.call_batch(calls, collect=False)
        return _node_aggregate_from_specs(self._river_map, node_specs, float(g))

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

    def call_batch_and_interface_snapshots(self, calls, names=None, snapshot_mode='full'):
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

    def advance_local_step(self, names=None, use_implicit_branch_update=False, save_names=None):
        grouped_names = self._group_names(names)
        save_set = set(save_names or ())
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

    def call_batch_and_node_aggregates(self, calls, node_specs, g):
        grouped_calls = {worker['id']: [] for worker in self._workers}
        for call in calls:
            grouped_calls[self._river_to_worker[call['river']]].append(call)

        grouped_specs = {worker['id']: [] for worker in self._workers}
        for spec in node_specs:
            grouped_specs[self._river_to_worker[spec[1]]].append(spec)

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

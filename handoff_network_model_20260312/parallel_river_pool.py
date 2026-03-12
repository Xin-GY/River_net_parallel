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


def _safe_float(value):
    if value is None:
        return math.nan
    return float(value)


def _river_interface_snapshot(river):
    tiny = 1.0e-12

    def pack_end(ghost_idx, cell_idx, face_suffix):
        ghost_area = float(max(river.S[ghost_idx], 0.0))
        cell_area = float(max(river.S[cell_idx], 0.0))
        ghost_width = 0.0
        cell_width = 0.0
        if ghost_area > 0.0:
            ghost_width = float(
                river.cross_section_table.get_width_by_area(
                    river.cell_sections[ghost_idx],
                    max(ghost_area, tiny),
                )
            )
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
                connection.send(
                    (
                        task_id,
                        'ok',
                        {name: _river_interface_snapshot(river_map[name]) for name in names},
                    )
                )
                continue

            if command == 'call_batch_and_interface_snapshots':
                for call in payload['calls']:
                    river = river_map[call['river']]
                    method = getattr(river, call['method'])
                    method(*call.get('args', ()), **call.get('kwargs', {}))
                names = payload['names']
                connection.send(
                    (
                        task_id,
                        'ok',
                        {name: _river_interface_snapshot(river_map[name]) for name in names},
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

    def call_batch_and_interface_snapshots(self, calls, names=None):
        selected = names if names is not None else [name for name, _ in self.river_items]
        self.call_batch(calls, collect=False)
        return {name: _river_interface_snapshot(self._river_map[name]) for name in selected}

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

    def get_interface_snapshots(self, names=None):
        grouped = self._group_names(names)
        pending = []
        for worker in self._workers:
            worker_names = grouped.get(worker['id'])
            if not worker_names:
                continue
            task_id = self._submit(worker, 'interface_snapshots', {'names': worker_names})
            pending.append((worker, task_id))

        results = {}
        for worker, task_id in pending:
            results.update(self._collect(worker, task_id))
        return results

    def call_batch_and_interface_snapshots(self, calls, names=None):
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
                },
            )
            pending.append((worker, task_id))

        results = {}
        for worker, task_id in pending:
            results.update(self._collect(worker, task_id))
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

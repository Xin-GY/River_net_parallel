import random
import time
import os
import json
from copy import deepcopy

from river_for_net import River
# from river_for_net_optimized import River
import networkx as nx
from pprint import pprint
import pandas as pd
import datetime
import numpy as np
from parallel_river_pool import (
    NODE_AGG_AC,
    NODE_AGG_GHOST_COUNT,
    NODE_AGG_GHOST_SUM,
    NODE_AGG_REAL_COUNT,
    NODE_AGG_REAL_SUM,
    NODE_AGG_RESIDUAL,
    PersistentRiverProcessPool,
    PersistentRiverThreadPool,
    SNAP_BOUNDARY_FACE_AREA,
    SNAP_BOUNDARY_FACE_DISCHARGE,
    SNAP_BOUNDARY_FACE_LEVEL,
    SNAP_BOUNDARY_FACE_WIDTH,
    SNAP_CELL_LEVEL,
    SNAP_CELL_Q,
    SNAP_CELL_S,
    SNAP_CELL_WIDTH,
    SNAP_GHOST_LEVEL,
    SNAP_GHOST_Q,
    SNAP_GHOST_S,
    SNAP_GHOST_WIDTH,
    SNAP_COMPACT_CELL_LEVEL,
    SNAP_COMPACT_GHOST_LEVEL,
    SNAP_COMPACT_GHOST_Q,
    SNAP_COMPACT_GHOST_S,
    SNAP_COMPACT_GHOST_WIDTH,
    SNAP_LEFT,
    SNAP_RIGHT,
    _exact_node_eval_from_plan,
)

class Rivernet():
    def __init__(self, Topology, model_data, verbos=True):
        # 构建参数
        self.verbos = verbos # 是否打印详细信息
        self.Fine_flag = False  # 网格参数是否已优化
        self.model_data = model_data # 模型数据
        self.caculation_time = 0 # 模拟总时间（单位：秒）
        self.caculation_start_time = 0 # 模拟开始时间（单位：秒）

        # 构建河网拓扑
        self.topology = Topology # 存储河网拓扑信息
        self.G = nx.DiGraph() # 创建有向图
        self.Create_Rivernet() # 创建河网
        self._refresh_river_cache()

        # 边界条件组织
        # { node_name: {"type": btype, "call": f(t), "_val":[v](仅常数有)} }
        self.boundaries = {} # 边界条件字典
        self.ALLOWED_OUT_BTYPE = {'free', 'fix_level'} # 允许的出边界类型
        self.ALLOWED_IN_BTYPE = {'flow', 'fix_level'} # 允许的入边界类型

        # 模拟时间参数
        self.sim_start_time = datetime.datetime.strptime(model_data['sim_start_time'], '%Y-%m-%d %H:%M:%S')
        self.sim_end_time = datetime.datetime.strptime(model_data['sim_end_time'], '%Y-%m-%d %H:%M:%S')
        self.total_sim_time = (self.sim_end_time - self.sim_start_time).total_seconds()  # 模拟总时间（单位：秒）
        self.step_count = 0 # 模拟步数

        # 子步参数
        self.sub_step_count = 0 # 子步数
        self.sub_step_time = 0.0 # 子步时间
        self.sub_step_max_dt = 0.0 # 子步最大时间步长
        self.sub_step_min_dt = 999999 # 子步最小时间步长
        self.sub_step_start_time = 0 # 子步开始时间
        self.sub_step_caculation_time_using= 0 # 子步计算时间（单位：秒）

        # 河网所需参数
        self.current_sim_time = 0.0 # 模拟进行时间
        self.cfl_allowed_dt = 1e-5 # cfl允许的时间步长
        self.DT = 1e-5 # 时间步长

        # 汊点迭代算法相关参数
        self.alpha = 1.2 # 计算调节参数，1-2之间
        self.relax = 0.5
        self.max_iteration = 20 # 汊点计算最大迭代次数
        self.g = 9.81 # 重力加速度
        self.JPWSPC_EPS = 1e-3 # JPWSPC算法容差
        self.JPWSPC_Q_limit = 1e-3 # JPWSPC算法流量限制
        # 边界稳定化开关（默认关闭）
        self.external_bc_use_stabilizers = False
        self.internal_bc_use_stabilizers = False
        # FullSWOF 风格：超临界端不施加单一水位边界（采用外推）
        self.external_bc_respect_supercritical = True
        self.internal_bc_respect_supercritical = True
        # FullSWOF 风格：上游给定流量边界采用特征线恢复面积
        self.external_flow_bc_use_characteristic = True
        # 固定水位边界“界面型解释”开关（可区分外边界与内部汊点）
        self.external_bc_stage_on_face = False
        self.internal_bc_stage_on_face = False
        # 汊点导数采用“相邻实格+受控分支”版本
        self.internal_use_ac_v2 = True
        # 是否在汊点牛顿中使用数值雅可比（默认关闭，保持原有收敛特性）
        self.internal_use_numeric_jacobian = False
        # 是否使用“结点残差全耦合牛顿”求解（默认关闭，保持原有行为）
        self.internal_use_coupled_newton = False
        # 调试开关：固定水位边界使用旧版 V2 公式（用于与历史实现对比）
        self.use_fix_level_bc_v2 = False
        # JPWSPC 风格 Ac：使用结点端（ghost）状态构造导数近似
        self.internal_use_paper_ac = True
        # JPWSPC 预测步：默认以上一时间步收敛后的结点水位作为当前初值
        self.internal_level_predict_from_last = True
        # 内部-内部支路端点流量同步（用于结点修正阶段增强支路两端一致性）
        self.internal_sync_branch_end_Q = False
        self.internal_sync_branch_end_Q_relax = 1.0
        # 结点质量残差口径：False=用ghost端Q；True=用端界面近似Qface(0.5*(Qghost+Qreal))
        self.internal_node_use_face_discharge = False
        # 若边界函数已显式恢复“边界界面 discharge”，结点残差优先使用该口径
        self.internal_node_prefer_boundary_face_discharge = False
        # JPWSPC 的 Ac 默认仍沿用历史 ghost 端状态；
        # 仅在显式试验时才切到 boundary-face 口径。
        self.internal_node_use_boundary_face_ac = False
        # 结点残差进一步改为“边界界面质量通量”口径，和 FV 更新通量保持一致
        self.internal_node_use_face_flux_residual = False
        self._internal_node_level_cache = {}
        self.internal_node_history = []
        # 输出开关：用于 warmup 等仅需末态、不需写盘的场景
        self.save_outputs = True
        # 结果输出河道过滤：None=全部输出；否则仅输出集合中的河道名
        self.output_river_names = None
        # 分支更新格式：False=显式组装（默认），True=隐式传输系数组装
        self.use_implicit_branch_update = False
        # 可选：河道级持久化并行执行。默认关闭，保持历史串行行为。
        self.use_parallel_workers = False
        self.parallel_backend = 'threads'
        self.parallel_n_workers = max((os.cpu_count() or 1), 1)
        self.parallel_start_method = 'auto'
        self.parallel_sync_main_state_on_yield = True
        self.internal_exact_backend = 'legacy_parallel'
        self.save_cfl_history = False
        self.cfl_history = []
        self.output_save_interval = None
        self.save_perf_report = False
        self.internal_use_response_table = False
        self.internal_response_samples = 9
        self.internal_response_base_span = 0.25
        self.internal_response_max_span = 2.0
        self.internal_response_refine_steps = 2
        self.fast_mode_enabled = False
        self.fast_mode_name = 'off'
        self.fast_node_solver_mode = 'off'
        self.fast_node_correction_iters = 1
        self.fast_node_dz_tol = 5.0e-4
        self.fast_node_q_tol = 5.0e-3
        self.fast_cfl_scale = 1.0
        self.fast_dt_increase_factor = None
        self.save_internal_node_history = True
        self.save_run_summary = False
        self._internal_node_solver_cache = {}
        self._perf_sections = {}
        self._perf_local_sections = {}
        self._perf_internal_node_stats = {}
        self._perf_internal_orchestration = {}
        self._reset_perf_stats()

    def _refresh_river_cache(self):
        # Topology is fixed after construction in the current workflow. Cache
        # edge payloads and bound methods to reduce repeated networkx view
        # traversal and hasattr/getattr dispatch in the tight time loop.
        self._river_edges = list(self.G.edges(data=True))
        self._in_edges_by_node = {n: list(self.G.in_edges(n, data=True)) for n in self.G.nodes()}
        self._out_edges_by_node = {n: list(self.G.out_edges(n, data=True)) for n in self.G.nodes()}
        self._in_branches_by_node = {
            n: [(data['river'], data.get('name', 'river')) for _, _, data in self._in_edges_by_node[n]]
            for n in self.G.nodes()
        }
        self._out_branches_by_node = {
            n: [(data['river'], data.get('name', 'river')) for _, _, data in self._out_edges_by_node[n]]
            for n in self.G.nodes()
        }
        self._river_method_cache = {}
        self._parallel_internal_node_specs_cache = None
        self._internal_node_branch_specs_cache = None
        self._internal_dense_plan_cache = None
        self._parallel_dense_plan_cache = None
        self._internal_snapshot_names_cache = None

    def _all_river_names(self):
        return [data.get('name') for _, _, data in self._river_edges]

    def _river_map(self):
        return {data.get('name'): data['river'] for _, _, data in self._river_edges}

    def _new_perf_bucket(self):
        return {'time': 0.0, 'calls': 0}

    def _new_internal_orchestration_bucket(self):
        return {'time': 0.0, 'calls': 0}

    def _reset_perf_stats(self):
        self._perf_sections = {
            'boundary_updater': self._new_perf_bucket(),
            'face_uc_net': self._new_perf_bucket(),
            'roe_matrix_net': self._new_perf_bucket(),
            'source_net': self._new_perf_bucket(),
            'roe_flux_net': self._new_perf_bucket(),
            'assemble_net': self._new_perf_bucket(),
            'update_net': self._new_perf_bucket(),
            'advance_local_step_wall': self._new_perf_bucket(),
            'cfl_update': self._new_perf_bucket(),
        }
        self._perf_local_sections = {
            'face_uc': self._new_perf_bucket(),
            'roe_matrix': self._new_perf_bucket(),
            'source_term': self._new_perf_bucket(),
            'roe_flux': self._new_perf_bucket(),
            'assemble': self._new_perf_bucket(),
            'update': self._new_perf_bucket(),
            'cfl_update': self._new_perf_bucket(),
            'boundary_updater': self._new_perf_bucket(),
        }
        self._perf_internal_node_stats = {}
        self._perf_stage_boundary = {
            'cython_fast_calls': 0,
            'cython_fast_hits': 0,
            'fast_reject_reasons': {},
            'runtime_reject_reasons': {},
            'overall': {'calls': 0, 'fast_hits': 0, 'precheck': {}, 'runtime': {}},
            'by_scenario': {},
            'by_node': {},
            'by_river_side': {},
            'by_call_scene': {},
        }
        self._perf_internal_orchestration = {
            'backend': None,
            'solve_calls': 0,
            'phase_times': {
                'initial_guess': self._new_internal_orchestration_bucket(),
                'trial_level_prepare': self._new_internal_orchestration_bucket(),
                'apply_prepare': self._new_internal_orchestration_bucket(),
                'pool_submit_dispatch': self._new_internal_orchestration_bucket(),
                'worker_apply': self._new_internal_orchestration_bucket(),
                'worker_aggregate': self._new_internal_orchestration_bucket(),
                'worker_snapshot': self._new_internal_orchestration_bucket(),
                'collect_deserialize_merge': self._new_internal_orchestration_bucket(),
                'residual_assembly': self._new_internal_orchestration_bucket(),
                'jacobian_assembly': self._new_internal_orchestration_bucket(),
                'relax_checks': self._new_internal_orchestration_bucket(),
                'diagnostics_history': self._new_internal_orchestration_bucket(),
            },
            'round_trips': 0,
            'payload_bytes_sent': 0,
            'payload_bytes_recv': 0,
            'river_side_applies': 0,
            'final_snapshot_calls': 0,
            'backend_counts': {},
        }

    def _new_stage_boundary_dim_bucket(self):
        return {'calls': 0, 'fast_hits': 0, 'precheck': {}, 'runtime': {}}

    def _merge_stage_boundary_dim_map(self, dest, src):
        for key, bucket in src.items():
            rec = dest.setdefault(key, self._new_stage_boundary_dim_bucket())
            rec['calls'] += int(bucket.get('calls', 0))
            rec['fast_hits'] += int(bucket.get('fast_hits', 0))
            for phase in ('precheck', 'runtime'):
                phase_map = rec[phase]
                for reason, count in bucket.get(phase, {}).items():
                    phase_map[reason] = int(phase_map.get(reason, 0)) + int(count)

    def _merge_stage_boundary_perf(self, stage_boundary):
        if not stage_boundary:
            return
        perf = self._perf_stage_boundary
        perf['cython_fast_calls'] += int(stage_boundary.get('cython_fast_calls', 0))
        perf['cython_fast_hits'] += int(stage_boundary.get('cython_fast_hits', 0))
        for reason, count in stage_boundary.get('fast_reject_reasons', {}).items():
            perf['fast_reject_reasons'][reason] = int(perf['fast_reject_reasons'].get(reason, 0)) + int(count)
        for reason, count in stage_boundary.get('runtime_reject_reasons', {}).items():
            perf['runtime_reject_reasons'][reason] = int(perf['runtime_reject_reasons'].get(reason, 0)) + int(count)
        overall = stage_boundary.get('overall', {})
        perf['overall']['calls'] += int(overall.get('calls', 0))
        perf['overall']['fast_hits'] += int(overall.get('fast_hits', 0))
        for phase in ('precheck', 'runtime'):
            for reason, count in overall.get(phase, {}).items():
                perf['overall'][phase][reason] = int(perf['overall'][phase].get(reason, 0)) + int(count)
        self._merge_stage_boundary_dim_map(perf['by_scenario'], stage_boundary.get('by_scenario', {}))
        self._merge_stage_boundary_dim_map(perf['by_node'], stage_boundary.get('by_node', {}))
        self._merge_stage_boundary_dim_map(perf['by_river_side'], stage_boundary.get('by_river_side', {}))
        self._merge_stage_boundary_dim_map(perf['by_call_scene'], stage_boundary.get('by_call_scene', {}))

    def _perf_add_time(self, bucket_map, key, elapsed):
        bucket = bucket_map.setdefault(key, self._new_perf_bucket())
        bucket['time'] += float(elapsed)
        bucket['calls'] += 1

    def _perf_add_internal_orchestration_time(self, key, elapsed):
        bucket = self._perf_internal_orchestration['phase_times'].setdefault(
            key,
            self._new_internal_orchestration_bucket(),
        )
        bucket['time'] += float(elapsed)
        bucket['calls'] += 1

    def _perf_record_internal_backend(self, backend_name):
        if not self.save_perf_report:
            return
        backend = str(backend_name)
        self._perf_internal_orchestration['backend'] = backend
        backend_counts = self._perf_internal_orchestration['backend_counts']
        backend_counts[backend] = int(backend_counts.get(backend, 0)) + 1
        self._perf_internal_orchestration['solve_calls'] += 1

    def _perf_record_internal_roundtrip(self, meta, final_snapshot=False):
        if (not self.save_perf_report) or (not meta):
            return
        perf = self._perf_internal_orchestration
        perf['round_trips'] += int(meta.get('round_trips', 0))
        perf['payload_bytes_sent'] += int(meta.get('sent_bytes', 0))
        perf['payload_bytes_recv'] += int(meta.get('recv_bytes', 0))
        perf['river_side_applies'] += int(meta.get('apply_count', 0))
        if final_snapshot:
            perf['final_snapshot_calls'] += 1
        self._perf_add_internal_orchestration_time('pool_submit_dispatch', float(meta.get('submit_time', 0.0)))
        self._perf_add_internal_orchestration_time('worker_apply', float(meta.get('worker_apply_time', 0.0)))
        self._perf_add_internal_orchestration_time('worker_aggregate', float(meta.get('worker_aggregate_time', 0.0)))
        self._perf_add_internal_orchestration_time('worker_snapshot', float(meta.get('worker_snapshot_time', 0.0)))
        collect_merge = float(meta.get('collect_time', 0.0)) + float(meta.get('merge_time', 0.0))
        self._perf_add_internal_orchestration_time('collect_deserialize_merge', collect_merge)

    def _perf_node_entry(self, node):
        return self._perf_internal_node_stats.setdefault(
            node,
            {
                'solve_calls': 0,
                'solve_time': 0.0,
                'iterations': 0,
                'boundary_closure_calls': 0,
                'table_attempts': 0,
                'table_success': 0,
                'table_fallbacks': 0,
                'exact_refine_iterations': 0,
                'fast_calls': 0,
                'fast_hits': 0,
                'fallback_reasons': {},
                'final_abs_residual_sum': 0.0,
            },
        )

    def _perf_record_node_solve(self, node, solve_time, iterations, boundary_closure_calls, table_attempted=False, table_success=False, fast_calls=0, fast_hits=0, exact_refine_iterations=0, final_abs_residual=None, fallback_reason=None):
        if (not self.save_perf_report) and (not self.internal_use_response_table):
            return
        rec = self._perf_node_entry(node)
        rec['solve_calls'] += 1
        rec['solve_time'] += float(solve_time)
        rec['iterations'] += int(iterations)
        rec['boundary_closure_calls'] += int(boundary_closure_calls)
        rec['fast_calls'] += int(fast_calls)
        rec['fast_hits'] += int(fast_hits)
        rec['exact_refine_iterations'] += int(exact_refine_iterations)
        if table_attempted:
            rec['table_attempts'] += 1
        if table_success:
            rec['table_success'] += 1
        elif table_attempted:
            rec['table_fallbacks'] += 1
        if final_abs_residual is not None and np.isfinite(final_abs_residual):
            rec['final_abs_residual_sum'] += float(abs(final_abs_residual))
        if fallback_reason:
            reasons = rec['fallback_reasons']
            reasons[fallback_reason] = int(reasons.get(fallback_reason, 0)) + 1

    def _internal_boundary_kwargs(self):
        return {
            'Fr_max': 0.85,
            'head_gain_factor': 0.65,
            'relax_Q': 0.4,
            'cap_du_factor': 0.8,
            'cap_dQ_factor': 0.7,
            'use_stabilizers': bool(self.internal_bc_use_stabilizers),
            'respect_supercritical': bool(self.internal_bc_respect_supercritical),
            'stage_on_face': bool(self.internal_bc_stage_on_face),
        }

    def _internal_response_solver_supported(self):
        return (
            bool(self.internal_use_response_table)
            and (not self.internal_use_coupled_newton)
            and (not self.internal_use_numeric_jacobian)
            and (not self.internal_sync_branch_end_Q)
            and (not self.internal_node_use_face_flux_residual)
        )

    def _fast_internal_solver_active(self):
        mode = str(getattr(self, 'fast_node_solver_mode', 'off')).strip().lower()
        return bool(self.fast_mode_enabled) and mode in {'response_root', 'response_corrector'} and self._internal_response_solver_supported()

    def _internal_solver_iteration_limit(self):
        if self._fast_internal_solver_active():
            return max(1, int(getattr(self, 'fast_node_correction_iters', 1)))
        return max(1, int(self.max_iteration))

    def _internal_solver_dz_tol(self):
        if self._fast_internal_solver_active():
            return float(max(getattr(self, 'fast_node_dz_tol', 5.0e-4), 1.0e-8))
        return 1.0e-4

    def _internal_solver_q_tol(self):
        if self._fast_internal_solver_active():
            return float(max(getattr(self, 'fast_node_q_tol', 5.0e-3), self.JPWSPC_Q_limit))
        return float(self.JPWSPC_Q_limit)

    def _internal_node_history_enabled(self):
        return bool(self.save_outputs and self.internal_nodes and self.save_internal_node_history)

    def _internal_node_branch_specs(self, node_name):
        cache = self._internal_node_branch_specs_cache
        if cache is None:
            cache = {}
            for node in self.internal_nodes:
                specs = []
                for river_obj, river_name in self._in_branches_by_node[node]:
                    specs.append({
                        'river_obj': river_obj,
                        'river': river_name,
                        'side': 'right',
                        'flow_sign': 1.0,
                    })
                for river_obj, river_name in self._out_branches_by_node[node]:
                    specs.append({
                        'river_obj': river_obj,
                        'river': river_name,
                        'side': 'left',
                        'flow_sign': -1.0,
                    })
                cache[node] = specs
            self._internal_node_branch_specs_cache = cache
        return cache.get(node_name, ())

    def _predict_internal_node_level(self, node_name, fallback_level):
        cache = self._internal_node_solver_cache.get(node_name)
        if cache is None:
            return float(fallback_level)
        last_level = cache.get('last_level')
        prev_level = cache.get('prev_level')
        if last_level is None or (not np.isfinite(last_level)):
            return float(fallback_level)
        if prev_level is None or (not np.isfinite(prev_level)):
            return float(last_level)
        predicted = float(last_level) + (float(last_level) - float(prev_level))
        return max(0.0, predicted)

    def _update_internal_node_solver_cache(self, node_name, level, residual=None, dR_dZ=None):
        if not self.internal_use_response_table:
            return
        rec = self._internal_node_solver_cache.setdefault(node_name, {})
        rec['prev_level'] = rec.get('last_level')
        rec['last_level'] = float(level)
        if residual is not None and np.isfinite(residual):
            rec['last_residual'] = float(residual)
        if dR_dZ is not None and np.isfinite(dR_dZ):
            rec['last_dR_dZ'] = float(dR_dZ)

    def _sync_parallel_rivers_to_main(self, pool, names=None):
        main_map = self._river_map()
        worker_map = pool.get_rivers(names=names)
        for name, worker_river in worker_map.items():
            main_river = main_map[name]
            main_river.__dict__.clear()
            main_river.__dict__.update(worker_river.__dict__)

    def _parallel_supported(self):
        return not (
            self.internal_use_coupled_newton
            or self.internal_use_numeric_jacobian
            or self.internal_sync_branch_end_Q
            or self.internal_node_use_face_flux_residual
        )

    def _resolve_process_start_method(self):
        method = str(getattr(self, 'parallel_start_method', 'auto')).strip().lower()
        if method in {'', 'auto'}:
            return 'fork' if os.name == 'posix' else 'spawn'
        if method == 'fork' and os.name != 'posix':
            return 'spawn'
        return method

    def _legacy_internal_exact_default_active(self):
        return (
            (not self.save_perf_report)
            and (not self.internal_use_response_table)
            and str(getattr(self, 'internal_exact_backend', 'legacy_parallel')).strip().lower() not in {'fused_parallel', 'fused_serial'}
        )

    # 创建河网
    def Create_Rivernet(self):
        for (u, v), info in self.topology.items():

            # 基于数据，组织河道class所需model_data
            name = info['name']
            manning = info['manning']

            model_data = {
                'model_name': name,
                'sim_start_time': self.model_data['sim_start_time'],
                'sim_end_time': self.model_data['sim_end_time'],
                'time_step': self.model_data['time_step'],  # 单位：秒
                'output_path': self.model_data['output_path'],
                'CFL': self.model_data['CFL'],
                'n': manning
            }

            # 创建河道对象
            river_data = deepcopy(info['river_data'])
            section_data = deepcopy(info['section_data'])
            section_pos = deepcopy(info['section_pos']) if info['section_pos'] is not None else None
            river = River(river_data, section_data, section_pos, model_data)
            self.G.add_edge(u, v, river=river, name=info['name'])
            print(f'河道{name}创建完成')

    # 判断流向
    def edge_direction(self):
        if not self.G.is_directed():
            raise ValueError('无向图没有天然方向，请先转换为有向图或添加方向属性')
        results = []
        for u, v in self.G.edges():
            results.append({
                'edge': (u, v),
                'from_node': u,
                'to_node': v
            })
        if self.verbos:
            pprint(results)

    # 判断内外部点
    def classfy_nodes(self):
        """
        将节点分成三类：
          - internal:   degree >= 2
          - external_in:  in_degree == 0 且 out_degree == 1（外部入流端）
          - external_out: in_degree == 1 且 out_degree == 0（外部出流端）
        另外会记录孤立点（degree == 0），以便排查拓扑问题。
        """
        self._refresh_river_cache()
        self.internal_nodes = []
        self.external_in_nodes = []
        self.external_out_nodes = []
        self.isolated_nodes = []

        for n in self.G.nodes():
            indeg = len(self._in_edges_by_node[n])
            outdeg = len(self._out_edges_by_node[n])
            deg = indeg + outdeg

            if deg == 0:
                self.isolated_nodes.append(n)
            elif deg == 1:
                if indeg == 1 and outdeg == 0:
                    self.external_out_nodes.append(n)
                elif outdeg == 1 and indeg == 0:
                    self.external_in_nodes.append(n)
                else:
                    # 理论上不会出现（DiGraph 无并行边时 deg==1 只能是上面两种）
                    pass
            else:
                # deg >= 2
                self.internal_nodes.append(n)

        # 兼容旧属性：external_nodes = external_in ∪ external_out
        self.external_nodes = self.external_in_nodes + self.external_out_nodes

        if self.verbos:
            print('内部节点 (internal):', self.internal_nodes)
            print('外部入点 (external_in):', self.external_in_nodes)
            print('外部出点 (external_out):', self.external_out_nodes)
            if self.isolated_nodes:
                print('孤立节点 (degree=0):', self.isolated_nodes)

    # 分别遍历内部和外部节点
    def node_flow_direction(self):
        if not self.G.is_directed():
            raise ValueError('无向图没有天然方向，请先转换为有向图或添加方向属性')

        # 确保已经按三类完成分类
        need_attrs = ('internal_nodes', 'external_in_nodes', 'external_out_nodes')
        if not all(hasattr(self, a) for a in need_attrs):
            self.classfy_nodes()

        result = {'internal': {}, 'external_in': {}, 'external_out': {}}

        # —— 内部节点：既有入又有出
        for n in self.internal_nodes:
            ins = self._in_edges_by_node[n]  # [(u, n, data), ...]
            outs = self._out_edges_by_node[n]  # [(n, v, data), ...]
            result['internal'][n] = {'in': ins, 'out': outs}

        # —— 外部入点：只有入边（按你的定义应当 out_edges 为空）
        for n in self.external_in_nodes:
            ins = self._in_edges_by_node[n]
            outs = self._out_edges_by_node[n]
            result['external_in'][n] = {'in': ins, 'out': outs}

        # —— 外部出点：只有出边（按你的定义应当 in_edges 为空）
        for n in self.external_out_nodes:
            ins = self._in_edges_by_node[n]
            outs = self._out_edges_by_node[n]
            result['external_out'][n] = {'in': ins, 'out': outs}

        if self.verbos:
            print('\n—— 内部节点 (internal) ——')
            for n, d in result['internal'].items():
                print(f'节点 {n}:')
                for u, v, data in d['in']:
                    print(f'  in  : {data.get("name", f"({u},{v})")}  ({u} -> {v})')
                for u, v, data in d['out']:
                    print(f'  out : {data.get("name", f"({u},{v})")}  ({u} -> {v})')

            print('\n—— 外部入点 (external_in) ——')
            for n, d in result['external_in'].items():
                print(f'节点 {n}:')
                for u, v, data in d['in']:
                    print(f'  in  : {data.get("name", f"({u},{v})")}  ({u} -> {v})')
                if d['out']:
                    for u, v, data in d['out']:
                        print(f'  out : {data.get("name", f"({u},{v})")}  ({u} -> {v})')

            print('\n—— 外部出点 (external_out) ——')
            for n, d in result['external_out'].items():
                print(f'节点 {n}:')
                if d['in']:
                    for u, v, data in d['in']:
                        print(f'  in  : {data.get("name", f"({u},{v})")}  ({u} -> {v})')
                for u, v, data in d['out']:
                    print(f'  out : {data.get("name", f"({u},{v})")}  ({u} -> {v})')

            # print('\n—— 结构化结果 ——')
            # pprint(result)

        return result

    # 调用每条河道函数
    def call_river_function(self):
        for u, v, data in self._river_edges:
            river = data['river']
            river.Call_fun_test()  # 假设每条河道都有 Call_fun_test 函数

    # 调用河道指定函数
    def call_river_function_by_name(self, function_name):
        cached = self._river_method_cache.get(function_name)
        if cached is None:
            cached = []
            for _, _, data in self._river_edges:
                river = data['river']
                if river is None:
                    print(f'河道 {data["name"]} 没有定义河流对象，无法调用')
                    continue
                if not hasattr(river, function_name):
                    print(f'河道 {data["name"]} 没有名为 {function_name} 的函数')
                    continue
                func = getattr(river, function_name)
                if not callable(func):
                    print(f'河道 {data["name"]} 的 {function_name} 不是一个可调用的函数')
                    continue
                cached.append((data['name'], func))
            self._river_method_cache[function_name] = cached

        for river_name, func in cached:
            func()
            if self.verbos:
                print(f'河道 {river_name} 的 {function_name} 函数调用成功')

    # 设置边界条件
    def set_boundary(self, node: str, btype: str, data=None):
        """
        设定边界
        - node: 节点名，如 "N1"
        - btype: 边界类型，如 "free" / "stage" / "flow" / "rating" / "wall" ...
        - data:  None（自由/自然边界等不需要输入）
                 或 常数（int/float）
                 或 函数 f(t)
        """
        # 确保节点分类可用
        need_attrs = ('internal_nodes', 'external_in_nodes', 'external_out_nodes')
        if not all(hasattr(self, a) for a in need_attrs):
            self.classfy_nodes()

        # 检查设定边界是否合法
        if node in self.external_in_nodes:
            if btype not in self.ALLOWED_IN_BTYPE:
                raise ValueError(f"{node}为入流边界，不支持边界类型: {btype!r}；可选: {sorted(self.ALLOWED_IN_BTYPE)}")
        elif node in self.external_out_nodes:
            if btype not in self.ALLOWED_OUT_BTYPE:
                raise ValueError(f"{node}为出流边界，不支持边界类型: {btype!r}；可选: {sorted(self.ALLOWED_OUT_BTYPE)}")
        else:
            raise ValueError(f"节点 {node} 不是外部入点或出点，无法设置边界条件，边界节点有：{self.external_in_nodes + self.external_out_nodes}")

        if data is None:
            # 例如自由边界
            self.boundaries[node] = {"type": btype, "call": (lambda t: None)}
            return

        if callable(data):
            # lambda/函数：直接存
            self.boundaries[node] = {"type": btype, "call": data}
        else:
            # 常数：用可变容器保存，方便运行中实时修改
            box = [float(data)]
            self.boundaries[node] = {
                "type": btype,
                "call": (lambda t, _box=box: _box[0]),
                "_val": box
            }

    # 修改定值的边界条件
    def update_const(self, node: str, new_value: float):
        """运行中实时修改【常数】边界的数值"""
        item = self.boundaries.get(node)
        if not item or "_val" not in item:
            raise TypeError(f"{node} 不是常数边界或未设置")
        item["_val"][0] = float(new_value)

    # 替换边界条件函数
    def update_func(self, node: str, new_func):
        """运行中替换【函数】边界"""
        if not callable(new_func):
            raise TypeError("new_func 必须可调用")
        item = self.boundaries.get(node)
        if not item:
            raise KeyError(f"{node} 边界未设置")
        item["call"] = new_func

    # 更新边界类型
    def update_type(self, node: str, new_type: str):
        """需要的话也可动态切换边界类型（数值/函数保持不变）"""
        if node not in self.boundaries:
            raise KeyError(f"{node} 边界未设置")
        self.boundaries[node]["type"] = new_type

    # 获取边界值
    def get_boundary_value(self, node: str, t: float):
        """
        返回 (btype, value)
        - 对于自由/不需要数值的边界，value 为 None
        - 其余返回浮点数
        """
        item = self.boundaries.get(node)
        if not item:
            raise KeyError(f"{node} 边界未设置")
        return item["type"], item["call"](t)

    # 求指定时刻所有边界的值
    def evaluate_all_boundaries(self, t: float):
        """批量获取：{ node: {'type': ..., 'value': ...} }"""
        out = {}
        for node, item in self.boundaries.items():
            out[node] = {"type": item["type"], "value": item["call"](t)}
        return out

    # 调用河道网格参数优化函数
    def Fine_cell_property_net(self):
        self.call_river_function_by_name('Fine_cell_property2')
        self.Fine_flag = True  # 标记网格参数已优化

    # 调用水面初始化函数
    def Init_water_surface_net(self):
        self.call_river_function_by_name('Init_water_serface')

    # 初始化网格参数
    def Init_cell_property_net(self):
        if self.Fine_flag:
            for _, _, data in self._river_edges:
                river = data['river']
                river.Init_cell_proprity(True) # 如果网格已重新插值，则不根据断面高度修改河底高程
        else:
            for _, _, data in self._river_edges:
                river = data['river']
                river.Init_cell_proprity(False) # 如果网格未重新插值，则根据断面高度修改河底高程

    # 保存初始结果
    def Save_basic_data_net(self):
        selected = self.output_river_names
        if selected is not None and not isinstance(selected, set):
            selected = set(selected)
            self.output_river_names = selected

        for _, _, data in self._river_edges:
            name = data.get('name')
            if selected is not None and name not in selected:
                continue
            river = data['river']
            river.Save_Basic_data()
            if river.initial_total_volume is None and hasattr(river, '_compute_total_volume'):
                river.initial_total_volume = float(river._compute_total_volume())

    # 计算界面平均流速和波速
    def Caculate_face_U_C_net(self):
        self.call_river_function_by_name('Caculate_face_U_C')

    # 计算Roe格式特征值
    def Caculate_Roe_matrix_net(self):
        self.call_river_function_by_name('Caculate_Roe_matrix')

    # 计算源项
    def Caculate_Source_term_net(self):
        self.call_river_function_by_name('Caculate_source_term_2')

    # 计算Roe格式通量
    def Caculate_Roe_flux_net(self):
        self.call_river_function_by_name('Caculate_Roe_Flux_2')

    # 组合通量
    def Assemble_flux_net(self):
        self.call_river_function_by_name('Assemble_Flux_2')

    # 计算隐式传输系数
    def Caculate_impli_trans_coefficient_net(self):
        self.call_river_function_by_name('Caculate_impli_trans_coefficient')

    # 隐式组合通量
    def Assemble_flux_impli_net(self):
        self.call_river_function_by_name('Assemble_Flux_impli_trans')

    # 保存单步模拟结果
    def Save_step_result_net(self):
        selected = self.output_river_names
        for _, _, data in self._river_edges:
            name = data.get('name')
            if selected is not None and name not in selected:
                continue
            data['river'].maybe_save_result_per_time_step()

    def _configure_output_save_schedule(self, yield_step):
        if not self.save_outputs:
            return
        default_interval = self.output_save_interval
        if default_interval is None:
            default_interval = float(yield_step)
        selected = self.output_river_names
        for _, _, data in self._river_edges:
            name = data.get('name')
            if selected is not None and name not in selected:
                continue
            data['river'].configure_save_scheduler(default_interval=default_interval, save_initial=True)

    def Save_internal_node_history(self):
        if not (self.save_internal_node_history and self.internal_node_history):
            return
        out_path = os.path.join(self.model_data['output_path'], 'internal_node_history.csv')
        pd.DataFrame(self.internal_node_history).to_csv(out_path, index=False)
        if self.verbos:
            print(f'[OK] 内部节点时序已保存 -> {out_path}')

    def Save_run_summary(self):
        if not self.save_run_summary:
            return
        out_dir = self.model_data['output_path']
        os.makedirs(out_dir, exist_ok=True)
        river_rows = []
        total_initial = 0.0
        total_final = 0.0
        for _, _, data in self._river_edges:
            river = data['river']
            initial_volume = getattr(river, 'initial_total_volume', None)
            if initial_volume is None and hasattr(river, '_compute_total_volume'):
                initial_volume = float(river._compute_total_volume())
                river.initial_total_volume = float(initial_volume)
            final_volume = getattr(river, 'final_total_volume', None)
            if final_volume is None and hasattr(river, '_compute_total_volume'):
                final_volume = float(river._compute_total_volume())
                river.final_total_volume = float(final_volume)
            initial_volume = float(initial_volume if initial_volume is not None else 0.0)
            final_volume = float(final_volume if final_volume is not None else initial_volume)
            denom = max(abs(initial_volume), 1.0e-12)
            rel = float((final_volume - initial_volume) / denom)
            river.volume_relative_change = rel
            total_initial += initial_volume
            total_final += final_volume
            river_rows.append(
                {
                    'river': data.get('name'),
                    'initial_volume': initial_volume,
                    'final_volume': final_volume,
                    'relative_volume_change': rel,
                    'cell_num': int(getattr(river, 'cell_num', 0)),
                }
            )
        net_denom = max(abs(total_initial), 1.0e-12)
        summary = {
            'model_name': self.model_data.get('model_name'),
            'output_path': self.model_data.get('output_path'),
            'fast_mode_enabled': bool(self.fast_mode_enabled),
            'fast_mode_name': str(self.fast_mode_name),
            'fast_node_solver_mode': str(self.fast_node_solver_mode),
            'current_sim_time': float(self.current_sim_time),
            'total_sim_time': float(self.total_sim_time),
            'step_count': int(self.step_count),
            'sub_step_count_last': int(self.sub_step_count),
            'calculation_time': float(getattr(self, 'caculation_time', 0.0)),
            'save_outputs': bool(self.save_outputs),
            'save_internal_node_history': bool(self.save_internal_node_history),
            'internal_node_count': int(len(self.internal_nodes)),
            'network_total_volume_initial': float(total_initial),
            'network_total_volume_final': float(total_final),
            'network_relative_volume_change': float((total_final - total_initial) / net_denom),
            'rivers': river_rows,
        }
        out_path = os.path.join(out_dir, 'run_summary.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def _record_cfl_history(self, dt_items):
        if not self.save_cfl_history:
            return
        rec = {'time': float(self.current_sim_time)}
        dt_min = np.inf
        for name, value in dt_items:
            dt_val = float(value)
            rec[str(name)] = dt_val
            dt_min = min(dt_min, dt_val)
        rec['global_dt'] = float(dt_min)
        self.cfl_history.append(rec)

    def Save_cfl_history(self):
        if not (self.save_cfl_history and self.cfl_history):
            return
        out_path = os.path.join(self.model_data['output_path'], 'cfl_history.csv')
        pd.DataFrame(self.cfl_history).to_csv(out_path, index=False)
        if self.verbos:
            print(f'[OK] CFL 时序已保存 -> {out_path}')

    def Save_perf_report(self):
        if not self.save_perf_report:
            return
        out_dir = self.model_data['output_path']
        os.makedirs(out_dir, exist_ok=True)
        total_time = float(self.caculation_time)
        node_summary = {}
        total_node_solves = 0
        total_node_iterations = 0
        total_node_closure_calls = 0
        total_node_solve_time = 0.0
        for node_name, rec in self._perf_internal_node_stats.items():
            solve_calls = max(int(rec['solve_calls']), 1)
            total_node_solves += int(rec['solve_calls'])
            total_node_iterations += int(rec['iterations'])
            total_node_closure_calls += int(rec['boundary_closure_calls'])
            total_node_solve_time += float(rec['solve_time'])
            fast_bucket = self._perf_stage_boundary.get('by_node', {}).get(
                node_name,
                {'calls': int(rec['fast_calls']), 'fast_hits': int(rec['fast_hits'])},
            )
            fast_calls = int(fast_bucket.get('calls', rec['fast_calls']))
            fast_hits = int(fast_bucket.get('fast_hits', rec['fast_hits']))
            node_summary[node_name] = {
                'solve_calls': int(rec['solve_calls']),
                'solve_time': float(rec['solve_time']),
                'avg_solve_time': float(rec['solve_time']) / solve_calls,
                'avg_iterations': float(rec['iterations']) / solve_calls,
                'avg_boundary_closure_calls': float(rec['boundary_closure_calls']) / solve_calls,
                'table_attempts': int(rec['table_attempts']),
                'table_success': int(rec['table_success']),
                'table_fallbacks': int(rec['table_fallbacks']),
                'exact_refine_iterations': int(rec['exact_refine_iterations']),
                'fast_calls': fast_calls,
                'fast_hits': fast_hits,
                'fast_hit_rate': float(fast_hits) / max(fast_calls, 1),
                'avg_final_abs_residual': float(rec['final_abs_residual_sum']) / solve_calls,
                'fallback_reasons': dict(rec['fallback_reasons']),
            }
        report = {
            'total_evolve_time': total_time,
            'section_wall_times': {
                key: {
                    'time': float(bucket['time']),
                    'calls': int(bucket['calls']),
                    'share_of_evolve': (float(bucket['time']) / total_time) if total_time > 0.0 else 0.0,
                }
                for key, bucket in self._perf_sections.items()
            },
            'local_river_compute_times': {
                key: {
                    'time': float(bucket['time']),
                    'calls': int(bucket['calls']),
                }
                for key, bucket in self._perf_local_sections.items()
            },
            'internal_node_summary': {
                'total_solves': int(total_node_solves),
                'avg_iterations': (float(total_node_iterations) / total_node_solves) if total_node_solves > 0 else 0.0,
                'avg_boundary_closure_calls': (float(total_node_closure_calls) / total_node_solves) if total_node_solves > 0 else 0.0,
                'total_solve_time': float(total_node_solve_time),
                'share_of_evolve': (float(total_node_solve_time) / total_time) if total_time > 0.0 else 0.0,
                'nodes': node_summary,
            },
            'stage_boundary_fastpath': deepcopy(self._perf_stage_boundary),
        }
        orchestration_phase_times = {
            key: {
                'time': float(bucket['time']),
                'calls': int(bucket['calls']),
            }
            for key, bucket in self._perf_internal_orchestration['phase_times'].items()
        }
        report['internal_node_orchestration'] = {
            'backend': self._perf_internal_orchestration.get('backend'),
            'solve_calls': int(self._perf_internal_orchestration.get('solve_calls', 0)),
            'phase_times': orchestration_phase_times,
            'round_trips': int(self._perf_internal_orchestration.get('round_trips', 0)),
            'payload_bytes_sent': int(self._perf_internal_orchestration.get('payload_bytes_sent', 0)),
            'payload_bytes_recv': int(self._perf_internal_orchestration.get('payload_bytes_recv', 0)),
            'river_side_applies': int(self._perf_internal_orchestration.get('river_side_applies', 0)),
            'final_snapshot_calls': int(self._perf_internal_orchestration.get('final_snapshot_calls', 0)),
            'backend_counts': dict(self._perf_internal_orchestration.get('backend_counts', {})),
        }
        json_path = os.path.join(out_dir, 'evolve_perf_report.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        md_lines = [
            '# Evolve Performance Report',
            '',
            f'- total evolve time: {total_time:.6f} s',
            '',
            '## Section Wall Time',
        ]
        for key, bucket in report['section_wall_times'].items():
            md_lines.append(
                f'- {key}: {bucket["time"]:.6f} s, calls={bucket["calls"]}, share={bucket["share_of_evolve"]:.2%}'
            )
        md_lines.extend([
            '',
            '## Internal Node Solve Summary',
            f'- total solves: {report["internal_node_summary"]["total_solves"]}',
            f'- avg iterations: {report["internal_node_summary"]["avg_iterations"]:.4f}',
            f'- avg boundary closure calls: {report["internal_node_summary"]["avg_boundary_closure_calls"]:.4f}',
            f'- total solve time: {report["internal_node_summary"]["total_solve_time"]:.6f} s',
            f'- share of evolve: {report["internal_node_summary"]["share_of_evolve"]:.2%}',
            '',
            '## Stage Boundary Fast Path',
            f'- closure calls: {report["stage_boundary_fastpath"]["overall"]["calls"]}',
            f'- cython fast attempts: {report["stage_boundary_fastpath"]["cython_fast_calls"]}',
            f'- cython fast hits: {report["stage_boundary_fastpath"]["cython_fast_hits"]}',
            f'- fast hit rate: {float(report["stage_boundary_fastpath"]["cython_fast_hits"]) / max(int(report["stage_boundary_fastpath"]["overall"]["calls"]), 1):.2%}',
            '',
            '## Local River Compute Times',
        ])
        for key, bucket in report['local_river_compute_times'].items():
            md_lines.append(f'- {key}: {bucket["time"]:.6f} s, calls={bucket["calls"]}')
        md_lines.extend(['', '## Per Node'])
        for node_name, rec in node_summary.items():
            md_lines.append(
                f'- {node_name}: avg_iter={rec["avg_iterations"]:.4f}, '
                f'avg_closure_calls={rec["avg_boundary_closure_calls"]:.4f}, '
                f'fast_hit_rate={rec["fast_hit_rate"]:.2%}, '
                f'table_success={rec["table_success"]}/{max(rec["table_attempts"], 1)}'
            )
        md_path = os.path.join(out_dir, 'evolve_perf_report.md')
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(md_lines) + '\n')

        def _append_ranked(lines, title, mapping, topn=None):
            lines.extend(['', title])
            items = sorted(mapping.items(), key=lambda item: (-item[1], item[0]))
            if topn is not None:
                items = items[:topn]
            if not items:
                lines.append('- none')
                return
            for key, value in items:
                lines.append(f'- {key}: {value}')

        audit = report['stage_boundary_fastpath']
        audit_lines = [
            '# Stage Boundary Fast-Path Audit',
            '',
            f'- total closure calls: {audit["overall"]["calls"]}',
            f'- cython fast attempts: {audit["cython_fast_calls"]}',
            f'- cython fast hits: {audit["cython_fast_hits"]}',
            f'- fast hit rate: {float(audit["cython_fast_hits"]) / max(int(audit["overall"]["calls"]), 1):.2%}',
        ]
        _append_ranked(audit_lines, '## Overall Precheck Blockers', audit.get('fast_reject_reasons', {}))
        _append_ranked(audit_lines, '## Overall Runtime Blockers', audit.get('runtime_reject_reasons', {}))
        audit_lines.extend(['', '## By Scenario'])
        for key, bucket in sorted(audit.get('by_scenario', {}).items()):
            hit_rate = float(bucket['fast_hits']) / max(int(bucket['calls']), 1)
            audit_lines.append(
                f'- {key}: calls={bucket["calls"]}, fast_hits={bucket["fast_hits"]}, fast_hit_rate={hit_rate:.2%}'
            )
            pre_top = sorted(bucket.get('precheck', {}).items(), key=lambda item: (-item[1], item[0]))[:5]
            run_top = sorted(bucket.get('runtime', {}).items(), key=lambda item: (-item[1], item[0]))[:5]
            audit_lines.append(f'  precheck={pre_top if pre_top else []}')
            audit_lines.append(f'  runtime={run_top if run_top else []}')
        audit_lines.extend(['', '## By Node'])
        for key, bucket in sorted(audit.get('by_node', {}).items()):
            hit_rate = float(bucket['fast_hits']) / max(int(bucket['calls']), 1)
            audit_lines.append(
                f'- {key}: calls={bucket["calls"]}, fast_hits={bucket["fast_hits"]}, fast_hit_rate={hit_rate:.2%}'
            )
        audit_lines.extend(['', '## By River Side'])
        for key, bucket in sorted(audit.get('by_river_side', {}).items()):
            hit_rate = float(bucket['fast_hits']) / max(int(bucket['calls']), 1)
            audit_lines.append(
                f'- {key}: calls={bucket["calls"]}, fast_hits={bucket["fast_hits"]}, fast_hit_rate={hit_rate:.2%}'
            )
        audit_lines.extend(['', '## By Call Scene'])
        for key, bucket in sorted(audit.get('by_call_scene', {}).items()):
            hit_rate = float(bucket['fast_hits']) / max(int(bucket['calls']), 1)
            audit_lines.append(
                f'- {key}: calls={bucket["calls"]}, fast_hits={bucket["fast_hits"]}, fast_hit_rate={hit_rate:.2%}'
            )
        audit_md_path = os.path.join(out_dir, 'stage_boundary_fastpath_audit.md')
        with open(audit_md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(audit_lines) + '\n')

        orchestration = report['internal_node_orchestration']
        orch_json_path = os.path.join(out_dir, 'internal_node_orchestration_profile.json')
        with open(orch_json_path, 'w', encoding='utf-8') as f:
            json.dump(orchestration, f, ensure_ascii=False, indent=2)

        phase_items = sorted(
            orchestration['phase_times'].items(),
            key=lambda item: (-item[1]['time'], item[0]),
        )
        total_node_solve_time = max(report['internal_node_summary']['total_solve_time'], 0.0)
        orch_lines = [
            '# Internal Node Orchestration Profile',
            '',
            f'- backend: {orchestration["backend"]}',
            f'- solve calls: {orchestration["solve_calls"]}',
            f'- round trips: {orchestration["round_trips"]}',
            f'- payload sent bytes: {orchestration["payload_bytes_sent"]}',
            f'- payload recv bytes: {orchestration["payload_bytes_recv"]}',
            f'- river-side applies: {orchestration["river_side_applies"]}',
            f'- final snapshot calls: {orchestration["final_snapshot_calls"]}',
            f'- avg round trips per solve: {float(orchestration["round_trips"]) / max(int(orchestration["solve_calls"]), 1):.4f}',
            f'- avg sent bytes per round trip: {float(orchestration["payload_bytes_sent"]) / max(int(orchestration["round_trips"]), 1):.2f}',
            f'- avg recv bytes per round trip: {float(orchestration["payload_bytes_recv"]) / max(int(orchestration["round_trips"]), 1):.2f}',
            f'- avg river-side applies per solve: {float(orchestration["river_side_applies"]) / max(int(orchestration["solve_calls"]), 1):.4f}',
            '',
            '## Phase Ranking',
        ]
        if phase_items:
            for key, bucket in phase_items:
                share = float(bucket['time']) / total_node_solve_time if total_node_solve_time > 0.0 else 0.0
                orch_lines.append(
                    f'- {key}: {bucket["time"]:.6f} s, calls={bucket["calls"]}, share_of_node_solve={share:.2%}'
                )
        else:
            orch_lines.append('- none')
        orch_md_path = os.path.join(out_dir, 'internal_node_orchestration_profile.md')
        with open(orch_md_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(orch_lines) + '\n')

    def _unpack_advance_local_step_results(self, result_map, collect_perf=False):
        if not collect_perf:
            return result_map
        dt_map = {}
        for name, payload in result_map.items():
            dt_map[name] = payload['dt']
            perf = payload.get('perf', {})
            for key, bucket in perf.get('section_times', {}).items():
                section_key = key
                self._perf_local_sections.setdefault(section_key, self._new_perf_bucket())
                self._perf_local_sections[section_key]['time'] += float(bucket.get('time', 0.0))
                self._perf_local_sections[section_key]['calls'] += int(bucket.get('calls', 0))
            self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
        return dt_map

    # 更新网格参数
    def Update_cell_property_net(self):
        self.call_river_function_by_name('Update_cell_proprity2')

    # 计算全局CFL时间步长
    def Caculate_global_CFL(self):
        dt_list = []
        dt_items = []

        # 计算每条河道的CFL时间步长
        for _, _, data in self._river_edges:
            dti = data['river'].Caculate_CFL_time_for_river_net()
            dt_list.append(dti)
            dt_items.append((data.get('name'), dti))

        self.cfl_allowed_dt = min(dt_list) # 计算全局最小时间步长
        self._record_cfl_history(dt_items)

        if self.verbos:
            print(f'全局最小CFL时间步长: {self.cfl_allowed_dt:.4f} 秒')

    def Set_global_time_step(self, dt):
        # 更新每条河道的时间步长
        for _, _, data in self._river_edges:
            data['river'].set_next_dt(dt)

    # 更新边界条件
    def Update_boundary_conditions(self):
        # 更新外部边界条件
        self.Update_external_boundary_conditions_V2()

        # 更新内部边界条件
        self.Update_internal_boundary_conditions()

    # 更新外部边界条件
    '''
    def Update_external_boundary_conditions(self):
        if self.verbos: print('更新外部入流边界')
        for n in self.external_in_nodes:
            # 获取边界条件及类型
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for u, v, data in self.G.out_edges(n, data=True):
                river_temp = data['river']
                if btype == 'flow': # 流量边界
                    river_temp.InBound_In_Q(value)
                elif btype == 'fix_level': # 固定水位边界
                    river_temp.InBound_Fix_level_V2(value)
            if self.verbos: print(river_temp.model_name, n, btype, value)

        if self.verbos: print('更新外部出流边界')
        for n in self.external_out_nodes:
            # 获取边界条件及类型
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for u, v, data in self.G.in_edges(n, data=True):
                river_temp = data['river']
                if btype == 'free': # 自由边界
                    river_temp.OutBound_Free_Outfall()
                elif btype == 'fix_level': # 固定水位边界
                    river_temp.OutBound_Fix_level_V2(value)
            if self.verbos: print(river_temp.model_name, n, btype, value)
    '''

    def Update_external_boundary_conditions_V2(self):
        if self.verbos: print('更新外部入流边界')
        for n in self.external_in_nodes:
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for r, _ in self._out_branches_by_node[n]:
                if btype == 'flow':
                    if self.external_flow_bc_use_characteristic and hasattr(r, 'InBound_In_Q2'):
                        r.InBound_In_Q2(value)
                    else:
                        r.InBound_In_Q(value)
                elif btype == 'fix_level':
                    # 用稳健版（一般断面 + Fr 限幅 + 水头限速 + ΔQ 限幅 + 欠松弛）
                    if self.use_fix_level_bc_v2:
                        r.InBound_Fix_level_V2(level=value)
                    else:
                        r.InBound_Fix_level_V3(
                            value, Fr_max=0.85, head_gain_factor=0.65,
                            relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7,
                            use_stabilizers=self.external_bc_use_stabilizers,
                            respect_supercritical=self.external_bc_respect_supercritical,
                            stage_on_face=self.external_bc_stage_on_face,
                            audit_context={
                                'scenario': 'external_in',
                                'node': n,
                                'river': getattr(r, 'model_name', 'unknown'),
                                'call_scene': 'external_in',
                            } if self.save_perf_report else None,
                        )
            if self.verbos: print(r.model_name, n, btype, value)

        if self.verbos: print('更新外部出流边界')
        for n in self.external_out_nodes:
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for r, _ in self._in_branches_by_node[n]:
                if btype == 'free':
                    r.OutBound_Free_Outfall()
                elif btype == 'fix_level':
                    if self.use_fix_level_bc_v2:
                        r.OutBound_Fix_level_V2(level=value)
                    else:
                        r.OutBound_Fix_level_V3(
                            value, Fr_max=0.85, head_gain_factor=0.65,
                            relax_Q=0.4, cap_du_factor=0.8, cap_dQ_factor=0.7,
                            use_stabilizers=self.external_bc_use_stabilizers,
                            respect_supercritical=self.external_bc_respect_supercritical,
                            stage_on_face=self.external_bc_stage_on_face,
                            audit_context={
                                'scenario': 'external_out',
                                'node': n,
                                'river': getattr(r, 'model_name', 'unknown'),
                                'call_scene': 'external_out',
                            } if self.save_perf_report else None,
                        )
            if self.verbos: print(r.model_name, n, btype, value)

    # 判断流态
    def _branch_regime(self, A, T, Q, flow_dir_sign):
        """基于相邻实格判断分支流态: 'sub' | 'super_in' | 'super_out'"""
        g = self.g
        A = float(max(A, 1e-12))
        T = float(max(T, 1e-8))
        u = float(Q) / A
        c = (g * A / T) ** 0.5
        Fr = abs(u) / max(c, 1e-12)

        if Fr < 1.0:
            return 'sub', u, c, Fr
        # flow_dir_sign: +1 表示该支“指向汊点为正向”；-1 表示“远离汊点为正向”
        if flow_dir_sign * Q > 0:
            return 'super_in', u, c, Fr   # 超临界且指向汊点 → 来流，上游控制
        else:
            return 'super_out', u, c, Fr  # 超临界且离开汊点 → 出流，受结点控制

    def _is_monotonic_series(self, values, tol=1.0e-12):
        if len(values) < 3:
            return True
        diffs = np.diff(np.asarray(values, dtype=float))
        nonzero = diffs[np.abs(diffs) > tol]
        if nonzero.size == 0:
            return True
        sign = 1.0 if nonzero[0] > 0.0 else -1.0
        return bool(np.all(nonzero * sign >= -tol))

    def _node_response_eta_grid(self, node_name, center_eta):
        center = max(0.0, float(center_eta))
        span = float(self.internal_response_base_span)
        cache = self._internal_node_solver_cache.get(node_name)
        if cache is not None:
            last_level = cache.get('last_level')
            prev_level = cache.get('prev_level')
            if last_level is not None and prev_level is not None and np.isfinite(last_level) and np.isfinite(prev_level):
                span = max(span, min(self.internal_response_max_span, 2.0 * abs(float(last_level) - float(prev_level))))
            last_residual = cache.get('last_residual')
            last_dR = cache.get('last_dR_dZ')
            if (
                last_residual is not None and last_dR is not None
                and np.isfinite(last_residual) and np.isfinite(last_dR)
                and abs(float(last_dR)) > 1.0e-10
            ):
                span = max(span, min(self.internal_response_max_span, 1.5 * abs(float(last_residual) / float(last_dR))))
        span = min(max(span, 0.05), float(self.internal_response_max_span))
        n_samples = max(int(self.internal_response_samples), 5)
        lo = max(0.0, center - span)
        hi = center + span
        if hi <= lo + 1.0e-8:
            hi = lo + max(span, 0.05)
        return np.linspace(lo, hi, n_samples, dtype=float)

    def _node_residual_pure(self, node_name, level):
        residual = 0.0
        closure_calls = 0
        fast_calls = 0
        fast_hits = 0
        reasons = {}
        for spec in self._internal_node_branch_specs(node_name):
            response = spec['river_obj']._evaluate_stage_boundary_response(
                spec['side'],
                level,
                **self._internal_boundary_kwargs(),
                update_prev=False,
            )
            closure_calls += 1
            fast_calls += 1
            if response.get('mode') == 'cython_fast':
                fast_hits += 1
            if response.get('status') != 'ok':
                reason = str(response.get('status'))
                reasons[reason] = int(reasons.get(reason, 0)) + 1
                return {
                    'valid': False,
                    'residual': np.nan,
                    'closure_calls': closure_calls,
                    'fast_calls': fast_calls,
                    'fast_hits': fast_hits,
                    'reasons': reasons,
                }
            residual += float(spec['flow_sign']) * float(response['Qb'])
        return {
            'valid': True,
            'residual': float(residual),
            'closure_calls': closure_calls,
            'fast_calls': fast_calls,
            'fast_hits': fast_hits,
            'reasons': reasons,
        }

    def _build_node_response_table_serial(self, node_name, center_eta):
        etas = self._node_response_eta_grid(node_name, center_eta)
        residual = np.zeros(etas.shape[0], dtype=float)
        closure_calls = 0
        fast_calls = 0
        fast_hits = 0
        reasons = {}
        # Important: this is a per-time-step local response table with frozen
        # adjacent interior states. It is not a static mapping from external
        # inflow Q(t) to node stage.
        for spec in self._internal_node_branch_specs(node_name):
            q_series = []
            a_series = []
            t_series = []
            for idx, eta in enumerate(etas):
                response = spec['river_obj']._evaluate_stage_boundary_response(
                    spec['side'],
                    float(eta),
                    **self._internal_boundary_kwargs(),
                    update_prev=False,
                )
                closure_calls += 1
                fast_calls += 1
                if response.get('mode') == 'cython_fast':
                    fast_hits += 1
                if response.get('status') != 'ok':
                    reason = str(response.get('status'))
                    reasons[reason] = int(reasons.get(reason, 0)) + 1
                    return {
                        'valid': False,
                        'etas': etas,
                        'residual': residual,
                        'closure_calls': closure_calls,
                        'fast_calls': fast_calls,
                        'fast_hits': fast_hits,
                        'reasons': reasons,
                    }
                q_val = float(response['Qb'])
                a_val = float(response['Ab'])
                t_val = float(response.get('Tb', 0.0))
                q_series.append(q_val)
                a_series.append(a_val)
                t_series.append(t_val)
                residual[idx] += float(spec['flow_sign']) * q_val
            if (not self._is_monotonic_series(q_series)) or (not self._is_monotonic_series(a_series)) or (not self._is_monotonic_series(t_series)):
                reasons['non_monotonic'] = int(reasons.get('non_monotonic', 0)) + 1
                return {
                    'valid': False,
                    'etas': etas,
                    'residual': residual,
                    'closure_calls': closure_calls,
                    'fast_calls': fast_calls,
                    'fast_hits': fast_hits,
                    'reasons': reasons,
                }
        if not self._is_monotonic_series(residual):
            reasons['residual_non_monotonic'] = int(reasons.get('residual_non_monotonic', 0)) + 1
            return {
                'valid': False,
                'etas': etas,
                'residual': residual,
                'closure_calls': closure_calls,
                'fast_calls': fast_calls,
                'fast_hits': fast_hits,
                'reasons': reasons,
            }
        return {
            'valid': True,
            'etas': etas,
            'residual': residual,
            'closure_calls': closure_calls,
            'fast_calls': fast_calls,
            'fast_hits': fast_hits,
            'reasons': reasons,
        }

    def _node_response_root_from_table(self, table):
        etas = np.asarray(table.get('etas', table.get('eta')), dtype=float)
        residual = np.asarray(table['residual'], dtype=float)
        min_idx = int(np.argmin(np.abs(residual)))
        if abs(float(residual[min_idx])) <= self.JPWSPC_Q_limit:
            slope = 0.0
            if 0 < min_idx < residual.size - 1:
                denom = float(etas[min_idx + 1] - etas[min_idx - 1])
                if abs(denom) > 1.0e-12:
                    slope = float((residual[min_idx + 1] - residual[min_idx - 1]) / denom)
            return {
                'success': True,
                'eta': float(etas[min_idx]),
                'slope': float(slope),
            }
        for idx in range(residual.size - 1):
            r0 = float(residual[idx])
            r1 = float(residual[idx + 1])
            if r0 == 0.0:
                return {'success': True, 'eta': float(etas[idx]), 'slope': 0.0}
            if r0 * r1 <= 0.0:
                z0 = float(etas[idx])
                z1 = float(etas[idx + 1])
                if abs(r1 - r0) > 1.0e-12:
                    eta = z0 - r0 * (z1 - z0) / (r1 - r0)
                else:
                    eta = 0.5 * (z0 + z1)
                slope = (r1 - r0) / max(z1 - z0, 1.0e-12)
                return {'success': True, 'eta': float(eta), 'slope': float(slope)}
        return {'success': False}

    def _refine_node_level_pure(self, node_name, eta_guess, slope_hint=0.0):
        eta = max(0.0, float(eta_guess))
        eta_prev = None
        residual_prev = None
        closure_calls = 0
        fast_calls = 0
        fast_hits = 0
        iterations = 0
        last_eval = None
        slope = float(slope_hint)
        for _ in range(max(int(self.internal_response_refine_steps), 1)):
            iterations += 1
            last_eval = self._node_residual_pure(node_name, eta)
            closure_calls += int(last_eval['closure_calls'])
            fast_calls += int(last_eval['fast_calls'])
            fast_hits += int(last_eval['fast_hits'])
            if (not last_eval['valid']) or abs(float(last_eval['residual'])) <= self.JPWSPC_Q_limit:
                break
            if eta_prev is not None and abs(eta - eta_prev) > 1.0e-10:
                slope = float((last_eval['residual'] - residual_prev) / (eta - eta_prev))
            elif abs(slope) <= 1.0e-10:
                cache = self._internal_node_solver_cache.get(node_name, {})
                slope = float(cache.get('last_dR_dZ', 0.0) or 0.0)
            if abs(slope) <= 1.0e-10:
                break
            dz = -float(last_eval['residual']) / slope
            if not self.internal_use_paper_ac:
                dz = float(np.clip(dz, -0.5, 0.5))
            dz = self.relax * dz
            eta_prev = eta
            residual_prev = float(last_eval['residual'])
            eta = max(0.0, eta + dz)
        return {
            'eta': float(eta),
            'iterations': int(iterations),
            'closure_calls': int(closure_calls),
            'fast_calls': int(fast_calls),
            'fast_hits': int(fast_hits),
            'eval': last_eval,
            'slope': float(slope),
        }

    def _initial_internal_node_levels(self, use_node_aggregates=False, aggregates=None, snapshots=None, extrapolate=False):
        node_levels = {}
        for n in self.internal_nodes:
            if self.internal_level_predict_from_last and n in self._internal_node_level_cache:
                z0 = float(self._internal_node_level_cache[n])
            else:
                if use_node_aggregates:
                    z0 = float(self._parallel_node_average_level_at_real_cell_from_aggregates(n, aggregates))
                elif snapshots is not None:
                    z0 = float(self._parallel_node_average_level_at_real_cell(n, snapshots))
                else:
                    z0 = float(self.Caculate_node_average_level_at_real_cell(n))
                if np.isnan(z0):
                    if use_node_aggregates:
                        z0 = float(self._parallel_node_average_level_at_ghost_cell_from_aggregates(n, aggregates))
                    elif snapshots is not None:
                        z0 = float(self._parallel_node_average_level_at_ghost_cell(n, snapshots))
                    else:
                        z0 = float(self.Caculate_node_average_level_at_ghost_cell(n))
                if np.isnan(z0):
                    z0 = 0.0
            if extrapolate:
                node_levels[n] = max(0.0, self._predict_internal_node_level(n, z0))
            else:
                node_levels[n] = max(0.0, z0)
        return node_levels

    def _build_parallel_node_response_jobs(self, node_levels):
        jobs = []
        boundary_kwargs = self._internal_boundary_kwargs()
        for node_name in self.internal_nodes:
            etas = self._node_response_eta_grid(node_name, node_levels[node_name])
            for spec in self._internal_node_branch_specs(node_name):
                jobs.append({
                    'node': node_name,
                    'river': spec['river'],
                    'side': spec['side'],
                    'flow_sign': float(spec['flow_sign']),
                    'etas': [float(v) for v in etas],
                })
        return jobs, boundary_kwargs

    def _node_mass_residual(self, node: str, level: float) -> float:
        """施加结点水位后，返回结点质量守恒残差（入流-出流）。"""
        self.Apply_node_target_level_V4(node, level)
        if self.internal_node_use_face_flux_residual:
            self._update_boundary_flux_for_current_state()
        return float(self._get_node_mass_residual_current_state(node))

    def _node_mass_jacobian_numeric(self, node: str, level: float, residual_at_level: float | None = None) -> float:
        """
        对结点残差 R(level) 做单边差分，得到 dR/dZ。
        说明：R = ΣQ_in - ΣQ_out，牛顿步使用 dZ = -R/(dR/dZ)。
        """
        if residual_at_level is None:
            residual_at_level = self._node_mass_residual(node, level)

        dlevel = max(1e-4, 1e-3 * max(1.0, abs(level)))
        r_plus = self._node_mass_residual(node, level + dlevel)
        return (r_plus - residual_at_level) / dlevel

    def _apply_internal_node_levels(self, node_levels: dict[str, float]) -> None:
        """
        对当前所有内部结点同步施加目标水位，避免按结点顺序更新带来的偏置。
        """
        for n in self.internal_nodes:
            self.Apply_node_target_level_V4(n, float(node_levels[n]))
        if self.internal_sync_branch_end_Q:
            self._synchronize_internal_branch_end_discharge()
        if self.internal_node_use_face_flux_residual:
            self._update_boundary_flux_for_current_state()

    def _update_boundary_flux_for_current_state(self) -> None:
        """
        基于当前 ghost/real 状态重算界面通量。
        结点迭代阶段若以“界面质量通量”作为残差口径，需要先刷新 Flux_LOC。
        """
        self.Caculate_face_U_C_net()
        self.Caculate_Roe_matrix_net()
        self.Caculate_Source_term_net()
        self.Caculate_Roe_flux_net()

    def _synchronize_internal_branch_end_discharge(self) -> None:
        """
        对“内部节点-内部节点”连接支路，在结点修正阶段同步两端鬼格流量：
        Q_left <- Q_left + r*(Qm-Q_left), Q_right <- Q_right + r*(Qm-Q_right), Qm=(Q_left+Q_right)/2

        说明：JPWSPC 结点修正本质上依赖“给定端点水位后支路响应流量”，
        对连接两个内部结点的支路，若两端各自边界计算不一致，会引入额外残差偏置。
        此同步步骤仅在结点修正阶段启用，不改动主方程离散与输出后处理。
        """
        relax = float(np.clip(self.internal_sync_branch_end_Q_relax, 0.0, 1.0))
        if relax <= 0.0:
            return

        internal_set = set(self.internal_nodes)
        for u, v, data in self._river_edges:
            if u not in internal_set or v not in internal_set:
                continue
            r = data['river']
            q_left = float(r.Q[0])
            q_right = float(r.Q[-1])
            q_mid = 0.5 * (q_left + q_right)
            r.Q[0] = q_left + relax * (q_mid - q_left)
            r.Q[-1] = q_right + relax * (q_mid - q_right)
            # 仅同步边界流量，不改目标水位；刷新派生量供后续残差/雅可比使用
            if hasattr(r, '_refresh_cell_state'):
                r._refresh_cell_state(0, level_hint=float(r.water_level[0]))
                r._refresh_cell_state(-1, level_hint=float(r.water_level[-1]))

    def _node_mass_jacobian_numeric_with_map(
            self,
            node: str,
            node_levels: dict[str, float],
            residual_at_level: float
    ) -> float:
        """
        在“其余结点水位固定”为 node_levels 的条件下，对指定结点做数值导数 dR/dZ。
        """
        base_level = float(node_levels[node])
        dlevel = max(1e-4, 1e-3 * max(1.0, abs(base_level)))
        level_map_plus = dict(node_levels)
        level_map_plus[node] = max(0.0, base_level + dlevel)

        self._apply_internal_node_levels(level_map_plus)
        r_plus = float(self._get_node_mass_residual_current_state(node))

        # 恢复到基准水位场，保证后续结点导数计算一致
        self._apply_internal_node_levels(node_levels)
        return (r_plus - residual_at_level) / dlevel

    def _internal_residual_vector(self, node_levels: dict[str, float]) -> np.ndarray:
        """
        在给定全部内部结点水位下，返回残差向量 R（顺序与 self.internal_nodes 一致）：
        R_i = Qin_i - Qout_i。
        """
        self._apply_internal_node_levels(node_levels)
        return np.asarray(
            [float(self._get_node_mass_residual_current_state(n)) for n in self.internal_nodes],
            dtype=float
        )

    def _internal_jacobian_numeric(self, node_levels: dict[str, float], residual_vec: np.ndarray) -> np.ndarray:
        """
        数值差分构造全耦合雅可比 J_{ij} = dR_i/dZ_j（其余结点水位固定）。
        """
        m = len(self.internal_nodes)
        J = np.zeros((m, m), dtype=float)
        for j, node_j in enumerate(self.internal_nodes):
            base_level = float(node_levels[node_j])
            dlevel = max(1e-4, 1e-3 * max(1.0, abs(base_level)))
            plus_map = dict(node_levels)
            plus_map[node_j] = max(0.0, base_level + dlevel)
            r_plus = self._internal_residual_vector(plus_map)
            J[:, j] = (r_plus - residual_vec) / dlevel

        # 恢复基准水位场，确保后续边界一致
        self._apply_internal_node_levels(node_levels)
        return J

    def _prepare_internal_node_initial_guess_serial(self, node_levels):
        guess_levels = dict(node_levels)
        guess_stats = {}
        if not self._internal_response_solver_supported():
            return guess_levels, guess_stats
        for node_name in self.internal_nodes:
            t0 = time.perf_counter()
            table = self._build_node_response_table_serial(node_name, guess_levels[node_name])
            elapsed = time.perf_counter() - t0
            guess_stats[node_name] = {
                'time': float(elapsed),
                'closure_calls': int(table['closure_calls']),
                'fast_calls': int(table['fast_calls']),
                'fast_hits': int(table['fast_hits']),
                'table_attempted': True,
                'table_success': False,
                'fallback_reason': None,
            }
            if not table['valid']:
                fallback_reason = next(iter(table['reasons']), 'table_invalid')
                guess_stats[node_name]['fallback_reason'] = fallback_reason
                continue
            root = self._node_response_root_from_table(table)
            if not root.get('success', False):
                guess_stats[node_name]['fallback_reason'] = 'no_bracket'
                continue
            guess_levels[node_name] = max(0.0, float(root['eta']))
            guess_stats[node_name]['table_success'] = True
            guess_stats[node_name]['slope'] = float(root.get('slope', 0.0))
        return guess_levels, guess_stats

    def _solve_internal_nodes_exact_serial(self, node_levels, guess_stats=None):
        guess_stats = {} if guess_stats is None else guess_stats
        solve_start = time.perf_counter()
        converged = False
        max_abs_q = np.inf
        iter_count = 0
        if self.internal_use_coupled_newton:
            m = len(self.internal_nodes)
            for iter_time in range(1, self.max_iteration + 1):
                iter_count = iter_time
                r_vec = self._internal_residual_vector(node_levels)
                max_abs_q = float(np.max(np.abs(r_vec))) if r_vec.size > 0 else 0.0

                J = self._internal_jacobian_numeric(node_levels, r_vec)
                J_reg = J + 1e-9 * np.eye(m)
                try:
                    dz_vec = np.linalg.solve(J_reg, -r_vec)
                except np.linalg.LinAlgError:
                    dz_vec = np.linalg.lstsq(J_reg, -r_vec, rcond=None)[0]

                if not self.internal_use_paper_ac:
                    dz_vec = np.clip(dz_vec, -0.5, 0.5)
                dz_vec = self.relax * dz_vec
                max_abs_dz = float(np.max(np.abs(dz_vec))) if dz_vec.size > 0 else 0.0

                for i, n in enumerate(self.internal_nodes):
                    node_levels[n] = max(0.0, float(node_levels[n] + dz_vec[i]))
                    if self.verbos:
                        print(
                            f'节点 {n} 第{iter_time}次迭代(耦合牛顿): '
                            f'R={r_vec[i]:.4e}, dz={dz_vec[i]:.4e}, 新水位={node_levels[n]:.4f}'
                        )

                if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                    converged = True
                    break
        else:
            for iter_time in range(1, self.max_iteration + 1):
                iter_count = iter_time
                self._apply_internal_node_levels(node_levels)

                node_residual = {}
                max_abs_q = 0.0
                for n in self.internal_nodes:
                    pure_Q = float(self._get_node_mass_residual_current_state(n))
                    node_residual[n] = pure_Q
                    max_abs_q = max(max_abs_q, abs(pure_Q))

                new_levels = dict(node_levels)
                max_abs_dz = 0.0
                for n in self.internal_nodes:
                    pure_Q = node_residual[n]

                    if self.internal_use_numeric_jacobian:
                        dR_dZ = self._node_mass_jacobian_numeric_with_map(n, node_levels, pure_Q)
                        if abs(dR_dZ) < 1e-10:
                            if self.internal_use_paper_ac:
                                ac = float(self.Caculate_node_Ac_at_ghost_cell_JPWSPC(n))
                            elif self.internal_use_ac_v2:
                                ac = float(self.Caculate_node_Ac_at_ghost_cell_V2(n))
                            else:
                                ac = float(self.Caculate_node_Ac_at_ghost_cell(n))
                            dR_dZ = -ac
                    else:
                        if self.internal_use_paper_ac:
                            ac = float(self.Caculate_node_Ac_at_ghost_cell_JPWSPC(n))
                        elif self.internal_use_ac_v2:
                            ac = float(self.Caculate_node_Ac_at_ghost_cell_V2(n))
                        else:
                            ac = float(self.Caculate_node_Ac_at_ghost_cell(n))
                        dR_dZ = -ac

                    if abs(dR_dZ) < 1e-10:
                        dz = 0.0
                    else:
                        dz = -pure_Q / dR_dZ

                    if not self.internal_use_paper_ac:
                        dz = float(np.clip(dz, -0.5, 0.5))
                    dz = self.relax * dz
                    new_levels[n] = max(0.0, node_levels[n] + dz)
                    max_abs_dz = max(max_abs_dz, abs(dz))

                    if self.verbos:
                        print(
                            f'节点 {n} 第{iter_time}次迭代: '
                            f'pure_Q={pure_Q:.4e}, dR_dZ={dR_dZ:.4e}, dz={dz:.4e}, 新水位={new_levels[n]:.4f}'
                        )

                node_levels = new_levels
                if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                    converged = True
                    break

        self._apply_internal_node_levels(node_levels)
        self._internal_node_level_cache.update(node_levels)
        solve_time = time.perf_counter() - solve_start
        per_node_time = solve_time / max(len(self.internal_nodes), 1)
        final_residuals = {}
        for n in self.internal_nodes:
            final_residuals[n] = float(self._get_node_mass_residual_current_state(n))
            self._update_internal_node_solver_cache(n, node_levels[n], residual=final_residuals[n])
        for n in self.internal_nodes:
            branch_calls = len(self._internal_node_branch_specs(n)) * (iter_count + 1)
            pre = guess_stats.get(n, {})
            self._perf_record_node_solve(
                n,
                solve_time=per_node_time + float(pre.get('time', 0.0)),
                iterations=int(iter_count),
                boundary_closure_calls=int(branch_calls + pre.get('closure_calls', 0)),
                table_attempted=bool(pre.get('table_attempted', False)),
                table_success=bool(pre.get('table_success', False)),
                fast_calls=int(pre.get('fast_calls', 0)),
                fast_hits=int(pre.get('fast_hits', 0)),
                exact_refine_iterations=int(iter_count),
                final_abs_residual=final_residuals[n],
                fallback_reason=pre.get('fallback_reason'),
            )

        if self.verbos:
            if not converged:
                print(f'内部边界迭代达到上限 {self.max_iteration} 次，max|Qnet|={max_abs_q:.4e}')
            for n in self.internal_nodes:
                print(f'节点 {n} 最终水位: {node_levels[n]:.4f} 米')

    def _solve_internal_nodes_exact_serial_legacy_default(self, node_levels):
        converged = False
        max_abs_q = np.inf
        if self.internal_use_coupled_newton:
            m = len(self.internal_nodes)
            for iter_time in range(1, self.max_iteration + 1):
                r_vec = self._internal_residual_vector(node_levels)
                max_abs_q = float(np.max(np.abs(r_vec))) if r_vec.size > 0 else 0.0

                J = self._internal_jacobian_numeric(node_levels, r_vec)
                J_reg = J + 1e-9 * np.eye(m)
                try:
                    dz_vec = np.linalg.solve(J_reg, -r_vec)
                except np.linalg.LinAlgError:
                    dz_vec = np.linalg.lstsq(J_reg, -r_vec, rcond=None)[0]

                if not self.internal_use_paper_ac:
                    dz_vec = np.clip(dz_vec, -0.5, 0.5)
                dz_vec = self.relax * dz_vec
                max_abs_dz = float(np.max(np.abs(dz_vec))) if dz_vec.size > 0 else 0.0

                for i, n in enumerate(self.internal_nodes):
                    node_levels[n] = max(0.0, float(node_levels[n] + dz_vec[i]))
                    if self.verbos:
                        print(
                            f'节点 {n} 第{iter_time}次迭代(耦合牛顿): '
                            f'R={r_vec[i]:.4e}, dz={dz_vec[i]:.4e}, 新水位={node_levels[n]:.4f}'
                        )

                if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                    converged = True
                    break
        else:
            for iter_time in range(1, self.max_iteration + 1):
                self._apply_internal_node_levels(node_levels)

                node_residual = {}
                max_abs_q = 0.0
                for n in self.internal_nodes:
                    pure_Q = float(self._get_node_mass_residual_current_state(n))
                    node_residual[n] = pure_Q
                    max_abs_q = max(max_abs_q, abs(pure_Q))

                new_levels = dict(node_levels)
                max_abs_dz = 0.0
                for n in self.internal_nodes:
                    pure_Q = node_residual[n]

                    if self.internal_use_numeric_jacobian:
                        dR_dZ = self._node_mass_jacobian_numeric_with_map(n, node_levels, pure_Q)
                        if abs(dR_dZ) < 1e-10:
                            if self.internal_use_paper_ac:
                                ac = float(self.Caculate_node_Ac_at_ghost_cell_JPWSPC(n))
                            elif self.internal_use_ac_v2:
                                ac = float(self.Caculate_node_Ac_at_ghost_cell_V2(n))
                            else:
                                ac = float(self.Caculate_node_Ac_at_ghost_cell(n))
                            dR_dZ = -ac
                    else:
                        if self.internal_use_paper_ac:
                            ac = float(self.Caculate_node_Ac_at_ghost_cell_JPWSPC(n))
                        elif self.internal_use_ac_v2:
                            ac = float(self.Caculate_node_Ac_at_ghost_cell_V2(n))
                        else:
                            ac = float(self.Caculate_node_Ac_at_ghost_cell(n))
                        dR_dZ = -ac

                    if abs(dR_dZ) < 1e-10:
                        dz = 0.0
                    else:
                        dz = -pure_Q / dR_dZ

                    if not self.internal_use_paper_ac:
                        dz = float(np.clip(dz, -0.5, 0.5))
                    dz = self.relax * dz
                    new_levels[n] = max(0.0, node_levels[n] + dz)
                    max_abs_dz = max(max_abs_dz, abs(dz))

                    if self.verbos:
                        print(
                            f'节点 {n} 第{iter_time}次迭代: '
                            f'pure_Q={pure_Q:.4e}, dR_dZ={dR_dZ:.4e}, dz={dz:.4e}, 新水位={new_levels[n]:.4f}'
                        )

                node_levels = new_levels
                if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                    converged = True
                    break

        self._apply_internal_node_levels(node_levels)
        self._internal_node_level_cache.update(node_levels)
        if self.verbos:
            if not converged:
                print(f'内部边界迭代达到上限 {self.max_iteration} 次，max|Qnet|={max_abs_q:.4e}')
            for n in self.internal_nodes:
                print(f'节点 {n} 最终水位: {node_levels[n]:.4f} 米')

    # 更新内部边界条件
    def Update_internal_boundary_conditions(self):
        if self.verbos: print('\n更新内部边界条件...')
        if not self.internal_nodes:
            return
        if self._fast_internal_solver_active():
            node_levels = self._initial_internal_node_levels(extrapolate=True)
            self._solve_internal_nodes_fast_serial(node_levels)
            return
        if self._legacy_internal_exact_default_active():
            node_levels = self._initial_internal_node_levels()
            self._solve_internal_nodes_exact_serial_legacy_default(node_levels)
            return
        node_levels = self._initial_internal_node_levels()
        t0 = time.perf_counter() if self.save_perf_report else 0.0
        guess_levels, guess_stats = self._prepare_internal_node_initial_guess_serial(node_levels)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('initial_guess', time.perf_counter() - t0)
        backend = self._select_serial_internal_backend()
        if backend == 'fused_serial':
            self._solve_internal_nodes_exact_fused_serial(guess_levels, guess_stats=guess_stats)
            return
        self._perf_record_internal_backend('legacy_serial')
        self._solve_internal_nodes_exact_serial(guess_levels, guess_stats=guess_stats)


    # 计算节点处真实网格的平均水位
    def Caculate_node_average_level_at_real_cell(self, node):
        level_list = []
        river_name = []

        # 流入节点边
        for river_temp, name in self._in_branches_by_node[node]:
            level_list.append(river_temp.water_level[-2])
            river_name.append(name)

        # 流出节点边
        for river_temp, name in self._out_branches_by_node[node]:
            level_list.append(river_temp.water_level[1])
            river_name.append(name)

        if level_list:
            result = np.average(level_list)
        else:
            result = np.nan

        if self.verbos:
            print(f'节点 {node} 处的真实网格平均水位: {result:.2f} 米 (基于河道{river_name})')

        return result

    # 计算节点处Ac
    def Caculate_node_Ac_at_ghost_cell(self, node):
        ac = 0

        # 流入节点边
        for river_temp, _ in self._in_branches_by_node[node]:

            level_temp = river_temp.water_level[-1]  # 获取流入节点的水位
            section_name_temp = river_temp.cell_sections[-1]  # 虚拟网格对应断面名称

            A = river_temp.S[-1]  # 对应位置的水面面积
            B = river_temp.cross_section_table.get_width_by_area(section_name_temp, A)  # 获取对应断面宽度
            Q = river_temp.Q[-1]

            ac += (np.sqrt(self.g * A * B) - Q * B / A)

        # 流出节点边
        for river_temp, _ in self._out_branches_by_node[node]:
            level_temp = river_temp.water_level[0]
            section_name_temp = river_temp.cell_sections[0]  # 虚拟网格对应断面名称
            A = river_temp.S[0]  # 对应位置的水面面积
            B = river_temp.cross_section_table.get_width_by_area(section_name_temp, A)
            Q = river_temp.Q[0]
            ac += (np.sqrt(self.g * A * B) + Q * B / A)

            # 返回Ac
        return self.alpha * ac

    # GPT 修改
    def Caculate_node_Ac_at_ghost_cell_V2(self, node):
        ac = 0.0
        alpha = self.alpha
        epsA = 1e-12

        # 入支（node 为下游端）
        for r, _ in self._in_branches_by_node[node]:
            A2 = float(r.S[-2]); T2 = float(r.cross_section_table.get_width_by_area(r.cell_sections[-2], max(A2, epsA)))
            Q2 = float(r.Q[-2])
            regime, u_loc, c_loc, Fr_loc = self._branch_regime(A2, T2, Q2, flow_dir_sign=+1)
            if regime != 'super_in':           # 仅对受控分支计入导数
                ac += T2 * (c_loc - u_loc)

        # 出支（node 为上游端）
        for r, _ in self._out_branches_by_node[node]:
            A1 = float(r.S[1]); T1 = float(r.cross_section_table.get_width_by_area(r.cell_sections[1], max(A1, epsA)))
            Q1 = float(r.Q[1])
            regime, u_loc, c_loc, Fr_loc = self._branch_regime(A1, T1, Q1, flow_dir_sign=-1)
            if regime != 'super_in':
                ac += T1 * (c_loc + u_loc)

        return alpha * ac

    def Caculate_node_Ac_at_ghost_cell_JPWSPC(self, node):
        """
        论文 JPWSPC 近似：直接基于结点端（ghost）状态构造 Ac 分母项。
        对应形式：
          Σ_in (sqrt(gAB) - Q*B/A) + Σ_out (sqrt(gAB) + Q*B/A)
        """
        ac = 0.0
        epsA = 1e-12

        for r, _ in self._in_branches_by_node[node]:
            A_face = getattr(r, 'boundary_face_area_right', None)
            B_face = getattr(r, 'boundary_face_width_right', None)
            Q_face = getattr(r, 'boundary_face_discharge_right', None)
            if self.internal_node_use_boundary_face_ac and A_face is not None and B_face is not None and Q_face is not None:
                A = float(max(A_face, epsA))
                B = float(max(B_face, epsA))
                Q = float(Q_face)
            else:
                A = float(max(r.S[-1], epsA))
                B = float(r.cross_section_table.get_width_by_area(r.cell_sections[-1], A))
                Q = float(r.Q[-1])
            ac += (np.sqrt(self.g * A * B) - Q * B / A)

        for r, _ in self._out_branches_by_node[node]:
            A_face = getattr(r, 'boundary_face_area_left', None)
            B_face = getattr(r, 'boundary_face_width_left', None)
            Q_face = getattr(r, 'boundary_face_discharge_left', None)
            if self.internal_node_use_boundary_face_ac and A_face is not None and B_face is not None and Q_face is not None:
                A = float(max(A_face, epsA))
                B = float(max(B_face, epsA))
                Q = float(Q_face)
            else:
                A = float(max(r.S[0], epsA))
                B = float(r.cross_section_table.get_width_by_area(r.cell_sections[0], A))
                Q = float(r.Q[0])
            ac += (np.sqrt(self.g * A * B) + Q * B / A)

        return self.alpha * ac



    # 计算节点处虚拟网格的平均水位
    def Caculate_node_average_level_at_ghost_cell(self, node):
        level_list = []
        river_name = []

        # 流入节点边
        for river_temp, name in self._in_branches_by_node[node]:
            level_list.append(river_temp.water_level[-1])
            river_name.append(name)

        # 流出节点边
        for river_temp, name in self._out_branches_by_node[node]:
            level_list.append(river_temp.water_level[0])
            river_name.append(name)

        if level_list:
            result = np.average(level_list)
        else:
            result = np.nan

        if self.verbos:
            print(f'节点 {node} 处的虚拟网格平均水位: {result:.2f} 米 (基于河道{river_name})')
        return result

    # 将计算出的汊点水位应用
    def Apply_node_target_level(self, node, level):
        # 流入节点的边
        for river_temp, _ in self._in_branches_by_node[node]:
            river_temp.OutBound_Fix_level_V2(level)

        # 流出节点的边
        for river_temp, _ in self._out_branches_by_node[node]:
            river_temp.InBound_Fix_level_V2(level)

    def Apply_node_target_level_V2(self, node, level):
        # —— 流入结点的边（结点在下游端），检查相邻实单元 -2 的流态与流向
        for r, _ in self._in_branches_by_node[node]:
            U = r.U[-2]; C = r.C[-2]
            # 若超临界且速度指向离开结点（即从结点往上游方向），结点水位对该支路不起作用 -> 外推
            if abs(U) >= 0.95 * C and r.Q[-2] < 0:
                r.S[-1] = r.S[-2]
                r.Q[-1] = r.Q[-2]
            else:
                r.OutBound_Fix_level_V2(level)   # 仍按水位边界

        # —— 流出结点的边（结点在上游端），检查相邻实单元 +1
        for r, _ in self._out_branches_by_node[node]:
            U = r.U[1]; C = r.C[1]
            # 若超临界且速度离开结点（从结点下泄进入该支路），结点水位不起作用 -> 外推
            if abs(U) >= 0.95 * C and r.Q[1] > 0:
                r.S[0] = r.S[1]
                r.Q[0] = r.Q[1]
            else:
                r.InBound_Fix_level_V2(level)

    def Apply_node_target_level_V4(self, node_name: str, level: float, Kj: float = 0.0, regime: str = "sub") -> None:
        """
        将“结点水位 = level”施加到所有与 node_name 相连的河段端点（鬼格），
        并引入局部能量损失 Kj（K·V^2 / 2g）的等效处理（方向已修正）：

        - 对“入支”（node 作为下游端，边方向 u -> node）：
            若 Q[-2] > 0（从上游单元流向结点），则此支为“来流”，等效水位 level_eff = level + dH；
            若 Q[-2] < 0（从结点指向该支），为“离开”，level_eff = level - dH；
            最后调用 OutBound_Fix_level_V2(level_eff) 作用在下游鬼格。

        - 对“出支”（node 作为上游端，边方向 node -> v）：
            若 Q[1] < 0（从下游单元指向结点），为“来流”，level_eff = level + dH；
            若 Q[1] > 0（离开结点向下游），为“离开”，level_eff = level - dH；
            最后调用 InBound_Fix_level_V2(level_eff) 作用在上游鬼格。

        参数
        ----
        node_name : 结点名称（与 self.G 的节点一致）
        level     : 该汊点处统一水位（绝对标高，单位 m）
        Kj        : 局部损失系数（无量纲），dH = Kj * V^2 / (2g)
        regime    : 'sub'（默认，亚临界）或 'super_in'（超临界入流，直接复制相邻实格到鬼格）

        说明
        ----
        这是“把 Kj 以改边界等效水位的近似方式注入”的实现；若要更贴近 SWMM，
        建议把 Kj 迁移到“动量方程的局部损失源项”中（不改边界 level），
        但本函数已修正号向避免“加能量”导致的水位/流量整体偏高与轻微震荡。
        """
        g = getattr(self, "g", 9.81)
        epsA = 1.0e-12

        # -----------------------------
        # 1) 处理“入支”（node 为下游端，边方向 u -> node）
        #    下游鬼格索引为 -1（相邻实格为 -2）
        # -----------------------------
        for r, river_name in self._in_branches_by_node[node_name]:
            # 相邻实格（倒数第二个单元）面积与流量
            A2 = float(r.S[-2])
            Q2 = float(r.Q[-2])
            # 界面平均速度近似（用实格的平均流速）
            V = abs(Q2) / max(A2, epsA)
            dH = Kj * (V * V) / (2.0 * g)

            # 来流(+dH) / 离开(-dH) 的统一写法：
            # Q2 > 0 代表从河段内部流向结点（来流） → +dH
            # Q2 < 0 代表从结点流向河段（离开）     → -dH
            level_eff = level + (dH if Q2 > 0.0 else -dH)

            if regime == "super_in":
                print('super_in')
                # 超临界入流：直接把相邻实格赋到鬼格，水位设为结点水位
                r.S[-1] = r.S[-2]
                r.Q[-1] = r.Q[-2]
                r.water_level[-1] = level
            else:
                # 亚临界：给下游端施加等效水位边界
                if self.use_fix_level_bc_v2:
                    r.OutBound_Fix_level_V2(level_eff)
                else:
                    r.OutBound_Fix_level_V3(
                        level_eff,
                        use_stabilizers=self.internal_bc_use_stabilizers,
                        respect_supercritical=self.internal_bc_respect_supercritical,
                        stage_on_face=self.internal_bc_stage_on_face,
                        audit_context={
                            'scenario': 'internal_node',
                            'node': node_name,
                            'river': river_name,
                            'call_scene': 'internal_node',
                        } if self.save_perf_report else None,
                    )

        # -----------------------------
        # 2) 处理“出支”（node 为上游端，边方向 node -> v）
        #    上游鬼格索引为 0（相邻实格为 1）
        # -----------------------------
        for r, river_name in self._out_branches_by_node[node_name]:
            # 相邻实格（第一个单元）面积与流量
            A1 = float(r.S[1])
            Q1 = float(r.Q[1])
            V = abs(Q1) / max(A1, epsA)
            dH = Kj * (V * V) / (2.0 * g)

            # 来流(+dH) / 离开(-dH)：
            # Q1 < 0 代表从下游向结点回流（来流） → +dH
            # Q1 > 0 代表从结点向下游离开        → -dH
            level_eff = level + (dH if Q1 < 0.0 else -dH)

            if regime == "super_in":
                print('super_in')
                r.S[0] = r.S[1]
                r.Q[0] = r.Q[1]
                r.water_level[0] = level
            else:
                # 亚临界：给上游端施加等效水位边界
                if self.use_fix_level_bc_v2:
                    r.InBound_Fix_level_V2(level_eff)
                else:
                    r.InBound_Fix_level_V3(
                        level_eff,
                        use_stabilizers=self.internal_bc_use_stabilizers,
                        respect_supercritical=self.internal_bc_respect_supercritical,
                        stage_on_face=self.internal_bc_stage_on_face,
                        audit_context={
                            'scenario': 'internal_node',
                            'node': node_name,
                            'river': river_name,
                            'call_scene': 'internal_node',
                        } if self.save_perf_report else None,
                    )



    # 获取应用汊点水位后，汊点的净流量大小
    def Get_node_clear_flow_at_ghost_cell_net(self, node):
        pure_Q = 0 # 净流量

        # 流入节点的边
        for river_temp, _ in self._in_branches_by_node[node]:
            face_q = getattr(river_temp, 'boundary_face_discharge_right', None)
            if self.internal_node_prefer_boundary_face_discharge and face_q is not None:
                q_in = float(face_q)
            elif self.internal_node_use_face_discharge:
                q_in = 0.5 * (float(river_temp.Q[-1]) + float(river_temp.Q[-2]))
            else:
                q_in = float(river_temp.Q[-1])
            pure_Q += q_in  # 获取流入节点的水流量

        # 流出节点的边
        for river_temp, _ in self._out_branches_by_node[node]:
            face_q = getattr(river_temp, 'boundary_face_discharge_left', None)
            if self.internal_node_prefer_boundary_face_discharge and face_q is not None:
                q_out = float(face_q)
            elif self.internal_node_use_face_discharge:
                q_out = 0.5 * (float(river_temp.Q[0]) + float(river_temp.Q[1]))
            else:
                q_out = float(river_temp.Q[0])
            pure_Q -= q_out  # 获取流出节点的水流量1

        return pure_Q

    def Get_node_clear_flow_at_boundary_face_net(self, node):
        pure_Q = 0.0

        # 流入节点的边：节点位于支路下游端，取右边界界面通量
        for river_temp, _ in self._in_branches_by_node[node]:
            pure_Q += float(river_temp.Flux_LOC[river_temp.cell_num, 0])

        # 流出节点的边：节点位于支路上游端，取左边界界面通量
        for river_temp, _ in self._out_branches_by_node[node]:
            pure_Q -= float(river_temp.Flux_LOC[0, 0])

        return pure_Q

    def _get_node_mass_residual_current_state(self, node: str) -> float:
        if self.internal_node_use_face_flux_residual:
            return float(self.Get_node_clear_flow_at_boundary_face_net(node))
        return float(self.Get_node_clear_flow_at_ghost_cell_net(node))

    def _parallel_node_average_level_at_real_cell(self, node, snapshots):
        level_list = []
        for _, name in self._in_branches_by_node[node]:
            end = snapshots[name][SNAP_RIGHT]
            if len(end) == SNAP_COMPACT_GHOST_WIDTH + 1:
                level_list.append(float(end[SNAP_COMPACT_CELL_LEVEL]))
            else:
                level_list.append(float(end[SNAP_CELL_LEVEL]))
        for _, name in self._out_branches_by_node[node]:
            end = snapshots[name][SNAP_LEFT]
            if len(end) == SNAP_COMPACT_GHOST_WIDTH + 1:
                level_list.append(float(end[SNAP_COMPACT_CELL_LEVEL]))
            else:
                level_list.append(float(end[SNAP_CELL_LEVEL]))
        if level_list:
            return float(np.average(level_list))
        return np.nan

    def _parallel_node_average_level_at_real_cell_from_aggregates(self, node, aggregates):
        rec = aggregates.get(node)
        if rec is None or rec[NODE_AGG_REAL_COUNT] <= 0:
            return np.nan
        return float(rec[NODE_AGG_REAL_SUM] / rec[NODE_AGG_REAL_COUNT])

    def _parallel_node_average_level_at_ghost_cell(self, node, snapshots):
        level_list = []
        for _, name in self._in_branches_by_node[node]:
            end = snapshots[name][SNAP_RIGHT]
            if len(end) == SNAP_COMPACT_GHOST_WIDTH + 1:
                level_list.append(float(end[SNAP_COMPACT_GHOST_LEVEL]))
            else:
                level_list.append(float(end[SNAP_GHOST_LEVEL]))
        for _, name in self._out_branches_by_node[node]:
            end = snapshots[name][SNAP_LEFT]
            if len(end) == SNAP_COMPACT_GHOST_WIDTH + 1:
                level_list.append(float(end[SNAP_COMPACT_GHOST_LEVEL]))
            else:
                level_list.append(float(end[SNAP_GHOST_LEVEL]))
        if level_list:
            return float(np.average(level_list))
        return np.nan

    def _parallel_node_average_level_at_ghost_cell_from_aggregates(self, node, aggregates):
        rec = aggregates.get(node)
        if rec is None or rec[NODE_AGG_GHOST_COUNT] <= 0:
            return np.nan
        return float(rec[NODE_AGG_GHOST_SUM] / rec[NODE_AGG_GHOST_COUNT])

    def _parallel_node_mass_residual(self, node, snapshots):
        pure_q = 0.0
        for _, name in self._in_branches_by_node[node]:
            end = snapshots[name][SNAP_RIGHT]
            if len(end) == SNAP_COMPACT_GHOST_WIDTH + 1:
                pure_q += float(end[SNAP_COMPACT_GHOST_Q])
                continue
            face_q = float(end[SNAP_BOUNDARY_FACE_DISCHARGE])
            if self.internal_node_prefer_boundary_face_discharge and np.isfinite(face_q):
                q_in = face_q
            elif self.internal_node_use_face_discharge:
                q_in = 0.5 * (float(end[SNAP_GHOST_Q]) + float(end[SNAP_CELL_Q]))
            else:
                q_in = float(end[SNAP_GHOST_Q])
            pure_q += q_in

        for _, name in self._out_branches_by_node[node]:
            end = snapshots[name][SNAP_LEFT]
            if len(end) == SNAP_COMPACT_GHOST_WIDTH + 1:
                pure_q -= float(end[SNAP_COMPACT_GHOST_Q])
                continue
            face_q = float(end[SNAP_BOUNDARY_FACE_DISCHARGE])
            if self.internal_node_prefer_boundary_face_discharge and np.isfinite(face_q):
                q_out = face_q
            elif self.internal_node_use_face_discharge:
                q_out = 0.5 * (float(end[SNAP_GHOST_Q]) + float(end[SNAP_CELL_Q]))
            else:
                q_out = float(end[SNAP_GHOST_Q])
            pure_q -= q_out
        return float(pure_q)

    def _parallel_node_mass_residual_from_aggregates(self, node, aggregates):
        rec = aggregates.get(node)
        if rec is None:
            return 0.0
        return float(rec[NODE_AGG_RESIDUAL])

    def _parallel_node_ac(self, node, snapshots):
        eps_a = 1e-12
        ac = 0.0
        compact_mode = bool(snapshots) and len(next(iter(snapshots.values()))[SNAP_LEFT]) == SNAP_COMPACT_GHOST_WIDTH + 1
        if compact_mode:
            for _, name in self._in_branches_by_node[node]:
                end = snapshots[name][SNAP_RIGHT]
                area = float(max(end[SNAP_COMPACT_GHOST_S], eps_a))
                width = float(max(end[SNAP_COMPACT_GHOST_WIDTH], eps_a))
                discharge = float(end[SNAP_COMPACT_GHOST_Q])
                ac += np.sqrt(self.g * area * width) - discharge * width / area

            for _, name in self._out_branches_by_node[node]:
                end = snapshots[name][SNAP_LEFT]
                area = float(max(end[SNAP_COMPACT_GHOST_S], eps_a))
                width = float(max(end[SNAP_COMPACT_GHOST_WIDTH], eps_a))
                discharge = float(end[SNAP_COMPACT_GHOST_Q])
                ac += np.sqrt(self.g * area * width) + discharge * width / area
            return float(self.alpha * ac)

        if self.internal_use_paper_ac:
            for _, name in self._in_branches_by_node[node]:
                end = snapshots[name][SNAP_RIGHT]
                use_face = (
                    self.internal_node_use_boundary_face_ac
                    and np.isfinite(end[SNAP_BOUNDARY_FACE_AREA])
                    and np.isfinite(end[SNAP_BOUNDARY_FACE_WIDTH])
                    and np.isfinite(end[SNAP_BOUNDARY_FACE_DISCHARGE])
                )
                if use_face:
                    area = float(max(end[SNAP_BOUNDARY_FACE_AREA], eps_a))
                    width = float(max(end[SNAP_BOUNDARY_FACE_WIDTH], eps_a))
                    discharge = float(end[SNAP_BOUNDARY_FACE_DISCHARGE])
                else:
                    area = float(max(end[SNAP_GHOST_S], eps_a))
                    width = float(max(end[SNAP_GHOST_WIDTH], eps_a))
                    discharge = float(end[SNAP_GHOST_Q])
                ac += np.sqrt(self.g * area * width) - discharge * width / area

            for _, name in self._out_branches_by_node[node]:
                end = snapshots[name][SNAP_LEFT]
                use_face = (
                    self.internal_node_use_boundary_face_ac
                    and np.isfinite(end[SNAP_BOUNDARY_FACE_AREA])
                    and np.isfinite(end[SNAP_BOUNDARY_FACE_WIDTH])
                    and np.isfinite(end[SNAP_BOUNDARY_FACE_DISCHARGE])
                )
                if use_face:
                    area = float(max(end[SNAP_BOUNDARY_FACE_AREA], eps_a))
                    width = float(max(end[SNAP_BOUNDARY_FACE_WIDTH], eps_a))
                    discharge = float(end[SNAP_BOUNDARY_FACE_DISCHARGE])
                else:
                    area = float(max(end[SNAP_GHOST_S], eps_a))
                    width = float(max(end[SNAP_GHOST_WIDTH], eps_a))
                    discharge = float(end[SNAP_GHOST_Q])
                ac += np.sqrt(self.g * area * width) + discharge * width / area
            return float(self.alpha * ac)

        if self.internal_use_ac_v2:
            for _, name in self._in_branches_by_node[node]:
                end = snapshots[name][SNAP_RIGHT]
                area = float(max(end[SNAP_CELL_S], eps_a))
                width = float(max(end[SNAP_CELL_WIDTH], eps_a))
                discharge = float(end[SNAP_CELL_Q])
                regime, u_loc, c_loc, _ = self._branch_regime(area, width, discharge, flow_dir_sign=+1)
                if regime != 'super_in':
                    ac += width * (c_loc - u_loc)

            for _, name in self._out_branches_by_node[node]:
                end = snapshots[name][SNAP_LEFT]
                area = float(max(end[SNAP_CELL_S], eps_a))
                width = float(max(end[SNAP_CELL_WIDTH], eps_a))
                discharge = float(end[SNAP_CELL_Q])
                regime, u_loc, c_loc, _ = self._branch_regime(area, width, discharge, flow_dir_sign=-1)
                if regime != 'super_in':
                    ac += width * (c_loc + u_loc)
            return float(self.alpha * ac)

        for _, name in self._in_branches_by_node[node]:
            end = snapshots[name][SNAP_RIGHT]
            area = float(max(end[SNAP_GHOST_S], eps_a))
            width = float(max(end[SNAP_GHOST_WIDTH], eps_a))
            discharge = float(end[SNAP_GHOST_Q])
            ac += np.sqrt(self.g * area * width) - discharge * width / area

        for _, name in self._out_branches_by_node[node]:
            end = snapshots[name][SNAP_LEFT]
            area = float(max(end[SNAP_GHOST_S], eps_a))
            width = float(max(end[SNAP_GHOST_WIDTH], eps_a))
            discharge = float(end[SNAP_GHOST_Q])
            ac += np.sqrt(self.g * area * width) + discharge * width / area

        return float(self.alpha * ac)

    def _parallel_node_ac_from_aggregates(self, node, aggregates):
        rec = aggregates.get(node)
        if rec is None:
            return 0.0
        return float(self.alpha * rec[NODE_AGG_AC])

    def _build_parallel_external_boundary_ops(self):
        ops = []
        for n in self.external_in_nodes:
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for river_obj, name in self._out_branches_by_node[n]:
                if btype == 'flow':
                    method = 'InBound_In_Q2' if self.external_flow_bc_use_characteristic and hasattr(river_obj, 'InBound_In_Q2') else 'InBound_In_Q'
                    ops.append({'river': name, 'method': method, 'args': (value,), 'kwargs': {}})
                elif btype == 'fix_level':
                    if self.use_fix_level_bc_v2:
                        ops.append({'river': name, 'method': 'InBound_Fix_level_V2', 'args': (), 'kwargs': {'level': value}})
                    else:
                        ops.append({
                            'river': name,
                            'method': 'InBound_Fix_level_V3',
                            'args': (value,),
                            'kwargs': {
                                'Fr_max': 0.85,
                                'head_gain_factor': 0.65,
                                'relax_Q': 0.4,
                                'cap_du_factor': 0.8,
                                'cap_dQ_factor': 0.7,
                                'use_stabilizers': self.external_bc_use_stabilizers,
                                'respect_supercritical': self.external_bc_respect_supercritical,
                                'stage_on_face': self.external_bc_stage_on_face,
                                'audit_context': {
                                    'scenario': 'external_in',
                                    'node': n,
                                    'river': name,
                                    'call_scene': 'external_in',
                                } if self.save_perf_report else None,
                            },
                        })

        for n in self.external_out_nodes:
            btype, value = self.get_boundary_value(n, self.current_sim_time)
            for _, name in self._in_branches_by_node[n]:
                if btype == 'free':
                    ops.append({'river': name, 'method': 'OutBound_Free_Outfall', 'args': (), 'kwargs': {}})
                elif btype == 'fix_level':
                    if self.use_fix_level_bc_v2:
                        ops.append({'river': name, 'method': 'OutBound_Fix_level_V2', 'args': (), 'kwargs': {'level': value}})
                    else:
                        ops.append({
                            'river': name,
                            'method': 'OutBound_Fix_level_V3',
                            'args': (value,),
                            'kwargs': {
                                'Fr_max': 0.85,
                                'head_gain_factor': 0.65,
                                'relax_Q': 0.4,
                                'cap_du_factor': 0.8,
                                'cap_dQ_factor': 0.7,
                                'use_stabilizers': self.external_bc_use_stabilizers,
                                'respect_supercritical': self.external_bc_respect_supercritical,
                                'stage_on_face': self.external_bc_stage_on_face,
                                'audit_context': {
                                    'scenario': 'external_out',
                                    'node': n,
                                    'river': name,
                                    'call_scene': 'external_out',
                                } if self.save_perf_report else None,
                            },
                        })
        return ops

    def _build_parallel_internal_level_ops(self, node_levels, snapshots):
        ops = []
        g = self.g
        eps_a = 1.0e-12
        for node_name in self.internal_nodes:
            level = float(node_levels[node_name])
            for _, name in self._in_branches_by_node[node_name]:
                level_eff = level
                if self.use_fix_level_bc_v2:
                    ops.append({'river': name, 'method': 'OutBound_Fix_level_V2', 'args': (level_eff,), 'kwargs': {}})
                else:
                    ops.append({
                        'river': name,
                        'method': 'OutBound_Fix_level_V3',
                        'args': (level_eff,),
                        'kwargs': {
                            'use_stabilizers': self.internal_bc_use_stabilizers,
                            'respect_supercritical': self.internal_bc_respect_supercritical,
                            'stage_on_face': self.internal_bc_stage_on_face,
                            'audit_context': {
                                'scenario': 'internal_node',
                                'node': node_name,
                                'river': name,
                                'call_scene': 'internal_node',
                            } if self.save_perf_report else None,
                        },
                    })
            for _, name in self._out_branches_by_node[node_name]:
                level_eff = level
                if self.use_fix_level_bc_v2:
                    ops.append({'river': name, 'method': 'InBound_Fix_level_V2', 'args': (level_eff,), 'kwargs': {}})
                else:
                    ops.append({
                        'river': name,
                        'method': 'InBound_Fix_level_V3',
                        'args': (level_eff,),
                        'kwargs': {
                            'use_stabilizers': self.internal_bc_use_stabilizers,
                            'respect_supercritical': self.internal_bc_respect_supercritical,
                            'stage_on_face': self.internal_bc_stage_on_face,
                            'audit_context': {
                                'scenario': 'internal_node',
                                'node': node_name,
                                'river': name,
                                'call_scene': 'internal_node',
                            } if self.save_perf_report else None,
                        },
                    })
        return ops

    def _parallel_can_use_compact_snapshots(self):
        return (
            bool(self.internal_use_paper_ac)
            and (not self.internal_node_use_face_discharge)
            and (not self.internal_node_prefer_boundary_face_discharge)
            and (not self.internal_node_use_boundary_face_ac)
        )

    def _parallel_can_use_node_aggregates(self):
        return self._parallel_can_use_compact_snapshots()

    def _parallel_internal_node_aggregate_specs(self):
        cache = getattr(self, '_parallel_internal_node_specs_cache', None)
        if cache is not None:
            return cache
        specs = []
        for node_name in self.internal_nodes:
            for _, river_name in self._in_branches_by_node[node_name]:
                specs.append((node_name, river_name, SNAP_RIGHT, 1.0))
            for _, river_name in self._out_branches_by_node[node_name]:
                specs.append((node_name, river_name, SNAP_LEFT, -1.0))
        self._parallel_internal_node_specs_cache = specs
        return specs

    def _internal_snapshot_names(self):
        cache = self._internal_snapshot_names_cache
        if cache is not None:
            return cache
        names = []
        seen = set()
        for node_name in self.internal_nodes:
            for _, river_name in self._in_branches_by_node[node_name]:
                if river_name not in seen:
                    seen.add(river_name)
                    names.append(river_name)
            for _, river_name in self._out_branches_by_node[node_name]:
                if river_name not in seen:
                    seen.add(river_name)
                    names.append(river_name)
        self._internal_snapshot_names_cache = tuple(names)
        return self._internal_snapshot_names_cache

    def _dense_internal_node_levels(self, node_levels):
        return np.asarray([float(node_levels[node]) for node in self.internal_nodes], dtype=float)

    def _build_internal_dense_plan_serial(self):
        cache = self._internal_dense_plan_cache
        if cache is not None:
            return cache
        node_names = list(self.internal_nodes)
        river_slots = {}
        river_refs = []
        river_names = []
        branch_river_slots = []
        branch_side_codes = []
        branch_flow_signs = []
        node_offsets = [0]
        snapshot_slots = []
        snapshot_seen = set()
        for node_name in node_names:
            for river_obj, river_name in self._in_branches_by_node[node_name]:
                slot = river_slots.get(river_name)
                if slot is None:
                    slot = len(river_refs)
                    river_slots[river_name] = slot
                    river_refs.append(river_obj)
                    river_names.append(river_name)
                branch_river_slots.append(slot)
                branch_side_codes.append(SNAP_RIGHT)
                branch_flow_signs.append(1.0)
                if slot not in snapshot_seen:
                    snapshot_seen.add(slot)
                    snapshot_slots.append(slot)
            for river_obj, river_name in self._out_branches_by_node[node_name]:
                slot = river_slots.get(river_name)
                if slot is None:
                    slot = len(river_refs)
                    river_slots[river_name] = slot
                    river_refs.append(river_obj)
                    river_names.append(river_name)
                branch_river_slots.append(slot)
                branch_side_codes.append(SNAP_LEFT)
                branch_flow_signs.append(-1.0)
                if slot not in snapshot_seen:
                    snapshot_seen.add(slot)
                    snapshot_slots.append(slot)
            node_offsets.append(len(branch_river_slots))
        cache = {
            'node_names': tuple(node_names),
            'node_offsets': np.asarray(node_offsets, dtype=np.int32),
            'branch_river_slots': np.asarray(branch_river_slots, dtype=np.int32),
            'branch_side_codes': np.asarray(branch_side_codes, dtype=np.int8),
            'branch_flow_signs': np.asarray(branch_flow_signs, dtype=float),
            'river_refs': tuple(river_refs),
            'river_names': tuple(river_names),
            'active_river_slots': tuple(range(len(river_refs))),
            'snapshot_slots': tuple(snapshot_slots),
        }
        self._internal_dense_plan_cache = cache
        return cache

    def _build_parallel_dense_plan(self, pool):
        cache = self._parallel_dense_plan_cache
        worker_groups = tuple(
            (int(group['id']), tuple(group['rivers']))
            for group in pool.worker_river_groups()
        )
        if cache is not None and cache.get('worker_groups') == worker_groups:
            return cache
        node_names = list(self.internal_nodes)
        worker_plans = {}
        for worker_id, worker_rivers in worker_groups:
            river_slots = {name: idx for idx, name in enumerate(worker_rivers)}
            branch_river_slots = []
            branch_side_codes = []
            branch_flow_signs = []
            node_offsets = [0]
            snapshot_slots = []
            snapshot_seen = set()
            active_slots = []
            active_seen = set()
            for node_name in node_names:
                for _, river_name in self._in_branches_by_node[node_name]:
                    if river_name not in river_slots:
                        continue
                    slot = river_slots[river_name]
                    branch_river_slots.append(slot)
                    branch_side_codes.append(SNAP_RIGHT)
                    branch_flow_signs.append(1.0)
                    if slot not in active_seen:
                        active_seen.add(slot)
                        active_slots.append(slot)
                    if slot not in snapshot_seen:
                        snapshot_seen.add(slot)
                        snapshot_slots.append(slot)
                for _, river_name in self._out_branches_by_node[node_name]:
                    if river_name not in river_slots:
                        continue
                    slot = river_slots[river_name]
                    branch_river_slots.append(slot)
                    branch_side_codes.append(SNAP_LEFT)
                    branch_flow_signs.append(-1.0)
                    if slot not in active_seen:
                        active_seen.add(slot)
                        active_slots.append(slot)
                    if slot not in snapshot_seen:
                        snapshot_seen.add(slot)
                        snapshot_slots.append(slot)
                node_offsets.append(len(branch_river_slots))
            worker_plans[worker_id] = {
                'node_names': tuple(node_names),
                'node_offsets': np.asarray(node_offsets, dtype=np.int32),
                'branch_river_slots': np.asarray(branch_river_slots, dtype=np.int32),
                'branch_side_codes': np.asarray(branch_side_codes, dtype=np.int8),
                'branch_flow_signs': np.asarray(branch_flow_signs, dtype=float),
                'active_river_slots': tuple(active_slots),
                'snapshot_slots': tuple(snapshot_slots),
            }
        cache = {
            'worker_groups': worker_groups,
            'worker_plans': worker_plans,
        }
        self._parallel_dense_plan_cache = cache
        return cache

    def _configure_pool_exact_node_plan(self, pool):
        if not hasattr(pool, 'configure_exact_node_plan'):
            return False
        dense_plan = self._build_parallel_dense_plan(pool)
        pool.configure_exact_node_plan(dense_plan['worker_plans'])
        return True

    def _prepare_internal_node_initial_guess_parallel(self, pool, node_levels):
        guess_levels = dict(node_levels)
        guess_stats = {}
        if not self._internal_response_solver_supported():
            return guess_levels, guess_stats
        jobs, boundary_kwargs = self._build_parallel_node_response_jobs(node_levels)
        if not jobs:
            return guess_levels, guess_stats
        t0 = time.perf_counter()
        tables = pool.node_response_tables(jobs, boundary_kwargs)
        total_elapsed = time.perf_counter() - t0
        per_node_time = total_elapsed / max(len(self.internal_nodes), 1)
        for node_name in self.internal_nodes:
            table = tables.get(node_name)
            if table is None:
                guess_stats[node_name] = {
                    'time': per_node_time,
                    'closure_calls': 0,
                    'fast_calls': 0,
                    'fast_hits': 0,
                    'table_attempted': True,
                    'table_success': False,
                    'fallback_reason': 'missing_table',
                }
                continue
            guess_stats[node_name] = {
                'time': per_node_time,
                'closure_calls': int(table['closure_calls']),
                'fast_calls': int(table['fast_calls']),
                'fast_hits': int(table['fast_hits']),
                'table_attempted': True,
                'table_success': False,
                'fallback_reason': None,
            }
            if not bool(table.get('valid', False)):
                guess_stats[node_name]['fallback_reason'] = next(iter(table.get('reasons', {'table_invalid': 1})), 'table_invalid')
                continue
            root = self._node_response_root_from_table(table)
            if not root.get('success', False):
                guess_stats[node_name]['fallback_reason'] = 'no_bracket'
                continue
            guess_levels[node_name] = max(0.0, float(root['eta']))
            guess_stats[node_name]['table_success'] = True
            guess_stats[node_name]['slope'] = float(root.get('slope', 0.0))
        return guess_levels, guess_stats

    def _fast_guess_is_usable(self, guess_stats):
        return bool(guess_stats) and all(
            bool(guess_stats.get(node_name, {}).get('table_success', False))
            for node_name in self.internal_nodes
        )

    def _solve_internal_nodes_fast_serial(self, node_levels):
        if not self._internal_response_solver_supported():
            self._solve_internal_nodes_exact_serial(node_levels, guess_stats={})
            return
        t0 = time.perf_counter() if self.save_perf_report else 0.0
        guess_levels, guess_stats = self._prepare_internal_node_initial_guess_serial(node_levels)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('initial_guess', time.perf_counter() - t0)
        if not self._fast_guess_is_usable(guess_stats):
            self._solve_internal_nodes_exact_serial(guess_levels, guess_stats=guess_stats)
            return

        self._perf_record_internal_backend('fast_serial')
        node_levels = dict(guess_levels)
        q_tol = self._internal_solver_q_tol()
        dz_tol = self._internal_solver_dz_tol()
        correction_limit = 0
        if str(self.fast_node_solver_mode).strip().lower() == 'response_corrector':
            correction_limit = max(0, int(self.fast_node_correction_iters))
        converged = False
        max_abs_q = np.inf
        iter_count = 0
        solve_start = time.perf_counter()
        for iter_time in range(1, correction_limit + 1):
            iter_count = iter_time
            self._apply_internal_node_levels(node_levels)
            node_residual = {}
            node_jacobian = {}
            max_abs_q = 0.0
            for n in self.internal_nodes:
                pure_q = float(self._get_node_mass_residual_current_state(n))
                node_residual[n] = pure_q
                max_abs_q = max(max_abs_q, abs(pure_q))
                if self.internal_use_paper_ac:
                    node_jacobian[n] = -float(self.Caculate_node_Ac_at_ghost_cell_JPWSPC(n))
                elif self.internal_use_ac_v2:
                    node_jacobian[n] = -float(self.Caculate_node_Ac_at_ghost_cell_V2(n))
                else:
                    node_jacobian[n] = -float(self.Caculate_node_Ac_at_ghost_cell(n))
            new_levels = dict(node_levels)
            max_abs_dz = 0.0
            for n in self.internal_nodes:
                dR_dZ = float(node_jacobian[n])
                pure_q = float(node_residual[n])
                dz = 0.0 if abs(dR_dZ) < 1.0e-10 else -pure_q / dR_dZ
                if not self.internal_use_paper_ac:
                    dz = float(np.clip(dz, -0.5, 0.5))
                dz = self.relax * dz
                new_levels[n] = max(0.0, float(node_levels[n]) + dz)
                max_abs_dz = max(max_abs_dz, abs(dz))
            node_levels = new_levels
            if max_abs_dz < dz_tol and max_abs_q < q_tol:
                converged = True
                break

        self._apply_internal_node_levels(node_levels)
        solve_time = time.perf_counter() - solve_start
        per_node_time = solve_time / max(len(self.internal_nodes), 1)
        self._internal_node_level_cache.update(node_levels)
        final_residuals = {}
        for n in self.internal_nodes:
            final_residuals[n] = float(self._get_node_mass_residual_current_state(n))
            self._update_internal_node_solver_cache(n, node_levels[n], residual=final_residuals[n])
        for n in self.internal_nodes:
            pre = guess_stats.get(n, {})
            branch_calls = len(self._internal_node_branch_specs(n)) * int(iter_count)
            self._perf_record_node_solve(
                n,
                solve_time=per_node_time + float(pre.get('time', 0.0)),
                iterations=int(iter_count),
                boundary_closure_calls=int(pre.get('closure_calls', 0) + branch_calls),
                table_attempted=bool(pre.get('table_attempted', False)),
                table_success=bool(pre.get('table_success', False)),
                fast_calls=int(pre.get('fast_calls', 0)),
                fast_hits=int(pre.get('fast_hits', 0)),
                exact_refine_iterations=int(iter_count),
                final_abs_residual=final_residuals[n],
                fallback_reason=pre.get('fallback_reason'),
            )
        if self.verbos and (not converged) and correction_limit > 0:
            print(f'FAST_MODE 内部边界校正达到上限 {correction_limit} 次，max|Qnet|={max_abs_q:.4e}')

    def _solve_internal_nodes_fast_parallel(
            self,
            pool,
            node_levels,
            use_node_aggregates,
            snapshot_mode,
            aggregates=None,
            snapshots=None,
    ):
        if not self._internal_response_solver_supported():
            return self._solve_internal_nodes_exact_parallel(
                pool,
                node_levels,
                use_node_aggregates=use_node_aggregates,
                snapshot_mode=snapshot_mode,
                aggregates=aggregates,
                snapshots=snapshots,
                guess_stats={},
            )

        t0 = time.perf_counter() if self.save_perf_report else 0.0
        guess_levels, guess_stats = self._prepare_internal_node_initial_guess_parallel(pool, node_levels)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('initial_guess', time.perf_counter() - t0)
        if not self._fast_guess_is_usable(guess_stats):
            return self._solve_internal_nodes_exact_parallel(
                pool,
                guess_levels,
                use_node_aggregates=use_node_aggregates,
                snapshot_mode=snapshot_mode,
                aggregates=aggregates,
                snapshots=snapshots,
                guess_stats=guess_stats,
            )

        self._perf_record_internal_backend('fast_parallel')
        node_levels = dict(guess_levels)
        q_tol = self._internal_solver_q_tol()
        dz_tol = self._internal_solver_dz_tol()
        correction_limit = 0
        if str(self.fast_node_solver_mode).strip().lower() == 'response_corrector':
            correction_limit = max(0, int(self.fast_node_correction_iters))
        converged = False
        max_abs_q = np.inf
        iter_count = 0
        solve_time_start = time.perf_counter()
        for iter_idx in range(1, correction_limit + 1):
            iter_count = iter_idx
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            iter_ops = self._build_parallel_internal_level_ops(node_levels, snapshots)
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('apply_prepare', time.perf_counter() - t0)

            if use_node_aggregates:
                agg_payload = pool.call_batch_and_node_aggregates(
                    iter_ops,
                    self._parallel_internal_node_aggregate_specs(),
                    g=self.g,
                    collect_perf=self.save_perf_report,
                )
                if self.save_perf_report:
                    aggregates = agg_payload['aggregates']
                    self._perf_record_internal_roundtrip(agg_payload.get('meta', {}))
                    for perf in agg_payload.get('perf', {}).values():
                        self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                else:
                    aggregates = agg_payload
            else:
                snap_payload = pool.call_batch_and_interface_snapshots(
                    iter_ops,
                    snapshot_mode=snapshot_mode,
                    collect_perf=self.save_perf_report,
                )
                if self.save_perf_report:
                    snapshots = snap_payload['snapshots']
                    self._perf_record_internal_roundtrip(snap_payload.get('meta', {}))
                    for perf in snap_payload.get('perf', {}).values():
                        self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                else:
                    snapshots = snap_payload

            t_resid = time.perf_counter() if self.save_perf_report else 0.0
            node_residual = {}
            max_abs_q = 0.0
            for n in self.internal_nodes:
                pure_q = (
                    self._parallel_node_mass_residual_from_aggregates(n, aggregates)
                    if use_node_aggregates else
                    self._parallel_node_mass_residual(n, snapshots)
                )
                node_residual[n] = float(pure_q)
                max_abs_q = max(max_abs_q, abs(float(pure_q)))
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('residual_assembly', time.perf_counter() - t_resid)

            t_jac = time.perf_counter() if self.save_perf_report else 0.0
            node_jacobian = {}
            for n in self.internal_nodes:
                node_jacobian[n] = -float(
                    self._parallel_node_ac_from_aggregates(n, aggregates)
                    if use_node_aggregates else
                    self._parallel_node_ac(n, snapshots)
                )
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('jacobian_assembly', time.perf_counter() - t_jac)

            t_relax = time.perf_counter() if self.save_perf_report else 0.0
            new_levels = dict(node_levels)
            max_abs_dz = 0.0
            for n in self.internal_nodes:
                dR_dZ = float(node_jacobian[n])
                pure_q = float(node_residual[n])
                dz = 0.0 if abs(dR_dZ) < 1.0e-10 else -pure_q / dR_dZ
                if not self.internal_use_paper_ac:
                    dz = float(np.clip(dz, -0.5, 0.5))
                dz = self.relax * dz
                new_levels[n] = max(0.0, float(node_levels[n]) + dz)
                max_abs_dz = max(max_abs_dz, abs(dz))
            node_levels = new_levels
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('relax_checks', time.perf_counter() - t_relax)
            if max_abs_dz < dz_tol and max_abs_q < q_tol:
                converged = True
                break

        t0 = time.perf_counter() if self.save_perf_report else 0.0
        final_ops = self._build_parallel_internal_level_ops(node_levels, snapshots)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('apply_prepare', time.perf_counter() - t0)
        final_payload = pool.call_batch_and_interface_snapshots(
            final_ops,
            snapshot_mode='full',
            collect_perf=self.save_perf_report,
        )
        if self.save_perf_report:
            snapshots = final_payload['snapshots']
            self._perf_record_internal_roundtrip(final_payload.get('meta', {}), final_snapshot=True)
            for perf in final_payload.get('perf', {}).values():
                self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
        else:
            snapshots = final_payload

        solve_time = time.perf_counter() - solve_time_start
        per_node_time = solve_time / max(len(self.internal_nodes), 1)
        self._internal_node_level_cache.update(node_levels)
        for n in self.internal_nodes:
            final_residual = float(self._parallel_node_mass_residual(n, snapshots))
            self._update_internal_node_solver_cache(n, node_levels[n], residual=final_residual)
            pre = guess_stats.get(n, {})
            branch_calls = len(self._internal_node_branch_specs(n)) * int(iter_count)
            self._perf_record_node_solve(
                n,
                solve_time=per_node_time + float(pre.get('time', 0.0)),
                iterations=int(iter_count),
                boundary_closure_calls=int(pre.get('closure_calls', 0) + branch_calls),
                table_attempted=bool(pre.get('table_attempted', False)),
                table_success=bool(pre.get('table_success', False)),
                fast_calls=int(pre.get('fast_calls', 0)),
                fast_hits=int(pre.get('fast_hits', 0)),
                exact_refine_iterations=int(iter_count),
                final_abs_residual=final_residual,
                fallback_reason=pre.get('fallback_reason'),
            )
        if self.verbos and (not converged) and correction_limit > 0:
            print(f'FAST_MODE 内部边界校正达到上限 {correction_limit} 次，max|Qnet|={max_abs_q:.4e}')
        return snapshots

    def _select_parallel_internal_backend(self, pool, use_node_aggregates):
        requested = str(getattr(self, 'internal_exact_backend', 'legacy_parallel')).strip().lower()
        if (
            requested == 'fused_parallel'
            and use_node_aggregates
            and (not self.use_fix_level_bc_v2)
            and hasattr(pool, 'call_exact_node_eval_batch')
        ):
            return 'fused_parallel'
        return 'legacy_parallel'

    def _select_serial_internal_backend(self):
        requested = str(getattr(self, 'internal_exact_backend', 'legacy_parallel')).strip().lower()
        if requested != 'fused_serial':
            return 'legacy_serial'
        if (
            self.internal_use_coupled_newton
            or self.internal_use_numeric_jacobian
            or self.internal_sync_branch_end_Q
            or self.internal_node_use_face_flux_residual
            or self.use_fix_level_bc_v2
        ):
            return 'legacy_serial'
        return 'fused_serial'

    def _solve_internal_nodes_exact_fused_parallel(self, pool, node_levels, guess_stats=None):
        guess_stats = {} if guess_stats is None else guess_stats
        self._perf_record_internal_backend('fused_parallel')
        converged = False
        max_abs_q = np.inf
        iter_count = 0
        solve_start = time.perf_counter()
        for iter_idx in range(1, self.max_iteration + 1):
            iter_count = iter_idx
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            dense_levels = self._dense_internal_node_levels(node_levels)
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('trial_level_prepare', time.perf_counter() - t0)

            payload = pool.call_exact_node_eval_batch(
                dense_levels,
                g=self.g,
                snapshot_mode=None,
                collect_perf=self.save_perf_report,
            )
            aggregates = payload['aggregates']
            if self.save_perf_report:
                self._perf_record_internal_roundtrip(payload.get('meta', {}))
                for perf in payload.get('perf', {}).values():
                    self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))

            t0 = time.perf_counter() if self.save_perf_report else 0.0
            residuals = np.asarray(aggregates[:, NODE_AGG_RESIDUAL], dtype=float)
            max_abs_q = float(np.max(np.abs(residuals))) if residuals.size > 0 else 0.0
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('residual_assembly', time.perf_counter() - t0)

            t_jac = time.perf_counter() if self.save_perf_report else 0.0
            dR_dZ = -self.alpha * np.asarray(aggregates[:, NODE_AGG_AC], dtype=float)
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('jacobian_assembly', time.perf_counter() - t_jac)

            t_relax = time.perf_counter() if self.save_perf_report else 0.0
            new_levels = dict(node_levels)
            max_abs_dz = 0.0
            for idx, node_name in enumerate(self.internal_nodes):
                pure_q = float(residuals[idx])
                deriv = float(dR_dZ[idx])
                if abs(deriv) < 1e-10:
                    dz = 0.0
                else:
                    dz = -pure_q / deriv
                if not self.internal_use_paper_ac:
                    dz = float(np.clip(dz, -0.5, 0.5))
                dz = self.relax * dz
                new_levels[node_name] = max(0.0, float(node_levels[node_name]) + dz)
                max_abs_dz = max(max_abs_dz, abs(dz))
            node_levels = new_levels
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('relax_checks', time.perf_counter() - t_relax)
            if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                converged = True
                break

        t0 = time.perf_counter() if self.save_perf_report else 0.0
        dense_levels = self._dense_internal_node_levels(node_levels)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('trial_level_prepare', time.perf_counter() - t0)
        final_payload = pool.call_exact_node_eval_batch(
            dense_levels,
            g=self.g,
            snapshot_mode='full',
            collect_perf=self.save_perf_report,
        )
        if self.save_perf_report:
            self._perf_record_internal_roundtrip(final_payload.get('meta', {}), final_snapshot=True)
            for perf in final_payload.get('perf', {}).values():
                self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
        snapshots = final_payload['snapshots']
        final_aggregates = final_payload['aggregates']
        final_residuals = np.asarray(final_aggregates[:, NODE_AGG_RESIDUAL], dtype=float)

        solve_time = time.perf_counter() - solve_start
        per_node_time = solve_time / max(len(self.internal_nodes), 1)
        self._internal_node_level_cache.update(node_levels)
        for idx, node_name in enumerate(self.internal_nodes):
            final_residual = float(final_residuals[idx]) if final_residuals.size > idx else 0.0
            self._update_internal_node_solver_cache(node_name, node_levels[node_name], residual=final_residual)
            pre = guess_stats.get(node_name, {})
            branch_calls = len(self._internal_node_branch_specs(node_name)) * (iter_count + 1)
            self._perf_record_node_solve(
                node_name,
                solve_time=per_node_time + float(pre.get('time', 0.0)),
                iterations=int(iter_count),
                boundary_closure_calls=int(branch_calls + pre.get('closure_calls', 0)),
                table_attempted=bool(pre.get('table_attempted', False)),
                table_success=bool(pre.get('table_success', False)),
                fast_calls=int(pre.get('fast_calls', 0)),
                fast_hits=int(pre.get('fast_hits', 0)),
                exact_refine_iterations=int(iter_count),
                final_abs_residual=final_residual,
                fallback_reason=pre.get('fallback_reason'),
            )
        if self.verbos and not converged:
            print(f'内部边界迭代达到上限 {self.max_iteration} 次，max|Qnet|={max_abs_q:.4e}')
        return snapshots

    def _solve_internal_nodes_exact_fused_serial(self, node_levels, guess_stats=None):
        guess_stats = {} if guess_stats is None else guess_stats
        self._perf_record_internal_backend('fused_serial')
        plan = self._build_internal_dense_plan_serial()
        converged = False
        max_abs_q = np.inf
        iter_count = 0
        solve_start = time.perf_counter()
        for iter_idx in range(1, self.max_iteration + 1):
            iter_count = iter_idx
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            dense_levels = self._dense_internal_node_levels(node_levels)
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('trial_level_prepare', time.perf_counter() - t0)

            payload = _exact_node_eval_from_plan(
                plan['river_refs'],
                plan['river_names'],
                plan,
                dense_levels,
                self.g,
                snapshot_mode=None,
                collect_perf=self.save_perf_report,
            )
            if self.save_perf_report:
                self._perf_record_internal_roundtrip(payload.get('meta', {}))
                for perf in payload.get('perf', {}).values():
                    self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))

            aggregates = payload['aggregates']
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            residuals = np.asarray(aggregates[:, NODE_AGG_RESIDUAL], dtype=float)
            max_abs_q = float(np.max(np.abs(residuals))) if residuals.size > 0 else 0.0
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('residual_assembly', time.perf_counter() - t0)

            t_jac = time.perf_counter() if self.save_perf_report else 0.0
            dR_dZ = -self.alpha * np.asarray(aggregates[:, NODE_AGG_AC], dtype=float)
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('jacobian_assembly', time.perf_counter() - t_jac)

            t_relax = time.perf_counter() if self.save_perf_report else 0.0
            new_levels = dict(node_levels)
            max_abs_dz = 0.0
            for idx, node_name in enumerate(self.internal_nodes):
                pure_q = float(residuals[idx])
                deriv = float(dR_dZ[idx])
                if abs(deriv) < 1e-10:
                    dz = 0.0
                else:
                    dz = -pure_q / deriv
                if not self.internal_use_paper_ac:
                    dz = float(np.clip(dz, -0.5, 0.5))
                dz = self.relax * dz
                new_levels[node_name] = max(0.0, float(node_levels[node_name]) + dz)
                max_abs_dz = max(max_abs_dz, abs(dz))
            node_levels = new_levels
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('relax_checks', time.perf_counter() - t_relax)
            if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                converged = True
                break

        t0 = time.perf_counter() if self.save_perf_report else 0.0
        dense_levels = self._dense_internal_node_levels(node_levels)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('trial_level_prepare', time.perf_counter() - t0)
        final_payload = _exact_node_eval_from_plan(
            plan['river_refs'],
            plan['river_names'],
            plan,
            dense_levels,
            self.g,
            snapshot_mode='full',
            collect_perf=self.save_perf_report,
        )
        if self.save_perf_report:
            self._perf_record_internal_roundtrip(final_payload.get('meta', {}), final_snapshot=True)
            for perf in final_payload.get('perf', {}).values():
                self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
        snapshots = final_payload['snapshots']
        final_aggregates = final_payload['aggregates']
        final_residuals = np.asarray(final_aggregates[:, NODE_AGG_RESIDUAL], dtype=float)

        solve_time = time.perf_counter() - solve_start
        per_node_time = solve_time / max(len(self.internal_nodes), 1)
        self._internal_node_level_cache.update(node_levels)
        for idx, node_name in enumerate(self.internal_nodes):
            final_residual = float(final_residuals[idx]) if final_residuals.size > idx else 0.0
            self._update_internal_node_solver_cache(node_name, node_levels[node_name], residual=final_residual)
            pre = guess_stats.get(node_name, {})
            branch_calls = len(self._internal_node_branch_specs(node_name)) * (iter_count + 1)
            self._perf_record_node_solve(
                node_name,
                solve_time=per_node_time + float(pre.get('time', 0.0)),
                iterations=int(iter_count),
                boundary_closure_calls=int(branch_calls + pre.get('closure_calls', 0)),
                table_attempted=bool(pre.get('table_attempted', False)),
                table_success=bool(pre.get('table_success', False)),
                fast_calls=int(pre.get('fast_calls', 0)),
                fast_hits=int(pre.get('fast_hits', 0)),
                exact_refine_iterations=int(iter_count),
                final_abs_residual=final_residual,
                fallback_reason=pre.get('fallback_reason'),
            )
        if self.verbos and not converged:
            print(f'内部边界迭代达到上限 {self.max_iteration} 次，max|Qnet|={max_abs_q:.4e}')
        return snapshots

    def _solve_internal_nodes_exact_parallel(self, pool, node_levels, use_node_aggregates, snapshot_mode, aggregates=None, snapshots=None, guess_stats=None):
        guess_stats = {} if guess_stats is None else guess_stats
        self._perf_record_internal_backend('legacy_parallel')
        converged = False
        max_abs_q = np.inf
        iter_count = 0
        solve_start = time.perf_counter()
        for iter_idx in range(1, self.max_iteration + 1):
            iter_count = iter_idx
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            iter_ops = self._build_parallel_internal_level_ops(node_levels, snapshots)
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('apply_prepare', time.perf_counter() - t0)
            if use_node_aggregates:
                agg_payload = pool.call_batch_and_node_aggregates(
                    iter_ops,
                    self._parallel_internal_node_aggregate_specs(),
                    g=self.g,
                    collect_perf=self.save_perf_report,
                )
                if self.save_perf_report:
                    aggregates = agg_payload['aggregates']
                    self._perf_record_internal_roundtrip(agg_payload.get('meta', {}))
                    for perf in agg_payload.get('perf', {}).values():
                        self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                else:
                    aggregates = agg_payload
            else:
                snap_payload = pool.call_batch_and_interface_snapshots(
                    iter_ops,
                    snapshot_mode=snapshot_mode,
                    collect_perf=self.save_perf_report,
                )
                if self.save_perf_report:
                    snapshots = snap_payload['snapshots']
                    self._perf_record_internal_roundtrip(snap_payload.get('meta', {}))
                    for perf in snap_payload.get('perf', {}).values():
                        self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                else:
                    snapshots = snap_payload

            t_resid = time.perf_counter() if self.save_perf_report else 0.0
            node_residual = {}
            max_abs_q = 0.0
            for n in self.internal_nodes:
                if use_node_aggregates:
                    pure_q = self._parallel_node_mass_residual_from_aggregates(n, aggregates)
                else:
                    pure_q = self._parallel_node_mass_residual(n, snapshots)
                node_residual[n] = pure_q
                max_abs_q = max(max_abs_q, abs(pure_q))
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('residual_assembly', time.perf_counter() - t_resid)

            t_jac = time.perf_counter() if self.save_perf_report else 0.0
            node_jacobian = {}
            for n in self.internal_nodes:
                if use_node_aggregates:
                    node_jacobian[n] = -float(self._parallel_node_ac_from_aggregates(n, aggregates))
                else:
                    node_jacobian[n] = -float(self._parallel_node_ac(n, snapshots))
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('jacobian_assembly', time.perf_counter() - t_jac)

            t_relax = time.perf_counter() if self.save_perf_report else 0.0
            new_levels = dict(node_levels)
            max_abs_dz = 0.0
            for n in self.internal_nodes:
                pure_q = node_residual[n]
                dR_dZ = node_jacobian[n]
                if abs(dR_dZ) < 1e-10:
                    dz = 0.0
                else:
                    dz = -pure_q / dR_dZ
                if not self.internal_use_paper_ac:
                    dz = float(np.clip(dz, -0.5, 0.5))
                dz = self.relax * dz
                new_levels[n] = max(0.0, node_levels[n] + dz)
                max_abs_dz = max(max_abs_dz, abs(dz))
            node_levels = new_levels
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('relax_checks', time.perf_counter() - t_relax)
            if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                converged = True
                break

        t0 = time.perf_counter() if self.save_perf_report else 0.0
        final_ops = self._build_parallel_internal_level_ops(node_levels, snapshots)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('apply_prepare', time.perf_counter() - t0)
        final_payload = pool.call_batch_and_interface_snapshots(
            final_ops,
            snapshot_mode='full',
            collect_perf=self.save_perf_report,
        )
        if self.save_perf_report:
            snapshots = final_payload['snapshots']
            self._perf_record_internal_roundtrip(final_payload.get('meta', {}), final_snapshot=True)
            for perf in final_payload.get('perf', {}).values():
                self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
        else:
            snapshots = final_payload
        solve_time = time.perf_counter() - solve_start
        per_node_time = solve_time / max(len(self.internal_nodes), 1)
        self._internal_node_level_cache.update(node_levels)
        for n in self.internal_nodes:
            final_residual = float(self._parallel_node_mass_residual(n, snapshots))
            self._update_internal_node_solver_cache(n, node_levels[n], residual=final_residual)
            pre = guess_stats.get(n, {})
            branch_calls = len(self._internal_node_branch_specs(n)) * (iter_count + 1)
            self._perf_record_node_solve(
                n,
                solve_time=per_node_time + float(pre.get('time', 0.0)),
                iterations=int(iter_count),
                boundary_closure_calls=int(branch_calls + pre.get('closure_calls', 0)),
                table_attempted=bool(pre.get('table_attempted', False)),
                table_success=bool(pre.get('table_success', False)),
                fast_calls=int(pre.get('fast_calls', 0)),
                fast_hits=int(pre.get('fast_hits', 0)),
                exact_refine_iterations=int(iter_count),
                final_abs_residual=final_residual,
                fallback_reason=pre.get('fallback_reason'),
            )
        if self.verbos and not converged:
            print(f'内部边界迭代达到上限 {self.max_iteration} 次，max|Qnet|={max_abs_q:.4e}')
        return snapshots

    def _solve_internal_nodes_exact_parallel_legacy_default(self, pool, node_levels, use_node_aggregates, snapshot_mode, aggregates=None, snapshots=None):
        converged = False
        max_abs_q = np.inf
        for _ in range(1, self.max_iteration + 1):
            iter_ops = self._build_parallel_internal_level_ops(node_levels, snapshots)
            if use_node_aggregates:
                aggregates = pool.call_batch_and_node_aggregates(
                    iter_ops,
                    self._parallel_internal_node_aggregate_specs(),
                    g=self.g,
                )
            else:
                snapshots = pool.call_batch_and_interface_snapshots(
                    iter_ops,
                    snapshot_mode=snapshot_mode,
                )

            node_residual = {}
            max_abs_q = 0.0
            for n in self.internal_nodes:
                if use_node_aggregates:
                    pure_q = self._parallel_node_mass_residual_from_aggregates(n, aggregates)
                else:
                    pure_q = self._parallel_node_mass_residual(n, snapshots)
                node_residual[n] = pure_q
                max_abs_q = max(max_abs_q, abs(pure_q))

            new_levels = dict(node_levels)
            max_abs_dz = 0.0
            for n in self.internal_nodes:
                pure_q = node_residual[n]
                if use_node_aggregates:
                    dR_dZ = -float(self._parallel_node_ac_from_aggregates(n, aggregates))
                else:
                    dR_dZ = -float(self._parallel_node_ac(n, snapshots))
                if abs(dR_dZ) < 1e-10:
                    dz = 0.0
                else:
                    dz = -pure_q / dR_dZ
                if not self.internal_use_paper_ac:
                    dz = float(np.clip(dz, -0.5, 0.5))
                dz = self.relax * dz
                new_levels[n] = max(0.0, node_levels[n] + dz)
                max_abs_dz = max(max_abs_dz, abs(dz))
            node_levels = new_levels
            if max_abs_dz < 1e-4 and max_abs_q < self.JPWSPC_Q_limit:
                converged = True
                break

        snapshots = pool.call_batch_and_interface_snapshots(
            self._build_parallel_internal_level_ops(node_levels, snapshots),
            snapshot_mode='full',
        )
        self._internal_node_level_cache.update(node_levels)
        if self.verbos and not converged:
            print(f'内部边界迭代达到上限 {self.max_iteration} 次，max|Qnet|={max_abs_q:.4e}')
        return snapshots

    def _update_boundary_conditions_parallel(self, pool):
        if self._fast_internal_solver_active():
            external_ops = self._build_parallel_external_boundary_ops()
            if not self.internal_nodes:
                payload = pool.call_batch_and_interface_snapshots(
                    external_ops,
                    snapshot_mode='full',
                    collect_perf=self.save_perf_report,
                )
                if self.save_perf_report:
                    self._perf_record_internal_roundtrip(payload.get('meta', {}))
                    for perf in payload.get('perf', {}).values():
                        self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                    return payload['snapshots']
                return payload

            use_node_aggregates = self._parallel_can_use_node_aggregates()
            compact_snapshots = self._parallel_can_use_compact_snapshots() and (not use_node_aggregates)
            snapshot_mode = 'compact' if compact_snapshots else 'full'
            if use_node_aggregates:
                agg_payload = pool.call_batch_and_node_aggregates(
                    external_ops,
                    self._parallel_internal_node_aggregate_specs(),
                    g=self.g,
                    collect_perf=self.save_perf_report,
                )
                if self.save_perf_report:
                    aggregates = agg_payload['aggregates']
                    self._perf_record_internal_roundtrip(agg_payload.get('meta', {}))
                    for perf in agg_payload.get('perf', {}).values():
                        self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                else:
                    aggregates = agg_payload
                snapshots = None
            else:
                snap_payload = pool.call_batch_and_interface_snapshots(
                    external_ops,
                    snapshot_mode=snapshot_mode,
                    collect_perf=self.save_perf_report,
                )
                if self.save_perf_report:
                    snapshots = snap_payload['snapshots']
                    self._perf_record_internal_roundtrip(snap_payload.get('meta', {}))
                    for perf in snap_payload.get('perf', {}).values():
                        self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                else:
                    snapshots = snap_payload
                aggregates = None

            node_levels = self._initial_internal_node_levels(
                use_node_aggregates=use_node_aggregates,
                aggregates=aggregates,
                snapshots=snapshots,
                extrapolate=True,
            )
            return self._solve_internal_nodes_fast_parallel(
                pool,
                node_levels,
                use_node_aggregates=use_node_aggregates,
                snapshot_mode=snapshot_mode,
                aggregates=aggregates,
                snapshots=snapshots,
            )

        if self._legacy_internal_exact_default_active():
            external_ops = self._build_parallel_external_boundary_ops()
            if not self.internal_nodes:
                return pool.call_batch_and_interface_snapshots(external_ops, snapshot_mode='full')

            use_node_aggregates = self._parallel_can_use_node_aggregates()
            compact_snapshots = self._parallel_can_use_compact_snapshots() and (not use_node_aggregates)
            snapshot_mode = 'compact' if compact_snapshots else 'full'
            if use_node_aggregates:
                aggregates = pool.call_batch_and_node_aggregates(
                    external_ops,
                    self._parallel_internal_node_aggregate_specs(),
                    g=self.g,
                )
                snapshots = None
            else:
                snapshots = pool.call_batch_and_interface_snapshots(
                    external_ops,
                    snapshot_mode=snapshot_mode,
                )
                aggregates = None

            node_levels = self._initial_internal_node_levels(
                use_node_aggregates=use_node_aggregates,
                aggregates=aggregates,
                snapshots=snapshots,
            )
            return self._solve_internal_nodes_exact_parallel_legacy_default(
                pool,
                node_levels,
                use_node_aggregates=use_node_aggregates,
                snapshot_mode=snapshot_mode,
                aggregates=aggregates,
                snapshots=snapshots,
            )

        external_ops = self._build_parallel_external_boundary_ops()
        if not self.internal_nodes:
            payload = pool.call_batch_and_interface_snapshots(
                external_ops,
                snapshot_mode='full',
                collect_perf=self.save_perf_report,
            )
            if self.save_perf_report:
                self._perf_record_internal_roundtrip(payload.get('meta', {}))
                for perf in payload.get('perf', {}).values():
                    self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
                return payload['snapshots']
            return payload

        use_node_aggregates = self._parallel_can_use_node_aggregates()
        compact_snapshots = self._parallel_can_use_compact_snapshots() and (not use_node_aggregates)
        snapshot_mode = 'compact' if compact_snapshots else 'full'
        if use_node_aggregates:
            agg_payload = pool.call_batch_and_node_aggregates(
                external_ops,
                self._parallel_internal_node_aggregate_specs(),
                g=self.g,
                collect_perf=self.save_perf_report,
            )
            if self.save_perf_report:
                aggregates = agg_payload['aggregates']
                for perf in agg_payload.get('perf', {}).values():
                    self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
            else:
                aggregates = agg_payload
            snapshots = None
        else:
            snap_payload = pool.call_batch_and_interface_snapshots(
                external_ops,
                snapshot_mode=snapshot_mode,
                collect_perf=self.save_perf_report,
            )
            if self.save_perf_report:
                snapshots = snap_payload['snapshots']
                for perf in snap_payload.get('perf', {}).values():
                    self._merge_stage_boundary_perf(perf.get('stage_boundary', {}))
            else:
                snapshots = snap_payload
            aggregates = None

        node_levels = self._initial_internal_node_levels(
            use_node_aggregates=use_node_aggregates,
            aggregates=aggregates,
            snapshots=snapshots,
        )
        t0 = time.perf_counter() if self.save_perf_report else 0.0
        guess_levels, guess_stats = self._prepare_internal_node_initial_guess_parallel(pool, node_levels)
        if self.save_perf_report:
            self._perf_add_internal_orchestration_time('initial_guess', time.perf_counter() - t0)
        backend = self._select_parallel_internal_backend(pool, use_node_aggregates)
        if backend == 'fused_parallel':
            return self._solve_internal_nodes_exact_fused_parallel(
                pool,
                guess_levels,
                guess_stats=guess_stats,
            )
        return self._solve_internal_nodes_exact_parallel(
            pool,
            guess_levels,
            use_node_aggregates=use_node_aggregates,
            snapshot_mode=snapshot_mode,
            aggregates=aggregates,
            snapshots=snapshots,
            guess_stats=guess_stats,
        )

    # 重采样并保存结果
    def Resample_and_Save_result_net(self):
        selected = self.output_river_names
        for _, _, data in self._river_edges:
            name = data.get('name')
            if selected is not None and name not in selected:
                continue
            data['river'].Check_Resample_and_Save_Output_result()

    # 获取演进信息
    def print_evolve_info(self):
        td = datetime.timedelta(seconds=float(self.current_sim_time))
        days = td.days
        hours, rem = divmod(td.seconds, 3600)  # 先拆小时
        minutes, seconds = divmod(rem, 60)  # 再拆分钟
        total_time_use = time.time() - self.caculation_start_time  # 总耗时
        print(f'当前模拟时间:{days}天{hours}小时{minutes}分钟{seconds}秒，模拟子步数量:{self.sub_step_count}，当前步计算耗时:{self.sub_step_caculation_time_using:.2f}秒，时间步长范围:[{self.sub_step_min_dt:.2f} - {self.sub_step_max_dt:.2f}]秒，总耗时:{total_time_use:.2f}秒')

    def _selected_output_names(self):
        if self.output_river_names is None:
            return self._all_river_names()
        return list(self.output_river_names)

    def _record_internal_node_history_from_snapshots(self, snapshots):
        if not self._internal_node_history_enabled():
            return
        rec = {'time': float(self.current_sim_time)}
        for n in self.internal_nodes:
            rec[f'{n}_level'] = float(self._internal_node_level_cache.get(n, np.nan))
            rec[f'{n}_Qnet'] = float(self._parallel_node_mass_residual(n, snapshots))
            for _, name in self._in_branches_by_node[n]:
                end = snapshots[name][SNAP_RIGHT]
                rec[f'{n}_{name}_face_level'] = float(end[SNAP_BOUNDARY_FACE_LEVEL])
                rec[f'{n}_{name}_face_Q'] = float(end[SNAP_BOUNDARY_FACE_DISCHARGE])
                rec[f'{n}_{name}_cell_level'] = float(end[SNAP_CELL_LEVEL])
                rec[f'{n}_{name}_cell_Q'] = float(end[SNAP_CELL_Q])
            for _, name in self._out_branches_by_node[n]:
                end = snapshots[name][SNAP_LEFT]
                rec[f'{n}_{name}_face_level'] = float(end[SNAP_BOUNDARY_FACE_LEVEL])
                rec[f'{n}_{name}_face_Q'] = float(end[SNAP_BOUNDARY_FACE_DISCHARGE])
                rec[f'{n}_{name}_cell_level'] = float(end[SNAP_CELL_LEVEL])
                rec[f'{n}_{name}_cell_Q'] = float(end[SNAP_CELL_Q])
        self.internal_node_history.append(rec)

    def _evolve_base_parallel_threads(self, yield_step, pool):
        yield_flag = False
        finish_flag = False
        selected_names = self._selected_output_names()
        self.sub_step_start_time = time.time()
        self.caculation_start_time = time.time()

        while self.current_sim_time < self.total_sim_time:
            self.Set_global_time_step(self.DT)

            self.current_sim_time += self.DT
            self.step_count += 1
            self.sub_step_time += self.DT
            self.sub_step_count += 1
            self.sub_step_max_dt = max(self.sub_step_max_dt, self.DT)
            self.sub_step_min_dt = min(self.sub_step_min_dt, self.DT)

            # Keep boundary coupling on the original serial path so the
            # junction iteration and all current boundary options stay
            # bitwise-aligned with the accepted serial workflow.
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Update_boundary_conditions()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'boundary_updater', time.perf_counter() - t0)

            if self._internal_node_history_enabled():
                rec = {'time': float(self.current_sim_time)}
                for n in self.internal_nodes:
                    rec[f'{n}_level'] = float(self._internal_node_level_cache.get(n, np.nan))
                    rec[f'{n}_Qnet'] = float(self._get_node_mass_residual_current_state(n))
                    for r, name in self._in_branches_by_node[n]:
                        rec[f'{n}_{name}_face_level'] = float(
                            getattr(r, 'boundary_face_level_right', np.nan)
                        )
                        rec[f'{n}_{name}_face_Q'] = float(
                            getattr(r, 'boundary_face_discharge_right', np.nan)
                        )
                        rec[f'{n}_{name}_cell_level'] = float(r.water_level[-2])
                        rec[f'{n}_{name}_cell_Q'] = float(r.Q[-2])
                    for r, name in self._out_branches_by_node[n]:
                        rec[f'{n}_{name}_face_level'] = float(
                            getattr(r, 'boundary_face_level_left', np.nan)
                        )
                        rec[f'{n}_{name}_face_Q'] = float(
                            getattr(r, 'boundary_face_discharge_left', np.nan)
                        )
                        rec[f'{n}_{name}_cell_level'] = float(r.water_level[1])
                        rec[f'{n}_{name}_cell_Q'] = float(r.Q[1])
                self.internal_node_history.append(rec)

            t0 = time.perf_counter() if self.save_perf_report else 0.0
            dt_payload = pool.advance_local_step(
                use_implicit_branch_update=self.use_implicit_branch_update,
                save_names=selected_names if self.save_outputs else None,
                collect_perf=self.save_perf_report,
            )
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'advance_local_step_wall', time.perf_counter() - t0)
            dt_map = self._unpack_advance_local_step_results(dt_payload, collect_perf=self.save_perf_report)
            self._record_cfl_history(list(dt_map.items()))
            self.cfl_allowed_dt = min(dt_map.values())

            if yield_flag:
                self.sub_step_caculation_time_using = time.time() - self.sub_step_start_time
                yield self.current_sim_time
                yield_flag = False
                self.sub_step_start_time = time.time()
                self.sub_step_time = 0.0
                self.sub_step_count = 0
                self.sub_step_max_dt = 0.0
                self.sub_step_min_dt = 999999

            if finish_flag:
                break

            if self.current_sim_time + self.cfl_allowed_dt > self.total_sim_time + 1e-5:
                self.DT = self.total_sim_time - self.current_sim_time
            elif self.sub_step_time + self.cfl_allowed_dt > yield_step + 1e-5:
                self.DT = yield_step - self.sub_step_time
                yield_flag = True
            else:
                self.DT = self.cfl_allowed_dt

        self.caculation_time = time.time() - self.caculation_start_time
        print(f'计算结束，保存结果...\n共计算 {self.step_count} 步，总耗时: {self.caculation_time:.2f} 秒')
        if self.save_outputs:
            self.Resample_and_Save_result_net()
            self.Save_internal_node_history()
            self.Save_cfl_history()
        self.Save_run_summary()
        self.Save_perf_report()

    def _evolve_base_parallel_process(self, yield_step, pool):
        yield_flag = False
        finish_flag = False
        selected_names = self._selected_output_names()
        self.sub_step_start_time = time.time()
        self.caculation_start_time = time.time()

        while self.current_sim_time < self.total_sim_time:
            pool.call_all('set_next_dt', args=(self.DT,))

            self.current_sim_time += self.DT
            self.step_count += 1
            self.sub_step_time += self.DT
            self.sub_step_count += 1
            self.sub_step_max_dt = max(self.sub_step_max_dt, self.DT)
            self.sub_step_min_dt = min(self.sub_step_min_dt, self.DT)

            t0 = time.perf_counter() if self.save_perf_report else 0.0
            snapshots = self._update_boundary_conditions_parallel(pool)
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'boundary_updater', time.perf_counter() - t0)
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self._record_internal_node_history_from_snapshots(snapshots)
            if self.save_perf_report:
                self._perf_add_internal_orchestration_time('diagnostics_history', time.perf_counter() - t0)

            t0 = time.perf_counter() if self.save_perf_report else 0.0
            dt_payload = pool.advance_local_step(
                use_implicit_branch_update=self.use_implicit_branch_update,
                save_names=selected_names if self.save_outputs else None,
                collect_perf=self.save_perf_report,
            )
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'advance_local_step_wall', time.perf_counter() - t0)
            dt_map = self._unpack_advance_local_step_results(dt_payload, collect_perf=self.save_perf_report)
            self._record_cfl_history(list(dt_map.items()))
            self.cfl_allowed_dt = min(dt_map.values())

            if yield_flag:
                if self.parallel_sync_main_state_on_yield:
                    self._sync_parallel_rivers_to_main(pool)
                self.sub_step_caculation_time_using = time.time() - self.sub_step_start_time
                yield self.current_sim_time
                yield_flag = False
                self.sub_step_start_time = time.time()
                self.sub_step_time = 0.0
                self.sub_step_count = 0
                self.sub_step_max_dt = 0.0
                self.sub_step_min_dt = 999999

            if finish_flag:
                break

            if self.current_sim_time + self.cfl_allowed_dt > self.total_sim_time + 1e-5:
                self.DT = self.total_sim_time - self.current_sim_time
            elif self.sub_step_time + self.cfl_allowed_dt > yield_step + 1e-5:
                self.DT = yield_step - self.sub_step_time
                yield_flag = True
            else:
                self.DT = self.cfl_allowed_dt

        self.caculation_time = time.time() - self.caculation_start_time
        print(f'计算结束，保存结果...\n共计算 {self.step_count} 步，总耗时: {self.caculation_time:.2f} 秒')
        if self.save_outputs:
            pool.call_all('Check_Resample_and_Save_Output_result', names=selected_names)
            self.Save_internal_node_history()
            self.Save_cfl_history()
        self._sync_parallel_rivers_to_main(pool)
        self.Save_run_summary()
        self.Save_perf_report()

    # 演进子步
    def _evolve_base(self, yield_step):
        yield_flag = False  # 是否需要回报子步
        finish_flag = False # 判断是否结束
        self.sub_step_start_time = time.time()  # 子步开始时间
        self.caculation_start_time = time.time()  # 计算开始时间
        while self.current_sim_time < self.total_sim_time:
            # 同步时间
            self.Set_global_time_step(self.DT)

            # 累加总时间
            self.current_sim_time += self.DT
            self.step_count += 1

            # 累加子步时间
            self.sub_step_time += self.DT
            self.sub_step_count += 1

            self.sub_step_max_dt = max(self.sub_step_max_dt, self.DT)  # 更新子步最大时间步长
            self.sub_step_min_dt = min(self.sub_step_min_dt, self.DT)  # 更新子步最小时间步长

            # 更新边界条件
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Update_boundary_conditions()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'boundary_updater', time.perf_counter() - t0)

            # 记录本时间步边界更新后的结点水位与净流量（用于与节点观测口径比对）
            if self._internal_node_history_enabled():
                rec = {'time': float(self.current_sim_time)}
                for n in self.internal_nodes:
                    rec[f'{n}_level'] = float(self._internal_node_level_cache.get(n, np.nan))
                    rec[f'{n}_Qnet'] = float(self._get_node_mass_residual_current_state(n))
                    for r, name in self._in_branches_by_node[n]:
                        rec[f'{n}_{name}_face_level'] = float(
                            getattr(r, 'boundary_face_level_right', np.nan)
                        )
                        rec[f'{n}_{name}_face_Q'] = float(
                            getattr(r, 'boundary_face_discharge_right', np.nan)
                        )
                        rec[f'{n}_{name}_cell_level'] = float(r.water_level[-2])
                        rec[f'{n}_{name}_cell_Q'] = float(r.Q[-2])
                    for r, name in self._out_branches_by_node[n]:
                        rec[f'{n}_{name}_face_level'] = float(
                            getattr(r, 'boundary_face_level_left', np.nan)
                        )
                        rec[f'{n}_{name}_face_Q'] = float(
                            getattr(r, 'boundary_face_discharge_left', np.nan)
                        )
                        rec[f'{n}_{name}_cell_level'] = float(r.water_level[1])
                        rec[f'{n}_{name}_cell_Q'] = float(r.Q[1])
                self.internal_node_history.append(rec)

            # 计算界面U、C
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Caculate_face_U_C_net()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'face_uc_net', time.perf_counter() - t0)

            # 计算Roe matrix
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Caculate_Roe_matrix_net()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'roe_matrix_net', time.perf_counter() - t0)

            # 计算Source_term2
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Caculate_Source_term_net()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'source_net', time.perf_counter() - t0)

            # 计算Roe_flux2
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Caculate_Roe_flux_net()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'roe_flux_net', time.perf_counter() - t0)

            # 组装通量（显式/隐式分支）
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            if self.use_implicit_branch_update:
                self.Caculate_impli_trans_coefficient_net()
                self.Assemble_flux_impli_net()
            else:
                self.Assemble_flux_net()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'assemble_net', time.perf_counter() - t0)

            # 更新河道网格参数 cell proptirty2
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Update_cell_property_net()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'update_net', time.perf_counter() - t0)

            # 保存结果
            if self.save_outputs:
                self.Save_step_result_net()

            # 汇报子步演进
            if yield_flag:
                self.sub_step_caculation_time_using = time.time() - self.sub_step_start_time  # 计算子步耗时
                yield self.current_sim_time

                yield_flag = False  # 重置标志
                self.sub_step_start_time = time.time()  # 重置子步开始时间
                self.sub_step_time = 0.0  # 重置子步时间
                self.sub_step_count = 0  # 重置子步计数
                self.sub_step_max_dt = 0.0  # 重置子步最大时间步长
                self.sub_step_min_dt = 999999  # 重置子步最小时间

            # 计算完最后一个时间步退出
            if finish_flag:
                break

            # 计算CFL条件，更新时间步长
            t0 = time.perf_counter() if self.save_perf_report else 0.0
            self.Caculate_global_CFL()
            if self.save_perf_report:
                self._perf_add_time(self._perf_sections, 'cfl_update', time.perf_counter() - t0)

            # 统计全局最小时间步长，处理时间逻辑
            # 保证最后一个时刻为总时间的最后一个时间
            if self.current_sim_time + self.cfl_allowed_dt > self.total_sim_time + 1e-5:
                self.DT = self.total_sim_time - self.current_sim_time # 基于总时间计算时间步长
                # finish_flag = True

            elif self.sub_step_time + self.cfl_allowed_dt > yield_step + 1e-5:
                self.DT = yield_step - self.sub_step_time # 基于子步时间计算时间步长
                yield_flag = True  # 标记需要回报子步

            else:
                self.DT = self.cfl_allowed_dt # 基于全局最小CFL时间步长计算时间步长

        # 计算结束，保存结果
        self.caculation_time = time.time() - self.caculation_start_time  # 计算总耗时
        print(f'计算结束，保存结果...\n共计算 {self.step_count} 步，总耗时: {self.caculation_time:.2f} 秒')
        if self.save_outputs:
            self.Resample_and_Save_result_net()
            self.Save_internal_node_history()
            self.Save_cfl_history()
        self.Save_run_summary()
        self.Save_perf_report()

    # 演进过程
    def Evolve(self, yield_step=None):
        self._reset_perf_stats()
        # 框定回报时间
        if yield_step is None:
            yield_step = self.model_data['time_step']

        # 优化网格参数
        if self.Fine_flag:
            self.Fine_cell_property_net()

        # 初始化水面参数
        self.Init_water_surface_net()

        # 同步各分支的隐式边界标志
        for _, _, data in self._river_edges:
            data['river'].Implic_flag = bool(self.use_implicit_branch_update)
            data['river'].perf_timing_enabled = bool(self.save_perf_report)
            data['river'].use_fix_level_bc_v2 = bool(self.use_fix_level_bc_v2)
            data['river'].internal_bc_use_stabilizers = bool(self.internal_bc_use_stabilizers)
            data['river'].internal_bc_respect_supercritical = bool(self.internal_bc_respect_supercritical)
            data['river'].internal_bc_stage_on_face = bool(self.internal_bc_stage_on_face)
            data['river'].internal_node_use_face_discharge = bool(self.internal_node_use_face_discharge)
            data['river'].internal_node_prefer_boundary_face_discharge = bool(self.internal_node_prefer_boundary_face_discharge)
            data['river'].internal_node_use_boundary_face_ac = bool(self.internal_node_use_boundary_face_ac)
            data['river'].internal_use_paper_ac = bool(self.internal_use_paper_ac)
            data['river'].internal_use_ac_v2 = bool(self.internal_use_ac_v2)

        # 初始化其余参数
        self.Init_cell_property_net()

        # 保存初始结果
        self.Save_basic_data_net()
        self._configure_output_save_schedule(yield_step)

        # 计算第一步时间步长
        self.Caculate_global_CFL()
        self.DT = self.cfl_allowed_dt  # 初始时间步长为全局最小CFL时间步长

        use_parallel = bool(self.use_parallel_workers and self.parallel_n_workers > 1 and len(self._river_edges) > 1)

        if use_parallel:
            river_items = [(data.get('name'), data['river']) for _, _, data in self._river_edges]
            backend = str(getattr(self, 'parallel_backend', 'threads')).strip().lower()
            if backend == 'process':
                if not self._parallel_supported():
                    if self.verbos:
                        print('当前节点配置包含进程并行路径未覆盖的选项，回退到串行 Evolve')
                    for t in self._evolve_base(yield_step):
                        yield t
                    return
                start_method = self._resolve_process_start_method()
                pool = PersistentRiverProcessPool(
                    river_items=river_items,
                    n_workers=self.parallel_n_workers,
                    start_method=start_method,
                )
                if self._select_parallel_internal_backend(pool, self._parallel_can_use_node_aggregates()) == 'fused_parallel':
                    self._configure_pool_exact_node_plan(pool)
                evolve_fn = self._evolve_base_parallel_process
            else:
                pool = PersistentRiverThreadPool(
                    river_items=river_items,
                    n_workers=self.parallel_n_workers,
                    start_method=self.parallel_start_method,
                )
                if self._select_parallel_internal_backend(pool, self._parallel_can_use_node_aggregates()) == 'fused_parallel':
                    self._configure_pool_exact_node_plan(pool)
                evolve_fn = self._evolve_base_parallel_threads
            try:
                for t in evolve_fn(yield_step, pool):
                    yield t
            finally:
                pool.shutdown()
        else:
            # 调用evolve_base, 统计子步演进数量、DT范围
            for t in self._evolve_base(yield_step):
                yield t


    # 导出为 PNG 图片
    def export_png(self, path='rivernet.png', figsize=(9, 6), layout='spring', show_node_labels=True, show_edge_labels=True, dpi=400):
        """
        将当前有向图渲染为 PNG 图片并保存到 path。
        - 默认输出到当前目录的 rivernet.png
        - 在无界面环境中强制使用 'Agg' 后端
        """
        import os, math
        import networkx as nx
        import matplotlib
        matplotlib.use('Agg', force=True)  # 关键：无界面后端
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch

        if not self.G.is_directed():
            raise ValueError('当前图不是有向图，请先用 DiGraph 存储或转换为有向图。')

        # 确保节点分类可用
        need_attrs = ('internal_nodes', 'external_in_nodes', 'external_out_nodes')
        if not all(hasattr(self, a) for a in need_attrs):
            self.classfy_nodes()

        # 选择布局
        n = max(len(self.G), 1)
        if layout == 'spring':
            k = 1 / math.sqrt(n)
            pos = nx.spring_layout(self.G, seed=42, k=k)
        elif layout == 'kamada_kawai':
            pos = nx.kamada_kawai_layout(self.G)
        elif layout == 'circular':
            pos = nx.circular_layout(self.G)
        elif layout == 'random':
            pos = nx.random_layout(self.G, seed=42)
        else:
            raise ValueError(f'未知布局: {layout}')

        # 颜色与尺寸
        color_internal = '#4C78A8'  # 蓝
        color_external_in = '#F58518'  # 橙（只有入）
        color_external_out = '#54A24B'  # 绿（只有出）
        node_size_internal, node_size_external = 700, 600

        # 绘图
        fig, ax = plt.subplots(figsize=figsize)

        nx.draw_networkx_nodes(self.G, pos,
                               nodelist=self.internal_nodes,
                               node_color=color_internal, node_size=node_size_internal, ax=ax, label='internal')
        nx.draw_networkx_nodes(self.G, pos,
                               nodelist=getattr(self, 'external_in_nodes', []),
                               node_color=color_external_in, node_size=node_size_external, ax=ax, label='external_in')
        nx.draw_networkx_nodes(self.G, pos,
                               nodelist=getattr(self, 'external_out_nodes', []),
                               node_color=color_external_out, node_size=node_size_external, ax=ax, label='external_out')

        nx.draw_networkx_edges(
            self.G, pos, ax=ax,
            arrows=True, arrowstyle='-|>', arrowsize=18,
            width=1.6, connectionstyle='arc3,rad=0.05'
        )

        if show_node_labels:
            nx.draw_networkx_labels(self.G, pos, font_size=10, ax=ax)

        if show_edge_labels:
            edge_labels = {(u, v): data.get('name') for u, v, data in self.G.edges(data=True) if data.get('name')}
            if edge_labels:
                nx.draw_networkx_edge_labels(self.G, pos, edge_labels=edge_labels,
                                             font_size=9, label_pos=0.5, ax=ax)

        # 图例
        handles = [
            Patch(facecolor=color_internal, edgecolor='none', label='internal'),
            Patch(facecolor=color_external_in, edgecolor='none', label='external_in'),
            Patch(facecolor=color_external_out, edgecolor='none', label='external_out'),
        ]
        ax.legend(handles=handles, loc='best', frameon=False)

        ax.set_axis_off()
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        plt.tight_layout()
        plt.savefig(path, dpi=dpi, bbox_inches='tight')
        plt.close(fig)

        if self.verbos:
            print(f'[OK] PNG 导出完成 -> {path}')


if __name__ == '__main__':
    output_path = 'result'  # 输出路径

    river_data = {
        "cell_num": 120,  # 计算单元数量
        "pos": [[1, 1, 0], [400, 1, 0], [800, 1, 0], [1200, 1, 0]],  # 河道点坐标 长度、宽度、高度
        "section_name": ['se1', 'se2', 'se3']  # 断面名称
    }
    section_data = {
        'se1': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
        'se2': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
        'se3': [[0, 12], [0.5, 0], [1, 0], [1.5, 12]],
    }

    model_data = {
        'model_name':'river_net',
        'sim_start_time': '2024-01-01 00:00:00',
        'sim_end_time': '2024-01-01 01:30:00',
        'time_step': 5,  # 单位：秒
        'output_path': output_path,
        'CFL': 0.3,
    }

    section_pos = {
        'se1': [1, 1],
        'se2': [400, 1],
        'se3': [1200, 1]
    }

    section_pos = None

    top = {
        ('n1', 'n5'): {'name': 'river1', 'river_data': river_data,
                       'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
                       'manning': 0.1},

        ('n2', 'n5'): {'name': 'river2', 'river_data': river_data,
                       'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
                       'manning': 0.1},

        ('n3', 'n6'): {'name': 'river3', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n4', 'n6'): {'name': 'river4', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n5', 'n6'): {'name': 'river5', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n7', 'n8'): {'name': 'river8', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n5', 'n7'): {'name': 'river6', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n6', 'n8'): {'name': 'river7', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n7', 'n9'): {'name': 'river9', 'river_data': river_data, 'section_data': section_data,
                       'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},

        ('n9', 'n10'): {'name': 'river10', 'river_data': river_data, 'section_data': section_data,
                        'model_data': model_data, 'section_pos': section_pos, 'manning': 0.1},
    }

    # top = {
    #     ('n1', 'n3'): {'name': 'river1', 'river_data': river_data,
    #                    'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
    #                    'manning': 0.1},
    #     ('n2', 'n3'): {'name': 'river2', 'river_data': river_data,
    #                    'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
    #                    'manning': 0.1},
    #     ('n3', 'n4'): {'name': 'river3', 'river_data': river_data,
    #                    'section_data': section_data, 'model_data': model_data, 'section_pos': section_pos,
    #                    'manning': 0.1},
    #
    # }

    net = Rivernet(top, model_data)

    net.export_png(path='result/rivernet.png')

    net.max_iteration = 50

    net.verbos = False

    # net.Fine_flag = True

    net.set_boundary('n1', 'flow', 1)  # 流量边界
    net.set_boundary('n2', 'flow', 2)
    net.set_boundary('n3', 'flow', 2)

    net.set_boundary('n4', 'flow', 2)  # 固定水位边界

    net.set_boundary('n10', 'free')


    for u, v, data in net.G.edges(data=True):
        river = data['river']
        river.Set_init_water_level(2)

    for t in net.Evolve(yield_step=300):
        net.print_evolve_info()

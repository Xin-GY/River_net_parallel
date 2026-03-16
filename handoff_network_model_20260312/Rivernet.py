import random
import time
import os
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
)
try:
    from cython_node_iteration import run_internal_node_iteration_exact as cython_run_internal_node_iteration_exact
except Exception:
    cython_run_internal_node_iteration_exact = None
try:
    from cython_cpp_bridge import (
        run_cpp_network_evolve_serial as cpp_run_network_evolve_serial,
        run_cpp_network_evolve_threads as cpp_run_network_evolve_threads,
    )
except Exception:
    cpp_run_network_evolve_serial = None
    cpp_run_network_evolve_threads = None

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
        self.save_cfl_history = False
        self.cfl_history = []
        self.output_save_interval = None
        self.use_cython_nodechain = False
        self._cython_nodechain_plan = None
        self.use_cpp_evolve = False
        self.cpp_threads = False
        self.cpp_n_threads = max((os.cpu_count() or 1), 1)
        self.cpp_write_mode = 'buffered_end'
        self.cpp_threads_last_mode = 'disabled'

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
        self._cython_nodechain_plan = None

    def _all_river_names(self):
        return [data.get('name') for _, _, data in self._river_edges]

    def _river_map(self):
        return {data.get('name'): data['river'] for _, _, data in self._river_edges}

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

    def _cython_nodechain_supported(self):
        if cython_run_internal_node_iteration_exact is None:
            return False
        if not bool(getattr(self, 'use_cython_nodechain', False)):
            return False
        if bool(getattr(self, 'use_parallel_workers', False)):
            return False
        if bool(getattr(self, 'internal_use_coupled_newton', False)):
            return False
        if bool(getattr(self, 'internal_use_numeric_jacobian', False)):
            return False
        if bool(getattr(self, 'internal_sync_branch_end_Q', False)):
            return False
        if bool(getattr(self, 'internal_node_use_face_flux_residual', False)):
            return False
        if bool(getattr(self, 'verbos', False)):
            return False
        return True

    def _build_cython_nodechain_plan(self):
        need_attrs = ('internal_nodes', 'external_in_nodes', 'external_out_nodes')
        if not all(hasattr(self, a) for a in need_attrs):
            self.classfy_nodes()
        node_names = tuple(self.internal_nodes)
        node_offsets = np.zeros(len(node_names) + 1, dtype=np.int32)
        branch_rivers = []
        branch_side_codes = []
        for i, node_name in enumerate(node_names):
            node_offsets[i] = len(branch_rivers)
            for river_obj, _ in self._in_branches_by_node[node_name]:
                branch_rivers.append(river_obj)
                branch_side_codes.append(1)  # node on branch right end -> outbound closure
            for river_obj, _ in self._out_branches_by_node[node_name]:
                branch_rivers.append(river_obj)
                branch_side_codes.append(0)  # node on branch left end -> inbound closure
        node_offsets[len(node_names)] = len(branch_rivers)
        self._cython_nodechain_plan = {
            'node_names': node_names,
            'node_offsets': node_offsets,
            'branch_rivers': tuple(branch_rivers),
            'branch_side_codes': np.asarray(branch_side_codes, dtype=np.int8),
        }
        return self._cython_nodechain_plan

    def _get_cython_nodechain_plan(self):
        plan = self._cython_nodechain_plan
        if plan is None:
            return self._build_cython_nodechain_plan()
        if len(plan['node_names']) != len(getattr(self, 'internal_nodes', ())):
            return self._build_cython_nodechain_plan()
        return plan

    def _try_update_internal_boundary_conditions_cython(self):
        if not self._cython_nodechain_supported():
            return False
        if not self.internal_nodes:
            return True
        plan = self._get_cython_nodechain_plan()
        return bool(
            cython_run_internal_node_iteration_exact(
                self,
                plan['node_names'],
                plan['node_offsets'],
                plan['branch_rivers'],
                plan['branch_side_codes'],
            )
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
            data['river'].Save_Basic_data()

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
        if not self.internal_node_history:
            return
        out_path = os.path.join(self.model_data['output_path'], 'internal_node_history.csv')
        pd.DataFrame(self.internal_node_history).to_csv(out_path, index=False)
        if self.verbos:
            print(f'[OK] 内部节点时序已保存 -> {out_path}')

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
                            stage_on_face=self.external_bc_stage_on_face
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
                            stage_on_face=self.external_bc_stage_on_face
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

    # 更新内部边界条件
    def Update_internal_boundary_conditions(self):
        if self.verbos: print('\n更新内部边界条件...')
        if not self.internal_nodes:
            return
        if self._try_update_internal_boundary_conditions_cython():
            return

        # 预测步：优先采用上一时刻收敛水位，缺失时回退到真实格平均水位
        node_levels = {}
        for n in self.internal_nodes:
            if self.internal_level_predict_from_last and n in self._internal_node_level_cache:
                z0 = float(self._internal_node_level_cache[n])
            else:
                z0 = float(self.Caculate_node_average_level_at_real_cell(n))
                if np.isnan(z0):
                    z0 = float(self.Caculate_node_average_level_at_ghost_cell(n))
                if np.isnan(z0):
                    z0 = 0.0
            node_levels[n] = max(0.0, z0)

        converged = False
        max_abs_q = np.inf
        if self.internal_use_coupled_newton:
            m = len(self.internal_nodes)
            for iter_time in range(1, self.max_iteration + 1):
                r_vec = self._internal_residual_vector(node_levels)
                max_abs_q = float(np.max(np.abs(r_vec))) if r_vec.size > 0 else 0.0

                J = self._internal_jacobian_numeric(node_levels, r_vec)
                # 轻度对角正则，避免近奇异导致方向失真
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
                # 同步施加全部汊点水位（JPWSPC 风格）
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

                        # 数值导数过小则回退到解析近似
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

                    # JPWSPC 原式不含显式裁剪；仅在非 paper 模式下保留保护裁剪
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

        # 用最终水位统一施加一次，保证后续通量计算使用一致边界
        self._apply_internal_node_levels(node_levels)
        self._internal_node_level_cache.update(node_levels)

        if self.verbos:
            if not converged:
                print(f'内部边界迭代达到上限 {self.max_iteration} 次，max|Qnet|={max_abs_q:.4e}')
            for n in self.internal_nodes:
                print(f'节点 {n} 最终水位: {node_levels[n]:.4f} 米')


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
        for r, _ in self._in_branches_by_node[node_name]:
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
                        stage_on_face=self.internal_bc_stage_on_face
                    )

        # -----------------------------
        # 2) 处理“出支”（node 为上游端，边方向 node -> v）
        #    上游鬼格索引为 0（相邻实格为 1）
        # -----------------------------
        for r, _ in self._out_branches_by_node[node_name]:
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
                        stage_on_face=self.internal_bc_stage_on_face
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

    def _update_boundary_conditions_parallel(self, pool):
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
            snapshots = pool.call_batch_and_interface_snapshots(external_ops, snapshot_mode=snapshot_mode)
            aggregates = None

        node_levels = {}
        for n in self.internal_nodes:
            if self.internal_level_predict_from_last and n in self._internal_node_level_cache:
                z0 = float(self._internal_node_level_cache[n])
            else:
                if use_node_aggregates:
                    z0 = float(self._parallel_node_average_level_at_real_cell_from_aggregates(n, aggregates))
                else:
                    z0 = float(self._parallel_node_average_level_at_real_cell(n, snapshots))
                if np.isnan(z0):
                    if use_node_aggregates:
                        z0 = float(self._parallel_node_average_level_at_ghost_cell_from_aggregates(n, aggregates))
                    else:
                        z0 = float(self._parallel_node_average_level_at_ghost_cell(n, snapshots))
                if np.isnan(z0):
                    z0 = 0.0
            node_levels[n] = max(0.0, z0)

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

    def _record_internal_node_history_current_state(self):
        if not (self.save_outputs and self.internal_nodes):
            return
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

    def _record_internal_node_history_from_snapshots(self, snapshots):
        if not (self.save_outputs and self.internal_nodes):
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

    def _finalize_evolve_outputs(self):
        if not self.save_outputs:
            return
        self.Resample_and_Save_result_net()
        self.Save_internal_node_history()
        self.Save_cfl_history()

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
            self.Update_boundary_conditions()

            self._record_internal_node_history_current_state()

            dt_map = pool.advance_local_step(
                use_implicit_branch_update=self.use_implicit_branch_update,
                save_names=selected_names if self.save_outputs else None,
            )
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
        self._finalize_evolve_outputs()

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

            snapshots = self._update_boundary_conditions_parallel(pool)
            self._record_internal_node_history_from_snapshots(snapshots)

            dt_map = pool.advance_local_step(
                use_implicit_branch_update=self.use_implicit_branch_update,
                save_names=selected_names if self.save_outputs else None,
            )
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
            self.Update_boundary_conditions()

            # 记录本时间步边界更新后的结点水位与净流量（用于与节点观测口径比对）
            if self.save_outputs and self.internal_nodes:
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
            self.Caculate_face_U_C_net()

            # 计算Roe matrix
            self.Caculate_Roe_matrix_net()

            # 计算Source_term2
            self.Caculate_Source_term_net()

            # 计算Roe_flux2
            self.Caculate_Roe_flux_net()

            # 组装通量（显式/隐式分支）
            if self.use_implicit_branch_update:
                self.Caculate_impli_trans_coefficient_net()
                self.Assemble_flux_impli_net()
            else:
                self.Assemble_flux_net()

            # 更新河道网格参数 cell proptirty2
            self.Update_cell_property_net()

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
            self.Caculate_global_CFL()

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
        self._finalize_evolve_outputs()

    def _run_prepared_evolve(self, yield_step):
        if self.use_cpp_evolve and cpp_run_network_evolve_serial is not None:
            if self.cpp_threads and cpp_run_network_evolve_threads is not None:
                emitted_times = cpp_run_network_evolve_threads(
                    self,
                    float(yield_step),
                    int(self.cpp_n_threads),
                )
            else:
                emitted_times = cpp_run_network_evolve_serial(self, float(yield_step))
            for t in emitted_times:
                yield t
            return

        for t in self._evolve_base(yield_step):
            yield t

    # 演进过程
    def Evolve(self, yield_step=None):
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

        # 初始化其余参数
        self.Init_cell_property_net()

        # 保存初始结果
        self.Save_basic_data_net()
        self._configure_output_save_schedule(yield_step)

        # 计算第一步时间步长
        self.Caculate_global_CFL()
        self.DT = self.cfl_allowed_dt  # 初始时间步长为全局最小CFL时间步长

        if self.use_cpp_evolve and cpp_run_network_evolve_serial is not None:
            for t in self._run_prepared_evolve(yield_step):
                yield t
            return

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
                evolve_fn = self._evolve_base_parallel_process
            else:
                pool = PersistentRiverThreadPool(
                    river_items=river_items,
                    n_workers=self.parallel_n_workers,
                    start_method=self.parallel_start_method,
                )
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

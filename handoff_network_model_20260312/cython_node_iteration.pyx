# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

import numpy as np
cimport numpy as cnp
from libc.math cimport fabs, isnan, sqrt
import time as pytime

from cython_cross_section cimport (
    CrossSectionTableCython,
    compute_stage_boundary_mainline_fast,
)


cdef inline double _maxd(double a, double b) noexcept:
    return a if a >= b else b


cdef inline int _to_positive_idx(int idx, int n) noexcept:
    return idx if idx >= 0 else n + idx


cdef inline double _direct_width(CrossSectionTableCython tbl, double area) noexcept:
    return float(tbl.get_width_by_area(area))


cdef inline double _resolve_width_exact(
    CrossSectionTableCython tbl,
    double area,
    double depth,
    double eps,
    double water_depth_limit,
    bint preserve_true_width,
) noexcept:
    cdef double width = float(tbl.get_width_by_area(area))
    if (not preserve_true_width) and width < eps and depth > water_depth_limit:
        width = _maxd(area / _maxd(depth, water_depth_limit), eps)
    return _maxd(width, eps)


cdef bint _apply_stage_boundary_wrapper_bypass(
    object river,
    bint is_left,
    double level,
    bint use_fix_level_bc_v2,
    bint use_stabilizers,
    bint respect_supercritical,
    bint stage_on_face,
):
    if use_fix_level_bc_v2:
        return False
    return bool(
        river._stage_boundary_fix_level_cython_fast(
            'left' if is_left else 'right',
            float(level),
            use_stabilizers=bool(use_stabilizers),
            respect_supercritical=bool(respect_supercritical),
            stage_on_face=bool(stage_on_face),
        )
    )


cdef class NodeBoundaryDeepPlan:
    cdef public object river
    cdef CrossSectionTableCython tbl_inner
    cdef CrossSectionTableCython tbl_target
    cdef CrossSectionTableCython tbl_second

    cdef int side_code
    cdef int ghost_idx
    cdef int inner_idx
    cdef int second_idx
    cdef int dry_limit_idx
    cdef bint is_left
    cdef bint use_o2
    cdef bint swap_moc_sign
    cdef bint implic_flag
    cdef bint preserve_true_width

    cdef double guard_q_delta
    cdef double guard_abs_delta
    cdef double g
    cdef double eps
    cdef double water_depth_limit
    cdef double velocity_depth_limit
    cdef double dt_moc

    cdef int near_dry_velocity_mode
    cdef int near_dry_derived_mode

    cdef cnp.float32_t[:] S
    cdef cnp.float32_t[:] Q
    cdef double[:] water_level
    cdef double[:] water_depth
    cdef cnp.float32_t[:] U
    cdef cnp.float32_t[:] C
    cdef cnp.float32_t[:] FR
    cdef cnp.float32_t[:] P
    cdef cnp.float32_t[:] PRESS
    cdef cnp.float32_t[:] R
    cdef double[:] cell_s_limit
    cdef double[:] cell_bed
    cdef cnp.uint8_t[:] forced_dry_recorded
    cdef cnp.float32_t[:] S_old
    cdef cnp.float32_t[:] Q_old
    cdef cnp.float32_t[:] V

    cdef bint face_valid
    cdef double face_level
    cdef double face_area
    cdef double face_discharge
    cdef double face_width

    cdef void set_dt(self, double dt) noexcept:
        self.dt_moc = dt

    cdef void _refresh_committed_state(self, double level, double Ab, double Qb, double Tb):
        self.S[self.ghost_idx] = <cnp.float32_t>Ab
        self.Q[self.ghost_idx] = <cnp.float32_t>Qb
        if self.side_code == 0:
            self.river._refresh_cell_state(0, level_hint=level)
        else:
            self.river._refresh_cell_state(-1, level_hint=level)

        self.face_valid = True
        self.face_level = level
        self.face_area = Ab
        self.face_discharge = Qb
        self.face_width = Tb

        if self.implic_flag:
            self.V[0] = <cnp.float32_t>(float(self.S[self.ghost_idx]) - float(self.S_old[self.ghost_idx]))
            self.V[1] = <cnp.float32_t>(float(self.Q[self.ghost_idx]) - float(self.Q_old[self.ghost_idx]))

    cdef bint apply_level(self, double level):
        cdef double A2 = 0.0
        cdef double Q2 = 0.0
        cdef object result

        if self.use_o2:
            A2 = _maxd(float(self.S[self.second_idx]), 1.0e-12)
            Q2 = float(self.Q[self.second_idx])
        result = compute_stage_boundary_mainline_fast(
            self.tbl_inner,
            self.tbl_target,
            self.tbl_second if self.use_o2 else None,
            self.is_left,
            self.g,
            1.0e-12,
            1.0e-08,
            level,
            float(self.S[self.inner_idx]),
            float(self.Q[self.inner_idx]),
            float(self.water_depth[self.inner_idx]),
            float(self.cell_s_limit[self.dry_limit_idx]),
            self.water_depth_limit,
            self.dt_moc,
            self.use_o2,
            A2,
            Q2,
            self.guard_q_delta,
            self.guard_abs_delta,
            self.swap_moc_sign,
        )
        if result is None:
            return False
        self._refresh_committed_state(
            level,
            float(result[0]),
            float(result[2]),
            float(result[1]),
        )
        return True

    cdef void capture_python_boundary_state(self):
        cdef object level_val
        cdef object area_val
        cdef object q_val
        cdef object width_val

        if self.side_code == 0:
            level_val = getattr(self.river, 'boundary_face_level_left', None)
            area_val = getattr(self.river, 'boundary_face_area_left', None)
            q_val = getattr(self.river, 'boundary_face_discharge_left', None)
            width_val = getattr(self.river, 'boundary_face_width_left', None)
        else:
            level_val = getattr(self.river, 'boundary_face_level_right', None)
            area_val = getattr(self.river, 'boundary_face_area_right', None)
            q_val = getattr(self.river, 'boundary_face_discharge_right', None)
            width_val = getattr(self.river, 'boundary_face_width_right', None)
        if level_val is None or area_val is None or q_val is None or width_val is None:
            self.face_valid = False
            self.face_level = 0.0
            self.face_area = 0.0
            self.face_discharge = 0.0
            self.face_width = 0.0
            return
        self.face_valid = True
        self.face_level = float(level_val)
        self.face_area = float(area_val)
        self.face_discharge = float(q_val)
        self.face_width = float(width_val)

    cdef void sync_python_boundary_state(self):
        if not self.face_valid:
            return
        if self.side_code == 0:
            self.river.boundary_face_level_left = float(self.face_level)
            self.river.boundary_face_area_left = float(self.face_area)
            self.river.boundary_face_discharge_left = float(self.face_discharge)
            self.river.boundary_face_width_left = float(self.face_width)
        else:
            self.river.boundary_face_level_right = float(self.face_level)
            self.river.boundary_face_area_right = float(self.face_area)
            self.river.boundary_face_discharge_right = float(self.face_discharge)
            self.river.boundary_face_width_right = float(self.face_width)

    cpdef object export_face_state(self):
        if not self.face_valid:
            return None
        return (
            float(self.face_level),
            float(self.face_area),
            float(self.face_discharge),
            float(self.face_width),
        )


cpdef object build_nodechain_deep_apply_plan(
    object branch_rivers,
    cnp.ndarray[cnp.int8_t, ndim=1] branch_side_codes_arr,
):
    cdef Py_ssize_t k, n = len(branch_rivers)
    cdef object river
    cdef object ctx
    cdef NodeBoundaryDeepPlan plan
    cdef list plans = []
    cdef int side_code
    cdef int total_cells
    cdef cnp.int8_t[:] branch_side_codes = branch_side_codes_arr
    cdef cnp.ndarray[cnp.uint8_t, ndim=1] forced_dry_flags

    for k in range(n):
        river = branch_rivers[k]
        side_code = <int>branch_side_codes[k]
        if not bool(getattr(river, '_cython_cell_state_ready', False)):
            return None
        ctx = river._get_stage_boundary_prebound_context('left' if side_code == 0 else 'right')
        if ctx is None:
            return None

        plan = NodeBoundaryDeepPlan()
        plan.river = river
        plan.tbl_inner = <CrossSectionTableCython>ctx['tbl_inner']
        plan.tbl_target = <CrossSectionTableCython>ctx['tbl_target']
        plan.tbl_second = None if ctx['tbl_second'] is None else <CrossSectionTableCython>ctx['tbl_second']
        total_cells = len(river.cell_sections)

        plan.side_code = side_code
        plan.ghost_idx = _to_positive_idx(int(ctx['ghost_idx']), total_cells)
        plan.inner_idx = _to_positive_idx(int(ctx['inner_idx']), total_cells)
        plan.second_idx = _to_positive_idx(int(ctx['second_idx']), total_cells)
        plan.dry_limit_idx = _to_positive_idx(int(ctx['dry_limit_idx']), total_cells)
        plan.is_left = bool(ctx['is_left'])
        plan.use_o2 = bool(ctx['use_o2'])
        plan.swap_moc_sign = bool(ctx['swap_moc_sign'])
        plan.implic_flag = bool(getattr(river, 'Implic_flag', False))
        plan.preserve_true_width = bool(getattr(river, 'fix_02_preserve_true_width', False))

        plan.guard_q_delta = float(ctx['guard_q_delta'])
        plan.guard_abs_delta = float(ctx['guard_abs_delta'])
        plan.g = float(river.g)
        plan.eps = float(river.EPSILON)
        plan.water_depth_limit = float(river.water_depth_limit)
        plan.velocity_depth_limit = float(river.velocity_depth_limit)
        plan.dt_moc = float(getattr(river, 'DT', 0.0))

        if river.near_dry_velocity_cutoff_mode == 'zero_q':
            plan.near_dry_velocity_mode = 0
        else:
            plan.near_dry_velocity_mode = 1
        if river.near_dry_derived_mode == 'floor_u_and_c':
            plan.near_dry_derived_mode = 0
        elif river.near_dry_derived_mode == 'actual_u_floor_c':
            plan.near_dry_derived_mode = 1
        elif river.near_dry_derived_mode == 'actual_u_soft_floor_c':
            plan.near_dry_derived_mode = 2
        else:
            plan.near_dry_derived_mode = 3

        plan.S = river.S
        plan.Q = river.Q
        plan.water_level = river.water_level
        plan.water_depth = river.water_depth
        plan.U = river.U
        plan.C = river.C
        plan.FR = river.FR
        plan.P = river.P
        plan.PRESS = river.PRESS
        plan.R = river.R
        plan.cell_s_limit = river._cell_s_limit_arr
        plan.cell_bed = river._cell_bed_level_arr
        forced_dry_flags = river._forced_dry_recorded.view(np.uint8)
        plan.forced_dry_recorded = forced_dry_flags
        if plan.implic_flag:
            plan.S_old = river.S_old
            plan.Q_old = river.Q_old
            plan.V = river.V0 if side_code == 0 else river.V1

        plan.face_valid = False
        plan.face_level = 0.0
        plan.face_area = 0.0
        plan.face_discharge = 0.0
        plan.face_width = 0.0
        plan.capture_python_boundary_state()
        plans.append(plan)
    return tuple(plans)


cpdef bint run_internal_node_iteration_exact(
    object net,
    object node_names,
    cnp.ndarray[cnp.int32_t, ndim=1] node_offsets_arr,
    object branch_rivers,
    cnp.ndarray[cnp.int8_t, ndim=1] branch_side_codes_arr,
    object branch_deep_apply_plans=None,
):
    cdef Py_ssize_t n_nodes = len(node_names)
    cdef Py_ssize_t i, k, start, end, n_branches
    cdef object node_name
    cdef object river
    cdef object deep_plan_obj
    cdef NodeBoundaryDeepPlan deep_plan
    cdef double z0, pure_q, dR_dZ, dz, max_abs_dz, max_abs_q
    cdef double ac, A, B, Qv, u_loc, c_loc, Fr
    cdef double g = float(net.g)
    cdef double alpha = float(net.alpha)
    cdef double relax = float(net.relax)
    cdef double q_limit = float(net.JPWSPC_Q_limit)
    cdef double epsA = 1.0e-12
    cdef double epsT = 1.0e-08
    cdef double dlevel_clip = 0.5
    cdef bint use_fix_level_bc_v2 = bool(net.use_fix_level_bc_v2)
    cdef bint use_stabilizers = bool(net.internal_bc_use_stabilizers)
    cdef bint respect_supercritical = bool(net.internal_bc_respect_supercritical)
    cdef bint stage_on_face = bool(net.internal_bc_stage_on_face)
    cdef bint use_paper_ac = bool(net.internal_use_paper_ac)
    cdef bint use_ac_v2 = bool(net.internal_use_ac_v2)
    cdef bint use_face_discharge = bool(net.internal_node_use_face_discharge)
    cdef bint prefer_boundary_face_q = bool(net.internal_node_prefer_boundary_face_discharge)
    cdef bint use_boundary_face_ac = bool(net.internal_node_use_boundary_face_ac)
    cdef object level_cache = net._internal_node_level_cache
    cdef bint converged = False
    cdef object face_q
    cdef object face_a
    cdef object face_b
    cdef Py_ssize_t ghost_idx, cell_idx
    cdef int side_code
    cdef int max_iteration = int(net.max_iteration)
    cdef bint perf_enabled = bool(getattr(net, 'perf_profile_enabled', False))
    cdef bint use_direct_fast = bool(getattr(net, 'use_cython_nodechain_direct_fast', False))
    cdef bint use_prebound_fast = bool(getattr(net, 'use_cython_nodechain_prebound_fast', False))
    cdef bint use_deep_apply = bool(getattr(net, 'use_cpp_nodechain_deep_apply', False)) and branch_deep_apply_plans is not None
    cdef bint use_commit_deep = bool(getattr(net, 'use_cpp_nodechain_commit_deep', False)) and use_deep_apply
    cdef double perf_total_start = 0.0
    cdef double perf_stage_start = 0.0
    cdef Py_ssize_t closure_calls = 0
    cdef Py_ssize_t width_lookup_calls = 0
    cdef Py_ssize_t boundary_python_calls = 0
    cdef Py_ssize_t prebound_fast_hits = 0
    cdef Py_ssize_t deep_apply_hits = 0
    cdef int iter_count = 0
    cdef bint used_face_state

    if n_nodes == 0:
        return True

    n_branches = len(branch_rivers)
    if use_deep_apply and len(branch_deep_apply_plans) != n_branches:
        use_deep_apply = False

    if use_deep_apply:
        for k in range(n_branches):
            deep_plan = <NodeBoundaryDeepPlan>branch_deep_apply_plans[k]
            deep_plan.set_dt(float(getattr(deep_plan.river, 'DT', 0.0)))

    if perf_enabled:
        perf_total_start = pytime.perf_counter()
        net._perf_inc('nodechain.solve_calls')
        net._perf_inc('nodechain.nodes_total', n_nodes)

    cdef cnp.ndarray[cnp.float64_t, ndim=1] levels = np.empty(n_nodes, dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] residuals = np.empty(n_nodes, dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] new_levels = np.empty(n_nodes, dtype=np.float64)
    cdef cnp.ndarray[cnp.float64_t, ndim=1] acs = np.empty(n_nodes, dtype=np.float64)

    cdef cnp.int32_t[:] node_offsets = node_offsets_arr
    cdef cnp.int8_t[:] branch_side_codes = branch_side_codes_arr

    if perf_enabled:
        perf_stage_start = pytime.perf_counter()
    for i in range(n_nodes):
        node_name = node_names[i]
        if bool(net.internal_level_predict_from_last) and node_name in level_cache:
            z0 = float(level_cache[node_name])
        else:
            z0 = float(net.Caculate_node_average_level_at_real_cell(node_name))
            if isnan(z0):
                z0 = float(net.Caculate_node_average_level_at_ghost_cell(node_name))
            if isnan(z0):
                z0 = 0.0
        levels[i] = _maxd(0.0, z0)
    if perf_enabled:
        net._perf_add('nodechain.predict', pytime.perf_counter() - perf_stage_start)

    for _ in range(max_iteration):
        iter_count += 1
        if perf_enabled:
            perf_stage_start = pytime.perf_counter()
        for i in range(n_nodes):
            start = node_offsets[i]
            end = node_offsets[i + 1]
            for k in range(start, end):
                closure_calls += 1
                river = branch_rivers[k]
                side_code = <int>branch_side_codes[k]
                if use_deep_apply:
                    deep_plan = <NodeBoundaryDeepPlan>branch_deep_apply_plans[k]
                    if deep_plan.apply_level(float(levels[i])):
                        prebound_fast_hits += 1
                        deep_apply_hits += 1
                        continue
                if use_prebound_fast:
                    boundary_python_calls += 1
                    if river._stage_boundary_fix_level_cython_prebound_fast(side_code, float(levels[i])):
                        prebound_fast_hits += 1
                        if use_deep_apply:
                            deep_plan.capture_python_boundary_state()
                        continue
                if use_direct_fast:
                    boundary_python_calls += 1
                    if _apply_stage_boundary_wrapper_bypass(
                        river,
                        side_code == 0,
                        float(levels[i]),
                        use_fix_level_bc_v2,
                        use_stabilizers,
                        respect_supercritical,
                        stage_on_face,
                    ):
                        if use_deep_apply:
                            deep_plan.capture_python_boundary_state()
                        continue
                boundary_python_calls += 1
                if side_code == 1:
                    if use_fix_level_bc_v2:
                        river.OutBound_Fix_level_V2(float(levels[i]))
                    else:
                        river.OutBound_Fix_level_V3(
                            float(levels[i]),
                            use_stabilizers=use_stabilizers,
                            respect_supercritical=respect_supercritical,
                            stage_on_face=stage_on_face,
                        )
                else:
                    if use_fix_level_bc_v2:
                        river.InBound_Fix_level_V2(float(levels[i]))
                    else:
                        river.InBound_Fix_level_V3(
                            float(levels[i]),
                            use_stabilizers=use_stabilizers,
                            respect_supercritical=respect_supercritical,
                            stage_on_face=stage_on_face,
                        )
                if use_deep_apply:
                    deep_plan.capture_python_boundary_state()
        if perf_enabled:
            net._perf_add('nodechain.apply_and_boundary_closure', pytime.perf_counter() - perf_stage_start)

        max_abs_q = 0.0
        max_abs_dz = 0.0

        if perf_enabled:
            perf_stage_start = pytime.perf_counter()
        for i in range(n_nodes):
            pure_q = 0.0
            ac = 0.0
            start = node_offsets[i]
            end = node_offsets[i + 1]

            for k in range(start, end):
                river = branch_rivers[k]
                side_code = <int>branch_side_codes[k]
                used_face_state = False

                if use_deep_apply:
                    deep_plan = <NodeBoundaryDeepPlan>branch_deep_apply_plans[k]
                if side_code == 1:
                    if use_deep_apply:
                        ghost_idx = deep_plan.ghost_idx
                        cell_idx = deep_plan.inner_idx
                        if prefer_boundary_face_q and deep_plan.face_valid:
                            pure_q += deep_plan.face_discharge
                            used_face_state = True
                        elif use_face_discharge:
                            pure_q += 0.5 * (float(deep_plan.Q[ghost_idx]) + float(deep_plan.Q[cell_idx]))
                        else:
                            pure_q += float(deep_plan.Q[ghost_idx])
                    else:
                        ghost_idx = int(river.cell_num) + 1
                        cell_idx = int(river.cell_num)
                        face_q = getattr(river, 'boundary_face_discharge_right', None)
                        if prefer_boundary_face_q and face_q is not None:
                            pure_q += float(face_q)
                            used_face_state = True
                        elif use_face_discharge:
                            pure_q += 0.5 * (float(river.Q[ghost_idx]) + float(river.Q[cell_idx]))
                        else:
                            pure_q += float(river.Q[ghost_idx])

                    if use_paper_ac:
                        if use_deep_apply and use_boundary_face_ac and deep_plan.face_valid:
                            A = _maxd(deep_plan.face_area, epsA)
                            B = _maxd(deep_plan.face_width, epsA)
                            Qv = deep_plan.face_discharge
                        else:
                            if use_deep_apply:
                                A = _maxd(float(deep_plan.S[ghost_idx]), epsA)
                                B = _maxd(_direct_width(deep_plan.tbl_target, A), epsA)
                                Qv = float(deep_plan.Q[ghost_idx])
                            else:
                                face_a = getattr(river, 'boundary_face_area_right', None)
                                face_b = getattr(river, 'boundary_face_width_right', None)
                                face_q = getattr(river, 'boundary_face_discharge_right', None)
                                if use_boundary_face_ac and face_a is not None and face_b is not None and face_q is not None:
                                    A = _maxd(float(face_a), epsA)
                                    B = _maxd(float(face_b), epsA)
                                    Qv = float(face_q)
                                else:
                                    A = _maxd(float(river.S[ghost_idx]), epsA)
                                    width_lookup_calls += 1
                                    B = _maxd(float(river.cross_section_table.get_width_by_area(river.cell_sections[ghost_idx], A)), epsA)
                                    Qv = float(river.Q[ghost_idx])
                        ac += sqrt(g * A * B) - Qv * B / A
                    elif use_ac_v2:
                        if use_deep_apply:
                            A = _maxd(float(deep_plan.S[cell_idx]), epsA)
                            B = _maxd(_direct_width(deep_plan.tbl_inner, A), epsT)
                            Qv = float(deep_plan.Q[cell_idx])
                        else:
                            A = _maxd(float(river.S[cell_idx]), epsA)
                            width_lookup_calls += 1
                            B = _maxd(float(river.cross_section_table.get_width_by_area(river.cell_sections[cell_idx], A)), epsT)
                            Qv = float(river.Q[cell_idx])
                        u_loc = Qv / A
                        c_loc = sqrt(g * A / B)
                        Fr = fabs(u_loc) / _maxd(c_loc, epsA)
                        if not (Fr >= 1.0 and Qv > 0.0):
                            ac += B * (c_loc - u_loc)
                    else:
                        if use_deep_apply:
                            A = _maxd(float(deep_plan.S[ghost_idx]), epsA)
                            B = _maxd(_direct_width(deep_plan.tbl_target, A), epsA)
                            Qv = float(deep_plan.Q[ghost_idx])
                        else:
                            A = _maxd(float(river.S[ghost_idx]), epsA)
                            width_lookup_calls += 1
                            B = _maxd(float(river.cross_section_table.get_width_by_area(river.cell_sections[ghost_idx], A)), epsA)
                            Qv = float(river.Q[ghost_idx])
                        ac += sqrt(g * A * B) - Qv * B / A

                else:
                    if use_deep_apply:
                        ghost_idx = deep_plan.ghost_idx
                        cell_idx = deep_plan.inner_idx
                        if prefer_boundary_face_q and deep_plan.face_valid:
                            pure_q -= deep_plan.face_discharge
                            used_face_state = True
                        elif use_face_discharge:
                            pure_q -= 0.5 * (float(deep_plan.Q[ghost_idx]) + float(deep_plan.Q[cell_idx]))
                        else:
                            pure_q -= float(deep_plan.Q[ghost_idx])
                    else:
                        ghost_idx = 0
                        cell_idx = 1
                        face_q = getattr(river, 'boundary_face_discharge_left', None)
                        if prefer_boundary_face_q and face_q is not None:
                            pure_q -= float(face_q)
                            used_face_state = True
                        elif use_face_discharge:
                            pure_q -= 0.5 * (float(river.Q[ghost_idx]) + float(river.Q[cell_idx]))
                        else:
                            pure_q -= float(river.Q[ghost_idx])

                    if use_paper_ac:
                        if use_deep_apply and use_boundary_face_ac and deep_plan.face_valid:
                            A = _maxd(deep_plan.face_area, epsA)
                            B = _maxd(deep_plan.face_width, epsA)
                            Qv = deep_plan.face_discharge
                        else:
                            if use_deep_apply:
                                A = _maxd(float(deep_plan.S[ghost_idx]), epsA)
                                B = _maxd(_direct_width(deep_plan.tbl_target, A), epsA)
                                Qv = float(deep_plan.Q[ghost_idx])
                            else:
                                face_a = getattr(river, 'boundary_face_area_left', None)
                                face_b = getattr(river, 'boundary_face_width_left', None)
                                face_q = getattr(river, 'boundary_face_discharge_left', None)
                                if use_boundary_face_ac and face_a is not None and face_b is not None and face_q is not None:
                                    A = _maxd(float(face_a), epsA)
                                    B = _maxd(float(face_b), epsA)
                                    Qv = float(face_q)
                                else:
                                    A = _maxd(float(river.S[ghost_idx]), epsA)
                                    width_lookup_calls += 1
                                    B = _maxd(float(river.cross_section_table.get_width_by_area(river.cell_sections[ghost_idx], A)), epsA)
                                    Qv = float(river.Q[ghost_idx])
                        ac += sqrt(g * A * B) + Qv * B / A
                    elif use_ac_v2:
                        if use_deep_apply:
                            A = _maxd(float(deep_plan.S[cell_idx]), epsA)
                            B = _maxd(_direct_width(deep_plan.tbl_inner, A), epsT)
                            Qv = float(deep_plan.Q[cell_idx])
                        else:
                            A = _maxd(float(river.S[cell_idx]), epsA)
                            width_lookup_calls += 1
                            B = _maxd(float(river.cross_section_table.get_width_by_area(river.cell_sections[cell_idx], A)), epsT)
                            Qv = float(river.Q[cell_idx])
                        u_loc = Qv / A
                        c_loc = sqrt(g * A / B)
                        Fr = fabs(u_loc) / _maxd(c_loc, epsA)
                        if not (Fr >= 1.0 and (-Qv) > 0.0):
                            ac += B * (c_loc + u_loc)
                    else:
                        if use_deep_apply:
                            A = _maxd(float(deep_plan.S[ghost_idx]), epsA)
                            B = _maxd(_direct_width(deep_plan.tbl_target, A), epsA)
                            Qv = float(deep_plan.Q[ghost_idx])
                        else:
                            A = _maxd(float(river.S[ghost_idx]), epsA)
                            width_lookup_calls += 1
                            B = _maxd(float(river.cross_section_table.get_width_by_area(river.cell_sections[ghost_idx], A)), epsA)
                            Qv = float(river.Q[ghost_idx])
                        ac += sqrt(g * A * B) + Qv * B / A

            residuals[i] = pure_q
            acs[i] = alpha * ac
            if fabs(pure_q) > max_abs_q:
                max_abs_q = fabs(pure_q)
        if perf_enabled:
            net._perf_add('nodechain.residual_and_ac', pytime.perf_counter() - perf_stage_start)

        if perf_enabled:
            perf_stage_start = pytime.perf_counter()
        for i in range(n_nodes):
            dR_dZ = -acs[i]
            if fabs(dR_dZ) < 1.0e-10:
                dz = 0.0
            else:
                dz = -residuals[i] / dR_dZ
            if not use_paper_ac:
                if dz > dlevel_clip:
                    dz = dlevel_clip
                elif dz < -dlevel_clip:
                    dz = -dlevel_clip
            dz = relax * dz
            new_levels[i] = _maxd(0.0, levels[i] + dz)
            if fabs(dz) > max_abs_dz:
                max_abs_dz = fabs(dz)

        for i in range(n_nodes):
            levels[i] = new_levels[i]

        if perf_enabled:
            net._perf_add('nodechain.update_and_stopping', pytime.perf_counter() - perf_stage_start)
        if max_abs_dz < 1.0e-4 and max_abs_q < q_limit:
            converged = True
            break

    if perf_enabled:
        perf_stage_start = pytime.perf_counter()
    for i in range(n_nodes):
        start = node_offsets[i]
        end = node_offsets[i + 1]
        for k in range(start, end):
            closure_calls += 1
            river = branch_rivers[k]
            side_code = <int>branch_side_codes[k]
            if use_deep_apply:
                deep_plan = <NodeBoundaryDeepPlan>branch_deep_apply_plans[k]
                if deep_plan.apply_level(float(levels[i])):
                    prebound_fast_hits += 1
                    deep_apply_hits += 1
                    if not use_commit_deep:
                        deep_plan.sync_python_boundary_state()
                    continue
            if use_prebound_fast:
                boundary_python_calls += 1
                if river._stage_boundary_fix_level_cython_prebound_fast(side_code, float(levels[i])):
                    prebound_fast_hits += 1
                    if use_deep_apply:
                        deep_plan.capture_python_boundary_state()
                    continue
            if use_direct_fast:
                boundary_python_calls += 1
                if _apply_stage_boundary_wrapper_bypass(
                    river,
                    side_code == 0,
                    float(levels[i]),
                    use_fix_level_bc_v2,
                    use_stabilizers,
                    respect_supercritical,
                    stage_on_face,
                ):
                    if use_deep_apply:
                        deep_plan.capture_python_boundary_state()
                    continue
            boundary_python_calls += 1
            if side_code == 1:
                if use_fix_level_bc_v2:
                    river.OutBound_Fix_level_V2(float(levels[i]))
                else:
                    river.OutBound_Fix_level_V3(
                        float(levels[i]),
                        use_stabilizers=use_stabilizers,
                        respect_supercritical=respect_supercritical,
                        stage_on_face=stage_on_face,
                    )
            else:
                if use_fix_level_bc_v2:
                    river.InBound_Fix_level_V2(float(levels[i]))
                else:
                    river.InBound_Fix_level_V3(
                        float(levels[i]),
                        use_stabilizers=use_stabilizers,
                        respect_supercritical=respect_supercritical,
                        stage_on_face=stage_on_face,
                    )
            if use_deep_apply:
                deep_plan.capture_python_boundary_state()

    for i in range(n_nodes):
        level_cache[node_names[i]] = float(levels[i])

    if perf_enabled:
        net._perf_add('nodechain.final_apply', pytime.perf_counter() - perf_stage_start)
        net._perf_inc('nodechain.iterations', iter_count)
        net._perf_inc('nodechain.boundary_closure_calls', closure_calls)
        net._perf_inc('nodechain.cython_to_python_boundary_calls', boundary_python_calls)
        net._perf_inc('nodechain.cython_to_python_width_calls', width_lookup_calls)
        net._perf_inc('nodechain.prebound_fast_hits', prebound_fast_hits)
        net._perf_inc('nodechain.deep_apply_hits', deep_apply_hits)
        net._perf_add('nodechain.total', pytime.perf_counter() - perf_total_start)
        net._perf_set_max('nodechain.max_iterations_per_solve', iter_count)

    return True

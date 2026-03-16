# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

import numpy as np
cimport numpy as cnp
from libc.math cimport fabs, isnan, sqrt
import time as pytime


cdef inline double _maxd(double a, double b) noexcept:
    return a if a >= b else b


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


cpdef bint run_internal_node_iteration_exact(
    object net,
    object node_names,
    cnp.ndarray[cnp.int32_t, ndim=1] node_offsets_arr,
    object branch_rivers,
    cnp.ndarray[cnp.int8_t, ndim=1] branch_side_codes_arr,
):
    cdef Py_ssize_t n_nodes = len(node_names)
    cdef Py_ssize_t i, k, start, end
    cdef object node_name
    cdef object river
    cdef double z0, pure_q, dR_dZ, dz, max_abs_dz, max_abs_q
    cdef double ac, A, B, Qv, width, u_loc, c_loc, Fr
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
    cdef double perf_total_start = 0.0
    cdef double perf_stage_start = 0.0
    cdef Py_ssize_t closure_calls = 0
    cdef Py_ssize_t width_lookup_calls = 0
    cdef int iter_count = 0

    if n_nodes == 0:
        return True

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

    # Predictor: exactly the same precedence as the Python path.
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
        # Apply all node levels in the same order as the Python serial path:
        # per-node, incoming branches first, then outgoing branches.
        if perf_enabled:
            perf_stage_start = pytime.perf_counter()
        for i in range(n_nodes):
            start = node_offsets[i]
            end = node_offsets[i + 1]
            for k in range(start, end):
                closure_calls += 1
                river = branch_rivers[k]
                side_code = <int>branch_side_codes[k]
                if use_direct_fast:
                    if _apply_stage_boundary_wrapper_bypass(
                        river,
                        side_code == 0,
                        float(levels[i]),
                        use_fix_level_bc_v2,
                        use_stabilizers,
                        respect_supercritical,
                        stage_on_face,
                    ):
                        continue
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

                if side_code == 1:
                    ghost_idx = int(river.cell_num) + 1
                    cell_idx = int(river.cell_num)
                    face_q = getattr(river, 'boundary_face_discharge_right', None)
                    if prefer_boundary_face_q and face_q is not None:
                        pure_q += float(face_q)
                    elif use_face_discharge:
                        pure_q += 0.5 * (float(river.Q[ghost_idx]) + float(river.Q[cell_idx]))
                    else:
                        pure_q += float(river.Q[ghost_idx])

                    if use_paper_ac:
                        face_a = getattr(river, 'boundary_face_area_right', None)
                        face_b = getattr(river, 'boundary_face_width_right', None)
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
                        A = _maxd(float(river.S[ghost_idx]), epsA)
                        width_lookup_calls += 1
                        B = _maxd(float(river.cross_section_table.get_width_by_area(river.cell_sections[ghost_idx], A)), epsA)
                        Qv = float(river.Q[ghost_idx])
                        ac += sqrt(g * A * B) - Qv * B / A

                else:
                    ghost_idx = 0
                    cell_idx = 1
                    face_q = getattr(river, 'boundary_face_discharge_left', None)
                    if prefer_boundary_face_q and face_q is not None:
                        pure_q -= float(face_q)
                    elif use_face_discharge:
                        pure_q -= 0.5 * (float(river.Q[ghost_idx]) + float(river.Q[cell_idx]))
                    else:
                        pure_q -= float(river.Q[ghost_idx])

                    if use_paper_ac:
                        face_a = getattr(river, 'boundary_face_area_left', None)
                        face_b = getattr(river, 'boundary_face_width_left', None)
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

    # Final synchronized apply to match the Python path.
    if perf_enabled:
        perf_stage_start = pytime.perf_counter()
    for i in range(n_nodes):
        start = node_offsets[i]
        end = node_offsets[i + 1]
        for k in range(start, end):
            closure_calls += 1
            river = branch_rivers[k]
            side_code = <int>branch_side_codes[k]
            if use_direct_fast:
                if _apply_stage_boundary_wrapper_bypass(
                    river,
                    side_code == 0,
                    float(levels[i]),
                    use_fix_level_bc_v2,
                    use_stabilizers,
                    respect_supercritical,
                    stage_on_face,
                ):
                    continue
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

    for i in range(n_nodes):
        level_cache[node_names[i]] = float(levels[i])

    if perf_enabled:
        net._perf_add('nodechain.final_apply', pytime.perf_counter() - perf_stage_start)
        net._perf_inc('nodechain.iterations', iter_count)
        net._perf_inc('nodechain.boundary_closure_calls', closure_calls)
        net._perf_inc('nodechain.cython_to_python_boundary_calls', closure_calls)
        net._perf_inc('nodechain.cython_to_python_width_calls', width_lookup_calls)
        net._perf_add('nodechain.total', pytime.perf_counter() - perf_total_start)
        net._perf_set_max('nodechain.max_iterations_per_solve', iter_count)

    return True

# distutils: language = c++
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

import time as pytime

import numpy as np
cimport numpy as cnp

cdef extern from "cpp/evolve_core.hpp" namespace "rivernet":
    float compute_river_cfl_candidate_exact_cpp_kernel "rivernet::compute_river_cfl_candidate_exact"(
        size_t n,
        float cfl,
        float dt_old,
        float dt_increase_factor,
        float min_dt,
        const float* U,
        const float* C,
        const float* cell_lengths,
        float* DTI,
    ) noexcept


cdef extern from "cpp/output_buffer.hpp" namespace "rivernet":
    cdef cppclass OutputBuffer:
        OutputBuffer(size_t space_size) except +
        void reset()
        void append(
            double time_value,
            const double* depth,
            const double* level,
            const double* velocity,
            const double* discharge,
            size_t n,
        ) except +
        size_t snapshot_count() const
        size_t space_size() const
        void copy_times(double* dst) const
        void copy_depth(double* dst) const
        void copy_level(double* dst) const
        void copy_velocity(double* dst) const
        void copy_discharge(double* dst) const


cdef class CppOutputBuffer:
    cdef OutputBuffer* _buf

    def __cinit__(self, Py_ssize_t space_size):
        self._buf = new OutputBuffer(<size_t>space_size)

    def __dealloc__(self):
        if self._buf != NULL:
            del self._buf
            self._buf = NULL

    def reset(self):
        self._buf.reset()

    def snapshot_count(self):
        return int(self._buf.snapshot_count())

    def space_size(self):
        return int(self._buf.space_size())

    def append_snapshot(self, double time_value, depth, level, velocity, discharge):
        cdef cnp.ndarray[cnp.float64_t, ndim=1, mode='c'] depth_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1, mode='c'] level_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1, mode='c'] velocity_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1, mode='c'] discharge_arr
        depth_arr = np.ascontiguousarray(depth, dtype=np.float64)
        level_arr = np.ascontiguousarray(level, dtype=np.float64)
        velocity_arr = np.ascontiguousarray(velocity, dtype=np.float64)
        discharge_arr = np.ascontiguousarray(discharge, dtype=np.float64)
        if not (
            depth_arr.shape[0]
            == level_arr.shape[0]
            == velocity_arr.shape[0]
            == discharge_arr.shape[0]
            == self._buf.space_size()
        ):
            raise ValueError("CppOutputBuffer append length mismatch")
        self._buf.append(
            time_value,
            &depth_arr[0],
            &level_arr[0],
            &velocity_arr[0],
            &discharge_arr[0],
            <size_t>depth_arr.shape[0],
        )

    def export_times(self):
        cdef Py_ssize_t n = <Py_ssize_t>self._buf.snapshot_count()
        cdef cnp.ndarray[cnp.float64_t, ndim=1] out = np.empty(n, dtype=np.float64)
        if n > 0:
            self._buf.copy_times(&out[0])
        return out

    def export_var(self, name):
        cdef Py_ssize_t n_snap = <Py_ssize_t>self._buf.snapshot_count()
        cdef Py_ssize_t n_space = <Py_ssize_t>self._buf.space_size()
        cdef cnp.ndarray[cnp.float64_t, ndim=2] out = np.empty((n_snap, n_space), dtype=np.float64)
        if n_snap == 0 or n_space == 0:
            return out
        if name == 'depth':
            self._buf.copy_depth(&out[0, 0])
        elif name == 'level':
            self._buf.copy_level(&out[0, 0])
        elif name == 'U':
            self._buf.copy_velocity(&out[0, 0])
        elif name == 'Q':
            self._buf.copy_discharge(&out[0, 0])
        else:
            raise KeyError(f'Unsupported output variable: {name}')
        return out


cpdef bint calculate_global_cfl_exact_cpp(object net):
    cdef object edges
    cdef list river_list
    cdef list name_list
    cdef tuple rivers
    cdef tuple names
    cdef cnp.ndarray[cnp.float32_t, ndim=1] dt_values
    cdef cnp.ndarray[cnp.float32_t, ndim=1] U_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] C_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] L_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] DTI_arr
    cdef object river
    cdef dict rec
    cdef Py_ssize_t i, n_rivers
    cdef cnp.float32_t dt_old
    cdef cnp.float32_t dt_candidate
    cdef cnp.float32_t dt_min

    if not bool(getattr(net, "_cpp_global_cfl_plan_ready", False)):
        edges = list(net._river_edges)
        river_list = []
        name_list = []
        for _, _, data in edges:
            river_list.append(data["river"])
            name_list.append(data.get("name"))
        net._cpp_global_cfl_rivers = tuple(river_list)
        net._cpp_global_cfl_names = tuple(name_list)
        net._cpp_global_cfl_dt_values = np.empty(len(edges), dtype=np.float32)
        net._cpp_global_cfl_plan_ready = True

    rivers = net._cpp_global_cfl_rivers
    names = net._cpp_global_cfl_names
    dt_values = net._cpp_global_cfl_dt_values
    n_rivers = len(rivers)
    if n_rivers == 0:
        return False

    for i in range(n_rivers):
        river = rivers[i]
        U_arr = river.U
        C_arr = river.C
        L_arr = river.cell_lengths
        DTI_arr = river.DTI
        dt_old = <cnp.float32_t>river.DT
        dt_candidate = compute_river_cfl_candidate_exact_cpp_kernel(
            <size_t>(river.cell_num + 2),
            <float>river.CFL,
            dt_old,
            <float>river.DT_increase_factor,
            <float>river.min_dt,
            &U_arr[0],
            &C_arr[0],
            &L_arr[0],
            &DTI_arr[0],
        )
        river.DT_old = np.float32(dt_old)
        river.DT = np.float32(dt_candidate)
        dt_values[i] = dt_candidate
        if i == 0 or dt_candidate < dt_min:
            dt_min = dt_candidate

    net.cfl_allowed_dt = np.float32(dt_min)

    if bool(net.save_cfl_history):
        rec = {"time": float(net.current_sim_time)}
        for i in range(n_rivers):
            rec[str(names[i])] = float(dt_values[i])
        rec["global_dt"] = float(net.cfl_allowed_dt)
        net.cfl_history.append(rec)

    if bool(net.verbos):
        print(f'全局最小CFL时间步长: {float(net.cfl_allowed_dt):.4f} 秒')
    return True


def run_cpp_network_evolve_serial(object net, object yield_step):
    cdef bint yield_flag = False
    cdef bint finish_flag = False
    cdef bint perf_enabled = bool(getattr(net, 'perf_profile_enabled', False))
    cdef list emitted_times = []
    cdef double perf_t0

    net.sub_step_start_time = pytime.time()
    net.caculation_start_time = pytime.time()

    while net.current_sim_time < net.total_sim_time:
        if perf_enabled:
            net._perf_inc('bridge.step_iterations')
        net.Set_global_time_step(net.DT)
        net.current_sim_time += net.DT
        net.step_count += 1
        net.sub_step_time += net.DT
        net.sub_step_count += 1
        net.sub_step_max_dt = max(net.sub_step_max_dt, net.DT)
        net.sub_step_min_dt = min(net.sub_step_min_dt, net.DT)

        if perf_enabled:
            perf_t0 = pytime.perf_counter()
        net.Update_boundary_conditions()
        if perf_enabled:
            net._perf_add('bridge.crossing.Update_boundary_conditions.time', pytime.perf_counter() - perf_t0)
            net._perf_inc('bridge.crossing.Update_boundary_conditions.calls')
            net._perf_inc('bridge.python_crossings')
        if bool(net.save_outputs) and bool(net.internal_nodes):
            if perf_enabled:
                perf_t0 = pytime.perf_counter()
            net._record_internal_node_history_current_state()
            if perf_enabled:
                net._perf_add('bridge.crossing._record_internal_node_history_current_state.time', pytime.perf_counter() - perf_t0)
                net._perf_inc('bridge.crossing._record_internal_node_history_current_state.calls')
                net._perf_inc('bridge.python_crossings')

        if perf_enabled:
            perf_t0 = pytime.perf_counter()
        net.Caculate_face_U_C_net()
        if perf_enabled:
            net._perf_add('river_step.face_uc', pytime.perf_counter() - perf_t0)
            net._perf_inc('river_step.face_uc.calls')
            net._perf_inc('bridge.crossing.Caculate_face_U_C_net.calls')
            net._perf_inc('bridge.python_crossings')
        if perf_enabled:
            perf_t0 = pytime.perf_counter()
        net.Caculate_Roe_matrix_net()
        if perf_enabled:
            net._perf_add('river_step.roe_matrix', pytime.perf_counter() - perf_t0)
            net._perf_inc('river_step.roe_matrix.calls')
            net._perf_inc('bridge.crossing.Caculate_Roe_matrix_net.calls')
            net._perf_inc('bridge.python_crossings')
        if perf_enabled:
            perf_t0 = pytime.perf_counter()
        net.Caculate_Source_term_net()
        if perf_enabled:
            net._perf_add('river_step.source', pytime.perf_counter() - perf_t0)
            net._perf_inc('river_step.source.calls')
            net._perf_inc('bridge.crossing.Caculate_Source_term_net.calls')
            net._perf_inc('bridge.python_crossings')
        if perf_enabled:
            perf_t0 = pytime.perf_counter()
        net.Caculate_Roe_flux_net()
        if perf_enabled:
            net._perf_add('river_step.flux', pytime.perf_counter() - perf_t0)
            net._perf_inc('river_step.flux.calls')
            net._perf_inc('bridge.crossing.Caculate_Roe_flux_net.calls')
            net._perf_inc('bridge.python_crossings')

        if bool(net.use_implicit_branch_update):
            if perf_enabled:
                perf_t0 = pytime.perf_counter()
            net.Caculate_impli_trans_coefficient_net()
            if perf_enabled:
                net._perf_add('river_step.impli_coeff', pytime.perf_counter() - perf_t0)
                net._perf_inc('bridge.crossing.Caculate_impli_trans_coefficient_net.calls')
                net._perf_inc('bridge.python_crossings')
                perf_t0 = pytime.perf_counter()
            net.Assemble_flux_impli_net()
            if perf_enabled:
                net._perf_add('river_step.assemble_impli', pytime.perf_counter() - perf_t0)
                net._perf_inc('bridge.crossing.Assemble_flux_impli_net.calls')
                net._perf_inc('bridge.python_crossings')
        else:
            if perf_enabled:
                perf_t0 = pytime.perf_counter()
            net.Assemble_flux_net()
            if perf_enabled:
                net._perf_add('river_step.assemble', pytime.perf_counter() - perf_t0)
                net._perf_inc('river_step.assemble.calls')
                net._perf_inc('bridge.crossing.Assemble_flux_net.calls')
                net._perf_inc('bridge.python_crossings')

        if perf_enabled:
            perf_t0 = pytime.perf_counter()
        net.Update_cell_property_net()
        if perf_enabled:
            net._perf_add('river_step.update_cell', pytime.perf_counter() - perf_t0)
            net._perf_inc('river_step.update_cell.calls')
            net._perf_inc('bridge.crossing.Update_cell_property_net.calls')
            net._perf_inc('bridge.python_crossings')

        if bool(net.save_outputs):
            if perf_enabled:
                perf_t0 = pytime.perf_counter()
            net.Save_step_result_net()
            if perf_enabled:
                net._perf_add('bridge.crossing.Save_step_result_net.time', pytime.perf_counter() - perf_t0)
                net._perf_inc('bridge.crossing.Save_step_result_net.calls')
                net._perf_inc('bridge.python_crossings')

        if yield_flag:
            net.sub_step_caculation_time_using = pytime.time() - net.sub_step_start_time
            emitted_times.append(net.current_sim_time)
            yield_flag = False
            net.sub_step_start_time = pytime.time()
            net.sub_step_time = 0.0
            net.sub_step_count = 0
            net.sub_step_max_dt = 0.0
            net.sub_step_min_dt = 999999

        if finish_flag:
            break

        if perf_enabled:
            perf_t0 = pytime.perf_counter()
        net.Caculate_global_CFL()
        if perf_enabled:
            net._perf_add('dt_update.global_cfl', pytime.perf_counter() - perf_t0)
            net._perf_inc('dt_update.global_cfl.calls')
            net._perf_inc('bridge.crossing.Caculate_global_CFL.calls')
            net._perf_inc('bridge.python_crossings')
        if net.current_sim_time + net.cfl_allowed_dt > net.total_sim_time + 1.0e-5:
            net.DT = net.total_sim_time - net.current_sim_time
        elif net.sub_step_time + net.cfl_allowed_dt > yield_step + 1.0e-5:
            net.DT = yield_step - net.sub_step_time
            yield_flag = True
        else:
            net.DT = net.cfl_allowed_dt

    net.caculation_time = pytime.time() - net.caculation_start_time
    print(f'计算结束，保存结果...\n共计算 {net.step_count} 步，总耗时: {net.caculation_time:.2f} 秒')
    net._finalize_evolve_outputs()
    return emitted_times


def run_cpp_network_evolve_threads(object net, object yield_step, int n_threads):
    net.cpp_threads_last_mode = f'serial_fallback:{n_threads}'
    return run_cpp_network_evolve_serial(net, yield_step)

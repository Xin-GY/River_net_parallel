# distutils: language = c++
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

import time as pytime

import numpy as np
cimport numpy as cnp


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


def run_cpp_network_evolve_serial(object net, object yield_step):
    cdef bint yield_flag = False
    cdef bint finish_flag = False
    cdef list emitted_times = []

    net.sub_step_start_time = pytime.time()
    net.caculation_start_time = pytime.time()

    while net.current_sim_time < net.total_sim_time:
        net.Set_global_time_step(net.DT)
        net.current_sim_time += net.DT
        net.step_count += 1
        net.sub_step_time += net.DT
        net.sub_step_count += 1
        net.sub_step_max_dt = max(net.sub_step_max_dt, net.DT)
        net.sub_step_min_dt = min(net.sub_step_min_dt, net.DT)

        net.Update_boundary_conditions()
        if bool(net.save_outputs) and bool(net.internal_nodes):
            net._record_internal_node_history_current_state()

        net.Caculate_face_U_C_net()
        net.Caculate_Roe_matrix_net()
        net.Caculate_Source_term_net()
        net.Caculate_Roe_flux_net()

        if bool(net.use_implicit_branch_update):
            net.Caculate_impli_trans_coefficient_net()
            net.Assemble_flux_impli_net()
        else:
            net.Assemble_flux_net()

        net.Update_cell_property_net()

        if bool(net.save_outputs):
            net.Save_step_result_net()

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

        net.Caculate_global_CFL()
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

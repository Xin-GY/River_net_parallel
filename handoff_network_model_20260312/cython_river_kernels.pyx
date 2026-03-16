# distutils: language = c++
# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

import numpy as np
from libc.math cimport fabs, sqrt
from libc.stdint cimport uint8_t
from libcpp.vector cimport vector

cimport numpy as cnp

from cython_cross_section cimport CrossSectionTableCython
from cython_cross_section import compute_general_hr_flux_interface

cdef extern from "cpp/river_kernels.hpp" namespace "rivernet":
    cdef cppclass TableView:
        const double* area_axis
        const double* depth_a
        const double* level_a
        const double* DEB_a
        const double* width_a
        const double* wetted_a
        const double* press_a
        const double* area_axis_wet
        const double* width_a_wet
        const double* depth_axis
        const double* area_d
        size_t area_len
        size_t wet_len
        size_t depth_len
        double bed_level

    cdef cppclass UpdateCellStats:
        size_t forced_dry_increment

    cdef cppclass AssemblePostStepStats:
        size_t forced_dry_increment

    cdef cppclass RoeMatrixStats:
        size_t supercritical_pos
        size_t supercritical_neg
        size_t subcritical
        size_t leveque_count
        float lambda1_min
        float lambda1_max
        float lambda2_min
        float lambda2_max

    UpdateCellStats update_cell_properties_exact_cpp_kernel "update_cell_properties_exact"(
        const TableView* tables,
        size_t n,
        float* S,
        float* Q,
        double* water_level,
        double* water_depth,
        float* U,
        float* C,
        float* FR,
        float* P,
        float* PRESS,
        float* R,
        float* QIN,
        const double* cell_s_limit,
        const double* cell_bed,
        uint8_t* forced_dry_recorded,
        double g,
        double eps,
        double water_depth_limit,
        double velocity_depth_limit,
        int preserve_true_width,
        int near_dry_velocity_mode,
        int near_dry_derived_mode,
    ) except +

    AssemblePostStepStats apply_explicit_manning_poststep_exact_cpp_kernel "apply_explicit_manning_poststep_exact"(
        const TableView* tables,
        size_t n,
        float* S,
        float* Q,
        const double* water_depth,
        const double* cell_s_limit,
        uint8_t* forced_dry_recorded,
        double g,
        double dt,
        double eps,
        double water_depth_limit,
        double friction_min_depth,
    ) except +

    RoeMatrixStats compute_roe_matrix_exact_cpp_kernel "rivernet::compute_roe_matrix_exact"(
        size_t n,
        float eps,
        float water_depth_limit,
        const float* F_C,
        const float* F_U,
        const float* BETA,
        const float* FR,
        const double* water_depth,
        const float* U,
        const float* C,
        const float* S,
        const float* Q,
        double* flag_LeVeque,
        float* abs_Lambda1,
        float* abs_Lambda2,
        float* alpha1,
        float* alpha2,
        float* Lambda1,
        float* Lambda2,
        double* Vactor1,
        double* Vactor2,
        double* Vactor1_T,
        double* Vactor2_T,
    ) except +

    void compute_face_uc_exact_cpp_kernel "rivernet::compute_face_uc_exact"(
        size_t n,
        double eps,
        double s_limit_default,
        int use_section_area_threshold,
        const float* S,
        const float* U,
        const float* C,
        const float* PRESS,
        const double* cell_s_limit,
        float* F_U,
        float* F_C,
    ) except +


cdef inline double _maxd(double a, double b) noexcept:
    return a if a >= b else b


cdef inline double _resolve_width_exact(
    object tbl,
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


cpdef bint fill_general_hr_flux_exact(object river):
    cdef Py_ssize_t i, j
    cdef int cell_num = int(river.cell_num)
    cdef tuple left_tables
    cdef tuple right_tables
    cdef object left_tbl
    cdef object right_tbl
    cdef double[:] river_bed_height
    cdef double[:] water_depth
    cdef cnp.float32_t[:] S
    cdef cnp.float32_t[:] Q
    cdef cnp.float32_t[:] cell_lengths
    cdef cnp.float32_t[:] PRESS
    cdef cnp.float32_t[:] QIN
    cdef double[:, :] Flux_LOC
    cdef double[:, :] Flux_Source_left
    cdef double[:, :] Flux_Source_right
    cdef double flux0, flux1, p_left_hr, p_right_hr
    cdef double available, max_flux, scale, rain_half
    cdef double tiny
    cdef double dt
    cdef int donor

    if not bool(getattr(river, "_general_hr_cython_batch_ready", False)):
        return False

    left_tables = river._general_hr_left_tables
    right_tables = river._general_hr_right_tables
    river_bed_height = river.river_bed_height
    water_depth = river.water_depth
    S = river.S
    Q = river.Q
    cell_lengths = river.cell_lengths
    PRESS = river.PRESS
    QIN = river.QIN
    Flux_LOC = river.Flux_LOC
    Flux_Source_left = river.Flux_Source_left
    Flux_Source_right = river.Flux_Source_right
    tiny = float(max(river.S_limit, river.EPSILON))
    dt = float(river.DT)

    for i in range(cell_num + 1):
        left_tbl = left_tables[i]
        right_tbl = right_tables[i]
        flux0, flux1, p_left_hr, p_right_hr = compute_general_hr_flux_interface(
            left_tbl,
            right_tbl,
            float(river.g),
            tiny,
            float(river.roe_entropy_fix),
            float(river.roe_entropy_fix_factor),
            float(river_bed_height[i]),
            float(river_bed_height[i + 1]),
            _maxd(float(water_depth[i]), 0.0),
            _maxd(float(water_depth[i + 1]), 0.0),
            float(S[i]),
            float(S[i + 1]),
            float(Q[i]),
            float(Q[i + 1]),
        )
        if bool(river.positivity_flux_control) and fabs(flux0) > tiny and dt > 0.0:
            donor = -1
            if flux0 > 0.0 and 1 <= i <= cell_num:
                donor = i
            elif flux0 < 0.0 and 1 <= i + 1 <= cell_num:
                donor = i + 1
            if donor >= 0:
                available = _maxd(float(S[donor]), 0.0) * _maxd(float(cell_lengths[donor]), tiny)
                max_flux = available / _maxd(dt, tiny)
                if max_flux < fabs(flux0):
                    scale = max_flux / _maxd(fabs(flux0), tiny)
                    flux0 *= scale
                    flux1 *= scale
        Flux_LOC[i, 0] = flux0
        Flux_LOC[i, 1] = flux1
        Flux_Source_right[i, 1] = float(PRESS[i]) - p_left_hr
        Flux_Source_left[i + 1, 1] = -(float(PRESS[i + 1]) - p_right_hr)

    for j in range(1, cell_num + 1):
        rain_half = -0.5 * float(cell_lengths[j]) * float(QIN[j])
        Flux_Source_left[j, 0] += rain_half
        Flux_Source_right[j, 0] += rain_half
    return True


cdef class CppUpdateCellPlan:
    cdef vector[TableView] _views
    cdef Py_ssize_t _size

    def __cinit__(self, object tables):
        cdef Py_ssize_t i, n = len(tables)
        cdef CrossSectionTableCython tbl
        cdef TableView view
        self._size = n
        self._views.reserve(<size_t>n)
        for i in range(n):
            tbl = <CrossSectionTableCython>tables[i]
            view.area_axis = &tbl._area_axis_mv[0]
            view.depth_a = &tbl._depth_a_mv[0]
            view.level_a = &tbl._level_a_mv[0]
            view.DEB_a = &tbl._DEB_a_mv[0]
            view.width_a = &tbl._width_a_mv[0]
            view.wetted_a = &tbl._wetted_a_mv[0]
            view.press_a = &tbl._press_a_mv[0]
            if tbl._area_axis_wet_mv.shape[0] > 0:
                view.area_axis_wet = &tbl._area_axis_wet_mv[0]
                view.width_a_wet = &tbl._width_a_wet_mv[0]
            else:
                view.area_axis_wet = NULL
                view.width_a_wet = NULL
            view.depth_axis = &tbl._depth_axis_mv[0]
            view.area_d = &tbl._area_d_mv[0]
            view.area_len = <size_t>tbl._area_axis_mv.shape[0]
            view.wet_len = <size_t>tbl._area_axis_wet_mv.shape[0]
            view.depth_len = <size_t>tbl._depth_axis_mv.shape[0]
            view.bed_level = tbl._bed_level
            self._views.push_back(view)

    cdef const TableView* data(self) noexcept:
        if self._views.size() == 0:
            return NULL
        return &self._views[0]

    cdef size_t size(self) noexcept:
        return self._views.size()


cpdef bint prepare_cpp_update_cell_plan(object river):
    cdef object plan = getattr(river, "_cpp_update_cell_plan", None)
    cdef tuple tables
    if plan is not None and bool(getattr(river, "_cpp_update_cell_ready", False)):
        return True
    if not bool(getattr(river, "_cython_cell_state_ready", False)):
        river._cpp_update_cell_plan = None
        river._cpp_update_cell_ready = False
        return False
    tables = river._cell_section_tables
    if not tables:
        river._cpp_update_cell_plan = None
        river._cpp_update_cell_ready = False
        return False
    river._cpp_update_cell_plan = CppUpdateCellPlan(tables)
    river._cpp_update_cell_ready = True
    return True


cpdef bint update_cell_properties_exact_cpp(object river):
    cdef CppUpdateCellPlan plan
    cdef cnp.ndarray[cnp.float32_t, ndim=1] S_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] Q_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] water_level_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] water_depth_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] U_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] C_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] FR_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] P_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] PRESS_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] R_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] QIN_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] cell_s_limit_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] cell_bed_arr
    cdef cnp.ndarray[cnp.uint8_t, ndim=1] forced_dry_flags
    cdef UpdateCellStats stats
    cdef int near_dry_velocity_mode
    cdef int near_dry_derived_mode

    if not prepare_cpp_update_cell_plan(river):
        return False

    plan = <CppUpdateCellPlan>river._cpp_update_cell_plan
    S_arr = river.S
    Q_arr = river.Q
    water_level_arr = river.water_level
    water_depth_arr = river.water_depth
    U_arr = river.U
    C_arr = river.C
    FR_arr = river.FR
    P_arr = river.P
    PRESS_arr = river.PRESS
    R_arr = river.R
    QIN_arr = river.QIN
    cell_s_limit_arr = river._cell_s_limit_arr
    cell_bed_arr = river._cell_bed_level_arr
    forced_dry_flags = river._forced_dry_recorded.view(np.uint8)

    if river.near_dry_velocity_cutoff_mode == "zero_q":
        near_dry_velocity_mode = 0
    else:
        near_dry_velocity_mode = 1

    if river.near_dry_derived_mode == "floor_u_and_c":
        near_dry_derived_mode = 0
    elif river.near_dry_derived_mode == "actual_u_floor_c":
        near_dry_derived_mode = 1
    elif river.near_dry_derived_mode == "actual_u_soft_floor_c":
        near_dry_derived_mode = 2
    else:
        near_dry_derived_mode = 3

    stats = update_cell_properties_exact_cpp_kernel(
        plan.data(),
        plan.size(),
        &S_arr[0],
        &Q_arr[0],
        &water_level_arr[0],
        &water_depth_arr[0],
        &U_arr[0],
        &C_arr[0],
        &FR_arr[0],
        &P_arr[0],
        &PRESS_arr[0],
        &R_arr[0],
        &QIN_arr[0],
        &cell_s_limit_arr[0],
        &cell_bed_arr[0],
        &forced_dry_flags[0],
        float(river.g),
        float(river.EPSILON),
        float(river.water_depth_limit),
        float(river.velocity_depth_limit),
        1 if bool(river.fix_02_preserve_true_width) else 0,
        near_dry_velocity_mode,
        near_dry_derived_mode,
    )
    river.current_forced_dry_count += int(stats.forced_dry_increment)
    river.total_forced_dry_count += int(stats.forced_dry_increment)
    return True


cpdef bint assemble_flux_poststep_exact_cpp(object river):
    cdef CppUpdateCellPlan plan
    cdef cnp.ndarray[cnp.float32_t, ndim=1] S_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] Q_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] water_depth_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] cell_s_limit_arr
    cdef cnp.ndarray[cnp.uint8_t, ndim=1] forced_dry_flags
    cdef AssemblePostStepStats stats

    if not bool(getattr(river, "FRTIMP", False)):
        return False
    if str(getattr(river, "friction_model", "manning")).lower() != "manning":
        return False
    if not prepare_cpp_update_cell_plan(river):
        return False

    plan = <CppUpdateCellPlan>river._cpp_update_cell_plan
    S_arr = river.S[1:river.cell_num + 1]
    Q_arr = river.Q[1:river.cell_num + 1]
    water_depth_arr = river.water_depth[1:river.cell_num + 1]
    cell_s_limit_arr = river._cell_s_limit_arr[1:river.cell_num + 1]
    forced_dry_flags = river._forced_dry_recorded[1:river.cell_num + 1].view(np.uint8)

    stats = apply_explicit_manning_poststep_exact_cpp_kernel(
        plan.data() + 1,
        river.cell_num,
        &S_arr[0],
        &Q_arr[0],
        &water_depth_arr[0],
        &cell_s_limit_arr[0],
        &forced_dry_flags[0],
        float(river.g),
        float(river.DT),
        float(river.EPSILON),
        float(river.water_depth_limit),
        float(getattr(river, "friction_min_depth", 0.0)),
    )
    river.current_forced_dry_count += int(stats.forced_dry_increment)
    river.total_forced_dry_count += int(stats.forced_dry_increment)
    return True


cpdef bint roe_matrix_exact_cpp(object river):
    cdef cnp.ndarray[cnp.float32_t, ndim=1] F_C_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] F_U_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] BETA_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] FR_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] water_depth_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] U_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] C_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] S_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] Q_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] flag_LeVeque_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] abs_Lambda1_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] abs_Lambda2_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] alpha1_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] alpha2_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] Lambda1_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] Lambda2_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=2] Vactor1_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=2] Vactor2_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=2] Vactor1_T_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=2] Vactor2_T_arr
    cdef RoeMatrixStats stats
    cdef int N

    N = int(river.cell_num) + 1
    if N <= 0:
        river.current_interface_counts = {
            'supercritical_pos': 0,
            'supercritical_neg': 0,
            'subcritical': 0,
        }
        river.current_leveque_count = 0
        return True

    F_C_arr = river.F_C
    F_U_arr = river.F_U
    BETA_arr = river.BETA
    FR_arr = river.FR
    water_depth_arr = river.water_depth
    U_arr = river.U
    C_arr = river.C
    S_arr = river.S
    Q_arr = river.Q
    flag_LeVeque_arr = river.flag_LeVeque
    abs_Lambda1_arr = river.abs_Lambda1
    abs_Lambda2_arr = river.abs_Lambda2
    alpha1_arr = river.alpha1
    alpha2_arr = river.alpha2
    Lambda1_arr = river.Lambda1
    Lambda2_arr = river.Lambda2
    Vactor1_arr = river.Vactor1
    Vactor2_arr = river.Vactor2
    Vactor1_T_arr = river.Vactor1_T
    Vactor2_T_arr = river.Vactor2_T

    stats = compute_roe_matrix_exact_cpp_kernel(
        <size_t>N,
        <float>float(river.EPSILON),
        <float>float(river.water_depth_limit),
        &F_C_arr[0],
        &F_U_arr[0],
        &BETA_arr[0],
        &FR_arr[0],
        &water_depth_arr[0],
        &U_arr[0],
        &C_arr[0],
        &S_arr[0],
        &Q_arr[0],
        &flag_LeVeque_arr[0],
        &abs_Lambda1_arr[0],
        &abs_Lambda2_arr[0],
        &alpha1_arr[0],
        &alpha2_arr[0],
        &Lambda1_arr[0],
        &Lambda2_arr[0],
        &Vactor1_arr[0, 0],
        &Vactor2_arr[0, 0],
        &Vactor1_T_arr[0, 0],
        &Vactor2_T_arr[0, 0],
    )

    river.current_interface_counts = {
        'supercritical_pos': int(stats.supercritical_pos),
        'supercritical_neg': int(stats.supercritical_neg),
        'subcritical': int(stats.subcritical),
    }
    river.current_leveque_count = int(stats.leveque_count)
    river.total_leveque_count += int(stats.leveque_count)
    river.lambda_range_current = {
        'lambda1_min': float(stats.lambda1_min),
        'lambda1_max': float(stats.lambda1_max),
        'lambda2_min': float(stats.lambda2_min),
        'lambda2_max': float(stats.lambda2_max),
    }
    return True


cpdef bint face_uc_exact_cpp(object river):
    cdef cnp.ndarray[cnp.float32_t, ndim=1] S_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] U_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] C_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] PRESS_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] F_U_arr
    cdef cnp.ndarray[cnp.float32_t, ndim=1] F_C_arr
    cdef cnp.ndarray[cnp.float64_t, ndim=1] cell_s_limit_arr
    cdef int N

    N = int(river.cell_num) + 1
    if N <= 0:
        return True

    S_arr = river.S
    U_arr = river.U
    C_arr = river.C
    PRESS_arr = river.PRESS
    F_U_arr = river.F_U
    F_C_arr = river.F_C
    cell_s_limit_arr = river._cell_s_limit_arr

    compute_face_uc_exact_cpp_kernel(
        <size_t>N,
        float(river.EPSILON),
        float(river.S_limit),
        1 if bool(river.fix_06_section_area_threshold) else 0,
        &S_arr[0],
        &U_arr[0],
        &C_arr[0],
        &PRESS_arr[0],
        &cell_s_limit_arr[0],
        &F_U_arr[0],
        &F_C_arr[0],
    )
    return True


cpdef bint update_cell_properties_exact(object river):
    cdef Py_ssize_t i, n
    cdef tuple cell_tables
    cdef object tbl
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
    cdef cnp.float32_t[:] QIN
    cdef double[:] cell_s_limit
    cdef double[:] cell_bed
    cdef double prev_s, prev_depth, area_i, level_i, depth_i, width_i
    cdef double area_actual, depth_actual, depth_floor, area_floor, width_floor
    cdef double final_area
    cdef double eps = float(river.EPSILON)
    cdef double water_depth_limit = float(river.water_depth_limit)
    cdef double velocity_depth_limit = float(river.velocity_depth_limit)
    cdef double g = float(river.g)
    cdef object near_dry_velocity_cutoff_mode = river.near_dry_velocity_cutoff_mode
    cdef object near_dry_derived_mode = river.near_dry_derived_mode
    cdef bint preserve_true_width = bool(river.fix_02_preserve_true_width)

    if not bool(getattr(river, "_cython_cell_state_ready", False)):
        return False

    cell_tables = river._cell_section_tables
    S = river.S
    Q = river.Q
    water_level = river.water_level
    water_depth = river.water_depth
    U = river.U
    C = river.C
    FR = river.FR
    P = river.P
    PRESS = river.PRESS
    R = river.R
    QIN = river.QIN
    cell_s_limit = river._cell_s_limit_arr
    cell_bed = river._cell_bed_level_arr
    n = int(river.cell_num) + 2

    for i in range(n):
        tbl = cell_tables[i]
        prev_s = float(S[i])
        prev_depth = float(water_depth[i])
        area_i = _maxd(float(S[i]), 0.0)
        S[i] = area_i
        level_i = float(tbl.get_level_by_area(area_i))
        water_level[i] = level_i
        depth_i = _maxd(level_i - float(cell_bed[i]), 0.0)
        water_depth[i] = depth_i

        if area_i <= float(cell_s_limit[i]) or (
            depth_i <= water_depth_limit
            and fabs(float(Q[i])) <= float(cell_s_limit[i]) * sqrt(g * _maxd(depth_i, _maxd(water_depth_limit, eps)))
        ):
            river._apply_conservative_dry_guard(i, prev_s=prev_s, prev_depth=prev_depth)
            water_depth[i] = 0.0
            water_level[i] = float(cell_bed[i])
            U[i] = 0.0
            C[i] = eps
            FR[i] = 0.0
        else:
            if depth_i <= velocity_depth_limit:
                if near_dry_velocity_cutoff_mode == "zero_q":
                    Q[i] = 0.0
                    U[i] = 0.0
                    C[i] = eps
                    FR[i] = 0.0
                else:
                    depth_actual = _maxd(depth_i, _maxd(water_depth_limit, eps))
                    area_actual = _maxd(area_i, _maxd(float(cell_s_limit[i]), eps))
                    depth_floor = _maxd(velocity_depth_limit, water_depth_limit)
                    if near_dry_derived_mode == "actual_u_soft_floor_c":
                        depth_floor = _maxd(
                            depth_actual,
                            sqrt(_maxd(water_depth_limit, eps) * depth_floor),
                        )
                    elif near_dry_derived_mode == "actual_u_waterdepth_floor_c":
                        depth_floor = _maxd(depth_actual, _maxd(water_depth_limit, eps))
                    area_floor = _maxd(
                        area_actual,
                        _maxd(float(tbl.get_area_by_depth(depth_floor)), _maxd(float(cell_s_limit[i]), eps)),
                    )
                    width_floor = _resolve_width_exact(
                        tbl,
                        area_floor,
                        depth_floor,
                        eps,
                        water_depth_limit,
                        preserve_true_width,
                    )
                    if near_dry_derived_mode == "floor_u_and_c":
                        U[i] = float(Q[i]) / area_floor
                    else:
                        U[i] = float(Q[i]) / area_actual
                    C[i] = sqrt(g * area_floor / width_floor)
                    FR[i] = fabs(float(U[i])) / _maxd(float(C[i]), eps)
            else:
                U[i] = float(Q[i]) / area_i
                width_i = _resolve_width_exact(
                    tbl,
                    area_i,
                    depth_i,
                    eps,
                    water_depth_limit,
                    preserve_true_width,
                )
                C[i] = sqrt(g * area_i / width_i)
                FR[i] = fabs(float(U[i])) / _maxd(float(C[i]), eps)

        final_area = float(S[i])
        P[i] = float(tbl.get_wetted_perimeter_by_area(final_area))
        PRESS[i] = float(tbl.get_press_by_area(final_area))
        R[i] = float(tbl.get_hydraulic_radius_by_area(final_area))
        QIN[i] = 0.0
    return True

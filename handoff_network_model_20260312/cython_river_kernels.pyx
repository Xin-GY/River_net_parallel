# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

from libc.math cimport fabs, sqrt

cimport numpy as cnp

from cython_cross_section import compute_general_hr_flux_interface


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

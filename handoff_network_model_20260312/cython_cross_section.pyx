# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

import numpy as np
cimport cython
cimport numpy as cnp
from libc.math cimport sqrt, isnan, fabs


cdef inline Py_ssize_t _find_exact(double x, double[:] axis) noexcept:
    cdef Py_ssize_t i, n = axis.shape[0]
    for i in range(n):
        if axis[i] == x:
            return i
    return -1


cdef inline double _interp_sorted(double x, double[:] xp, double[:] fp) noexcept:
    cdef Py_ssize_t n = xp.shape[0]
    cdef Py_ssize_t lo = 0
    cdef Py_ssize_t hi = n - 1
    cdef Py_ssize_t mid
    cdef double x0, x1, y0, y1

    if n == 0:
        return 0.0
    if n == 1 or x <= xp[0]:
        return fp[0]
    if x >= xp[n - 1]:
        return fp[n - 1]

    while hi - lo > 1:
        mid = (lo + hi) // 2
        if xp[mid] <= x:
            lo = mid
        else:
            hi = mid

    x0 = xp[lo]
    x1 = xp[lo + 1]
    y0 = fp[lo]
    y1 = fp[lo + 1]
    if x1 == x0:
        return y1
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


cdef inline double _roe_abs_with_fix_cython(double lam, double c, double roe_entropy_fix, double roe_entropy_fix_factor) noexcept:
    cdef double delta = roe_entropy_fix
    cdef double aval = fabs(lam)
    cdef double cabs = c if c >= 0.0 else -c
    cdef double scaled = roe_entropy_fix_factor * cabs
    if scaled > delta:
        delta = scaled
    if delta <= 0.0 or aval >= delta:
        return aval
    return 0.5 * (lam * lam / delta + delta)



cdef class CrossSectionTableCython:
    cdef public object _depth_axis
    cdef public object _area_d
    cdef public object _level_axis
    cdef public object _area_l
    cdef public object _area_axis
    cdef public object _depth_a
    cdef public object _level_a
    cdef public object _DEB_a
    cdef public object _width_a
    cdef public object _wetted_a
    cdef public object _hradius_a
    cdef public object _press_a
    cdef public object _area_axis_wet
    cdef public object _width_a_wet
    cdef object _chi_area_axis
    cdef object _chi_axis

    cdef double[:] _depth_axis_mv
    cdef double[:] _area_d_mv
    cdef double[:] _level_axis_mv
    cdef double[:] _area_l_mv
    cdef double[:] _area_axis_mv
    cdef double[:] _depth_a_mv
    cdef double[:] _level_a_mv
    cdef double[:] _DEB_a_mv
    cdef double[:] _width_a_mv
    cdef double[:] _wetted_a_mv
    cdef double[:] _hradius_a_mv
    cdef double[:] _press_a_mv
    cdef double[:] _area_axis_wet_mv
    cdef double[:] _width_a_wet_mv
    cdef double[:] _chi_area_axis_mv
    cdef double[:] _chi_axis_mv

    cdef double _bed_level
    cdef double _top_level
    cdef double _min_depth
    cdef double _max_depth
    cdef bint _chi_cache_ready
    cdef double _chi_cache_g
    cdef double _chi_cache_tinyA
    cdef double _chi_cache_tinyT
    cdef double _chi_A0
    cdef double _chi_Amax
    cdef double _chi_w0
    cdef double _chi_max
    cdef double _chi_kmax

    def __init__(self, depths, levels, areas, widths, wetted_perimeters, hydraulic_radii, presses, DEBs):
        cdef cnp.ndarray[cnp.float64_t, ndim=1] depths_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1] levels_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1] areas_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1] widths_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1] wetted_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1] hradius_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1] presses_arr
        cdef cnp.ndarray[cnp.float64_t, ndim=1] debs_arr
        cdef cnp.ndarray idx
        cdef cnp.ndarray positive_mask

        depths_arr = np.asarray(depths, dtype=np.float64)
        levels_arr = np.asarray(levels, dtype=np.float64)
        areas_arr = np.asarray(areas, dtype=np.float64)
        widths_arr = np.asarray(widths, dtype=np.float64)
        wetted_arr = np.asarray(wetted_perimeters, dtype=np.float64)
        hradius_arr = np.asarray(hydraulic_radii, dtype=np.float64)
        presses_arr = np.asarray(presses, dtype=np.float64)
        debs_arr = np.asarray(DEBs, dtype=np.float64)

        idx = np.argsort(depths_arr)
        self._depth_axis = np.ascontiguousarray(depths_arr[idx], dtype=np.float64)
        self._area_d = np.ascontiguousarray(areas_arr[idx], dtype=np.float64)

        idx = np.argsort(levels_arr)
        self._level_axis = np.ascontiguousarray(levels_arr[idx], dtype=np.float64)
        self._area_l = np.ascontiguousarray(areas_arr[idx], dtype=np.float64)

        idx = np.argsort(areas_arr)
        self._area_axis = np.ascontiguousarray(areas_arr[idx], dtype=np.float64)
        self._depth_a = np.ascontiguousarray(depths_arr[idx], dtype=np.float64)
        self._level_a = np.ascontiguousarray(levels_arr[idx], dtype=np.float64)
        self._DEB_a = np.ascontiguousarray(debs_arr[idx], dtype=np.float64)
        self._width_a = np.ascontiguousarray(widths_arr[idx], dtype=np.float64)
        self._wetted_a = np.ascontiguousarray(wetted_arr[idx], dtype=np.float64)
        self._hradius_a = np.ascontiguousarray(hradius_arr[idx], dtype=np.float64)
        self._press_a = np.ascontiguousarray(presses_arr[idx], dtype=np.float64)

        positive_mask = self._area_axis > 0.0
        self._area_axis_wet = np.ascontiguousarray(self._area_axis[positive_mask], dtype=np.float64)
        self._width_a_wet = np.ascontiguousarray(self._width_a[positive_mask], dtype=np.float64)

        self._depth_axis_mv = self._depth_axis
        self._area_d_mv = self._area_d
        self._level_axis_mv = self._level_axis
        self._area_l_mv = self._area_l
        self._area_axis_mv = self._area_axis
        self._depth_a_mv = self._depth_a
        self._level_a_mv = self._level_a
        self._DEB_a_mv = self._DEB_a
        self._width_a_mv = self._width_a
        self._wetted_a_mv = self._wetted_a
        self._hradius_a_mv = self._hradius_a
        self._press_a_mv = self._press_a
        self._area_axis_wet_mv = self._area_axis_wet
        self._width_a_wet_mv = self._width_a_wet
        self._chi_area_axis = None
        self._chi_axis = None
        self._chi_cache_ready = False
        self._chi_cache_g = -1.0
        self._chi_cache_tinyA = -1.0
        self._chi_cache_tinyT = -1.0
        self._chi_A0 = 0.0
        self._chi_Amax = 0.0
        self._chi_w0 = 0.0
        self._chi_max = 0.0
        self._chi_kmax = 0.0

        self._bed_level = float(self._level_axis_mv[0]) if self._level_axis_mv.shape[0] else 0.0
        self._top_level = float(self._level_axis_mv[self._level_axis_mv.shape[0] - 1]) if self._level_axis_mv.shape[0] else 0.0
        self._min_depth = float(self._depth_axis_mv[0]) if self._depth_axis_mv.shape[0] else 0.0
        self._max_depth = float(self._depth_axis_mv[self._depth_axis_mv.shape[0] - 1]) if self._depth_axis_mv.shape[0] else 0.0

    def __reduce__(self):
        return (
            CrossSectionTableCython,
            (
                np.asarray(self._depth_a),
                np.asarray(self._level_a),
                np.asarray(self._area_axis),
                np.asarray(self._width_a),
                np.asarray(self._wetted_a),
                np.asarray(self._hradius_a),
                np.asarray(self._press_a),
                np.asarray(self._DEB_a),
            ),
        )

    cpdef object get_area_by_depth(self, double depth, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(depth, self._depth_axis_mv)
            if idx < 0:
                return None
            return float(self._area_d_mv[idx])
        return float(_interp_sorted(depth, self._depth_axis_mv, self._area_d_mv))

    cpdef object get_area_by_level(self, double level, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(level, self._level_axis_mv)
            if idx < 0:
                return None
            return float(self._area_l_mv[idx])
        return float(_interp_sorted(level, self._level_axis_mv, self._area_l_mv))

    cpdef object get_level_by_area(self, double area, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(area, self._area_axis_mv)
            if idx < 0:
                return None
            return float(self._level_a_mv[idx])
        return float(_interp_sorted(area, self._area_axis_mv, self._level_a_mv))

    cpdef object get_DEB_by_area(self, double area, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(area, self._area_axis_mv)
            if idx < 0:
                return None
            return float(self._DEB_a_mv[idx])
        return float(_interp_sorted(area, self._area_axis_mv, self._DEB_a_mv))

    cpdef object get_depth_by_area(self, double area, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(area, self._area_axis_mv)
            if idx < 0:
                return None
            return float(self._depth_a_mv[idx])
        return float(_interp_sorted(area, self._area_axis_mv, self._depth_a_mv))

    cpdef object get_width_by_area(self, double area, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(area, self._area_axis_mv)
            if idx < 0:
                return None
            return float(self._width_a_mv[idx])
        if area <= 0.0:
            return 0.0
        if self._area_axis_wet_mv.shape[0] > 0:
            return float(_interp_sorted(area, self._area_axis_wet_mv, self._width_a_wet_mv))
        return float(_interp_sorted(area, self._area_axis_mv, self._width_a_mv))

    cpdef object get_wetted_perimeter_by_area(self, double area, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(area, self._area_axis_mv)
            if idx < 0:
                return None
            return float(self._wetted_a_mv[idx])
        return float(_interp_sorted(area, self._area_axis_mv, self._wetted_a_mv))

    cpdef object get_hydraulic_radius_by_area(self, double area, method='interp'):
        cdef Py_ssize_t idx
        cdef double wetted
        if method == 'exact':
            idx = _find_exact(area, self._area_axis_mv)
            if idx < 0:
                return None
            wetted = float(self._wetted_a_mv[idx])
            area = float(self._area_axis_mv[idx])
            if wetted <= 0.0:
                return 0.0
            return float(area / wetted)
        if area <= 0.0:
            return 0.0
        wetted = _interp_sorted(area, self._area_axis_mv, self._wetted_a_mv)
        if wetted <= 0.0 or isnan(wetted):
            return 1e-07
        return float(area / wetted)

    cpdef object get_press_by_area(self, double area, method='interp'):
        cdef Py_ssize_t idx
        if method == 'exact':
            idx = _find_exact(area, self._area_axis_mv)
            if idx < 0:
                return None
            return float(self._press_a_mv[idx])
        return float(_interp_sorted(area, self._area_axis_mv, self._press_a_mv))

    cdef void _ensure_general_chi_cache(self, double g, double tinyA, double tinyT):
        cdef cnp.ndarray area_axis
        cdef cnp.ndarray width_axis
        cdef cnp.ndarray integrand
        cdef cnp.ndarray chi_axis
        cdef Py_ssize_t i, n
        cdef double area
        cdef double width

        if (
            self._chi_cache_ready
            and self._chi_cache_g == g
            and self._chi_cache_tinyA == tinyA
            and self._chi_cache_tinyT == tinyT
        ):
            return

        area_axis = np.unique(np.asarray(self._area_axis, dtype=np.float64))
        area_axis = area_axis[np.isfinite(area_axis)]
        area_axis = area_axis[area_axis > tinyA]
        if area_axis.size == 0:
            self._chi_cache_ready = False
            self._chi_area_axis = None
            self._chi_axis = None
            return

        n = area_axis.shape[0]
        width_axis = np.empty(n, dtype=np.float64)
        for i in range(n):
            area = float(area_axis[i])
            width = float(self.get_width_by_area(area))
            if width < tinyT:
                width = tinyT
            width_axis[i] = width

        integrand = np.sqrt(g * area_axis / width_axis) / np.maximum(area_axis, tinyA)
        chi_axis = np.zeros_like(area_axis)
        if n > 1:
            chi_axis[1:] = np.cumsum(0.5 * (integrand[1:] + integrand[:-1]) * np.diff(area_axis))
        chi_axis = chi_axis + 2.0 * np.sqrt(g * area_axis[0] / width_axis[0])

        self._chi_area_axis = np.ascontiguousarray(area_axis, dtype=np.float64)
        self._chi_axis = np.ascontiguousarray(chi_axis, dtype=np.float64)
        self._chi_area_axis_mv = self._chi_area_axis
        self._chi_axis_mv = self._chi_axis
        self._chi_cache_ready = True
        self._chi_cache_g = g
        self._chi_cache_tinyA = tinyA
        self._chi_cache_tinyT = tinyT
        self._chi_A0 = float(self._chi_area_axis_mv[0])
        self._chi_Amax = float(self._chi_area_axis_mv[self._chi_area_axis_mv.shape[0] - 1])
        self._chi_w0 = float(width_axis[0])
        self._chi_max = float(self._chi_axis_mv[self._chi_axis_mv.shape[0] - 1])
        self._chi_kmax = float(integrand[n - 1])

    cpdef double get_general_chi_by_area(self, double area, double g, double tinyA=1e-12, double tinyT=1e-08):
        cdef double A
        cdef double width
        A = area if area > tinyA else tinyA
        self._ensure_general_chi_cache(g, tinyA, tinyT)
        if not self._chi_cache_ready:
            width = float(self.get_width_by_area(A))
            if width < tinyT:
                width = tinyT
            return 2.0 * sqrt(g * A / width)
        if A <= self._chi_A0:
            return 2.0 * sqrt(g * A / self._chi_w0)
        if A >= self._chi_Amax:
            return self._chi_max + self._chi_kmax * (A - self._chi_Amax)
        return _interp_sorted(A, self._chi_area_axis_mv, self._chi_axis_mv)

    cpdef tuple get_char_triplet_by_area(self, double area, double g, double tinyA=1e-12, double tinyT=1e-08):
        cdef double A
        cdef double width
        cdef double depth
        cdef double width_chi
        cdef double general_chi
        cdef double depth_ref_chi
        A = area if area > tinyA else tinyA
        width = float(self.get_width_by_area(A))
        if width < tinyT:
            width = tinyT
        depth = float(self.get_depth_by_area(A))
        if depth < 0.0:
            depth = 0.0
        width_chi = 2.0 * sqrt(g * A / width)
        general_chi = self.get_general_chi_by_area(A, g, tinyA=tinyA, tinyT=tinyT)
        depth_ref_chi = 2.0 * sqrt(g * depth)
        return (width_chi, general_chi, depth_ref_chi)

    cpdef double get_bed_level(self):
        return self._bed_level

    cpdef double get_top_level(self):
        return self._top_level

    cpdef double get_max_depth(self):
        return self._max_depth

    cpdef object get_value_by_area(self, double area, value_name, method='interp'):
        cdef double[:] axis
        cdef double[:] values
        cdef Py_ssize_t idx

        if value_name == 'depth':
            axis = self._area_axis_mv
            values = self._depth_a_mv
        elif value_name == 'level':
            axis = self._area_axis_mv
            values = self._level_a_mv
        elif value_name == 'area':
            axis = self._area_axis_mv
            values = self._area_axis_mv
        elif value_name == 'DEB':
            axis = self._area_axis_mv
            values = self._DEB_a_mv
        elif value_name == 'width':
            axis = self._area_axis_mv
            values = self._width_a_mv
        elif value_name == 'wetted_perimeter':
            axis = self._area_axis_mv
            values = self._wetted_a_mv
        elif value_name == 'hydraulic_radius':
            axis = self._area_axis_mv
            values = self._hradius_a_mv
        elif value_name == 'press':
            axis = self._area_axis_mv
            values = self._press_a_mv
        else:
            raise KeyError(f"No field named '{value_name}'")

        if method == 'exact':
            idx = _find_exact(area, axis)
            if idx < 0:
                return None
            return float(values[idx])
        return float(_interp_sorted(area, axis, values))


cpdef tuple compute_general_hr_flux_interface(
    CrossSectionTableCython left_tbl,
    CrossSectionTableCython right_tbl,
    double g,
    double tiny,
    double roe_entropy_fix,
    double roe_entropy_fix_factor,
    double z_left,
    double z_right,
    double h_left,
    double h_right,
    double area_left_center,
    double area_right_center,
    double q_left_center,
    double q_right_center,
):
    cdef double eta_left
    cdef double eta_right
    cdef double u_left
    cdef double u_right
    cdef double z_face
    cdef double h_left_hr
    cdef double h_right_hr
    cdef double a_left
    cdef double a_right
    cdef double p_left_hr
    cdef double p_right_hr
    cdef double q_left
    cdef double q_right
    cdef double f_left0
    cdef double f_left1
    cdef double f_right0
    cdef double f_right1
    cdef double t_left
    cdef double t_right
    cdef double c_left
    cdef double c_right
    cdef double s_left
    cdef double s_right
    cdef double sqrt_al
    cdef double sqrt_ar
    cdef double denom
    cdef double u_roe
    cdef double c_roe
    cdef double da
    cdef double dq
    cdef double alpha1
    cdef double alpha2
    cdef double lam1
    cdef double lam2
    cdef double abs1
    cdef double abs2
    cdef double flux0
    cdef double flux1

    if h_left < 0.0:
        h_left = 0.0
    if h_right < 0.0:
        h_right = 0.0

    eta_left = z_left + h_left
    eta_right = z_right + h_right
    if area_left_center > tiny and h_left > tiny:
        u_left = q_left_center / area_left_center
    else:
        u_left = 0.0
    if area_right_center > tiny and h_right > tiny:
        u_right = q_right_center / area_right_center
    else:
        u_right = 0.0

    z_face = z_left if z_left >= z_right else z_right
    h_left_hr = eta_left - z_face
    h_right_hr = eta_right - z_face
    if h_left_hr < 0.0:
        h_left_hr = 0.0
    if h_right_hr < 0.0:
        h_right_hr = 0.0

    a_left = float(left_tbl.get_area_by_depth(h_left_hr))
    a_right = float(right_tbl.get_area_by_depth(h_right_hr))
    p_left_hr = float(left_tbl.get_press_by_area(a_left))
    p_right_hr = float(right_tbl.get_press_by_area(a_right))
    q_left = a_left * u_left
    q_right = a_right * u_right
    f_left0 = q_left
    f_left1 = q_left * u_left + p_left_hr
    f_right0 = q_right
    f_right1 = q_right * u_right + p_right_hr

    if a_left <= tiny and a_right <= tiny:
        return (0.0, 0.0, p_left_hr, p_right_hr)

    t_left = float(left_tbl.get_width_by_area(a_left if a_left > tiny else tiny))
    t_right = float(right_tbl.get_width_by_area(a_right if a_right > tiny else tiny))
    if t_left < tiny:
        t_left = tiny
    if t_right < tiny:
        t_right = tiny
    c_left = sqrt(g * a_left / t_left) if a_left > tiny else 0.0
    c_right = sqrt(g * a_right / t_right) if a_right > tiny else 0.0
    s_left = u_left - c_left
    if u_right - c_right < s_left:
        s_left = u_right - c_right
    s_right = u_left + c_left
    if u_right + c_right > s_right:
        s_right = u_right + c_right

    if a_left > tiny and a_right > tiny:
        sqrt_al = sqrt(a_left if a_left > 0.0 else 0.0)
        sqrt_ar = sqrt(a_right if a_right > 0.0 else 0.0)
        denom = sqrt_al + sqrt_ar
        if denom <= tiny:
            u_roe = 0.0
        else:
            u_roe = (u_left * sqrt_al + u_right * sqrt_ar) / denom
        if fabs(a_right - a_left) > tiny:
            c_roe = sqrt((p_right_hr - p_left_hr) / (a_right - a_left)) if (p_right_hr - p_left_hr) / (a_right - a_left) > 0.0 else 0.0
        else:
            c_roe = 0.5 * (c_left + c_right)
        if c_roe <= tiny:
            flux0 = 0.5 * (f_left0 + f_right0)
            flux1 = 0.5 * (f_left1 + f_right1)
        else:
            da = a_right - a_left
            dq = q_right - q_left
            alpha1 = ((u_roe + c_roe) * da - dq) / (2.0 * c_roe)
            alpha2 = (dq - (u_roe - c_roe) * da) / (2.0 * c_roe)
            lam1 = u_roe - c_roe
            lam2 = u_roe + c_roe
            abs1 = _roe_abs_with_fix_cython(lam1, c_roe, roe_entropy_fix, roe_entropy_fix_factor)
            abs2 = _roe_abs_with_fix_cython(lam2, c_roe, roe_entropy_fix, roe_entropy_fix_factor)
            flux0 = 0.5 * (f_left0 + f_right0) - 0.5 * (abs1 * alpha1 + abs2 * alpha2)
            flux1 = 0.5 * (f_left1 + f_right1) - 0.5 * (abs1 * alpha1 * (u_roe - c_roe) + abs2 * alpha2 * (u_roe + c_roe))
    elif s_left >= 0.0:
        flux0 = f_left0
        flux1 = f_left1
    elif s_right <= 0.0:
        flux0 = f_right0
        flux1 = f_right1
    elif s_right - s_left <= tiny:
        flux0 = 0.0
        flux1 = 0.0
    else:
        flux0 = (s_right * f_left0 - s_left * f_right0 + s_left * s_right * (a_right - a_left)) / (s_right - s_left)
        flux1 = (s_right * f_left1 - s_left * f_right1 + s_left * s_right * (q_right - q_left)) / (s_right - s_left)
    return (flux0, flux1, p_left_hr, p_right_hr)

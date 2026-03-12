# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True

import numpy as np
cimport cython
cimport numpy as cnp
from libc.math cimport sqrt, isnan


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

    cdef double _bed_level
    cdef double _top_level
    cdef double _min_depth
    cdef double _max_depth

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

cimport numpy as cnp


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
    cdef object _stage_width_l
    cdef object _stage_depth_l
    cdef object _stage_general_chi_l

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
    cdef double[:] _stage_width_l_mv
    cdef double[:] _stage_depth_l_mv
    cdef double[:] _stage_general_chi_l_mv

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
    cdef bint _stage_target_cache_ready
    cdef double _stage_target_cache_g
    cdef double _stage_target_cache_tinyA
    cdef double _stage_target_cache_tinyT

    cpdef object get_area_by_depth(self, double depth, method=*)
    cpdef object get_area_by_level(self, double level, method=*)
    cpdef object get_level_by_area(self, double area, method=*)
    cpdef object get_DEB_by_area(self, double area, method=*)
    cpdef object get_depth_by_area(self, double area, method=*)
    cpdef object get_width_by_area(self, double area, method=*)
    cpdef object get_wetted_perimeter_by_area(self, double area, method=*)
    cpdef object get_hydraulic_radius_by_area(self, double area, method=*)
    cpdef object get_press_by_area(self, double area, method=*)
    cdef void _ensure_general_chi_cache(self, double g, double tinyA, double tinyT)
    cdef void _ensure_stage_target_cache(self, double g, double tinyA, double tinyT)
    cpdef double get_general_chi_by_area(self, double area, double g, double tinyA=*, double tinyT=*)
    cpdef ensure_stage_target_bundle_cache(self, double g, double tinyA=*, double tinyT=*)
    cpdef tuple get_char_triplet_by_area(self, double area, double g, double tinyA=*, double tinyT=*)
    cpdef tuple get_stage_target_bundle_by_level(self, double level, double g, double tinyA=*, double tinyT=*)
    cpdef double get_bed_level(self)
    cpdef double get_top_level(self)
    cpdef double get_max_depth(self)
    cpdef object get_value_by_area(self, double area, value_name, method=*)

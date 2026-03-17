#pragma once

#include <cstddef>
#include <cstdint>

namespace rivernet {

struct TableView {
    const double* area_axis;
    const double* depth_a;
    const double* level_a;
    const double* DEB_a;
    const double* width_a;
    const double* wetted_a;
    const double* press_a;
    const double* area_axis_wet;
    const double* width_a_wet;
    const double* depth_axis;
    const double* area_d;
    std::size_t area_len;
    std::size_t wet_len;
    std::size_t depth_len;
    double bed_level;
};

struct UpdateCellStats {
    std::size_t forced_dry_increment;
};

struct AssemblePostStepStats {
    std::size_t forced_dry_increment;
};

struct RoeMatrixStats {
    std::size_t supercritical_pos;
    std::size_t supercritical_neg;
    std::size_t subcritical;
    std::size_t leveque_count;
    float lambda1_min;
    float lambda1_max;
    float lambda2_min;
    float lambda2_max;
};

enum NearDryVelocityMode : int {
    ZERO_Q = 0,
    PRESERVE_Q_FLOOR_DERIVED = 1,
};

enum NearDryDerivedMode : int {
    FLOOR_U_AND_C = 0,
    ACTUAL_U_FLOOR_C = 1,
    ACTUAL_U_SOFT_FLOOR_C = 2,
    ACTUAL_U_WATERDEPTH_FLOOR_C = 3,
};

UpdateCellStats update_cell_properties_exact(
    const TableView* tables,
    std::size_t n,
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
    std::uint8_t* forced_dry_recorded,
    double g,
    double eps,
    double water_depth_limit,
    double velocity_depth_limit,
    int preserve_true_width,
    int near_dry_velocity_mode,
    int near_dry_derived_mode
);

AssemblePostStepStats apply_explicit_manning_poststep_exact(
    const TableView* tables,
    std::size_t n,
    float* S,
    float* Q,
    const double* water_depth,
    const double* cell_s_limit,
    std::uint8_t* forced_dry_recorded,
    double g,
    double dt,
    double eps,
    double water_depth_limit,
    double friction_min_depth
);

AssemblePostStepStats assemble_flux_exact_deep(
    const TableView* tables,
    std::size_t n,
    const double* flux_loc,
    const double* flux_source_left,
    const double* flux_source_right,
    const double* flux_source_center,
    const double* flux_friction_left,
    const double* flux_friction_right,
    double* flux,
    float* S,
    float* Q,
    const double* water_depth,
    const double* cell_s_limit,
    std::uint8_t* forced_dry_recorded,
    const float* cell_lengths,
    double g,
    double dt,
    double eps,
    double water_depth_limit,
    double friction_min_depth
);

RoeMatrixStats compute_roe_matrix_exact(
    std::size_t n,
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
    double* Vactor2_T
);

void compute_face_uc_exact(
    std::size_t n,
    double eps,
    double s_limit_default,
    int use_section_area_threshold,
    const float* S,
    const float* U,
    const float* C,
    const float* PRESS,
    const double* cell_s_limit,
    float* F_U,
    float* F_C
);

void fill_general_hr_flux_exact_deep(
    const TableView* left_tables,
    const TableView* right_tables,
    std::size_t n,
    double g,
    double tiny,
    double roe_entropy_fix,
    double roe_entropy_fix_factor,
    const double* river_bed_height,
    const double* water_depth,
    const float* S,
    const float* Q,
    const float* PRESS,
    const float* QIN,
    const double* cell_lengths,
    double dt,
    int cell_num,
    double* flux_loc,
    double* flux_source_left,
    double* flux_source_right
);

void fill_rectangular_hr_flux_exact_deep(
    std::size_t n,
    double g,
    double tiny,
    double width,
    double roe_entropy_fix,
    double roe_entropy_fix_factor,
    const double* river_bed_height,
    const double* water_depth,
    const float* S,
    const float* Q,
    const float* PRESS,
    const float* QIN,
    const float* cell_lengths,
    double* flux_loc,
    double* flux_source_left,
    double* flux_source_right,
    double* flux_source_center,
    double* flux_friction_left,
    double* flux_friction_right,
    double* cell_press_source
);

}  // namespace rivernet

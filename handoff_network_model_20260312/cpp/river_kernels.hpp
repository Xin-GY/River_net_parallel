#pragma once

#include <cstddef>
#include <cstdint>

namespace rivernet {

struct TableView {
    const double* area_axis;
    const double* depth_a;
    const double* level_a;
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

}  // namespace rivernet

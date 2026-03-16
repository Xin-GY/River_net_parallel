#include "river_kernels.hpp"

#include <algorithm>
#include <cmath>

namespace rivernet {

namespace {

inline double max3(double a, double b, double c) noexcept {
    return std::max(a, std::max(b, c));
}

inline double interp_sorted(double x, const double* xp, const double* fp, std::size_t n) noexcept {
    if (n == 0) {
        return 0.0;
    }
    if (n == 1 || x <= xp[0]) {
        return fp[0];
    }
    if (x >= xp[n - 1]) {
        return fp[n - 1];
    }

    std::size_t lo = 0;
    std::size_t hi = n - 1;
    while (hi - lo > 1) {
        const std::size_t mid = (lo + hi) / 2;
        if (xp[mid] <= x) {
            lo = mid;
        } else {
            hi = mid;
        }
    }

    const double x0 = xp[lo];
    const double x1 = xp[lo + 1];
    const double y0 = fp[lo];
    const double y1 = fp[lo + 1];
    if (x1 == x0) {
        return y1;
    }
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0);
}

inline double table_area_by_depth(const TableView& tbl, double depth) noexcept {
    return interp_sorted(depth, tbl.depth_axis, tbl.area_d, tbl.depth_len);
}

inline double table_level_by_area(const TableView& tbl, double area) noexcept {
    return interp_sorted(area, tbl.area_axis, tbl.level_a, tbl.area_len);
}

inline double table_deb_by_area(const TableView& tbl, double area) noexcept {
    return interp_sorted(area, tbl.area_axis, tbl.DEB_a, tbl.area_len);
}

inline double table_depth_by_area(const TableView& tbl, double area) noexcept {
    return interp_sorted(area, tbl.area_axis, tbl.depth_a, tbl.area_len);
}

inline double table_width_by_area(const TableView& tbl, double area) noexcept {
    if (area <= 0.0) {
        return 0.0;
    }
    if (tbl.wet_len > 0) {
        return interp_sorted(area, tbl.area_axis_wet, tbl.width_a_wet, tbl.wet_len);
    }
    return interp_sorted(area, tbl.area_axis, tbl.width_a, tbl.area_len);
}

inline double table_wetted_by_area(const TableView& tbl, double area) noexcept {
    return interp_sorted(area, tbl.area_axis, tbl.wetted_a, tbl.area_len);
}

inline double table_press_by_area(const TableView& tbl, double area) noexcept {
    return interp_sorted(area, tbl.area_axis, tbl.press_a, tbl.area_len);
}

inline double table_hradius_by_area(const TableView& tbl, double area) noexcept {
    if (area <= 0.0) {
        return 0.0;
    }
    const double wetted = table_wetted_by_area(tbl, area);
    if (wetted <= 0.0 || std::isnan(wetted)) {
        return 1.0e-07;
    }
    return area / wetted;
}

inline double resolve_width_exact(
    const TableView& tbl,
    double area,
    double depth,
    double eps,
    double water_depth_limit,
    bool preserve_true_width
) noexcept {
    double width = table_width_by_area(tbl, area);
    if ((!preserve_true_width) && width < eps && depth > water_depth_limit) {
        width = std::max(area / std::max(depth, water_depth_limit), eps);
    }
    return std::max(width, eps);
}

inline bool is_cell_dry(
    double area,
    double depth,
    double q,
    double area_limit,
    double g,
    double eps,
    double water_depth_limit
) noexcept {
    if (area <= area_limit) {
        return true;
    }
    if (depth <= water_depth_limit) {
        const double depth_ref = max3(depth, water_depth_limit, eps);
        const double tol = area_limit * std::sqrt(g * depth_ref);
        return std::abs(q) <= tol;
    }
    return false;
}

}  // namespace

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
) {
    UpdateCellStats stats{};
    const bool keep_true_width = preserve_true_width != 0;
    const float g_f = static_cast<float>(g);
    const float eps_f = static_cast<float>(eps);

    for (std::size_t i = 0; i < n; ++i) {
        const TableView& tbl = tables[i];
        const double prev_s = static_cast<double>(S[i]);
        const double prev_depth = static_cast<double>(water_depth[i]);
        const double s_limit = cell_s_limit[i];

        double area_i = std::max(static_cast<double>(S[i]), 0.0);
        S[i] = static_cast<float>(area_i);

        double level_i = table_level_by_area(tbl, area_i);
        water_level[i] = level_i;
        double depth_i = std::max(level_i - cell_bed[i], 0.0);
        water_depth[i] = depth_i;

        if (is_cell_dry(area_i, depth_i, static_cast<double>(Q[i]), s_limit, g, eps, water_depth_limit)) {
            if (forced_dry_recorded[i] == 0 && (prev_s > s_limit || prev_depth > water_depth_limit)) {
                forced_dry_recorded[i] = 1;
                stats.forced_dry_increment += 1;
            }
            S[i] = 0.0f;
            Q[i] = 0.0f;
            water_depth[i] = 0.0;
            water_level[i] = cell_bed[i];
            U[i] = 0.0f;
            C[i] = static_cast<float>(eps);
            FR[i] = 0.0f;
        } else {
            if (depth_i <= velocity_depth_limit) {
                if (near_dry_velocity_mode == ZERO_Q) {
                    Q[i] = 0.0f;
                    U[i] = 0.0f;
                    C[i] = static_cast<float>(eps);
                    FR[i] = 0.0f;
                } else {
                    const double depth_actual = max3(depth_i, water_depth_limit, eps);
                    const double area_actual = max3(area_i, s_limit, eps);
                    double depth_floor = std::max(velocity_depth_limit, water_depth_limit);
                    if (near_dry_derived_mode == ACTUAL_U_SOFT_FLOOR_C) {
                        depth_floor = std::max(depth_actual, std::sqrt(std::max(water_depth_limit, eps) * depth_floor));
                    } else if (near_dry_derived_mode == ACTUAL_U_WATERDEPTH_FLOOR_C) {
                        depth_floor = max3(depth_actual, water_depth_limit, eps);
                    }
                    const double area_floor = std::max(
                        area_actual,
                        std::max(table_area_by_depth(tbl, depth_floor), std::max(s_limit, eps))
                    );
                    const double width_floor = resolve_width_exact(
                        tbl,
                        area_floor,
                        depth_floor,
                        eps,
                        water_depth_limit,
                        keep_true_width
                    );
                    if (near_dry_derived_mode == FLOOR_U_AND_C) {
                        U[i] = static_cast<float>(static_cast<double>(Q[i]) / area_floor);
                    } else {
                        U[i] = static_cast<float>(static_cast<double>(Q[i]) / area_actual);
                    }
                    C[i] = static_cast<float>(std::sqrt(g * area_floor / width_floor));
                    FR[i] = std::fabs(U[i]) / std::max(C[i], eps_f);
                }
            } else {
                const double width_i = resolve_width_exact(
                    tbl,
                    area_i,
                    depth_i,
                    eps,
                    water_depth_limit,
                    keep_true_width
                );
                const float area_f = S[i];
                const float width_f = std::max(static_cast<float>(width_i), eps_f);
                U[i] = Q[i] / area_f;
                C[i] = std::sqrt(g_f * area_f / width_f);
                FR[i] = std::fabs(U[i]) / std::max(C[i], eps_f);
            }
        }

        const double final_area = static_cast<double>(S[i]);
        P[i] = static_cast<float>(table_wetted_by_area(tbl, final_area));
        PRESS[i] = static_cast<float>(table_press_by_area(tbl, final_area));
        R[i] = static_cast<float>(table_hradius_by_area(tbl, final_area));
        QIN[i] = 0.0f;
    }

    return stats;
}

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
) {
    AssemblePostStepStats stats{};
    const float g_f = static_cast<float>(g);
    const float dt_f = static_cast<float>(dt);

    for (std::size_t i = 0; i < n; ++i) {
        const TableView& tbl = tables[i];
        const double prev_s = static_cast<double>(S[i]);
        const double prev_depth = water_depth[i];
        const float area_pos = std::max(S[i], 0.0f);
        const double depth_i = table_depth_by_area(tbl, static_cast<double>(area_pos));
        const double s_limit = cell_s_limit[i];

        if (is_cell_dry(static_cast<double>(S[i]), depth_i, static_cast<double>(Q[i]), s_limit, g, eps, water_depth_limit)) {
            if (forced_dry_recorded[i] == 0 && (prev_s > s_limit || prev_depth > water_depth_limit)) {
                forced_dry_recorded[i] = 1;
                stats.forced_dry_increment += 1;
            }
            S[i] = 0.0f;
            Q[i] = 0.0f;
        } else {
            float coef = 0.0f;
            if (!(friction_min_depth > 0.0 && depth_i <= friction_min_depth)) {
                const double deb = table_deb_by_area(tbl, static_cast<double>(S[i]));
                const float num1 = g_f * dt_f;
                const float num2 = num1 * S[i];
                const float den = static_cast<float>(deb * deb);
                coef = num2 / den;
            }
            const float abs_q = std::fabs(Q[i]);
            const float mult1 = 4.0f * coef;
            const float mult2 = mult1 * abs_q;
            const float delta = 1.0f + mult2;
            if (coef > 1.0e-06f) {
                const float root = std::sqrt(delta);
                const float denom = 2.0f * coef;
                if (Q[i] > 0.0f) {
                    const float numer = -1.0f + root;
                    Q[i] = numer / denom;
                } else {
                    const float numer = 1.0f - root;
                    Q[i] = numer / denom;
                }
            } else {
                const float mult3 = coef * Q[i];
                const float factor = 1.0f - mult3;
                Q[i] = Q[i] * factor;
            }
        }
    }

    for (std::size_t i = 0; i < n; ++i) {
        const TableView& tbl = tables[i];
        const double prev_s = static_cast<double>(S[i]);
        const double prev_depth = water_depth[i];
        const float area_pos = std::max(S[i], 0.0f);
        const double depth_i = table_depth_by_area(tbl, static_cast<double>(area_pos));
        const double s_limit = cell_s_limit[i];
        if (is_cell_dry(static_cast<double>(S[i]), depth_i, static_cast<double>(Q[i]), s_limit, g, eps, water_depth_limit)) {
            if (forced_dry_recorded[i] == 0 && (prev_s > s_limit || prev_depth > water_depth_limit)) {
                forced_dry_recorded[i] = 1;
                stats.forced_dry_increment += 1;
            }
            S[i] = 0.0f;
            Q[i] = 0.0f;
        }
    }

    return stats;
}

}  // namespace rivernet

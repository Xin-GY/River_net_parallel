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

inline double roe_abs_with_fix(
    double lam,
    double c,
    double roe_entropy_fix,
    double roe_entropy_fix_factor
) noexcept {
    double delta = roe_entropy_fix;
    const double aval = std::fabs(lam);
    const double cabs = std::fabs(c);
    const double scaled = roe_entropy_fix_factor * cabs;
    if (scaled > delta) {
        delta = scaled;
    }
    if (delta <= 0.0 || aval >= delta) {
        return aval;
    }
    return 0.5 * (lam * lam / delta + delta);
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

inline double rectangular_pressure(double g, double width, double depth) noexcept {
    const double h = (depth > 0.0) ? depth : 0.0;
    return 0.5 * g * width * h * h;
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
) {
    AssemblePostStepStats stats{};
    const float g_f = static_cast<float>(g);
    const float dt_f = static_cast<float>(dt);

    for (std::size_t i = 0; i < n; ++i) {
        const std::size_t left_face = 2 * i;
        const std::size_t right_face = 2 * (i + 1);
        const std::size_t cell = 2 * (i + 1);
        const float length_i = cell_lengths[i];
        const float dt_over_length = dt_f / length_i;
        const double flux_mass =
            flux_loc[right_face] - flux_loc[left_face]
            + flux_source_right[cell]
            + flux_source_left[cell]
            + flux_friction_left[cell]
            + flux_friction_right[cell];
        const double flux_momentum =
            flux_loc[right_face + 1] - flux_loc[left_face + 1]
            + flux_source_center[cell + 1]
            + flux_source_right[cell + 1]
            + flux_source_left[cell + 1]
            + flux_friction_left[cell + 1]
            + flux_friction_right[cell + 1];
        flux[cell] = flux_mass;
        flux[cell + 1] = flux_momentum;
        S[i] = static_cast<float>(static_cast<double>(S[i]) - flux_mass * dt_over_length);
        Q[i] = static_cast<float>(static_cast<double>(Q[i]) - flux_momentum * dt_over_length);
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
) {
    RoeMatrixStats stats{};
    if (n == 0) {
        stats.lambda1_min = 0.0f;
        stats.lambda1_max = 0.0f;
        stats.lambda2_min = 0.0f;
        stats.lambda2_max = 0.0f;
        return stats;
    }

    bool lambda_init = false;

    for (std::size_t i = 0; i < n; ++i) {
        const float roe_c = F_C[i];
        const float roe_u = F_U[i];
        const float beta_arr = 0.5f * (BETA[i] + BETA[i + 1]);

        flag_LeVeque[i] = 0.0;

        const float tmp = beta_arr * (1.0f - beta_arr) * roe_u * roe_u;
        const float z_sq = std::max(roe_c * roe_c - tmp, 0.0f);
        const float z = std::sqrt(z_sq);
        const float z_safe = z + eps;

        float lambda1_i = beta_arr * roe_u - z;
        float lambda2_i = beta_arr * roe_u + z;

        const float fr_l = FR[i];
        const float fr_r = FR[i + 1];
        const double depth_l = water_depth[i];
        const double depth_r = water_depth[i + 1];
        const bool indic = (depth_l > water_depth_limit) && (depth_r > water_depth_limit);
        const bool mask1 = (fr_r > 1.0f) && (fr_l < 1.0f) && (roe_u > 0.0f) && indic;
        const bool mask2 = (fr_r < 1.0f) && (fr_l > 1.0f) && (roe_u < 0.0f) && indic;

        if (mask1) {
            const float l1d = beta_arr * U[i] - C[i];
            const float l1g = beta_arr * U[i + 1] - C[i + 1];
            const float den = l1g - l1d;
            float ratio1 = 0.0f;
            if (den != 0.0f) {
                ratio1 = (lambda1_i - l1d) / den;
            }
            lambda1_i = l1g * ratio1;
            flag_LeVeque[i] = 2.0;
        }
        if (mask2) {
            const float l2d = beta_arr * U[i] + C[i];
            const float l2g = beta_arr * U[i + 1] + C[i + 1];
            const float den = l2d - l2g;
            float ratio2 = 0.0f;
            if (den != 0.0f) {
                ratio2 = (lambda2_i - l2g) / den;
            }
            lambda2_i = l2d * ratio2;
            flag_LeVeque[i] = 1.0;
        }

        const float dS = S[i + 1] - S[i];
        const float dQ = Q[i + 1] - Q[i];
        const float two_roe_c = 2.0f * roe_c + eps;
        const float alpha2_i = (dQ - dS * (roe_u - roe_c)) / two_roe_c;
        const float alpha1_i = dS - alpha2_i;
        const float beta_u = beta_arr * roe_u;

        abs_Lambda1[i] = std::fabs(lambda1_i);
        abs_Lambda2[i] = std::fabs(lambda2_i);
        alpha1[i] = alpha1_i;
        alpha2[i] = alpha2_i;
        Lambda1[i] = lambda1_i;
        Lambda2[i] = lambda2_i;

        Vactor1[2 * i] = 1.0;
        Vactor1[2 * i + 1] = static_cast<double>(beta_u - z);
        Vactor1_T[2 * i] = static_cast<double>((beta_u + z) / (2.0f * z_safe));
        Vactor1_T[2 * i + 1] = static_cast<double>(-1.0f / (2.0f * z_safe));
        Vactor2[2 * i] = 1.0;
        Vactor2[2 * i + 1] = static_cast<double>(beta_u + z);
        Vactor2_T[2 * i] = static_cast<double>(-(beta_u - z) / (2.0f * z_safe));
        Vactor2_T[2 * i + 1] = static_cast<double>(1.0f / (2.0f * z_safe));

        const bool wet_iface = (depth_l > water_depth_limit) || (depth_r > water_depth_limit);
        if (wet_iface) {
            if (roe_u >= roe_c) {
                stats.supercritical_pos += 1;
            } else if (roe_u <= -roe_c) {
                stats.supercritical_neg += 1;
            } else {
                stats.subcritical += 1;
            }
        }
        if (flag_LeVeque[i] != 0.0) {
            stats.leveque_count += 1;
        }

        if (!lambda_init) {
            stats.lambda1_min = lambda1_i;
            stats.lambda1_max = lambda1_i;
            stats.lambda2_min = lambda2_i;
            stats.lambda2_max = lambda2_i;
            lambda_init = true;
        } else {
            stats.lambda1_min = std::min(stats.lambda1_min, lambda1_i);
            stats.lambda1_max = std::max(stats.lambda1_max, lambda1_i);
            stats.lambda2_min = std::min(stats.lambda2_min, lambda2_i);
            stats.lambda2_max = std::max(stats.lambda2_max, lambda2_i);
        }
    }

    return stats;
}

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
) {
    const bool use_threshold = use_section_area_threshold != 0;

    for (std::size_t i = 0; i < n; ++i) {
        const double limit_left = use_threshold ? cell_s_limit[i] : s_limit_default;
        const double limit_right = use_threshold ? cell_s_limit[i + 1] : s_limit_default;

        const double sqrt_left = std::sqrt(std::max(static_cast<double>(S[i]), limit_left));
        const double sqrt_right = std::sqrt(std::max(static_cast<double>(S[i + 1]), limit_right));
        const double denom = sqrt_left + sqrt_right;
        const double fu = (static_cast<double>(U[i]) * sqrt_left + static_cast<double>(U[i + 1]) * sqrt_right) / denom;

        const double diff_s = std::fabs(sqrt_left - sqrt_right);
        double fc;
        if (diff_s <= 0.001) {
            fc = 0.5 * (static_cast<double>(C[i]) + static_cast<double>(C[i + 1]));
        } else {
            double ratio = 0.0;
            const double s_diff = static_cast<double>(S[i]) - static_cast<double>(S[i + 1]);
            ratio = (static_cast<double>(PRESS[i]) - static_cast<double>(PRESS[i + 1])) / s_diff;
            ratio = std::max(ratio, eps);
            fc = std::sqrt(ratio);
        }

        const bool dry_left = static_cast<double>(S[i]) <= limit_left;
        const bool dry_right = static_cast<double>(S[i + 1]) <= limit_right;
        const bool one_side_dry = dry_left != dry_right;
        const bool both_dry = dry_left && dry_right;

        if (one_side_dry) {
            if (dry_left) {
                F_U[i] = U[i + 1];
                F_C[i] = C[i + 1];
            } else {
                F_U[i] = U[i];
                F_C[i] = C[i];
            }
        } else if (both_dry) {
            F_U[i] = 0.0f;
            F_C[i] = static_cast<float>(eps);
        } else {
            F_U[i] = static_cast<float>(fu);
            F_C[i] = static_cast<float>(fc);
        }
    }
}

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
) {
    for (std::size_t i = 0; i < n; ++i) {
        const TableView& left_tbl = left_tables[i];
        const TableView& right_tbl = right_tables[i];

        double h_left = water_depth[i];
        double h_right = water_depth[i + 1];
        if (h_left < 0.0) {
            h_left = 0.0;
        }
        if (h_right < 0.0) {
            h_right = 0.0;
        }

        const double z_left = river_bed_height[i];
        const double z_right = river_bed_height[i + 1];
        const double eta_left = z_left + h_left;
        const double eta_right = z_right + h_right;

        const double area_left_center = static_cast<double>(S[i]);
        const double area_right_center = static_cast<double>(S[i + 1]);
        const double q_left_center = static_cast<double>(Q[i]);
        const double q_right_center = static_cast<double>(Q[i + 1]);

        double u_left = 0.0;
        double u_right = 0.0;
        if (area_left_center > tiny && h_left > tiny) {
            u_left = q_left_center / area_left_center;
        }
        if (area_right_center > tiny && h_right > tiny) {
            u_right = q_right_center / area_right_center;
        }

        const double z_face = (z_left >= z_right) ? z_left : z_right;
        double h_left_hr = eta_left - z_face;
        double h_right_hr = eta_right - z_face;
        if (h_left_hr < 0.0) {
            h_left_hr = 0.0;
        }
        if (h_right_hr < 0.0) {
            h_right_hr = 0.0;
        }

        const double a_left = table_area_by_depth(left_tbl, h_left_hr);
        const double a_right = table_area_by_depth(right_tbl, h_right_hr);
        const double p_left_hr = table_press_by_area(left_tbl, a_left);
        const double p_right_hr = table_press_by_area(right_tbl, a_right);
        const double q_left = a_left * u_left;
        const double q_right = a_right * u_right;
        const double f_left0 = q_left;
        const double f_left1 = q_left * u_left + p_left_hr;
        const double f_right0 = q_right;
        const double f_right1 = q_right * u_right + p_right_hr;

        double flux0 = 0.0;
        double flux1 = 0.0;

        if (!(a_left <= tiny && a_right <= tiny)) {
            double t_left = table_width_by_area(left_tbl, (a_left > tiny) ? a_left : tiny);
            double t_right = table_width_by_area(right_tbl, (a_right > tiny) ? a_right : tiny);
            if (t_left < tiny) {
                t_left = tiny;
            }
            if (t_right < tiny) {
                t_right = tiny;
            }

            const double c_left = (a_left > tiny) ? std::sqrt(g * a_left / t_left) : 0.0;
            const double c_right = (a_right > tiny) ? std::sqrt(g * a_right / t_right) : 0.0;
            double s_left = u_left - c_left;
            const double s_left_r = u_right - c_right;
            if (s_left_r < s_left) {
                s_left = s_left_r;
            }
            double s_right = u_left + c_left;
            const double s_right_r = u_right + c_right;
            if (s_right_r > s_right) {
                s_right = s_right_r;
            }

            if (a_left > tiny && a_right > tiny) {
                const double sqrt_al = std::sqrt((a_left > 0.0) ? a_left : 0.0);
                const double sqrt_ar = std::sqrt((a_right > 0.0) ? a_right : 0.0);
                const double denom = sqrt_al + sqrt_ar;
                double u_roe = 0.0;
                if (denom > tiny) {
                    u_roe = (u_left * sqrt_al + u_right * sqrt_ar) / denom;
                }

                double c_roe;
                if (std::fabs(a_right - a_left) > tiny) {
                    const double ratio = (p_right_hr - p_left_hr) / (a_right - a_left);
                    c_roe = (ratio > 0.0) ? std::sqrt(ratio) : 0.0;
                } else {
                    c_roe = 0.5 * (c_left + c_right);
                }

                if (c_roe <= tiny) {
                    flux0 = 0.5 * (f_left0 + f_right0);
                    flux1 = 0.5 * (f_left1 + f_right1);
                } else {
                    const double da = a_right - a_left;
                    const double dq = q_right - q_left;
                    const double alpha1 = ((u_roe + c_roe) * da - dq) / (2.0 * c_roe);
                    const double alpha2 = (dq - (u_roe - c_roe) * da) / (2.0 * c_roe);
                    const double lam1 = u_roe - c_roe;
                    const double lam2 = u_roe + c_roe;
                    const double abs1 = roe_abs_with_fix(lam1, c_roe, roe_entropy_fix, roe_entropy_fix_factor);
                    const double abs2 = roe_abs_with_fix(lam2, c_roe, roe_entropy_fix, roe_entropy_fix_factor);
                    flux0 = 0.5 * (f_left0 + f_right0) - 0.5 * (abs1 * alpha1 + abs2 * alpha2);
                    flux1 = 0.5 * (f_left1 + f_right1) - 0.5 * (
                        abs1 * alpha1 * (u_roe - c_roe) + abs2 * alpha2 * (u_roe + c_roe)
                    );
                }
            } else if (s_left >= 0.0) {
                flux0 = f_left0;
                flux1 = f_left1;
            } else if (s_right <= 0.0) {
                flux0 = f_right0;
                flux1 = f_right1;
            } else if (s_right - s_left <= tiny) {
                flux0 = 0.0;
                flux1 = 0.0;
            } else {
                flux0 = (s_right * f_left0 - s_left * f_right0 + s_left * s_right * (a_right - a_left)) / (s_right - s_left);
                flux1 = (s_right * f_left1 - s_left * f_right1 + s_left * s_right * (q_right - q_left)) / (s_right - s_left);
            }
        }

        if (dt > 0.0 && std::fabs(flux0) > tiny) {
            int donor = -1;
            if (flux0 > 0.0 && 1 <= static_cast<int>(i) && static_cast<int>(i) <= cell_num) {
                donor = static_cast<int>(i);
            } else if (flux0 < 0.0 && 1 <= static_cast<int>(i) + 1 && static_cast<int>(i) + 1 <= cell_num) {
                donor = static_cast<int>(i) + 1;
            }
            if (donor >= 0) {
                double available = std::max(static_cast<double>(S[donor]), 0.0);
                available *= std::max(cell_lengths[donor], tiny);
                const double max_flux = available / std::max(dt, tiny);
                if (max_flux < std::fabs(flux0)) {
                    const double scale = max_flux / std::max(std::fabs(flux0), tiny);
                    flux0 *= scale;
                    flux1 *= scale;
                }
            }
        }

        flux_loc[i * 2] = flux0;
        flux_loc[i * 2 + 1] = flux1;
        flux_source_right[i * 2 + 1] = static_cast<double>(PRESS[i]) - p_left_hr;
        flux_source_left[(i + 1) * 2 + 1] = -(static_cast<double>(PRESS[i + 1]) - p_right_hr);
    }

    for (int j = 1; j <= cell_num; ++j) {
        const double rain_half = -0.5 * cell_lengths[j] * static_cast<double>(QIN[j]);
        flux_source_left[j * 2] += rain_half;
        flux_source_right[j * 2] += rain_half;
    }
}

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
) {
    if (n == 0) {
        return;
    }

    const std::size_t cell_num = n - 1;

    std::fill(flux_loc, flux_loc + n * 2, 0.0);
    std::fill(flux_source_center, flux_source_center + n * 2, 0.0);
    std::fill(cell_press_source, cell_press_source + n * 2, 0.0);
    std::fill(flux_source_left, flux_source_left + (n + 1) * 2, 0.0);
    std::fill(flux_source_right, flux_source_right + (n + 1) * 2, 0.0);
    std::fill(flux_friction_left, flux_friction_left + (n + 1) * 2, 0.0);
    std::fill(flux_friction_right, flux_friction_right + (n + 1) * 2, 0.0);

    for (std::size_t i = 0; i < n; ++i) {
        const double z_left = river_bed_height[i];
        const double z_right = river_bed_height[i + 1];
        const double h_left_center = std::max(water_depth[i], 0.0);
        const double h_right_center = std::max(water_depth[i + 1], 0.0);
        const double eta_left = z_left + h_left_center;
        const double eta_right = z_right + h_right_center;
        const double q_left_center = static_cast<double>(Q[i]);
        const double q_right_center = static_cast<double>(Q[i + 1]);
        double u_left = 0.0;
        double u_right = 0.0;
        if (h_left_center > tiny && static_cast<double>(S[i]) > tiny) {
            u_left = q_left_center / static_cast<double>(S[i]);
        }
        if (h_right_center > tiny && static_cast<double>(S[i + 1]) > tiny) {
            u_right = q_right_center / static_cast<double>(S[i + 1]);
        }

        const double z_face = (z_left >= z_right) ? z_left : z_right;
        const double h_left_hr = std::max(eta_left - z_face, 0.0);
        const double h_right_hr = std::max(eta_right - z_face, 0.0);
        const double a_left = width * h_left_hr;
        const double a_right = width * h_right_hr;
        double q_left = q_left_center;
        double q_right = q_right_center;
        double flux0 = 0.0;
        double flux1 = 0.0;

        if (a_left <= tiny && a_right <= tiny) {
            flux0 = 0.0;
            flux1 = 0.0;
        } else if (a_right <= tiny) {
            const double c_left = std::sqrt(g * std::max(h_left_hr, 0.0));
            const double left_flux0 = q_left;
            const double left_flux1 = q_left * u_left + rectangular_pressure(g, width, h_left_hr);
            if (u_left - c_left >= 0.0) {
                flux0 = left_flux0;
                flux1 = left_flux1;
            } else if (u_left + 2.0 * c_left <= 0.0) {
                flux0 = 0.0;
                flux1 = 0.0;
            } else {
                const double c_star = std::max((u_left + 2.0 * c_left) / 3.0, 0.0);
                const double h_star = (c_star * c_star) / g;
                const double u_star = c_star;
                const double q_star = width * h_star * u_star;
                flux0 = q_star;
                flux1 = q_star * u_star + rectangular_pressure(g, width, h_star);
            }
        } else if (a_left <= tiny) {
            const double c_right = std::sqrt(g * std::max(h_right_hr, 0.0));
            const double right_flux0 = q_right;
            const double right_flux1 = q_right * u_right + rectangular_pressure(g, width, h_right_hr);
            if (u_right + c_right <= 0.0) {
                flux0 = right_flux0;
                flux1 = right_flux1;
            } else if (u_right - 2.0 * c_right >= 0.0) {
                flux0 = 0.0;
                flux1 = 0.0;
            } else {
                const double c_star = std::max((2.0 * c_right - u_right) / 3.0, 0.0);
                const double h_star = (c_star * c_star) / g;
                const double u_star = -c_star;
                const double q_star = width * h_star * u_star;
                flux0 = q_star;
                flux1 = q_star * u_star + rectangular_pressure(g, width, h_star);
            }
        } else {
            q_left = a_left * u_left;
            q_right = a_right * u_right;
            const double f_left0 = q_left;
            const double f_left1 = q_left * u_left + rectangular_pressure(g, width, h_left_hr);
            const double f_right0 = q_right;
            const double f_right1 = q_right * u_right + rectangular_pressure(g, width, h_right_hr);
            const double sqrt_hl = std::sqrt(std::max(h_left_hr, 0.0));
            const double sqrt_hr = std::sqrt(std::max(h_right_hr, 0.0));
            const double denom = sqrt_hl + sqrt_hr;
            double u_roe = 0.0;
            if (denom > tiny) {
                u_roe = (u_left * sqrt_hl + u_right * sqrt_hr) / denom;
            }
            const double c_roe = std::sqrt(g * 0.5 * std::max(h_left_hr + h_right_hr, 0.0));
            if (c_roe <= tiny) {
                flux0 = 0.5 * (f_left0 + f_right0);
                flux1 = 0.5 * (f_left1 + f_right1);
            } else {
                const double dh = h_right_hr - h_left_hr;
                const double dq = q_right - q_left;
                const double alpha1 = ((u_roe + c_roe) * dh - dq) / (2.0 * c_roe);
                const double alpha2 = (dq - (u_roe - c_roe) * dh) / (2.0 * c_roe);
                const double lam1 = u_roe - c_roe;
                const double lam2 = u_roe + c_roe;
                const double abs1 = roe_abs_with_fix(lam1, c_roe, roe_entropy_fix, roe_entropy_fix_factor);
                const double abs2 = roe_abs_with_fix(lam2, c_roe, roe_entropy_fix, roe_entropy_fix_factor);
                flux0 = 0.5 * (f_left0 + f_right0) - 0.5 * (abs1 * alpha1 + abs2 * alpha2);
                flux1 = 0.5 * (f_left1 + f_right1) - 0.5 * (
                    abs1 * alpha1 * (u_roe - c_roe) + abs2 * alpha2 * (u_roe + c_roe)
                );
            }
        }

        const double corr_left = rectangular_pressure(g, width, std::max(h_left_center, 0.0)) - rectangular_pressure(g, width, h_left_hr);
        const double corr_right = rectangular_pressure(g, width, std::max(h_right_center, 0.0)) - rectangular_pressure(g, width, h_right_hr);

        flux_loc[i * 2] = flux0;
        flux_loc[i * 2 + 1] = flux1;
        flux_source_right[i * 2 + 1] = corr_left;
        flux_source_left[(i + 1) * 2 + 1] = -corr_right;
    }

    for (std::size_t j = 1; j <= cell_num; ++j) {
        if (std::fabs(static_cast<double>(QIN[j])) > 0.0) {
            const double rain_half = -0.5 * cell_lengths[j] * static_cast<double>(QIN[j]);
            flux_source_left[j * 2] += rain_half;
            flux_source_right[j * 2] += rain_half;
        }
    }
}

}  // namespace rivernet

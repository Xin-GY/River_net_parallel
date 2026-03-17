#include "evolve_core.hpp"

#include <algorithm>
#include <cmath>

namespace rivernet {

ThreadPool::ThreadPool(std::size_t n_threads) : n_threads_(n_threads) {}

ThreadPool::~ThreadPool() = default;

std::size_t ThreadPool::size() const noexcept {
    return n_threads_;
}

float compute_river_cfl_candidate_exact(
    std::size_t n,
    float cfl,
    float dt_old,
    float dt_increase_factor,
    float min_dt,
    const float* U,
    const float* C,
    const float* cell_lengths,
    float* DTI
) noexcept {
    float dt_min = 0.0f;
    for (std::size_t i = 0; i < n; ++i) {
        const float diff1 = std::fabs(U[i] - C[i]);
        const float diff2 = std::fabs(U[i] + C[i]);
        const float cnode = std::max(std::max(diff1, diff2), 0.001f);
        const float cou = cnode / cell_lengths[i];
        const float dti = cfl / cou;
        DTI[i] = dti;
        if (i == 0 || dti < dt_min) {
            dt_min = dti;
        }
    }

    const float dt_limit = dt_old + 10.0f;
    float dt = std::min(dt_limit, dt_min);
    if (dt < min_dt) {
        dt = min_dt;
    }
    dt = std::min(dt, dt_old * dt_increase_factor);
    return dt;
}

}  // namespace rivernet

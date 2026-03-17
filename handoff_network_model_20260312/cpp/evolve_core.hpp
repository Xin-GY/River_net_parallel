#pragma once

#include <cstddef>
#include <cstdint>

namespace rivernet {

class ThreadPool {
public:
    explicit ThreadPool(std::size_t n_threads);
    ~ThreadPool();

    std::size_t size() const noexcept;

private:
    std::size_t n_threads_;
};

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
) noexcept;

}  // namespace rivernet

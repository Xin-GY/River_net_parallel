#include "evolve_core.hpp"

namespace rivernet {

ThreadPool::ThreadPool(std::size_t n_threads) : n_threads_(n_threads) {}

ThreadPool::~ThreadPool() = default;

std::size_t ThreadPool::size() const noexcept {
    return n_threads_;
}

}  // namespace rivernet

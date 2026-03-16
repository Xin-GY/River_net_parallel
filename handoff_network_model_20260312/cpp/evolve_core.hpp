#pragma once

#include <cstddef>

namespace rivernet {

class ThreadPool {
public:
    explicit ThreadPool(std::size_t n_threads);
    ~ThreadPool();

    std::size_t size() const noexcept;

private:
    std::size_t n_threads_;
};

}  // namespace rivernet

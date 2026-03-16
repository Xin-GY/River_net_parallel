#pragma once

#include <cstddef>
#include <vector>

namespace rivernet {

class OutputBuffer {
public:
    explicit OutputBuffer(std::size_t space_size);

    void reset();
    void append(
        double time_value,
        const double* depth,
        const double* level,
        const double* velocity,
        const double* discharge,
        std::size_t n
    );

    std::size_t snapshot_count() const noexcept;
    std::size_t space_size() const noexcept;

    void copy_times(double* dst) const;
    void copy_depth(double* dst) const;
    void copy_level(double* dst) const;
    void copy_velocity(double* dst) const;
    void copy_discharge(double* dst) const;

private:
    std::size_t space_size_;
    std::vector<double> times_;
    std::vector<double> depth_;
    std::vector<double> level_;
    std::vector<double> velocity_;
    std::vector<double> discharge_;
};

}  // namespace rivernet

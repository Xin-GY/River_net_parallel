#include "output_buffer.hpp"

#include <algorithm>
#include <stdexcept>

namespace rivernet {

OutputBuffer::OutputBuffer(std::size_t space_size) : space_size_(space_size) {}

void OutputBuffer::reset() {
    times_.clear();
    depth_.clear();
    level_.clear();
    velocity_.clear();
    discharge_.clear();
}

void OutputBuffer::append(
    double time_value,
    const double* depth,
    const double* level,
    const double* velocity,
    const double* discharge,
    std::size_t n
) {
    if (n != space_size_) {
        throw std::runtime_error("OutputBuffer append length mismatch");
    }
    times_.push_back(time_value);
    depth_.insert(depth_.end(), depth, depth + n);
    level_.insert(level_.end(), level, level + n);
    velocity_.insert(velocity_.end(), velocity, velocity + n);
    discharge_.insert(discharge_.end(), discharge, discharge + n);
}

std::size_t OutputBuffer::snapshot_count() const noexcept {
    return times_.size();
}

std::size_t OutputBuffer::space_size() const noexcept {
    return space_size_;
}

void OutputBuffer::copy_times(double* dst) const {
    std::copy(times_.begin(), times_.end(), dst);
}

void OutputBuffer::copy_depth(double* dst) const {
    std::copy(depth_.begin(), depth_.end(), dst);
}

void OutputBuffer::copy_level(double* dst) const {
    std::copy(level_.begin(), level_.end(), dst);
}

void OutputBuffer::copy_velocity(double* dst) const {
    std::copy(velocity_.begin(), velocity_.end(), dst);
}

void OutputBuffer::copy_discharge(double* dst) const {
    std::copy(discharge_.begin(), discharge_.end(), dst);
}

}  // namespace rivernet

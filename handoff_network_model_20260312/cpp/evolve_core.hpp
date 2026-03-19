#pragma once

#include <cstddef>
#include <cstdint>
#include <condition_variable>
#include <exception>
#include <mutex>
#include <thread>
#include <vector>

#include "river_kernels.hpp"

namespace rivernet {

enum FluxTaskMode : int {
    FLUX_MODE_GENERAL = 1,
    FLUX_MODE_RECTANGULAR = 2,
};

struct FaceUcTask {
    std::size_t n;
    double eps;
    double s_limit_default;
    int use_section_area_threshold;
    const float* S;
    const float* U;
    const float* C;
    const float* PRESS;
    const double* cell_s_limit;
    float* F_U;
    float* F_C;
};

struct RoeMatrixTask {
    std::size_t n;
    float eps;
    float water_depth_limit;
    const float* F_C;
    const float* F_U;
    const float* BETA;
    const float* FR;
    const double* water_depth;
    const float* U;
    const float* C;
    const float* S;
    const float* Q;
    double* flag_LeVeque;
    float* abs_Lambda1;
    float* abs_Lambda2;
    float* alpha1;
    float* alpha2;
    float* Lambda1;
    float* Lambda2;
    double* Vactor1;
    double* Vactor2;
    double* Vactor1_T;
    double* Vactor2_T;
    RoeMatrixStats stats;
};

struct SourceTermTask {
    const TableView* left_tables;
    const TableView* right_tables;
    std::size_t n;
    const float* S;
    const float* Q;
    const double* water_depth;
    double* friction_source;
    double g;
    double eps;
    double friction_min_depth;
    int frtimp_enabled;
    int use_manning_friction;
    SourceTermStats stats;
};

struct FluxTask {
    int mode;
    const TableView* left_tables;
    const TableView* right_tables;
    std::size_t n;
    double g;
    double tiny;
    double roe_entropy_fix;
    double roe_entropy_fix_factor;
    const double* river_bed_height;
    const double* water_depth;
    const float* S;
    const float* Q;
    const float* PRESS;
    const float* QIN;
    const double* cell_lengths_double;
    const float* cell_lengths_float;
    double dt;
    int cell_num;
    double width;
    double* flux_loc;
    double* flux_source_left;
    double* flux_source_right;
    double* flux_source_center;
    double* flux_friction_left;
    double* flux_friction_right;
    double* cell_press_source;
};

struct AssembleTask {
    const TableView* tables;
    std::size_t n;
    const double* flux_loc;
    const double* flux_source_left;
    const double* flux_source_right;
    const double* flux_source_center;
    const double* flux_friction_left;
    const double* flux_friction_right;
    double* flux;
    float* S;
    float* Q;
    const double* water_depth;
    const double* cell_s_limit;
    std::uint8_t* forced_dry_recorded;
    const float* cell_lengths;
    double g;
    double dt;
    double eps;
    double water_depth_limit;
    double friction_min_depth;
    AssemblePostStepStats stats;
};

struct UpdateCellTask {
    const TableView* tables;
    std::size_t n;
    float* S;
    float* Q;
    double* water_level;
    double* water_depth;
    float* U;
    float* C;
    float* FR;
    float* P;
    float* PRESS;
    float* R;
    float* QIN;
    const double* cell_s_limit;
    const double* cell_bed;
    std::uint8_t* forced_dry_recorded;
    double g;
    double eps;
    double water_depth_limit;
    double velocity_depth_limit;
    int preserve_true_width;
    int near_dry_velocity_mode;
    int near_dry_derived_mode;
    UpdateCellStats stats;
};

struct CflTask {
    std::size_t n;
    float cfl;
    float dt_old;
    float dt_increase_factor;
    float min_dt;
    const float* U;
    const float* C;
    const float* cell_lengths;
    float* DTI;
    float dt_candidate;
};

class ThreadPool {
public:
    explicit ThreadPool(std::size_t n_threads);
    ~ThreadPool();

    std::size_t size() const noexcept;

    void run_face_uc(FaceUcTask* tasks, std::size_t n_tasks);
    void run_roe_matrix(RoeMatrixTask* tasks, std::size_t n_tasks);
    void run_source(SourceTermTask* tasks, std::size_t n_tasks);
    void run_flux(FluxTask* tasks, std::size_t n_tasks);
    void run_assemble(AssembleTask* tasks, std::size_t n_tasks);
    void run_update_cell(UpdateCellTask* tasks, std::size_t n_tasks);
    void run_cfl(CflTask* tasks, std::size_t n_tasks);

private:
    using TaskFn = void (*)(void*, std::size_t, std::size_t);

    void run_task_batch(void* tasks, std::size_t n_tasks, TaskFn fn);
    void worker_loop(std::size_t slot);

    static void execute_face_uc_batch(void* tasks, std::size_t begin, std::size_t end);
    static void execute_roe_matrix_batch(void* tasks, std::size_t begin, std::size_t end);
    static void execute_source_batch(void* tasks, std::size_t begin, std::size_t end);
    static void execute_flux_batch(void* tasks, std::size_t begin, std::size_t end);
    static void execute_assemble_batch(void* tasks, std::size_t begin, std::size_t end);
    static void execute_update_cell_batch(void* tasks, std::size_t begin, std::size_t end);
    static void execute_cfl_batch(void* tasks, std::size_t begin, std::size_t end);

    std::size_t n_threads_;
    std::vector<std::thread> workers_;
    std::mutex mutex_;
    std::condition_variable cv_;
    std::condition_variable done_cv_;
    bool stop_{false};
    std::size_t epoch_{0};
    std::size_t pending_workers_{0};
    void* current_tasks_{nullptr};
    std::size_t current_task_count_{0};
    TaskFn current_task_fn_{nullptr};
    std::exception_ptr pending_exception_;
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

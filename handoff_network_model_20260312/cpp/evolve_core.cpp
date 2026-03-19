#include "evolve_core.hpp"

#include <algorithm>
#include <cmath>
#include <utility>

namespace rivernet {

namespace {

inline std::pair<std::size_t, std::size_t> chunk_for_slot(
    std::size_t total,
    std::size_t slots,
    std::size_t slot
) noexcept {
    if (slots == 0 || slot >= slots) {
        return {0, 0};
    }
    const std::size_t begin = (total * slot) / slots;
    const std::size_t end = (total * (slot + 1)) / slots;
    return {begin, end};
}

inline void run_face_uc_task(FaceUcTask& task) {
    compute_face_uc_exact(
        task.n,
        task.eps,
        task.s_limit_default,
        task.use_section_area_threshold,
        task.S,
        task.U,
        task.C,
        task.PRESS,
        task.cell_s_limit,
        task.F_U,
        task.F_C
    );
}

inline void run_roe_matrix_task(RoeMatrixTask& task) {
    task.stats = compute_roe_matrix_exact(
        task.n,
        task.eps,
        task.water_depth_limit,
        task.F_C,
        task.F_U,
        task.BETA,
        task.FR,
        task.water_depth,
        task.U,
        task.C,
        task.S,
        task.Q,
        task.flag_LeVeque,
        task.abs_Lambda1,
        task.abs_Lambda2,
        task.alpha1,
        task.alpha2,
        task.Lambda1,
        task.Lambda2,
        task.Vactor1,
        task.Vactor2,
        task.Vactor1_T,
        task.Vactor2_T
    );
}

inline void run_source_task(SourceTermTask& task) {
    task.stats = compute_source_term_exact(
        task.left_tables,
        task.right_tables,
        task.n,
        task.S,
        task.Q,
        task.water_depth,
        task.friction_source,
        task.g,
        task.eps,
        task.friction_min_depth,
        task.frtimp_enabled,
        task.use_manning_friction
    );
}

inline void run_flux_task(FluxTask& task) {
    if (task.mode == FLUX_MODE_GENERAL) {
        fill_general_hr_flux_exact_deep(
            task.left_tables,
            task.right_tables,
            task.n,
            task.g,
            task.tiny,
            task.roe_entropy_fix,
            task.roe_entropy_fix_factor,
            task.river_bed_height,
            task.water_depth,
            task.S,
            task.Q,
            task.PRESS,
            task.QIN,
            task.cell_lengths_double,
            task.dt,
            task.cell_num,
            task.flux_loc,
            task.flux_source_left,
            task.flux_source_right
        );
        return;
    }

    if (task.mode == FLUX_MODE_RECTANGULAR) {
        fill_rectangular_hr_flux_exact_deep(
            task.n,
            task.g,
            task.tiny,
            task.width,
            task.roe_entropy_fix,
            task.roe_entropy_fix_factor,
            task.river_bed_height,
            task.water_depth,
            task.S,
            task.Q,
            task.PRESS,
            task.QIN,
            task.cell_lengths_float,
            task.flux_loc,
            task.flux_source_left,
            task.flux_source_right,
            task.flux_source_center,
            task.flux_friction_left,
            task.flux_friction_right,
            task.cell_press_source
        );
    }
}

inline void run_assemble_task(AssembleTask& task) {
    task.stats = assemble_flux_exact_deep(
        task.tables,
        task.n,
        task.flux_loc,
        task.flux_source_left,
        task.flux_source_right,
        task.flux_source_center,
        task.flux_friction_left,
        task.flux_friction_right,
        task.flux,
        task.S,
        task.Q,
        task.water_depth,
        task.cell_s_limit,
        task.forced_dry_recorded,
        task.cell_lengths,
        task.g,
        task.dt,
        task.eps,
        task.water_depth_limit,
        task.friction_min_depth
    );
}

inline void run_update_cell_task(UpdateCellTask& task) {
    task.stats = update_cell_properties_exact(
        task.tables,
        task.n,
        task.S,
        task.Q,
        task.water_level,
        task.water_depth,
        task.U,
        task.C,
        task.FR,
        task.P,
        task.PRESS,
        task.R,
        task.QIN,
        task.cell_s_limit,
        task.cell_bed,
        task.forced_dry_recorded,
        task.g,
        task.eps,
        task.water_depth_limit,
        task.velocity_depth_limit,
        task.preserve_true_width,
        task.near_dry_velocity_mode,
        task.near_dry_derived_mode
    );
}

inline void run_cfl_task(CflTask& task) noexcept {
    task.dt_candidate = compute_river_cfl_candidate_exact(
        task.n,
        task.cfl,
        task.dt_old,
        task.dt_increase_factor,
        task.min_dt,
        task.U,
        task.C,
        task.cell_lengths,
        task.DTI
    );
}

}  // namespace

ThreadPool::ThreadPool(std::size_t n_threads)
    : n_threads_(std::max<std::size_t>(1, n_threads)) {
    if (n_threads_ <= 1) {
        return;
    }
    workers_.reserve(n_threads_ - 1);
    for (std::size_t slot = 1; slot < n_threads_; ++slot) {
        workers_.emplace_back(&ThreadPool::worker_loop, this, slot);
    }
}

ThreadPool::~ThreadPool() {
    if (workers_.empty()) {
        return;
    }
    {
        std::lock_guard<std::mutex> lock(mutex_);
        stop_ = true;
        ++epoch_;
    }
    cv_.notify_all();
    for (auto& worker : workers_) {
        if (worker.joinable()) {
            worker.join();
        }
    }
}

std::size_t ThreadPool::size() const noexcept {
    return n_threads_;
}

void ThreadPool::run_face_uc(FaceUcTask* tasks, std::size_t n_tasks) {
    run_task_batch(tasks, n_tasks, &ThreadPool::execute_face_uc_batch);
}

void ThreadPool::run_roe_matrix(RoeMatrixTask* tasks, std::size_t n_tasks) {
    run_task_batch(tasks, n_tasks, &ThreadPool::execute_roe_matrix_batch);
}

void ThreadPool::run_source(SourceTermTask* tasks, std::size_t n_tasks) {
    run_task_batch(tasks, n_tasks, &ThreadPool::execute_source_batch);
}

void ThreadPool::run_flux(FluxTask* tasks, std::size_t n_tasks) {
    run_task_batch(tasks, n_tasks, &ThreadPool::execute_flux_batch);
}

void ThreadPool::run_assemble(AssembleTask* tasks, std::size_t n_tasks) {
    run_task_batch(tasks, n_tasks, &ThreadPool::execute_assemble_batch);
}

void ThreadPool::run_update_cell(UpdateCellTask* tasks, std::size_t n_tasks) {
    run_task_batch(tasks, n_tasks, &ThreadPool::execute_update_cell_batch);
}

void ThreadPool::run_cfl(CflTask* tasks, std::size_t n_tasks) {
    run_task_batch(tasks, n_tasks, &ThreadPool::execute_cfl_batch);
}

void ThreadPool::run_task_batch(void* tasks, std::size_t n_tasks, TaskFn fn) {
    if (fn == nullptr || n_tasks == 0) {
        return;
    }
    if (n_threads_ <= 1) {
        fn(tasks, 0, n_tasks);
        return;
    }

    {
        std::lock_guard<std::mutex> lock(mutex_);
        pending_exception_ = nullptr;
        current_tasks_ = tasks;
        current_task_count_ = n_tasks;
        current_task_fn_ = fn;
        pending_workers_ = workers_.size();
        ++epoch_;
    }
    cv_.notify_all();

    try {
        const auto range = chunk_for_slot(n_tasks, n_threads_, 0);
        fn(tasks, range.first, range.second);
    } catch (...) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!pending_exception_) {
            pending_exception_ = std::current_exception();
        }
    }

    {
        std::unique_lock<std::mutex> lock(mutex_);
        done_cv_.wait(lock, [this]() { return pending_workers_ == 0; });
        current_tasks_ = nullptr;
        current_task_count_ = 0;
        current_task_fn_ = nullptr;
        if (pending_exception_) {
            std::rethrow_exception(pending_exception_);
        }
    }
}

void ThreadPool::worker_loop(std::size_t slot) {
    std::size_t seen_epoch = 0;
    while (true) {
        void* tasks = nullptr;
        std::size_t n_tasks = 0;
        TaskFn fn = nullptr;

        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait(lock, [this, &seen_epoch]() { return stop_ || epoch_ != seen_epoch; });
            if (stop_) {
                return;
            }
            seen_epoch = epoch_;
            tasks = current_tasks_;
            n_tasks = current_task_count_;
            fn = current_task_fn_;
        }

        try {
            if (fn != nullptr) {
                const auto range = chunk_for_slot(n_tasks, n_threads_, slot);
                fn(tasks, range.first, range.second);
            }
        } catch (...) {
            std::lock_guard<std::mutex> lock(mutex_);
            if (!pending_exception_) {
                pending_exception_ = std::current_exception();
            }
        }

        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (pending_workers_ > 0) {
                --pending_workers_;
                if (pending_workers_ == 0) {
                    done_cv_.notify_one();
                }
            }
        }
    }
}

void ThreadPool::execute_face_uc_batch(void* tasks, std::size_t begin, std::size_t end) {
    auto* typed_tasks = static_cast<FaceUcTask*>(tasks);
    for (std::size_t i = begin; i < end; ++i) {
        run_face_uc_task(typed_tasks[i]);
    }
}

void ThreadPool::execute_roe_matrix_batch(void* tasks, std::size_t begin, std::size_t end) {
    auto* typed_tasks = static_cast<RoeMatrixTask*>(tasks);
    for (std::size_t i = begin; i < end; ++i) {
        run_roe_matrix_task(typed_tasks[i]);
    }
}

void ThreadPool::execute_source_batch(void* tasks, std::size_t begin, std::size_t end) {
    auto* typed_tasks = static_cast<SourceTermTask*>(tasks);
    for (std::size_t i = begin; i < end; ++i) {
        run_source_task(typed_tasks[i]);
    }
}

void ThreadPool::execute_flux_batch(void* tasks, std::size_t begin, std::size_t end) {
    auto* typed_tasks = static_cast<FluxTask*>(tasks);
    for (std::size_t i = begin; i < end; ++i) {
        run_flux_task(typed_tasks[i]);
    }
}

void ThreadPool::execute_assemble_batch(void* tasks, std::size_t begin, std::size_t end) {
    auto* typed_tasks = static_cast<AssembleTask*>(tasks);
    for (std::size_t i = begin; i < end; ++i) {
        run_assemble_task(typed_tasks[i]);
    }
}

void ThreadPool::execute_update_cell_batch(void* tasks, std::size_t begin, std::size_t end) {
    auto* typed_tasks = static_cast<UpdateCellTask*>(tasks);
    for (std::size_t i = begin; i < end; ++i) {
        run_update_cell_task(typed_tasks[i]);
    }
}

void ThreadPool::execute_cfl_batch(void* tasks, std::size_t begin, std::size_t end) {
    auto* typed_tasks = static_cast<CflTask*>(tasks);
    for (std::size_t i = begin; i < end; ++i) {
        run_cfl_task(typed_tasks[i]);
    }
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

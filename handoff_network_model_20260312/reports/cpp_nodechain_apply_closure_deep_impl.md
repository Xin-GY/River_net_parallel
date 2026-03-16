# cpp nodechain apply/closure deep implementation

## changed files

- `handoff_network_model_20260312/cython_cross_section.pxd`
- `handoff_network_model_20260312/cython_node_iteration.pyx`
- `handoff_network_model_20260312/Rivernet.py`
- `handoff_network_model_20260312/Islam.py`
- `handoff_network_model_20260312/tools/profile_cpp_exact_serial.py`

## implementation summary

### 1. exported fast closure entry

`cython_cross_section.pxd` 暴露：

- `compute_stage_boundary_mainline_fast(...)`

这样 nodechain Cython 层可以直接持有 exact fast closure，而不再每次经由 Python wrapper。

### 2. deep plan object

`cython_node_iteration.pyx` 新增：

- `NodeBoundaryDeepPlan`
- `build_nodechain_deep_apply_plan(...)`

`NodeBoundaryDeepPlan` 预绑定：

- side/layout 索引
- target/inner/second tables
- typed state arrays
- guard 常量
- face cache
- implicit 向量写回所需数组

### 3. node iteration routing

`run_internal_node_iteration_exact(...)` 现在接受：

- `branch_deep_apply_plans`

当：

- `net.use_cpp_nodechain_deep_apply = True`
- 且 build plan 成功

则 apply/final apply 阶段优先走 deep plan：

- 直接调用 `compute_stage_boundary_mainline_fast(...)`
- 直接写 `S/Q`
- 直接更新 cached face state
- residual/Ac 阶段直接消费 deep face cache

### 4. exact refresh fallback

第一版曾尝试在 deep plan 内重写 ghost-cell refresh，但 10m compare 出现明显漂移。
accepted 版本回退为：

- closure/native write-back 后仍调用原始 `river._refresh_cell_state(...)`

这样保留了当前 accepted exact 语义，同时把最重的 repeated binding、closure 调度和 face-state
重复读取从 Python 层移走。

### 5. network wiring

`Rivernet.py`：

- 在 `_build_cython_nodechain_plan()` 中构造 `branch_deep_apply_plans`
- 在 `_try_update_internal_boundary_conditions_cython()` 中传给
  `cython_run_internal_node_iteration_exact(...)`

`Islam.py`：

- 新增环境变量：
  - `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY`

`tools/profile_cpp_exact_serial.py`：

- 新增 CLI 开关：
  - `--use-cpp-nodechain-deep-apply`

## exactness status

accepted deep-apply 配置：

- `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`

validation：

- 10m compare: pass
- 2h compare: pass
- 40h compare: pass

40h compare 结果：

- `allclose = true`
- reported metrics `max_abs = 0.0`

## why this one works

这一步有效的原因不是换 dispatch 形态，而是让 nodechain 的最热那段 ownership 更深：

- `boundary_calls` 保持 `4010220`
- 但 `cython_to_python_boundary_calls` 从 `4010220 -> 0`
- `cython_to_python_width_calls` 从 `3414560 -> 0`

所以 full case 的收益来自：

- native closure
- native face-state reuse
- native width lookup reuse

而不是来自短 case 偶然更快的调度变化。

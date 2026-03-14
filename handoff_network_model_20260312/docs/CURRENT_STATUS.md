# Current Status

## 当前代码状态

当前这份 handoff 包对应的是：
- 已将 `handoff_river_solver_core_20260312` 的单河道核心接入到现有河网
- 并为现有网络层补齐兼容接口后的版本

## 当前最新结果

目录：`artifacts/latest_handoff/`

指标：
- `node11_level = 0.873332`
- `node11_Q = -0.089159`
- `node12_level = 0.911626`
- `node12_Q = -0.105344`
- `mean = 0.397614`

性能：
- 当前最快严格校验通过的 CPU 路径：
  - `ISLAM_USE_PARALLEL=1`
  - `ISLAM_PARALLEL_BACKEND=process`
  - `ISLAM_N_WORKERS=4`
  - `ISLAM_USE_CYTHON_TABLE=1`
- `ISLAM_SAVE_INTERVAL` 留空，默认按 `yield_step` 保存输出
- 默认输出模式：`ISLAM_OUTPUT_WRITE_MODE=single_resampled`
- Islam 40h full-case 模型内部自报时间：`148.54 s`
- 当前验收优先看模型内部自报演进时间，不计初始化时间

解释：
- 本轮性能提升主要来自“输出仅在内存缓冲，结束时一次性构造 xarray 并写单文件”
- 默认只保留 `river11_interpolated_output.nc`
- 若需要历史双文件行为，可设 `ISLAM_OUTPUT_WRITE_MODE=legacy_dual`
- 数值核未改，内部节点时序与最终重采样结果保持一致

## 当前已打包的历史较优结果

目录：`artifacts/historical_best/`

指标：
- `node11_level = 0.873332`
- `node11_Q = -0.089159`
- `node12_level = 0.911626`
- `node12_Q = -0.105344`
- `mean = 0.397614`

说明：
- 按当前用户指定，`artifacts/historical_best/` 已替换为本轮最新结果
- 因此当前 handoff 包中的 `latest_handoff/` 与 `historical_best/` 内容一致

## 已确认的结论

1. handoff 单河道核心接入成功，Islam 40h 可稳定运行。
2. 当前最快 CPU 路径已经把 40h full-case 的模型内部自报时间压到 `148.54 s`。
3. 新输出口径下，`internal_node_history.csv` 与 `river11_interpolated_output.nc` 均逐点一致。
4. `interpolated_output.nc` 现在是唯一默认产物，因此下游脚本应优先依赖它。
5. 若继续提速，下一步应回到单河道数值热点，而不是继续压输出构建。

## 下一步最值得查的地方

1. `river_for_net.py`
- `_refresh_cell_state()`、边界闭合链、general HR/chi 剩余 Python 热点

2. `Rivernet.py`
- 内部结点串行/并行调度还有没有可以继续下沉的纯 Python 开销

3. `Islam.py`
- 是否需要把 `ISLAM_SAVE_INTERVAL` 暴露到更细的案例配置层

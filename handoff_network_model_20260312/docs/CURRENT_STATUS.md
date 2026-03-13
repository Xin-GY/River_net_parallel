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
- Islam 40h full-case wall time：`427.97 s`
- 模型内部自报时间：`385.73 s`
- 当前验收优先看模型内部自报演进时间，不计初始化时间

解释：
- 水位两条线已经进入可接受区间，但流量两条线仍明显不达标
- `river11` 两端流量同步偏高，说明是整条 branch 的输水能力偏大

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
2. `node11/node12` 流量比较不是简单符号问题。
3. `internal_node_history.csv` 显示结点净流量接近 0，说明结点守恒本身不是当前主问题。
4. 当前主问题更像 `river11 / river12` 的相对 conveyance 偏差。
5. `Fine` 会显著影响结果，但关闭 `Fine` 也无法把 Q 修好。

## 下一步最值得查的地方

1. `Islam.py`
- `river11` / `river12` 的几何、断面宽度、床线和 `section offset` 是否与论文完全一致

2. `Rivernet.py`
- 内部结点施加水位后，`river11` / `river12` 的 branch 响应是否存在系统偏置

3. `river_for_net.py`
- 在矩形支路 + 内部固定水位边界条件下，摩阻/几何链是否仍与河网层口径不完全一致

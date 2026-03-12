# River Network Handoff Pack

这个目录是给“另一个 Codex 接续当前河网模型工作”用的交接包。

目标：
- 给出当前可运行的 Islam 河网计算链路最小代码集
- 给出运行、评估、打包结果的最短路径
- 说明当前已经确认的修改、当前结果、下一步该查什么

## 推荐阅读顺序

1. `docs/START_HERE.md`
2. `docs/CURRENT_STATUS.md`
3. `docs/RUNBOOK.md`
4. `docs/CHANGES_IN_THIS_PACK.md`
5. `result/pause_handoff_20260312.txt`

## 目录

- `Islam.py`
  - Islam 论文案例构建、边界读取、运行入口
- `Rivernet.py`
  - 河网拓扑、外边界/内部汊点调度
- `river_for_net.py`
  - 单河道有限体积求解器
- `config.py`
  - 基础数值配置
- `persistent_interpolator.py`
  - 边界时序插值与缓存
- `tool_fun/section_偏移.py`
  - 断面高程平移工具
- `bound/`
  - Islam 边界条件数据
- `result/Islam_real_data/`
  - Islam 对比实测/参考数据
- `result/eval_river11_nse.py`
  - 四条目标曲线的 NSE 评估入口
- `result/package_river11_report.py`
  - 打包对比图和原始绘图数据
- `artifacts/latest_handoff/`
  - 本轮 handoff 代码的最新结果图包
- `artifacts/historical_best/`
  - 当前已打包的历史较优结果图包

## 当前结论摘要

- handoff 单河道核心已经成功接入当前河网层。
- Islam 40h 主案例可以稳定跑通。
- 当前最快且结果保持一致的 CPU 路径是：
  - `4 workers` 持久化进程池
  - 可选 `Cython` 断面表查表后端
  - 40h full-case wall time `507.12 s`
  - 模型内部演进时间 `463.76 s`
- 当前问题主要不是水位，而是 `river11` 两端流量系统性偏高。
- 该问题更像 `river11 / river12` 分流比例或 conveyance 偏差，而不是流量符号问题。
- 当前还没有达到四条曲线 `NSE > 0.95`。

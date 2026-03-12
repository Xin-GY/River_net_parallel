# Start Here

## 1. 这套代码的主链路

运行入口：
- `Islam.py`

河网层：
- `Rivernet.py`

单河道求解器：
- `river_for_net.py`

评估工具：
- `result/eval_river11_nse.py`
- `result/package_river11_report.py`
- `result/river11_compare_utils.py`

## 2. 建议先看什么

先看这 4 个文件：
- `Islam.py`
- `Rivernet.py`
- `river_for_net.py`
- `docs/CURRENT_STATUS.md`

## 3. 当前真正需要关注的问题

不是：
- 输出点符号翻转
- 结果后处理口径
- 结点质量不守恒

而是：
- `river11` / `river12` 在内部结点水位施加后的分流能力分配
- `Fine` 重构对 branch conveyance 的影响
- 单河道内部几何/摩阻链与河网内部边界闭合之间是否仍有口径不一致

## 4. 交接建议

另一个 Codex 接手时，优先做这几件事：
- 复跑 `examples/run_islam_40h_current.sh`
- 看 `artifacts/latest_handoff/` 和 `artifacts/historical_best/` 的四张图差异
- 核对 `river11` / `river12` 的几何、床线、roughness、section offset、Fine 重构
- 再决定是否继续改单河道边界函数或汊点耦合

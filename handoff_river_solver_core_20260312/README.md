# River Solver Handoff Pack

这个目录是给“另一个 Codex 做河网组装”用的交接包。

目标很单一：
- 交代当前单河段求解器怎么调用
- 交代核心计算代码放在哪里
- 交代当前 baseline 相对最初版本修了什么、哪些必须保留
- 交代在做河网组装时，哪些职责应该留在网络层，哪些职责已经在单河段内核里

## 目录

- `code/current/`
  - 当前求解器核心代码
  - `single_river_clean.py`
  - `config.py`
- `code/original_reference/`
  - 最初版本参考
  - `single_riever_base.py`
- `examples/`
  - 最小调用示例
  - `minimal_single_reach_call.py`
  - `minimal_irregular_dynamic_call.py`
- `docs/`
  - `CALLING_PATTERNS.md`
  - `COMPUTATION_FLOW.md`
  - `INTEGRATION_NOTES_FOR_NETWORK_ASSEMBLY.md`
  - `CHANGES_FROM_INITIAL_VERSION.md`
- `FILE_MAP.csv`
  - 本交接包文件索引

## 推荐阅读顺序

1. `docs/CALLING_PATTERNS.md`
2. `docs/COMPUTATION_FLOW.md`
3. `docs/INTEGRATION_NOTES_FOR_NETWORK_ASSEMBLY.md`
4. `docs/CHANGES_FROM_INITIAL_VERSION.md`

## 这份交接包的边界

这份交接包只覆盖“单河段内核”。

它不负责：
- 河网拓扑
- 汇流/分流节点质量动量耦合
- reach 之间的调度顺序
- 外部边界时间序列管理
- 多河段结果拼接

这些应该由上层河网组装代码负责。

## 当前 baseline 必保留的关键行为

如果另一个 Codex 只是复用当前求解器，不应该回退这些行为：

1. `dry/near-dry head-cap` 修复
2. `InBound_In_Q2` 干床入流 wetting fallback
3. `fully-wet + bc_use_general_chi=True` 的 `guarded-clamp`
4. exact dry-state table anchor
5. section-specific `DEB` roughness scope
6. `width(A)` 正湿支修复
7. still-wet near-dry cell 保留 conservative `Q`
8. explicit dry admissibility narrowing
9. near-dry derived-state softening / `C` regularization 收窄
10. irregular boundary/general-chi accepted baseline
11. `bc_use_order2_extrap*` runtime wiring 修复

这些内容在 `docs/CHANGES_FROM_INITIAL_VERSION.md` 里有更详细说明。

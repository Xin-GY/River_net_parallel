# Integration Notes For Network Assembly

这份说明不是给“继续修单河段 solver”的，而是给“上层河网组装”使用的。

## 1. 这个 solver 在网络层里的推荐角色

把当前 `River` 看成：

**单河段内核**

它负责：
- 单 reach 断面表构建
- 单 reach 内部通量/源项推进
- 单 reach 的 near-dry / dry / derived-state 逻辑
- 单 reach 的边界闭合函数

网络层应该负责：
- reach graph / junction graph
- reach 间流量、水位或特征量交换
- 多 reach 调度顺序
- 全局时间步管理
- 边界时间序列管理
- 汇流、分流、节点守恒

## 2. 不要在网络层复制单河段内部逻辑

尤其不要在网络层重写这些逻辑：
- near-dry / dry admissibility
- general-chi guarded-clamp
- CrossSectionTable accessors
- `_refresh_cell_state()`
- `_compute_near_dry_derived_state()`

网络层应该只决定：
- 每条 reach 当前步的边界目标量是什么
- 然后调用 reach 内核已有边界接口

## 3. reach 之间的推荐接口层

如果要做河网组装，建议抽一层薄适配器，例如：

```python
class ReachKernel:
    def __init__(...):
        self.river = River(...)

    def set_initial_state(...):
        ...

    def set_external_boundary(...):
        ...

    def step_until(report_time):
        ...

    def get_face_state(side):
        ...

    def get_cell_snapshot():
        ...
```

这样可以把网络层和 `River` 的直接细节隔开。

## 4. 当前 baseline 配置建议

对于不规则断面 reach，建议默认保留：

```python
{
    "bc_use_general_chi": True,
    "bc_general_chi_candidate_mode": "guarded_clamp",
    "bc_general_chi_guard_selector": "closure_q_delta",
    "bc_general_chi_guard_q_delta": 0.005,
    "bc_use_order2_extrap": True,
    "bc_use_order2_extrap_flow": True,
    "bc_use_order2_extrap_stage": True,
}
```

如果网络层另加配置，不要默认覆盖掉这些项。

## 5. 当前不建议由网络层先动的内容

在没有新证据前，不建议网络层自己去改：
- `general HR` 主公式
- `boundary/general-chi` 主公式
- friction semi-implicit 公式
- DEB / width / PRESS / table builder 公式

这些都应该仍由单河段内核统一维护。

## 6. 另一个 Codex 最容易犯的错误

最常见错误不是“不会调 solver”，而是：

1. 在网络层重新做一套 near-dry 判据
2. reach 边界和 solver 内 ghost/boundary 闭合逻辑打架
3. 把 `section_data` 解释成网络层几何，而不是单断面几何
4. 把 `yield_step` 当成内部真实 CFL 步长
5. 认为只要边界 probe 过了，就等价于 dynamic path 也过了

当前项目已经走过这些坑，所以不建议重复。

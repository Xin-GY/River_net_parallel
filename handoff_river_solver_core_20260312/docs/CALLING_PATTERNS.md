# Calling Patterns

## 1. 输入对象

当前求解器直接吃 4 个对象：

1. `river_data`
2. `section_data`
3. `section_pos`
4. `sim_data`

它们最终传给：

```python
river = River(river_data, section_data, section_pos, sim_data)
```

## 2. `river_data`

最小字段：

```python
river_data = {
    "cell_num": num_cells,
    "pos": [[0.0, 0.0, 0.0], [length, 0.0, 0.0]],
    "section_name": ["s0", "s1", ..., "sN"],
}
```

含义：
- `cell_num`: 真正物理单元数，不含 ghost cell
- `pos`: 河段起终点
- `section_name`: 每个单元中心对应的断面名

## 3. `section_data`

格式是：

```python
section_data["s0"] = [[x0, z0], [x1, z1], ...]
```

要求：
- 每个断面是一条折线
- 横坐标 `x` 是断面内局部横向坐标
- 纵坐标 `z` 是该断面高程
- 当前代码默认 `section_data` 已经代表 intended hydraulic domain
  - 当前项目语义里，通常就是主河道域
  - 不再在 solver 内自动做复杂滩地裁切

## 4. `section_pos`

格式：

```python
section_pos["s0"] = [streamwise_x, 0.0]
```

当前主要使用第一列的河道方向位置。

## 5. `sim_data`

最小字段：

```python
sim_data = {
    "model_name": "demo",
    "sim_start_time": "2024-01-01 00:00:00.000000",
    "sim_end_time": "2024-01-01 00:00:02.000000",
    "time_step": 0.05,
    "save_min_interval": 0.05,
    "output_path": "/path/to/output",
    "CFL": 0.35,
    "n": 0.03,
}
```

当前 baseline 相关的关键可选项：

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

如果另一个 Codex 只做河网组装，不建议在网络层私自改这些默认语义，除非明确做新实验。

## 6. 初始化方式

常用的 3 种：

1. 常水深：

```python
river.Set_init_watr_depth(1.0)
```

2. 全域水深 profile：

```python
river.Set_init_water_depth_profile(depth_profile)
```

3. 常水位：

```python
river.Set_init_water_level(level)
```

最常用的是第 2 种，因为它适合直接从解析解、参考剖面或 reach 间传递结果初始化。

## 7. 时间推进

最常见调用方式：

```python
for current_time in river.Evolve(fine=False, yield_step=0.05):
    pass
```

说明：
- `Evolve()` 内部会：
  - 初始化断面表
  - 做边界更新
  - 计算界面通量/源项
  - 做保守量更新
  - 做摩阻子步
  - 做 dry admissibility
  - 回刷派生状态
- `yield_step` 控制对外报告节奏，不等于内部 CFL 步长

## 8. 边界的推荐用法

最常见方式是给 `river.boundary_updater` 赋一个函数：

```python
def boundary_updater(r):
    ...

river.boundary_updater = boundary_updater
```

常用边界函数：
- `InBound_In_Q2`
- `InBound_Fix_level_V3`
- `OutBound_Fix_level_V3`
- `OutBound_Free_Outfall`

如果要做河网组装，建议网络层只负责：
- 计算每条 reach 此刻的边界目标量
- 调用这几个边界接口

不要把单河段内部的 near-dry、general-chi、HR 通量逻辑复制到网络层。

## 9. 推荐示例

- 矩形单河段：`examples/minimal_single_reach_call.py`
- 不规则断面动态例子：`examples/minimal_irregular_dynamic_call.py`

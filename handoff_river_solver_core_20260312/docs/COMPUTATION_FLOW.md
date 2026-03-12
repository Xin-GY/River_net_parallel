# Computation Flow

下面只说明当前 `single_river_clean.py` 的主链，不讨论被拒绝的实验分支。

## 1. 初始化

入口类：

```python
class River(Process)
```

初始化阶段主要做：

1. 读取 `sim_data`
2. 设置 baseline 开关和阈值
3. 建立 cell / section / ghost layout
4. 准备状态量数组：
   - `S`
   - `Q`
   - `water_depth`
   - `water_level`
   - `U`
   - `C`
   - `FR`
   - `PRESS`
   - `R`
   - `DEB`

## 2. CrossSectionTable 构建

关键函数：

```python
Create_cross_section_table()
```

当前 baseline 特征：
- exact dry-state anchor 已显式加入
- `DEB` 按 section-local roughness 构建
- `width(A)` 对正湿支单独插值

这一步构出统一 `CrossSectionTable`，供：
- refresh
- general HR
- boundary/general-chi
共同消费

## 3. 时间推进主循环

主入口：

```python
Evolve()
```

每个内部步大致顺序：

1. 应用边界
2. 计算界面通量/源项
3. `Assemble_Flux_2()`
   - conservative increment
   - friction substep
   - explicit dry admissibility
4. `Update_cell_proprity2()`
5. `_refresh_cell_state()`
6. 输出/保存

## 4. 矩形与不规则断面两条界面路径

矩形路径：

```python
_compute_rectangular_hr_interface_flux()
```

不规则断面路径：

```python
_compute_general_hr_interface_flux()
```

当前项目已经做过结构拆分，但没有把 `general HR` 主公式作为当前第一修复层。

## 5. 状态 ownership

当前应理解为：

- `Assemble_Flux_2()`
  - owner: conservative `S/Q` 更新
  - owner: friction substep
  - owner: explicit dry admissibility

- `_refresh_cell_state()`
  - owner: 派生量回刷
  - 回刷：
    - `water_depth`
    - `water_level`
    - `U`
    - `C`
    - `FR`
    - `PRESS`
    - `R`
    - `DEB`

这是当前版本相对早期版本的一个重要结构变化：最终 derived-state refresh 已唯一化。

## 6. near-dry 共享链

当前 baseline 里，near-dry 共享链已经包含几轮 accepted 修复：

1. still-wet near-dry cell 不再因为 `velocity_depth_limit` 被硬清 `Q`
2. explicit dry admissibility 不再允许仅凭 `depth <= water_depth_limit` 就把正面积 cell 判干
3. `_compute_near_dry_derived_state()` 中：
   - 保留 actual `U = Q / A_actual`
   - 软化 `C` regularization

这条链现在不仅服务矩形 case，也已经在 irregular dynamic path 上做过迁移验证。

## 7. irregular boundary/general-chi

当前 irregular fully-wet stage-boundary baseline：

```python
bc_use_general_chi = True
bc_general_chi_candidate_mode = "guarded_clamp"
bc_general_chi_guard_selector = "closure_q_delta"
bc_general_chi_guard_q_delta = 0.005
```

补充：
- `bc_use_order2_extrap`
- `bc_use_order2_extrap_flow`
- `bc_use_order2_extrap_stage`

这 3 个配置项必须正确从 `sim_data` 接入 runtime。这个 wiring 修复已经是 baseline 必需项。

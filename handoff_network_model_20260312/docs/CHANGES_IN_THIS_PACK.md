# Changes In This Pack

相对于最初 handoff 单河道包，这里额外补入了河网接入所需的修改。

## 1. 网络层兼容接口

在 `river_for_net.py` 中增加了：
- `boundary_face_discharge_left/right`
- `boundary_face_area_left/right`
- `boundary_face_width_left/right`
- `boundary_face_level_left/right`

用途：
- 供 `Rivernet.py` 在结点残差、Ac 构造、诊断输出中读取边界界面状态

## 2. Fine 断面重构守卫

在 `river_for_net.py` 中增加：
- `section_interpolation_enabled`

并保证：
- 无 `section_pos` 时不会误触发 Fine 插值报错
- `Fine_cell_property2()` 无插值器时会直接跳过

## 3. Fine 断面重构口径修正

`Fine_cell_property2()` 当前采用：
- 断面插值后整体回贴到拟合床线 `y_fit`

而不是：
- 直接把插值断面的 `y_min` 写成新的 `river_bed_height`

原因：
- 后者会把插值噪声直接注入床坡源项和通量链

## 4. general-chi 默认值接入 Islam

在 `Islam.py` 中把这些默认值接到了当前 handoff 流程：
- `ISLAM_BC_EXTRAP_ORDER2=1`
- `ISLAM_BC_GENERAL_CHI=1`
- `ISLAM_BC_GENERAL_CHI_CANDIDATE_MODE=guarded_clamp`
- `ISLAM_BC_GENERAL_CHI_GUARD_SELECTOR=closure_q_delta`
- `ISLAM_BC_GENERAL_CHI_GUARD_Q_DELTA=0.005`

## 5. 已修复但效果有限的数学错误

`CrossSectionTable.get_hydraulic_radius_by_area()` 已修回：
- 不再直接插值 `R`
- 统一按 `R = A / P`

说明：
- 这是数学上必须正确的修复
- 但对当前 Islam 矩形支路的 40h 指标改善很有限

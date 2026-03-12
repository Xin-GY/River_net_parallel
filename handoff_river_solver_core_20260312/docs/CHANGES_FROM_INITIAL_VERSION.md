# Changes From Initial Version

这里的“最初版本”指：

```text
code/original_reference/single_riever_base.py
```

这里不追求逐行 diff，而是只列对当前 baseline 真正重要的变化。

## 1. 结构级变化

### 1.1 状态 ownership 被拆清

当前版本相对最初版本，最重要的结构整理之一是：

- `Assemble_Flux_2()`
  - 负责 conservative `S/Q` 更新
  - 负责 friction substep
  - 负责 explicit dry admissibility
- `_refresh_cell_state()`
  - 负责最终 derived-state 回刷

这解决了早期版本里“更新、dry reset、派生量回刷、诊断 side effect 混在一起”的问题。

### 1.2 矩形 / 不规则 HR 路径都做过结构拆分

已经做过：
- `_compute_rectangular_hr_interface_flux()` 结构拆分
- `_compute_general_hr_interface_flux()` 结构拆分
- `boundary/general-chi` 结构拆分

注意：
- 这是结构清理，不等于重写主公式
- 当前 baseline 并没有把 `general HR` 主公式作为第一怀疑对象

## 2. 当前 baseline 必保留的数值修复

这些已经不是实验项，而是 baseline 组成部分。

### 2.1 干湿 / near-dry 共享链

1. `dry/near-dry head-cap` 修复
2. `InBound_In_Q2` 干床入流 wetting fallback
3. still-wet near-dry cell 保留 conservative `Q`
4. explicit dry admissibility narrowing
5. near-dry derived-state softening
6. `C` regularization 收窄

这些修复最初是在矩形 / 干溃坝线上明确暴露出来，但后续已经验证能迁移到 irregular dynamic path。

### 2.2 irregular boundary/general-chi

当前 accepted baseline：

```python
bc_use_general_chi = True
bc_general_chi_candidate_mode = "guarded_clamp"
bc_general_chi_guard_selector = "closure_q_delta"
bc_general_chi_guard_q_delta = 0.005
```

再加一条必须保留的 wiring 修复：

```text
90f03e8 fix: wire stage order2 extrapolation config
```

也就是必须把：
- `bc_use_order2_extrap`
- `bc_use_order2_extrap_flow`
- `bc_use_order2_extrap_stage`

从 `sim_data` 正确接入 `River.__init__`。

### 2.3 CrossSectionTable baseline 修复

1. exact dry-state table anchor
2. section-specific `DEB` roughness scope
3. `width(A)` 正湿支修复
4. datum owner 收敛到 table metadata

这些不是为了“更像 MASCARET 的多表族”，而是为了让当前统一 `CrossSectionTable` 在主河道-only 语义下自洽。

## 3. 明确不要并入 baseline 的实验分支

### 3.1 limiter / shock 路线

不要并入：
- explicit TVD limiter
- `eta_only`
- `q_only`
- 更窄 shock sensor 推广

### 3.2 irregular boundary/general-chi triplet 分量级实验

不要并入：
- `inner_only`
- `target_only`
- `second_only`
- `inner_target_only`
- 其他 triplet selector 扩展

原因很直接：
- 实验已经证明它们都比当前 accepted baseline 更差
- 当前 irregular boundary 主线已经阶段性封版

## 4. 当前版本相对最初版本的实质改动序列

下面这些 commit 是从“最初版本”一路走到当前 baseline 的关键节点：

1. `d491716 refactor: separate state refresh ownership`
2. `5621a66 refactor: split assemble side effects`
3. `6fa41b5 refactor: split rectangular hr interface structure`
4. `4c19197 refactor: split general hr interface structure`
5. `3ca01d6 refactor: split boundary general chi structure`
6. `56bd154 refactor: align cross section table datum consumers`
7. `c5433d6 fix: anchor cross section table dry state`
8. `4c5f054 fix: scope deb tables by section roughness`
9. `9f2fb43 fix: align width consumer with wet branch semantics`
10. `77ab88e fix: preserve q on near-dry wetted cells`
11. `4324daa fix: narrow explicit dry admissibility trigger`
12. `ccfe35a fix: soften near-dry derived state floor`
13. `d7a4056 fix: soften near-dry c regularization`
14. `55e16d4 fix: narrow irregular boundary chi clamp`
15. `90f03e8 fix: wire stage order2 extrapolation config`

如果另一个 Codex 只是要复用当前 reach solver，不建议从 `single_riever_base.py` 重新抄一遍再自己补这些修复，而应该直接以 `single_river_clean.py` 为当前源。

## 5. 当前不应重新打开的战线

在没有新证据前，不建议优先回头怀疑：
- friction semi-implicit
- DEB builder
- table builder
- `general HR` 主公式
- `boundary` 主公式整体重写

当前版本已经验证到的结论是：
- irregular boundary/general-chi accepted baseline 在扩覆盖下成立
- irregular dynamic 主线没有出现新的第一失败模式

这意味着：当前 reach solver 更适合被拿去做上层河网组装，而不是继续盲目重构主公式。

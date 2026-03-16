# cpp update cell before/after

## test setup

- compare target: accepted phase-3 exact path
- fixed config:
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`
- only toggle:
  - `ISLAM_CPP_USE_UPDATE_CELL=1`

## 10m result

### accepted phase-3 baseline

- evolve/model time: `1.457326 s`
- steps: `181`

### cpp update-cell candidate

- summary:
  - `reports/cpp_fullchain_pushdown_updatecell_10m_summary.json`
- evolve/model time: `1.259714 s`
- evolve wall: `1.335645 s`
- steps: `181`

### raw speed delta

- evolve/model:
  - `-0.197612 s`
  - `-13.56%`

### exact compare

- compare:
  - `reports/cpp_fullchain_pushdown_updatecell_10m_compare.json`
- result:
  - `allclose = true`

## 2h result

### accepted phase-3 baseline

- evolve/model time: `11.400661 s`
- steps: `1482`

### cpp update-cell candidate

- summary:
  - `reports/cpp_fullchain_pushdown_updatecell_2h_summary.json`
- evolve/model time: `10.262386 s`
- evolve wall: `10.520188 s`
- steps: `1482`

### raw speed delta

- evolve/model:
  - `-1.138275 s`
  - `-9.98%`

## exact compare

- compare:
  - `reports/cpp_fullchain_pushdown_updatecell_2h_compare.json`
- result:
  - `allclose = true`

## 40h result

### accepted phase-3 baseline

- evolve/model time: `202.210932 s`
- steps: `29783`

### cpp update-cell candidate

- summary:
  - `reports/cpp_fullchain_pushdown_updatecell_40h_summary.json`
- evolve/model time: `177.525983 s`
- evolve wall: `181.702177 s`
- steps: `29783`

### raw speed delta

- evolve/model:
  - `-24.684949 s`
  - `-12.21%`

## exact compare

- compare:
  - `reports/cpp_fullchain_pushdown_updatecell_40h_compare.json`
- result:
  - `allclose = true`

## interpretation

- 这条 C++ kernel 现在已经从“高潜力实验态”升级为“accepted exact 组成部分”。
- 它解决的是一块真正的大 native gap：
  - 2h `river_dispatch.Update_cell_proprity2.time` 从 `1.997687 s` 降到 `0.215858 s`
- 当前本分支推荐 exact 配置应改为：
  - `ISLAM_CPP_USE_UPDATE_CELL=1`

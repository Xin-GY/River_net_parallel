# Caculate_Roe_matrix before/after

## compare target

baseline is the current accepted continuation exact config before Roe-matrix pushdown:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

candidate only adds:

- `ISLAM_CPP_USE_ROE_MATRIX=1`

## 10m

### baseline

- `evolve/model = 1.0746283531188965 s`

### candidate

- `evolve/model = 0.997236967086792 s`
- `evolve/wall = 1.0264809329528362 s`

### delta

- `-0.07739138603210449 s`
- `-7.20%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_roematrix_10m_compare.json`
- `allclose = true`

## 2h

### baseline

- `evolve/model = 8.403064250946045 s`

### candidate

- `evolve/model = 7.5613861083984375 s`
- `evolve/wall = 7.760811161017045 s`

### delta

- `-0.8416781425476074 s`
- `-10.02%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_roematrix_2h_compare.json`
- `allclose = true`

## 40h

### baseline

- `evolve/model = 142.21045446395874 s`

### candidate

- `evolve/model = 124.53437638282776 s`
- `evolve/wall = 128.4795877370052 s`

### delta

- `-17.67607808113098 s`
- `-12.43%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_roematrix_40h_compare.json`
- `allclose = true`

## hotspot effect

2h profiled metric:

- before:
  - `river_dispatch.Caculate_Roe_matrix.time = 0.962274 s` after assemble baseline? no, profiled candidate baseline was `0.962274 s`
- after:
  - `river_dispatch.Caculate_Roe_matrix.time = 0.073517 s`

40h profiled metric:

- before:
  - `river_dispatch.Caculate_Roe_matrix.time = 19.322687 s`
- after:
  - `river_dispatch.Caculate_Roe_matrix.time = 1.342151 s`

这说明这块 native kernel 已经把 `Roe_matrix` 的主要 arrays-heavy 外层循环基本收走了。

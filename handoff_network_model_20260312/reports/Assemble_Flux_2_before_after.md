# Assemble_Flux_2 before/after

## compare target

baseline is the current continuation working exact baseline before assemble pushdown:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

candidate only adds:

- `ISLAM_CPP_USE_ASSEMBLE=1`

## 10m

### baseline

- `evolve/model = 1.2669095993041992 s`

### candidate

- `evolve/model = 1.0746283531188965 s`
- `evolve/wall = 1.1028734549763612 s`

### delta

- `-0.19228124618530273 s`
- `-15.18%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_assemble_10m_v2_compare.json`
- `allclose = true`

## 2h

### baseline

- `evolve/model = 9.865381956100464 s`

### candidate

- `evolve/model = 8.403064250946045 s`
- `evolve/wall = 8.607171916984953 s`

### delta

- `-1.462317705154419 s`
- `-14.82%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_assemble_2h_compare.json`
- `allclose = true`

## 40h

### baseline

- `evolve/model = 177.52598333358765 s`

### candidate

- `evolve/model = 142.21045446395874 s`
- `evolve/wall = 146.15263089397922 s`

### delta

- `-35.315528869628906 s`
- `-19.89%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_assemble_40h_compare.json`
- `allclose = true`

## hotspot effect

2h profiled metric:

- before:
  - `river_dispatch.Assemble_Flux_2.time = 3.056615 s`
- after:
  - `river_dispatch.Assemble_Flux_2.time = 0.300105 s`

这说明这条 kernel 不只是 headline 更快，而是真的把 `Assemble_Flux_2` 的主要 per-cell Python gap 收走了。

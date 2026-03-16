# cpp nodechain commit before/after

## compare target

baseline is the current accepted continuation exact config before nodechain prebound-fast commit pushdown:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

candidate only adds:

- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`

## 10m

### baseline

- `evolve/model = 0.9273443222045898 s`

### candidate

- `evolve/model = 0.8605475425720215 s`
- `evolve/wall = 0.8896220889873803 s`

### delta

- `-0.06679677963256836 s`
- `-7.20%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_nodecommit_10m_compare.json`
- `allclose = true`

## 2h

### baseline

- `evolve/model = 7.022465467453003 s`

### candidate

- `evolve/model = 6.488842725753784 s`
- `evolve/wall = 6.694022400013637 s`

### delta

- `-0.5336227416992188 s`
- `-7.60%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_nodecommit_2h_compare.json`
- `allclose = true`

## 40h

### baseline

- `evolve/model = 115.94071912765503 s`

### candidate

- `evolve/model = 109.42589354515076 s`
- `evolve/wall = 113.50273791496875 s`

### delta

- `-6.5148255825042725 s`
- `-5.62%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_nodecommit_40h_compare.json`
- `allclose = true`

## hotspot effect

40h profiled metrics:

- `boundary_updater.total`
  - `54.287393 s -> 48.312066 s`
- `nodechain.total`
  - `76.496979 s -> 64.568132 s`
- `nodechain.apply_and_boundary_closure`
  - `30.729300 s -> 25.667796 s`
- `nodechain.final_apply`
  - `5.202304 s -> 4.317332 s`
- `nodechain.prebound_fast_hits`
  - `4010220`

这说明收益不是来自步数变化，而是来自 direct-fast nodechain closure/commit 链本身更深的 native ownership。

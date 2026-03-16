# Caculate_face_U_C before/after

## compare target

baseline is the current accepted continuation exact config before Face_U_C pushdown:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

candidate only adds:

- `ISLAM_CPP_USE_FACE_UC=1`

## 10m

### baseline

- `evolve/model = 0.997236967086792 s`

### candidate

- `evolve/model = 0.9273443222045898 s`
- `evolve/wall = 0.9552248299587518 s`

### delta

- `-0.06989264488220215 s`
- `-7.01%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_faceuc_10m_compare.json`
- `allclose = true`

## 2h

### baseline

- `evolve/model = 7.5613861083984375 s`

### candidate

- `evolve/model = 7.022465467453003 s`
- `evolve/wall = 7.223797142971307 s`

### delta

- `-0.5389206409454346 s`
- `-7.13%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_faceuc_2h_compare.json`
- `allclose = true`

## 40h

### baseline

- `evolve/model = 124.53437638282776 s`

### candidate

- `evolve/model = 115.94071912765503 s`
- `evolve/wall = 119.87252113601426 s`

### delta

- `-8.59365725517273 s`
- `-6.90%`

### exact compare

- `reports/cpp_fullchain_pushdown_next_faceuc_40h_compare.json`
- `allclose = true`

## hotspot effect

2h profiled metric:

- before:
  - `river_dispatch.Caculate_face_U_C.time = 0.483796 s`
- after:
  - `river_dispatch.Caculate_face_U_C.time = 0.028639 s`

40h profiled metric:

- before:
  - `river_dispatch.Caculate_face_U_C.time = 9.305142 s`
- after:
  - `river_dispatch.Caculate_face_U_C.time = 0.590912 s`

这说明 `Face_U_C` 这块的 arrays-heavy 外层界面循环已经基本被 native kernel 收走了。

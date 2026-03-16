# C++ Nodechain Before / After

## Baseline

- branch checkpoint before this phase:
  - `13b80ca`
- exact mode:
  - single-process only
  - `ISLAM_USE_CPP_EVOLVE=1`
  - `ISLAM_CPP_THREADS=0`
  - `ISLAM_USE_CYTHON_NODECHAIN=1`
  - `ISLAM_USE_CYTHON_ROE_FLUX=1`
  - `ISLAM_CPP_USE_UPDATE_CELL=0`

## Accepted Phase-3 Variant

- additional flag:
  - `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- semantics:
  - exact wrapper bypass only
  - no approximate closure
  - no multiprocessing
  - no FAST mode

## Validation Status

### Failed prototypes kept out of the exact path

- direct stage-boundary numeric closure from inside `cython_node_iteration.pyx`
  - result: segmentation fault on 10m smoke
- width lookup by direct table ref inside residual/Ac
  - result: tiny but real drift in `internal_node_history.csv`

### Accepted wrapper-bypass candidate

- 10m compare:
  - `allclose = true`
- 2h compare:
  - `allclose = true`
- 40h compare:
  - `allclose = true`

## Speed Before / After

### 10m

- baseline evolve/model time:
  - `1.459050 s`
- wrapper-bypass evolve/model time:
  - `1.457326 s`
- delta:
  - `-0.001724 s`
  - about `0.12%` faster

### 2h

- baseline evolve/model time:
  - `12.330136 s`
- wrapper-bypass evolve/model time:
  - `11.400661 s`
- delta:
  - `-0.929476 s`
  - about `7.54%` faster

### 2h perf counters

- `boundary_updater.total`:
  - `4.076405 s -> 3.969430 s`
  - delta `-0.106975 s`
- `nodechain.apply_and_boundary_closure`:
  - `2.771246 s -> 2.681397 s`
  - delta `-0.089849 s`
- `nodechain.final_apply`:
  - `0.261257 s -> 0.253436 s`
  - delta `-0.007820 s`

### 40h

- baseline evolve/model time:
  - `206.306033 s`
- wrapper-bypass evolve/model time:
  - `202.210932 s`
- delta:
  - `-4.095101 s`
  - about `1.98%` faster

## Compare Artifacts

- 10m:
  - `cpp_nodechain_wrapperbypass_10m_summary.json`
  - `cpp_nodechain_wrapperbypass_10m_compare.json`
- 2h:
  - `cpp_nodechain_wrapperbypass_2h_summary.json`
  - `cpp_nodechain_wrapperbypass_2h_compare.json`
  - `cpp_nodechain_wrapperbypass_2h_perf_summary.json`
  - `cpp_nodechain_wrapperbypass_2h_perf.json`
- 40h:
  - `cpp_nodechain_wrapperbypass_40h_summary.json`
  - `cpp_nodechain_wrapperbypass_40h_compare.json`

## Interpretation

The accepted exact gain in this phase comes from cutting wrapper overhead, not from changing the low-level closure math. The next bottleneck is still the rest of the hot path:

1. `Caculate_Roe_Flux_2`
2. `Update_cell_proprity2`
3. remaining Python/Cython/C++ step orchestration

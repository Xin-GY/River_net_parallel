# Assemble Deep Implementation

## What changed

- `river_for_net.py`
  - added `ISLAM_CPP_USE_ASSEMBLE_DEEP`
  - routed `Assemble_Flux_2()` to a new deep native path before the older post-step helper
- `cython_river_kernels.pyx`
  - added `assemble_flux_exact_deep_cpp()`
  - passed full stage arrays and update-cell plan refs into the deeper C++ kernel
- `cpp/river_kernels.hpp/.cpp`
  - added `rivernet::assemble_flux_exact_deep`
  - fused:
    - flux accumulation into `Flux`
    - conservative `S/Q` increment
    - exact Manning post-step
    - conservative dry admissibility
- `tools/profile_cpp_exact_serial.py`
  - added `--use-cpp-assemble-deep` for isolated benchmarking

## What stayed out

- no `Update_cell_proprity2` rewrite
- no `_refresh_cell_state` reuse
- no fullstep / dispatch changes
- no external-boundary-deep code path

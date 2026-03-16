## Goal

Push `Caculate_Roe_Flux_2` from “compiled helper around Python-owned tables and tuple-return interface calls” to a deeper native ownership path for the general-HR exact flux loop.

## Accepted baseline before this change

- 10m: `0.860548 s`
- 2h: `6.488843 s`
- 40h: `109.425894 s`

Current accepted phase before this step:

- `ISLAM_USE_CPP_EVOLVE=1`
- `ISLAM_CPP_THREADS=0`
- `ISLAM_USE_CYTHON_NODECHAIN=1`
- `ISLAM_USE_CYTHON_NODECHAIN_DIRECT_FAST=1`
- `ISLAM_USE_CYTHON_NODECHAIN_PREBOUND_FAST=1`
- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_UPDATE_CELL=1`
- `ISLAM_CPP_USE_ASSEMBLE=1`
- `ISLAM_CPP_USE_ROE_MATRIX=1`
- `ISLAM_CPP_USE_FACE_UC=1`
- `ISLAM_USE_CPP_BRIDGE_DIRECT_DISPATCH=0`

## Ownership gap being removed

Before this step, the accepted general-HR Roe flux path still had these costs:

- per-face loop was compiled, but still driven by Python tuples of `CrossSectionTableCython`
- `compute_general_hr_flux_interface(...)` returned Python tuples for every face
- flux corrections were gathered/scattered through Python-owned intermediate values
- table ownership stayed in Python/Cython objects rather than a persistent native plan

That meant `Caculate_Roe_Flux_2` was compiled, but not yet deeply native-owned.

## Plan

1. Add a persistent prebound face plan:
   - `CppGeneralHrFluxPlan`
   - stores left/right `TableView` vectors for every interface
2. Add a new native kernel in `cpp/river_kernels.cpp`:
   - exact general-HR per-face loop
   - exact positivity control
   - exact pressure correction writeback
   - exact rain-source writeback
3. Keep the existing accepted path as fallback:
   - new flag: `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`
4. Preserve exactness constraints:
   - same `float64` math
   - same interface order
   - same donor selection and positivity scaling order
   - no formula changes

## Expected payoff

Primary expected gain is inside:

- `river_dispatch.Caculate_Roe_Flux_2.time`

Secondary expected gain:

- reduced Python/Cython object churn during general-HR interface evaluation
- slightly lower pressure on downstream stage orchestration

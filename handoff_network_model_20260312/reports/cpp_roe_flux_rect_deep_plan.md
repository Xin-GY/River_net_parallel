# C++ Rectangular Roe Flux Deep Plan

## Goal

Push the accepted exact rectangular Roe-flux path from:

- Python-owned per-face loop
- Python dict-based interface state
- Python gather/project/solve/write-back chain

to:

- native-owned per-face loop
- native-owned flux/source zeroing
- native-owned exact dry/wet branch logic
- native-owned flux and source write-back

while keeping:

- exact formulas
- exact branch order
- exact `float64` semantics
- exact update order

## Why This Path

Fresh accepted-path audit showed:

- `river_step.flux = 42.333267 s` on the clean 40h replay
- 2h cProfile hotspot chain:
  - `Caculate_Roe_Flux_2`
  - `_caculate_roe_flux_rectangular_hr`
  - `_compute_rectangular_hr_interface_flux`
  - `_solve_rectangular_hr_roe_flux`

General-HR deep ownership was already present. The remaining gap was specifically the rectangular-HR path.

## Scope

Only push the rectangular path that is active when:

- `use_rectangular_hr_flux = True`
- `constant_rectangular_width is not None`
- `use_explicit_tvd_limiter = False`

If the TVD limiter path is active, fall back to the existing Python implementation unchanged.

## Native Ownership Push

The new native kernel owns:

1. per-face loop over `0..cell_num`
2. exact center-state load from arrays
3. hydrostatic reconstruction
4. exact rectangular Roe solve
5. exact dry/dry, wet/dry-right, dry/wet-left, wet/wet branch logic
6. pressure correction write-back
7. rain-source write-back
8. stage-array zeroing for:
   - `Flux_LOC`
   - `Flux_Source_left`
   - `Flux_Source_right`
   - `Flux_Source_center`
   - `Flux_Friction_left`
   - `Flux_Friction_right`
   - `cell_press_source`

## Feature Flag

- new flag: `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`

Default remains off until strict compare and 40h full-case gain are confirmed.

## Exact Risk Points

- preserve the exact Python branch order for all dry/wet combinations
- preserve `roe_entropy_fix` and `roe_entropy_fix_factor`
- preserve rectangular pressure and flux formulas exactly
- do not reintroduce donor-cell positivity limiting for the rectangular path
- keep all outputs on the same arrays in the same order

## Rollback

- leave flag off
- keep Python fallback as the active path
- do not change accepted exact configuration unless 10m, 2h, and 40h all pass strict compare and 40h gives real net gain

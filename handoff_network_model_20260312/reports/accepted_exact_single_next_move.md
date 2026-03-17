# Accepted Exact Single Next Move

## Chosen Direction

`Roe flux remaining ownership`, specifically the **rectangular HR** path in `Caculate_Roe_Flux_2`.

## Why This Is The Best Single Move

The fresh accepted exact audit showed:

- `river_step.flux = 42.333267 s` on the 40h clean re-audit replay
- 2h cProfile drilldown:
  - `_caculate_roe_flux_rectangular_hr = 3.408339 s`
  - `_compute_rectangular_hr_interface_flux = 3.170979 s`
  - `_solve_rectangular_hr_roe_flux = 1.731337 s`

That is the largest remaining blocker with both:

1. large full-case weight
2. clearly visible Python ownership

## Why This Is Not A Repeat Of A Rejected Direction

This is not:

- refresh deep
- residual/Jacobian deep
- fullstep loop
- build-flag experimentation
- dispatch reshaping
- the already-accepted **general-HR** deep flux path

The accepted branch family already deepened the general-HR ownership. The rectangular-HR flux path was still running as a Python-owned per-face loop with Python dict-based interface states.

## Expected Cost To Target

Primary target cost:

- `river_step.flux = 42.333267 s` on the fresh 40h replay

Even a partial ownership push here had a much higher expected payoff than revisiting nodechain residual/Jacobian or reopening refresh/fullstep no-go directions.

## Exact Risk Points

- preserve the rectangular dry/dry, wet/dry-right, dry/wet-left, and wet/wet branch order exactly
- keep `float64` semantics in flux assembly
- keep Roe entropy fix semantics unchanged
- keep rain-source write-back order unchanged
- do not accidentally re-enable donor-cell positivity logic for the rectangular path
- do not engage when the explicit TVD limiter path is active

## Rollback Strategy

Keep the new path behind a dedicated flag:

- `ISLAM_CPP_USE_ROE_FLUX_RECT_DEEP=1`

If any compare fails or 40h regresses, the rollback is simply:

- leave the flag off
- keep the implementation documented as an experiment
- do not change the accepted exact configuration

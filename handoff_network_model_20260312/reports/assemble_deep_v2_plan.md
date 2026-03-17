# Assemble Deep V2 Plan

## Goal

Re-run the exact `Assemble_Flux_2` deeper ownership pushdown on top of the accepted global-CFL baseline `689ae0b`, rather than benchmarking the older preserved prototype directly.

## Baseline

- accepted source branch: `feature/cpp-exact-accepted-after-global-cfl`
- accepted source commit: `689ae0b`
- accepted 40h gate to beat: `60.74310255050659 s`

## Ownership Gap On 689ae0b

Current `Assemble_Flux_2()` still has mixed ownership:

- Python owns `_apply_explicit_conservative_increment()`
- Cython/C++ own only the Manning post-step and conservative dry admissibility
- Python still owns stage-level entry, orchestration, and the pre-poststep conservative write-back path

This leaves the stage as:

1. Python conservative flux increment
2. native Manning post-step
3. native dry admissibility
4. Python returns control to the next stage

## V2 Pushdown Scope

Only push the assemble stage deeper:

- conservative flux increment
- exact Manning / friction post-step
- conservative dry admissibility
- stage-local `Flux` write-back
- stage-local scratch and cell-length use

Do not expand scope into:

- `Update_cell_proprity2`
- `_refresh_cell_state`
- nodechain tail
- fullstep loop
- external-boundary-deep logic

## Implementation Shape

- keep existing `ISLAM_CPP_USE_ASSEMBLE=1`
- add isolated flag `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`
- let deep mode short-circuit the old Python conservative increment path
- reuse the existing update-cell plan/table binding so the new kernel can consume prebound table views
- keep ordering and floating-point semantics identical to the accepted path

## Exact Risks

- flux array indexing must remain consistent with the Python layout
- the conservative decrement on `S/Q` must use the same sign and cell/face mapping
- dry admissibility must match the accepted path exactly
- friction post-step must remain in the same order after the conservative increment

## Acceptance

- 10m / 2h / 40h strict compare all pass
- 40h `evolve/model time < 60.74310255050659 s`

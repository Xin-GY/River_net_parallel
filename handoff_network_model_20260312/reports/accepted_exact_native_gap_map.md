# Accepted Exact Native Gap Map

## One-Step Ownership Map Before This Round

This map describes the accepted exact path at `9535623`, before any new implementation in this re-audit round.

| Step stage | Current main layer | Ownership status | Remaining gap |
| --- | --- | --- | --- |
| `boundary_updater / Update_boundary_conditions` | Python + Cython | mixed | step shell still Python-owned |
| internal node apply/closure | Cython + native helper | substantial native ownership | tail orchestration still mixed, but no obvious exact push remained except already-rejected refresh variants |
| internal node residual / Ac | Cython | already small | not first-order |
| internal node final apply / commit | Cython + native cache | partially native-owned | no longer the largest cost after `9535623` |
| `Caculate_face_U_C` | Python wrapper + C++ kernel | substantial native-owned | wrapper ownership only |
| `Caculate_Roe_matrix` | Python wrapper + C++ kernel | substantial native-owned | wrapper ownership only |
| `Caculate_source_term_2` | Python / NumPy | helper-owned | still Python-owned, but not first-order |
| `Caculate_Roe_Flux_2` general-HR path | Python wrapper + C++ deep kernel | substantial native-owned | general-HR deep path already in place |
| `Caculate_Roe_Flux_2` rectangular-HR path | Python | helper-owned only | **main remaining flux ownership gap** |
| `Assemble_Flux_2` | Python wrapper + C++ kernel | substantial native-owned | wrapper ownership only |
| `Update_cell_proprity2` | Python wrapper + C++ kernel | substantial native-owned | surrounding refresh/state exposure still mixed |
| global CFL / dt reduction | Python / NumPy | helper-owned | still fully stage-owned by Python |

## Key Recheck

The fresh audit invalidates the lazy assumption that “Roe flux is already done” just because:

- `ISLAM_USE_CYTHON_ROE_FLUX=1`
- `ISLAM_CPP_USE_ROE_FLUX_DEEP=1`

Those flags only cover the accepted deep path for **general-HR** flux ownership. The **rectangular-HR** per-face path remained Python-owned, and that is where the remaining first-order flux cost sat.

## What This Means

- nodechain is still large, but its remaining obvious deeper routes are either already accepted or already rejected.
- the only clean, non-redundant first-order native gap left in the accepted path is the rectangular Roe-flux ownership chain:
  - state gather
  - face projection
  - Roe solve
  - flux write-back
  - rain-source write-back

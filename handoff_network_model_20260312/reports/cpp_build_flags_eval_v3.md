# C++ Build Flags Eval v3

## Scope

This evaluation was run only after the accepted deep-commit exact path was stable.

Accepted exact baseline for this branch family:

- commit: `9535623`
- 10m model time: `0.6676914691925049 s`
- 2h model time: `5.10357141494751 s`
- 40h model time: `91.32992911338806 s`

## What was tested

I added opt-in build flags to:

- `build_cython_cross_section.py`
- `build_cython_exact_kernels.py`
- `build_cpp_exact_kernels.py`

Environment toggles:

- `ISLAM_BUILD_USE_NDEBUG=1`
- `ISLAM_BUILD_USE_MARCH_NATIVE=1`

## Important note

In this conda toolchain, the default extension compile command already includes `-DNDEBUG`.

That means the only meaningful new optimization here was effectively:

- `-march=native`

## Result

The `-march=native` build is rejected for this exact line.

Observed 10m result:

- accepted: `181` steps, `0.6676914691925049 s`
- candidate: `7494` steps, `22.017317295074463 s`
- strict compare: fail

Observed 2h result:

- accepted: `1482` steps, `5.10357141494751 s`
- candidate: `8823` steps, `25.89154863357544 s`
- strict compare: fail

Failure mode:

- step count exploded
- `cfl_history.csv` and `internal_node_history.csv` shape changed
- this is not a tolerable floating-point epsilon issue; it is a full exact-path semantic drift

## Decision

- keep the opt-in build-flag infrastructure
- reject `ISLAM_BUILD_USE_MARCH_NATIVE=1` for the accepted exact path
- do not run 40h under this build; 10m and 2h already prove it is invalid for exact use

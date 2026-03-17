# C++ Speed Report

## Best accepted path in this continuation line

There is no new accepted exact candidate beyond the inherited `9535623` checkpoint.

Current best exact path remains:

- 10m: `0.6676914691925049 s`
- 2h: `5.10357141494751 s`
- 40h: `91.32992911338806 s`

## This round's outcomes

### 1. Refresh-deep ownership

- inline Cython refresh:
  - faster in 10m
  - rejected because exact compare failed
- single-cell C++ exact refresh:
  - exact on 10m and 2h
  - rejected because it was materially slower than accepted baseline

### 2. Build flags

- `-march=native` was evaluated through the new opt-in build toggles
- it is rejected for this exact line because it changed the step schedule catastrophically

## Net result

This continuation branch improves documentation, rejection evidence, and build-flag control, but does **not** produce a new faster accepted exact path.

The best exact performance remains the `9535623` configuration at:

- `40h evolve/model = 91.32992911338806 s`

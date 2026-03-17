# C++ Error Report

## Accepted baseline

Accepted exact reference:

- commit `9535623`
- 10m / 2h / 40h strict compare all passed

## Refresh-deep experiments

### Inline Cython refresh

Status:

- rejected

Reason:

- not exact

Failure signature:

- 10m strict compare failed
- CFL history drifted
- global dt diverged

### Single-cell C++ exact refresh

Status:

- exact on 10m and 2h
- rejected for speed, not for correctness

## Build-flags experiment

### `-march=native`

Status:

- rejected

Reason:

- exact compare failed decisively on 10m and 2h

Failure signature:

- 10m steps: `181 -> 7494`
- 2h steps: `1482 -> 8823`
- `cfl_history.csv` and `internal_node_history.csv` row counts changed

Interpretation:

- this is not a tiny rounding deviation
- this build changes the accepted exact path enough to invalidate it

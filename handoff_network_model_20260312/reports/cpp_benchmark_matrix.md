# Assemble Deep Exact Benchmark Matrix

## Timing Policy

- headline metric: `evolve/model time`
- initialization excluded
- single-process exact only

## Variants

### Accepted exact baseline

- branch/checkpoint: `feature/cpp-exact-accepted-reaudit-next@9a7c094`
- config:
  - accepted exact flags
  - `ISLAM_CPP_USE_ASSEMBLE_DEEP=0`

### Fresh replay on this branch

- same code as `9a7c094`
- replayed in the clean continuation worktree

### Candidate

- fresh replay plus:
  - `ISLAM_CPP_USE_ASSEMBLE_DEEP=1`

## Results

| Variant | 10m evolve (s) | 2h evolve (s) | 40h evolve (s) | 40h wall (s) | Strict compare |
| --- | ---: | ---: | ---: | ---: | --- |
| Accepted historical `9a7c094` | `0.912919` | `6.680291` | `65.237010` | `69.804079` | yes |
| Fresh replay | `0.926752` | `7.167058` | `74.175709` | `78.970642` | yes |
| Candidate `+ ISLAM_CPP_USE_ASSEMBLE_DEEP=1` | `0.965080` | `6.509730` | `68.212999` | `74.039133` | yes |

## Gate Verdict

- exactness gate: pass
- performance gate against accepted baseline: fail

Reason:

- `68.212999 s` is still slower than the accepted exact reference `65.237010 s`

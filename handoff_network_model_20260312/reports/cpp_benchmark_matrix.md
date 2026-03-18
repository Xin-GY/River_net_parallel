# CPP Benchmark Matrix

## Current Accepted Reference

- branch: `feature/cpp-exact-after-assemble-source-deep-v1`
- commit: `c92a3ca`

| case | model/evolve time (s) | strict compare |
| --- | ---: | --- |
| 10m | accepted on source-deep branch | pass |
| 2h | accepted on source-deep branch | pass |
| 40h | `34.265936` | pass |

## UpdateCell V2 Round

| phase | action | outcome |
| --- | --- | --- |
| 0 | clean continuation from `c92a3ca` | pass |
| 1 | fresh update-cell audit | no-go |
| 2 | implementation | not started |
| 3 | exact compare | not run |
| 4 | threads recheck | not applicable |

## Why No New Benchmark Row Exists

The round stopped after phase 1 because the fresh audit showed:

- the accepted update-cell kernel already owns the heavy state-exposure work
- the visible remaining wrapper shell is too thin to justify a dedicated `updatecell_v2` implementation
- the raw remaining heavy stages are still `nodechain / boundary_updater`, whose obvious deeper routes remain too close to rejected exact families

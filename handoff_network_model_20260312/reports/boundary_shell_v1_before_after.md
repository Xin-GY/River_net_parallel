# Boundary Shell V1 Before/After

## Fresh 40h Replay On This Branch

These numbers come from the same no-netcdf replay harness used for both baseline and candidate in this worktree.

| mode | exact | 40h model/evolve time (s) | boundary_updater.external (s) | boundary_updater.total (s) | nodechain.total (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| baseline `ISLAM_CPP_USE_BOUNDARY_SHELL_DEEP=0` | yes | `43.934351` | `12.996334` | `29.933907` | `31.562714` |
| grouped deep-shell attempt | no | `39.838713` | `11.047204` | `27.620337` | `32.814130` |
| final exact deep-shell v1 | yes | `44.538749` | `14.989032` | `32.342391` | `34.368405` |

## Interpretation

- grouped batching had the only clear speed win, but failed 40h exact compare
- exact deep-shell v1 restores numerical identity, but loses the grouped speed win
- on the same local A/B replay harness, final exact v1 is slower than baseline by about `0.604398 s`

## Historical Accepted Gate Reference

User-provided accepted exact reference from `445c2c9`:

- 40h `evolve/model time = 47.05382442474365 s`

Final exact boundary-shell v1 is below that historical gate:

- `44.538749 s < 47.053824 s`

But because the same-harness fresh replay baseline is still faster than the candidate, this branch should be treated as:

- exact
- documented
- below accepted gate for promotion

rather than a true new accepted exact upgrade.

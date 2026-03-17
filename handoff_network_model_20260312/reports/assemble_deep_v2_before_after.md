# Assemble Deep V2 Before/After

## Reference Frames

- historical accepted gate: `689ae0b` at `60.74310255050659 s`
- fresh replay on this branch before v2: `50.94107961654663 s`
- v2 candidate: `47.05382442474365 s`

## 40h Before/After On Fresh Replay

- `river_step.assemble`: `5.869043 s -> 2.428812 s`
- `river_step.update_cell`: `2.976607 s -> 2.673096 s`
- `river_step.source`: `1.269551 s -> 1.244976 s`
- `river_step.roe_matrix`: `1.295697 s -> 1.277582 s`
- `river_step.face_uc`: `0.718905 s -> 0.710665 s`
- `dt_update.global_cfl`: `0.697966 s -> 0.667256 s`
- `nodechain.total`: `33.988113 s -> 34.057932 s`
- `boundary_updater.total`: `32.159558 s -> 32.375613 s`

## Net Effect

- fresh replay gain: `50.941080 s -> 47.053824 s`
- fresh replay speedup: `1.083x`
- gain relative to historical accepted gate: `60.743103 s -> 47.053824 s`
- historical-gate speedup: `1.291x`

## Interpretation

The deeper assemble ownership does exactly what the old prototype suggested:

- the local assemble stage drops sharply
- update/follow-on river stages get a small secondary benefit

On the new global-CFL baseline, the previous blocker that prevented acceptance is gone, so the local assemble win now survives at full 40h scale and produces a net accepted gain.

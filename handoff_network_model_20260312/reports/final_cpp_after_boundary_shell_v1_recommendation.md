# Final CPP After Boundary Shell V1 Recommendation

## Result

`boundary_shell_v1` should be kept as an exact documented prototype, not promoted as a new accepted exact result.

## Why

### Exactness

Final repaired candidate passes:

- 10m strict compare
- 2h strict compare
- 40h strict compare

### Performance

Same-harness 40h replay:

- baseline: `43.93435072898865 s`
- final exact candidate: `44.53874897956848 s`

That is a regression of about `0.604398 s`.

### Important nuance

The final exact candidate is still below the historical accepted reference:

- historical accepted `445c2c9`: `47.05382442474365 s`
- final exact candidate: `44.53874897956848 s`

But the apples-to-apples A/B replay on this branch does not show a real speed win, so promotion would not be technically defensible.

## What Was Learned

1. The boundary routing/dispatch shell can be pushed down behind a feature flag without breaking exactness.
2. Shared evaluator batching is not safe enough for 40h exact on this case, even though it passes 10m and 2h.
3. The exact-preserving shell-only version does not recover enough speed once grouped batching is removed.

## Current Top Blocker

Current raw Top 1 remains `boundary_updater / nodechain`.

But this round further narrows the story:

- formula bodies are not the first issue here
- grouped evaluator reuse is too risky for exact
- shell-only deepening by itself is not enough to produce a clean 40h win

## Recommendation

If we continue from `445c2c9`, the next round should not blindly continue this boundary-shell line. We should re-audit the remaining blocker landscape again and only pick one new point if it is clearly outside the already-rejected refresh/fullstep/external-boundary-deep families.

## Explicit No-Go List

Do not reopen:

- refresh deep
- residual / Jacobian deep
- fullstep / dispatch experiments
- external-boundary-deep
- boundary grouped evaluator batching from this branch
- FAST_MODE
- Python multiprocessing / threading
- `-march=native`

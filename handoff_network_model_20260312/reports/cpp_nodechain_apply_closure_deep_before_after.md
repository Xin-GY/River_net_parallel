# cpp nodechain apply/closure deep before after

## benchmark scope

只统计 `evolve/model time`，不计初始化。

对比对象：

- before: `feature/cpp-exact-evolve-flux-residual-fullstep@d26ea2a`
- after: current branch with `ISLAM_CPP_USE_NODECHAIN_DEEP_APPLY=1`

## exact compare

- 10m: pass
- 2h: pass
- 40h: pass

40h compare file:

- `reports/cpp_nodechain_deepapply_40h_compare.json`

## headline timing

### 10m

- before: `0.843206 s`
- after: `0.650956 s`
- delta: `-0.192250 s`
- speedup: `1.295x`

### 2h

- before: `6.374767 s`
- after: `5.090823 s`
- delta: `-1.283943 s`
- speedup: `1.252x`

### 40h

- before: `106.473473 s`
- after: `92.091939 s`
- delta: `-14.381533 s`
- speedup: `1.156x`

第一里程碑结果：

- `40h exact evolve/model < 100 s` 已达成

## nodechain perf breakdown

### 40h before

- `boundary_updater.total = 48.633332 s`
- `nodechain.total = 65.117052 s`
- `nodechain.apply_and_boundary_closure = 25.879760 s`
- `nodechain.residual_and_ac = 1.742821 s`
- `nodechain.final_apply = 4.360243 s`
- `nodechain.cython_to_python_boundary_calls = 4010220`
- `nodechain.cython_to_python_width_calls = 3414560`

### 40h after

- `boundary_updater.total = 34.411285 s`
- `nodechain.total = 36.756061 s`
- `nodechain.apply_and_boundary_closure = 14.925780 s`
- `nodechain.residual_and_ac = 0.213633 s`
- `nodechain.final_apply = 2.637463 s`
- `nodechain.cython_to_python_boundary_calls = 0`
- `nodechain.cython_to_python_width_calls = 0`
- `nodechain.deep_apply_hits = 4010220`

### 40h deltas

- `boundary_updater.total`: `-14.222047 s` (`-29.24%`)
- `nodechain.total`: `-28.360991 s` (`-43.56%`)
- `apply_and_boundary_closure`: `-10.953980 s` (`-42.33%`)
- `residual_and_ac`: `-1.529188 s` (`-87.74%`)
- `final_apply`: `-1.722780 s` (`-39.51%`)

## interpretation

这一步的收益已经说明：

1. 当前最大阻力确实在 nodechain ownership，而不是 Roe flux
2. 只要把 apply/closure 的 repeated binding、Python wrapper 和 width lookup 真正推下去，
   40h full case 就会给出稳定净收益
3. residual/Ac 的下降是附带收益，来源于：
   - deep face cache
   - direct width reuse
   - 不再反复跨 Python/Cython 边界取 boundary face state

## recommended next step

在这个新 accepted exact 基线上，下一优先级继续是：

1. residual / Ac / Jacobian / stopping deeper native ownership
2. final apply / state commit deeper native ownership
3. 然后再评估 fullstep native loop

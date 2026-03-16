## Native gap ranking

Accepted exact baseline:

- 10m `evolve/model` = `0.860548 s`
- 2h `evolve/model` = `6.488843 s`
- 40h `evolve/model` = `109.425894 s`

The gap between the current accepted exact line and a more fully native single-process evolve is no longer in “whether a bridge exists”. It is in who owns the hot data and outer loops.

## Ranked by expected 40h payoff

1. `Caculate_Roe_Flux_2` deep ownership
   - why ranked first:
     - still one of the largest river-step stages on both 2h and 40h
     - current accepted path is compiled, but not truly native-owned
     - per-face general-HR flux still flows through Python object tuples and tuple-return helpers
   - expected gain type:
     - reduce per-face table/state gather overhead
     - reduce tuple/object churn
     - reduce state scatter overhead

2. nodechain residual / `Ac` / solve-body nativeization
   - why ranked second:
     - nodechain remains the single largest total block
     - closure prebinding already helped, so the next missing ownership is clearly downstream of closure
   - expected gain type:
     - reduce residual assembly and convergence-loop orchestration
     - reduce final exact write-back cost

3. native full-step loop
   - why ranked third:
     - step-level boundary crossings remain, but direct-dispatch already showed that changing dispatch shape alone is not enough
     - full-step loop will matter more after the two largest ownership gaps above are reduced
   - expected gain type:
     - cut Python/Cython/C++ crossings per step
     - reduce marshaling and repeated stage-entry overhead

4. `Assemble_Flux_2` deeper ownership
   - already partly native, but still staged from Python
   - likely worthwhile after Roe flux because it sits immediately downstream

5. `Caculate_source_term_2`
   - still Python, but absolute cost is smaller than Roe flux and nodechain gaps

6. CFL / `dt` reduction and step commit
   - still Python-owned orchestration
   - important for final fullchain cleanup, but not the first payoff target

## Why this is not another bridge experiment

The current evidence says:

- wrapper-bypass and prebound exact closures brought real 40h gains
- direct-dispatch bridge reshaping did not

So the next iteration should only follow deeper ownership pushdown:

1. Roe flux deep ownership
2. nodechain residual / `Ac` native body
3. full-step native loop

If a later profile contradicts this ordering, the ranking should be updated, but until then this list is the only accepted pushdown order.

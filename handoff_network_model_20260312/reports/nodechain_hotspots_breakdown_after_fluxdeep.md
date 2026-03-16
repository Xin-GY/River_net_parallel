## Source

Primary source:

- `reports/cpp_nodechainpush_accepted_2h_perf.json`

40h accepted values from the parent accepted branch are used as the stability reference for ranking.

## Nodechain breakdown

### 2h accepted exact profile

- `nodechain.total = 5.399991 s`
- `nodechain.apply_and_boundary_closure = 2.308953 s`
- `nodechain.residual_and_ac = 0.145895 s`
- `nodechain.final_apply = 0.225879 s`
- `nodechain.predict = 0.001188 s`
- `nodechain.update_and_stopping = 0.001554 s`
- `nodechain.boundary_closure_calls = 336020`
- `nodechain.prebound_fast_hits = 336020`
- `nodechain.cython_to_python_boundary_calls = 336020`
- `nodechain.cython_to_python_width_calls = 306380`

### 40h accepted exact reference

- `nodechain.total = 65.117052 s`
- `nodechain.apply_and_boundary_closure = 25.879760 s`
- `nodechain.residual_and_ac = 1.742821 s`
- `nodechain.final_apply = 4.360243 s`
- `nodechain.cython_to_python_boundary_calls = 4010220`
- `nodechain.cython_to_python_width_calls = 3414560`

## Top 5 nodechain sub-hotspots

1. `apply_and_boundary_closure`
   - primary cost: crossing / marshaling + Python helper ownership
   - details:
     - one Python river closure call per branch
     - one Python commit/refresh path per successful closure

2. `final_apply`
   - primary cost: crossing / marshaling + Python helper ownership
   - details:
     - same closure/commit pattern paid again after convergence

3. `residual_and_ac`
   - primary cost: repeated lookup / rebinding
   - details:
     - width lookup from Python-owned cross-section methods
     - repeated `getattr` and object dereference

4. `cython_to_python_boundary_calls`
   - primary cost: crossing
   - details:
     - every accepted prebound fast closure still crosses into Python-owned river method code

5. `cython_to_python_width_calls`
   - primary cost: repeated lookup
   - details:
     - width lookups are still served through Python-owned river/cross-section access during residual/`Ac`

## Interpretation

The nodechain is no longer missing a fast closure formula. It is missing native ownership around that formula.

That is why the next implementation order is:

1. remove Python-owned apply/commit path around prebound fast closures
2. then reduce residual/`Ac` object and lookup cost
3. then fold the final apply/commit chain further into native ownership

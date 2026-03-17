# Untracked Inventory

This continuation worktree starts clean from accepted checkpoint `9a7c094`.

These generated artifacts exist in the source worktree
`/tmp/feature_cpp_exact_accepted_reaudit_next` and are intentionally excluded
from this continuation branch:

- Cython/C++ generated build outputs:
  - `cython_cpp_bridge.cpp`
  - `cython_cpp_bridge.cpython-311-x86_64-linux-gnu.so`
  - `cython_node_iteration.c`
  - `cython_node_iteration.cpython-311-x86_64-linux-gnu.so`
  - `cython_river_kernels.cpp`
  - `cython_river_kernels.cpython-311-x86_64-linux-gnu.so`
- Benchmark summaries and perf outputs:
  - `accepted_reaudit_*_summary.json`
  - `accepted_reaudit_*_perf.json`
  - `accepted_reaudit_*_compare.json`
  - `accepted_reaudit_*_cprofile.prof`
- Historical experimental JSON kept for reference only:
  - `cpp_bridge_directdispatch_*`
  - `cpp_evolve_serial_*`
  - `cpp_kernelize_next_*`
  - `cpp_nodechain_wrapperbypass_*`
  - `cython_exact_serial_*`
- Result directories under `result/accepted_reaudit_*`
- Any local `bound` links or copied input artifacts

None of the above should be staged or committed in this branch.

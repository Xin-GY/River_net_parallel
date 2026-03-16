# cpp fullchain untracked inventory

源工作树 `/tmp/feature_cpp_exact_evolve_kernelize_next` 当前只有未跟踪中间产物，没有未提交源码改动。

## compile artifacts
- `cython_cpp_bridge.cpp`
- `cython_cpp_bridge.cpython-311-x86_64-linux-gnu.so`
- `cython_node_iteration.c`
- `cython_node_iteration.cpython-311-x86_64-linux-gnu.so`
- `cython_river_kernels.c`
- `cython_river_kernels.cpython-311-x86_64-linux-gnu.so`

## benchmark intermediates
- `reports/cpp_bridge_directdispatch_10m_compare.json`
- `reports/cpp_bridge_directdispatch_10m_summary.json`
- `reports/cpp_kernelize_next_10m_noperf_summary.json`
- `reports/cpp_kernelize_next_10m_perf.json`
- `reports/cpp_kernelize_next_10m_summary.json`
- `reports/cpp_kernelize_next_2h.prof`
- `reports/cpp_kernelize_next_2h_cprofile.prof`
- `reports/cpp_kernelize_next_2h_cprofile_after_crosssection.prof`
- `reports/cpp_kernelize_next_2h_cprofile_summary.json`
- `reports/cpp_kernelize_next_2h_cprofile_top20.json`
- `reports/cpp_kernelize_next_2h_noperf_solo_summary.json`
- `reports/cpp_kernelize_next_2h_noperf_summary.json`
- `reports/cpp_kernelize_next_2h_perf.json`
- `reports/cpp_kernelize_next_2h_summary.json`
- `reports/cpp_kernelize_next_40h_noperf_summary.json`
- `reports/cpp_nodechain_widthfast_10m_compare.json`
- `reports/cpp_nodechain_widthfast_10m_summary.json`

## submit policy
- 上述文件都保留在源工作树，不删除。
- 本轮新分支不提交这些中间产物。
- 新分支若需要重新生成 benchmark/编译产物，只在本分支工作树中生成新的副本。

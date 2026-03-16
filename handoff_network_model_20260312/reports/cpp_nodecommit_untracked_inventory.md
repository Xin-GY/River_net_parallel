# cpp nodecommit refresh untracked inventory

The new continuation worktree starts from accepted commit `f8f0db0` and is clean.

Excluded from future commits on this branch:

- generated Cython/C++ build artifacts such as `.so`, generated `.c`, generated `.cpp`
- benchmark JSON summaries and compare outputs
- ad hoc result directories produced during validation
- branch-local cProfile outputs

Pre-existing tracked source files such as:

- `cpp/evolve_core.cpp`
- `cpp/output_buffer.cpp`
- `cpp/river_kernels.cpp`

are part of the accepted source tree and are not considered generated artifacts.

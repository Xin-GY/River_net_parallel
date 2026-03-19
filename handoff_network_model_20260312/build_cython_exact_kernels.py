from pathlib import Path

from setuptools import Extension, setup

import numpy as np
from Cython.Build import cythonize


def existing_extensions():
    specs = []
    root = Path(__file__).resolve().parent
    if (root / "cython_node_iteration.pyx").exists():
        specs.append(
            Extension(
                name="cython_node_iteration",
                sources=["cython_node_iteration.pyx"],
                include_dirs=[np.get_include()],
                extra_compile_args=["-O3"],
            )
        )
    if (root / "cython_river_kernels.pyx").exists():
        specs.append(
            Extension(
                name="cython_river_kernels",
                sources=["cython_river_kernels.pyx", "cpp/river_kernels.cpp", "cpp/evolve_core.cpp"],
                include_dirs=[np.get_include(), str(root)],
                language="c++",
                extra_compile_args=["-O3", "-std=c++17"],
            )
        )
    return specs


extensions = existing_extensions()

setup(
    name="cython_exact_kernels",
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": 3,
            "boundscheck": False,
            "wraparound": False,
            "initializedcheck": False,
            "cdivision": True,
        },
    ),
)

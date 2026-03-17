import os
from pathlib import Path

from setuptools import Extension, setup

import numpy as np
from Cython.Build import cythonize


def build_flags(*extra):
    flags = ["-O3"]
    if os.getenv("ISLAM_BUILD_USE_NDEBUG", "0") == "1":
        flags.append("-DNDEBUG")
    if os.getenv("ISLAM_BUILD_USE_MARCH_NATIVE", "0") == "1":
        flags.append("-march=native")
    flags.extend(extra)
    return flags


def existing_extensions():
    specs = []
    root = Path(__file__).resolve().parent
    if (root / "cython_node_iteration.pyx").exists():
        specs.append(
            Extension(
                name="cython_node_iteration",
                sources=["cython_node_iteration.pyx"],
                include_dirs=[np.get_include()],
                extra_compile_args=build_flags(),
            )
        )
    if (root / "cython_river_kernels.pyx").exists():
        specs.append(
            Extension(
                name="cython_river_kernels",
                sources=["cython_river_kernels.pyx", "cpp/river_kernels.cpp"],
                include_dirs=[np.get_include(), str(root)],
                language="c++",
                extra_compile_args=build_flags("-std=c++17"),
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

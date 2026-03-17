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


root = Path(__file__).resolve().parent

extensions = [
    Extension(
        name="cython_cpp_bridge",
        sources=[
            "cython_cpp_bridge.pyx",
            "cpp/output_buffer.cpp",
            "cpp/evolve_core.cpp",
        ],
        include_dirs=[np.get_include(), str(root)],
        language="c++",
        extra_compile_args=build_flags("-std=c++17"),
    )
]

setup(
    name="cpp_exact_kernels",
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

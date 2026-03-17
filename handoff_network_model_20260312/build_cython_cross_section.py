import os

from setuptools import Extension, setup

import numpy as np
from Cython.Build import cythonize


def build_flags():
    flags = ["-O3"]
    if os.getenv("ISLAM_BUILD_USE_NDEBUG", "0") == "1":
        flags.append("-DNDEBUG")
    if os.getenv("ISLAM_BUILD_USE_MARCH_NATIVE", "0") == "1":
        flags.append("-march=native")
    return flags


extensions = [
    Extension(
        name="cython_cross_section",
        sources=["cython_cross_section.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=build_flags(),
    )
]


setup(
    name="cython_cross_section",
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

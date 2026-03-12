from setuptools import Extension, setup

import numpy as np
from Cython.Build import cythonize


extensions = [
    Extension(
        name="cython_cross_section",
        sources=["cython_cross_section.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=["-O3"],
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

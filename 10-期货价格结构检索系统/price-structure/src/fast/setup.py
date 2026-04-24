"""
setup.py — 构建 C 扩展

用法：
    python setup.py build_ext --inplace

自动检测 NumPy include 路径，编译 _pivots.so 和 _dtw.so。
如果编译失败，系统会自动 fallback 到纯 Python 实现。
"""

from setuptools import setup, Extension
import numpy as np

pivots_ext = Extension(
    "src.fast._pivots",
    sources=["_pivots.c"],
    include_dirs=[np.get_include()],
    extra_compile_args=["/O2"],
)

dtw_ext = Extension(
    "src.fast._dtw",
    sources=["_dtw.c"],
    include_dirs=[np.get_include()],
    extra_compile_args=["/O2"],
)

setup(
    name="price-structure-fast",
    version="3.0.0",
    description="C extensions for price-structure compiler",
    ext_modules=[pivots_ext, dtw_ext],
)

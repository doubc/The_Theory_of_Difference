"""
setup.py — 构建 C 扩展

用法：
    python setup.py build_ext --inplace

自动检测 NumPy include 路径，编译 _pivots.so 和 _dtw.so。
如果编译失败，系统会自动 fallback 到纯 Python 实现。

优化标志说明：
    -O3             最高级别优化
    -march=native   针对当前 CPU 架构（启用 AVX2/SSE4.2 等 SIMD）
    -ffast-math     放松浮点精度换取速度（金融计算可接受）
    -funroll-loops  循环展开
    -flto           链接时优化（跨编译单元内联）
    -DNDEBUG        关闭 assert
"""

import sys
from setuptools import setup, Extension

# NumPy include 路径（可选，有则用）
try:
    import numpy as np
    numpy_include = [np.get_include()]
except ImportError:
    numpy_include = []

# 平台检测 + 编译参数
if sys.platform == "win32":
    # MSVC
    compile_args = ["/O2", "/DNDEBUG"]
    link_args = []
else:
    # GCC / Clang (Linux, macOS)
    compile_args = [
        "-O3",
        "-march=native",
        "-ffast-math",
        "-funroll-loops",
        "-flto",
        "-DNDEBUG",
        "-Wall",
        "-Wno-unused-variable",
    ]
    link_args = ["-flto", "-lm"]

pivots_ext = Extension(
    "src.fast._pivots",
    sources=["src/fast/_pivots.c"],
    include_dirs=numpy_include,
    extra_compile_args=compile_args,
    extra_link_args=link_args,
)

dtw_ext = Extension(
    "src.fast._dtw",
    sources=["src/fast/_dtw.c"],
    include_dirs=numpy_include,
    extra_compile_args=compile_args,
    extra_link_args=link_args,
)

similarity_ext = Extension(
    "src.fast._similarity",
    sources=["src/fast/_similarity.c"],
    include_dirs=numpy_include,
    extra_compile_args=compile_args,
    extra_link_args=link_args,
)

setup(
    name="price-structure-fast",
    version="3.0.0",
    description="C extensions for price-structure compiler",
    ext_modules=[pivots_ext, dtw_ext, similarity_ext],
)

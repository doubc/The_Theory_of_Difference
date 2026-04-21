"""
MySQL 数据接入与结构编译测试

目标：
1. 验证 MySQLLoader 能否从本地 sina 数据库读取 cu0 日线数据。
2. 运行结构编译器，观察极值点提取、关键区识别和结构组装的效果。
3. 输出编译报告到 output 目录。
"""

from src.data.loader import MySQLLoader
from src.compiler.pipeline import compile_full, CompilerConfig
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

def main():
    print("正在连接本地 MySQL 数据库 (sina.cu0)...")
    
    # 1. 初始化加载器
    loader = MySQLLoader(host='localhost', user='root', password='root', db='sina')
    
    # 2. 获取数据（最近 500 个交易日）
    bars = loader.get(symbol='cu0', freq='1d')
    if not bars:
        print("错误：未能从 MySQL 读取到数据，请检查数据库连接或表名。")
        return
        
    print(f"成功读取 {len(bars)} 根 K 线，时间范围：{bars[0].timestamp.date()} ~ {bars[-1].timestamp.date()}")
    
    # 3. 配置编译器参数
    config = CompilerConfig(
        min_amplitude=0.02,   # 最小摆动幅度 2%
        min_duration=3,       # 最小持续时间 3 天
        zone_bandwidth=0.01,  # Zone 带宽 1%
        cluster_eps=0.015,    # 聚类容差 1.5%
        min_cycles=2          # 至少 2 个循环构成结构
    )
    
    # 4. 执行编译
    print("开始结构编译...")
    result = compile_full(bars, config)
    
    # 5. 输出结果摘要
    summary = result.summary()
    print("\n--- 编译结果摘要 ---")
    for k, v in summary.items():
        print(f"{k}: {v}")
        
    # 6. 可视化（调用 visualize 模块的主逻辑）
    try:
        import sys
        import os
        # 确保根目录在路径中
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)
        
        # 显式导入 visualize 脚本文件
        import importlib.util
        spec = importlib.util.spec_from_file_location("visualize", os.path.join(root_dir, "scripts", "visualize.py"))
        visualize_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(visualize_module)
        
        svg = visualize_module.price_chart_svg(bars, result)
        with open("output/mysql_test_cu0.svg", "w") as f:
            f.write(svg)
        print("\n可视化图表已保存至: output/mysql_test_cu0.svg")
    except Exception as e:
        import traceback
        print(f"\n可视化失败: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()

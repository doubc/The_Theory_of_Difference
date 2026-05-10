""""Real_World CLI 入口。

Usage:
    python -m Real_world experiments/futures/exp_001_inventory_basis.yaml
    python -m Real_world experiments/futures/exp_001_inventory_basis.yaml --steps 20 --output outputs
"""

import argparse
import sys
from pathlib import Path

from .engine.runner import Runner
from .io.result_writer import write_results
from .io.yaml_loader import load_world_from_yaml


def main():
    parser = argparse.ArgumentParser(description="Real_World: 差异结构推理机")
    parser.add_argument("config", help="实验配置 YAML 文件路径")
    parser.add_argument("--steps", type=int, default=None, help="运行步数（覆盖配置文件）")
    parser.add_argument("--output", default="outputs", help="输出目录")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    parser.add_argument("--no-intervention", action="store_true", help="禁用交易所干预")

    args = parser.parse_args()

    # 加载世界
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"错误: 配置文件不存在: {config_path}")
        sys.exit(1)

    print(f"加载配置: {config_path}")
    world = load_world_from_yaml(str(config_path))

    # 覆盖步数
    if args.steps:
        world.max_steps = args.steps

    # 运行
    runner = Runner(world, verbose=not args.quiet, exchange_intervention=not args.no_intervention)
    world = runner.run()

    # 输出结果
    exp_id = config_path.stem  # 用文件名作为实验ID
    write_results(world, output_dir=args.output, exp_id=exp_id)

    print(f"\n完成。结果已写入 {args.output}/")


if __name__ == "__main__":
    main()

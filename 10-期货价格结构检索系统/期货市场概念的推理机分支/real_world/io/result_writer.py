""""结果写出：将轨迹、状态、报告写入输出目录。"""

import json
import yaml
from pathlib import Path
from typing import Optional

from ..core.world import World
from ..reporting.markdown_report import generate_report


def write_results(
    world: World,
    output_dir: str = "outputs",
    exp_id: str = "exp",
    formats: Optional[list] = None,
):
    """将运行结果写入文件。

    输出文件：
    - {output_dir}/traces/{exp_id}_trace.yaml
    - {output_dir}/states/{exp_id}_states.yaml
    - {output_dir}/reports/{exp_id}_report.md
    """
    if formats is None:
        formats = ["trace", "state", "report"]

    base = Path(output_dir)

    # 写轨迹
    if "trace" in formats:
        trace_dir = base / "traces"
        trace_dir.mkdir(parents=True, exist_ok=True)
        trace_path = trace_dir / f"{exp_id}_trace.yaml"
        with open(trace_path, "w", encoding="utf-8") as f:
            yaml.dump(world.trace.to_list(), f, allow_unicode=True, default_flow_style=False)
        print(f"[ResultWriter] 轨迹写入: {trace_path}")

    # 写状态
    if "state" in formats:
        state_dir = base / "states"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_path = state_dir / f"{exp_id}_states.yaml"
        with open(state_path, "w", encoding="utf-8") as f:
            yaml.dump([s.to_dict() for s in world.states], f, allow_unicode=True, default_flow_style=False)
        print(f"[ResultWriter] 状态写入: {state_path}")

    # 写报告
    if "report" in formats:
        report_dir = base / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{exp_id}_report.md"
        report = generate_report(world, exp_id)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[ResultWriter] 报告写入: {report_path}")
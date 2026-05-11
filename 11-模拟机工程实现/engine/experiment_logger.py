"""
experiment_logger.py — 实验日志标准化

JSON 日志 + 自动生成配套说明文档。
每次实验运行后，生成：
1. logs/exp_<name>_<timestamp>.json — 结构化数据
2. docs/experiments/exp_<name>_<timestamp>.md — 配套说明文档
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import asdict


class ExperimentLogger:
    """实验日志记录器"""

    def __init__(self, project_root: str):
        self.project_root = project_root
        self.logs_dir = os.path.join(project_root, "logs")
        self.docs_dir = os.path.join(project_root, "docs", "experiments")
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.docs_dir, exist_ok=True)

        self.experiment_name = ""
        self.config = {}
        self.results = {}
        self.axiom_trends = {}
        self.start_time = None

    def start(self, experiment_name: str, config: Dict[str, Any]):
        """开始记录实验"""
        self.experiment_name = experiment_name
        self.config = config
        self.start_time = datetime.now()
        self.axiom_trends = {}

    def log_step(self, step: int, loss: float, report: Dict[str, Any]):
        """记录每步的公理趋势"""
        for axiom_name, axiom_data in report.items():
            if axiom_name not in self.axiom_trends:
                self.axiom_trends[axiom_name] = []
            if isinstance(axiom_data, dict):
                value = axiom_data.get("raw_violation", 0.0)
            elif hasattr(axiom_data, "raw_violation"):
                value = axiom_data.raw_violation
            else:
                value = float(axiom_data)
            self.axiom_trends[axiom_name].append(value)

    def finish(
        self,
        total_steps: int,
        final_loss: float,
        structures_detected: int = 0,
        validation_result: Optional[Dict] = None,
        ascents: Optional[List] = None,
        final_state_summary: Optional[Dict] = None,
    ):
        """完成实验，生成日志和文档"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds() if self.start_time else 0

        self.results = {
            "total_steps": total_steps,
            "final_loss": final_loss,
            "structures_detected": structures_detected,
            "validation": validation_result or {},
            "ascents": ascents or [],
            "final_state_summary": final_state_summary or {},
            "duration_seconds": duration,
        }

        # 生成 JSON 日志
        json_path = self._write_json_log()
        # 生成配套文档
        doc_path = self._write_doc()

        return json_path, doc_path

    def _write_json_log(self) -> str:
        """写入 JSON 日志"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S") if self.start_time else "unknown"
        filename = f"exp_{self.experiment_name}_{timestamp}.json"
        filepath = os.path.join(self.logs_dir, filename)

        data = {
            "experiment": self.experiment_name,
            "timestamp": self.start_time.isoformat() if self.start_time else None,
            "config": self.config,
            "results": self.results,
            "axiom_trends": {k: v for k, v in self.axiom_trends.items()},
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        return filepath

    def _write_doc(self) -> str:
        """生成配套说明文档"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S") if self.start_time else "unknown"
        filename = f"exp_{self.experiment_name}_{timestamp}.md"
        filepath = os.path.join(self.docs_dir, filename)

        # 提取关键公理趋势的统计
        axiom_stats = {}
        for name, values in self.axiom_trends.items():
            if values:
                axiom_stats[name] = {
                    "initial": values[0],
                    "final": values[-1],
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                }

        # 验证结果
        validation = self.results.get("validation", {})
        val_lines = []
        if validation:
            for criterion, passed in validation.items():
                if isinstance(passed, bool):
                    val_lines.append(f"- **{criterion}**: {'PASS' if passed else 'FAIL'}")
                elif isinstance(passed, (int, float)):
                    val_lines.append(f"- **{criterion}**: {passed}")

        # 公理趋势表
        axiom_table_lines = ["| 公理 | 初始值 | 最终值 | 最小值 | 最大值 | 均值 |", "|------|--------|--------|--------|--------|------|"]
        for name, stats in axiom_stats.items():
            axiom_table_lines.append(
                f"| {name} | {stats['initial']:.6f} | {stats['final']:.6f} | "
                f"{stats['min']:.6f} | {stats['max']:.6f} | {stats['mean']:.6f} |"
            )

        doc = f"""# 实验报告：{self.experiment_name}

## 实验信息

- **时间**: {self.start_time.strftime('%Y-%m-%d %H:%M:%S') if self.start_time else 'unknown'}
- **耗时**: {self.results.get('duration_seconds', 0):.1f} 秒

## 实验目的

{self._describe_purpose()}

## 配置参数

```json
{json.dumps(self.config, indent=2, ensure_ascii=False)}
```

## 结果摘要

- **总步数**: {self.results.get('total_steps', 0)}
- **最终损失**: {self.results.get('final_loss', 0):.6f}
- **检测到的稳定结构数**: {self.results.get('structures_detected', 0)}
- **升维事件**: {len(self.results.get('ascents', []))}

## 公理趋势

{chr(10).join(axiom_table_lines)}

## 验证结果

{chr(10).join(val_lines) if val_lines else "无验证数据"}

## 关键发现

{self._describe_findings(axiom_stats, validation)}

## 理论对应

{self._theory_mapping()}

---
*自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(doc)

        return filepath

    def _describe_purpose(self) -> str:
        """根据实验名称描述实验目的"""
        purposes = {
            "1d": "验证 1D 差异反应堆的基本功能：A1 差异源注入、A5 守恒、A7 稳定结构涌现。",
            "2d": "验证 2D 差异反应堆在更大状态空间下的表现：稳定结构检测、区域分类、升维压力。",
            "smoke_test": "冒烟测试：验证所有 M1 组件可运行，无 NaN/Inf。",
            "validate": "运行稳定结构验证器，检查五标准（lifetime, boundary, closure, turnover, interaction）。",
            "coarse_grain": "测试粗粒化映射：L0 → L1 升维管道是否畅通。",
        }
        for key, purpose in purposes.items():
            if key in self.experiment_name:
                return purpose
        return "验证差异论模拟机的核心功能。"

    def _describe_findings(self, axiom_stats: Dict, validation: Dict) -> str:
        """根据数据描述关键发现"""
        findings = []

        # 损失趋势
        final_loss = self.results.get("final_loss", 0)
        if final_loss < 0.01:
            findings.append("- 损失收敛至较低水平，模型学习到满足公理约束的演化规则。")
        elif final_loss < 0.1:
            findings.append("- 损失有下降趋势，但尚未完全收敛。")
        else:
            findings.append("- 损失较高，模型可能需要更多训练步数或调整超参数。")

        # 公理趋势
        for name, stats in axiom_stats.items():
            if stats["final"] < stats["initial"] * 0.5:
                findings.append(f"- {name} 违背度显著下降（{stats['initial']:.4f} → {stats['final']:.4f}），约束有效。")

        # 稳定结构
        structures = self.results.get("structures_detected", 0)
        if structures > 0:
            findings.append(f"- 检测到 {structures} 个稳定结构，差异反应堆产生了可识别的组织。")
        else:
            findings.append("- 未检测到稳定结构，可能需要更多训练步数或调整稳定性窗口。")

        # 验证
        if validation:
            all_pass = all(v for v in validation.values() if isinstance(v, bool))
            if all_pass:
                findings.append("- 所有验证标准通过。")
            else:
                failed = [k for k, v in validation.items() if isinstance(v, bool) and not v]
                findings.append(f"- 以下验证标准未通过: {', '.join(failed)}")

        return "\n".join(findings) if findings else "无特别发现。"

    def _theory_mapping(self) -> str:
        """理论对应关系"""
        return """本实验对应差异论的以下机制：

1. **A1 差异源**（差异先行）：系统边界持续注入差异，维持远离平衡态
2. **A5 守恒**（守恒律）：开放系统通量平衡，注入-吸收=变化量
3. **A7 稳定结构**（循环）：差异在局部区域形成时间稳定的组织
4. **A9 升维**（层级）：稳定结构满足条件后触发粗粒化封装

这些机制对应《差异即世界》九机制生成链中的"聚簇→守恒→循环→层级"路径。
"""

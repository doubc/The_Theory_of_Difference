"""
experiments/logger.py — 结构化实验日志（M1.2 实验追溯性）

所有实验通过此模块统一输出 JSON 日志，解决"做了但没有记录"的问题。

用法:
    from experiments.logger import ExperimentLogger

    logger = ExperimentLogger("exp_0_baseline")
    logger.start(params={"length": 50, "steps": 200, ...})
    for step in range(steps):
        # ... 演化 ...
        logger.log_step(step, {"mean": mean, "std": std, "grad": grad})
    logger.log_event("checkpoint", {"step": 100, "mean": 0.5})
    logger.finish({"final_mean": 0.5, "status": "heat_death"})
"""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")


class ExperimentLogger:
    """结构化实验日志记录器"""

    def __init__(self, experiment_name: str):
        self.experiment_name = experiment_name
        self.start_time: Optional[float] = None
        self.tz_offset = "+08:00"  # Asia/Shanghai
        self._is_started = False
        self._is_finished = False

        # 日志数据结构
        self.log: Dict[str, Any] = {
            "experiment": experiment_name,
            "version": "1.0",
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "params": {},
            "steps": [],
            "events": [],
            "final": {},
            "conclusion": "",
        }

    def start(self, params: Optional[Dict[str, Any]] = None, description: str = ""):
        """标记实验开始"""
        if self._is_started:
            raise RuntimeError(f"Experiment '{self.experiment_name}' already started")

        self._is_started = True
        self.start_time = time.time()
        self.log["started_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + self.tz_offset
        self.log["params"] = params or {}
        self.log["description"] = description

    def log_step(self, step: int, metrics: Dict[str, Any]):
        """记录每一步的指标"""
        if not self._is_started:
            raise RuntimeError("Call start() before log_step()")
        entry = {"step": step, "ts": time.time() - self.start_time, **metrics}
        self.log["steps"].append(entry)

    def log_event(self, event_type: str, data: Dict[str, Any]):
        """记录关键事件（如升维触发、参数变更等）"""
        entry = {
            "event": event_type,
            "ts": time.time() - self.start_time,
            "data": data,
        }
        self.log["events"].append(entry)

    def finish(self, final_metrics: Optional[Dict[str, Any]] = None,
               conclusion: str = ""):
        """标记实验完成并保存"""
        if self._is_finished:
            return  # 幂等
        if not self._is_started:
            raise RuntimeError("Call start() before finish()")

        self._is_finished = True
        self.log["finished_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S") + self.tz_offset
        self.log["duration_seconds"] = round(time.time() - self.start_time, 3)
        self.log["final"] = final_metrics or {}
        self.log["conclusion"] = conclusion

        # 写入 JSON 文件
        path = self._log_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.log, f, indent=2, ensure_ascii=False)

        print(f"\n[LOG] Saved: {path}")
        return path

    def _log_path(self) -> str:
        """生成日志文件路径: logs/YYYY-MM-DD_exp_name.json"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"{date_str}_{self.experiment_name}.json"
        return os.path.join(LOG_DIR, filename)


def load_log(experiment_name: str) -> Optional[Dict]:
    """加载最近一次实验日志"""
    files = sorted(
        [f for f in os.listdir(LOG_DIR) if experiment_name in f and f.endswith(".json")],
        reverse=True,
    )
    if not files:
        return None
    with open(os.path.join(LOG_DIR, files[0]), "r", encoding="utf-8") as f:
        return json.load(f)


def list_logs() -> List[str]:
    """列出所有实验日志"""
    if not os.path.exists(LOG_DIR):
        return []
    return sorted([f for f in os.listdir(LOG_DIR) if f.endswith(".json")])


def compare_logs(name1: str, name2: str) -> Optional[Dict]:
    """比较两次实验日志"""
    log1 = load_log(name1)
    log2 = load_log(name2)
    if not log1 or not log2:
        return None

    result = {
        "experiment1": log1["experiment"],
        "started1": log1["started_at"],
        "experiment2": log2["experiment"],
        "started2": log2["started_at"],
        "params_match": log1.get("params") == log2.get("params"),
        "final_comparison": {},
    }

    # 比较 final 指标
    for key in set(list(log1.get("final", {}).keys()) + list(log2.get("final", {}).keys())):
        v1 = log1["final"].get(key)
        v2 = log2["final"].get(key)
        if v1 and v2 and v1 != 0:
            result["final_comparison"][key] = {
                "v1": v1, "v2": v2,
                "delta": round(v2 - v1, 6) if isinstance(v1, (int, float)) else None,
                "delta_pct": round((v2 - v1) / v1 * 100, 2) if isinstance(v1, (int, float)) and v1 != 0 else None,
            }

    return result
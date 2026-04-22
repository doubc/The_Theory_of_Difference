"""
知识图谱持久化存储层 — V1.6 P2

存储架构：
  data/graph/
  ├── structures.jsonl       # 结构节点（append-only）
  ├── zones.jsonl            # Zone 节点
  ├── narratives.jsonl       # 叙事节点（天然时序）
  ├── edges.jsonl            # 所有边
  ├── index/
  │   ├── by_zone.json       # zone_key → [struct_id]
  │   ├── by_symbol.json     # symbol → [struct_id]
  │   └── by_narrative.json  # keyword → [narrative_id]
  └── snapshots/
      └── YYYY-MM-DD.json    # 每日图谱快照

设计原则：
  - 主文件 = append-only log（真相源）
  - 索引 = 派生视图（每次编译后重建，丢了不慌）
  - 快照 = 时间切片（用于跨时间 diff / 演化分析）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
import json
import math


def _json_safe(obj: Any) -> Any:
    """确保对象可以 JSON 序列化"""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    return obj


@dataclass
class GraphStore:
    """
    知识图谱持久化存储

    基于 JSONL 的 append-only 存储 + 派生索引 + 每日快照。
    """
    base_path: str = "data/graph"

    def __post_init__(self):
        self.base = Path(self.base_path)
        self.idx_dir = self.base / "index"
        self.snap_dir = self.base / "snapshots"
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in [self.base, self.idx_dir, self.snap_dir]:
            d.mkdir(parents=True, exist_ok=True)

    # ─── 文件路径 ──────────────────────────────────────────

    @property
    def structures_file(self) -> Path:
        return self.base / "structures.jsonl"

    @property
    def zones_file(self) -> Path:
        return self.base / "zones.jsonl"

    @property
    def narratives_file(self) -> Path:
        return self.base / "narratives.jsonl"

    @property
    def edges_file(self) -> Path:
        return self.base / "edges.jsonl"

    # ─── 追加写入 ──────────────────────────────────────────

    def append_structure(self, record: dict) -> None:
        """追加一个结构节点"""
        record["_ts"] = datetime.now().isoformat()
        self._append(self.structures_file, record)

    def append_zone(self, record: dict) -> None:
        """追加一个 Zone 节点（同一 zone_key 不重复追加）"""
        zone_key = record.get("zone_key", "")
        if zone_key and self._zone_exists(zone_key):
            return
        record["_ts"] = datetime.now().isoformat()
        self._append(self.zones_file, record)

    def append_narrative(self, record: dict) -> None:
        """追加一个叙事节点"""
        record["_ts"] = datetime.now().isoformat()
        self._append(self.narratives_file, record)

    def append_edge(self, record: dict) -> None:
        """追加一条边（source + target + type 去重）"""
        edge_key = f"{record.get('source')}|{record.get('target')}|{record.get('edge_type')}"
        if self._edge_exists(edge_key):
            return
        record["_edge_key"] = edge_key
        record["_ts"] = datetime.now().isoformat()
        self._append(self.edges_file, record)

    def _append(self, path: Path, record: dict) -> None:
        safe = _json_safe(record)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(safe, ensure_ascii=False) + "\n")

    def _zone_exists(self, zone_key: str) -> bool:
        """检查 Zone 是否已存在"""
        if not self.zones_file.exists():
            return False
        with open(self.zones_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("zone_key") == zone_key:
                        return True
        return False

    def _edge_exists(self, edge_key: str) -> bool:
        """检查边是否已存在"""
        if not self.edges_file.exists():
            return False
        with open(self.edges_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rec = json.loads(line)
                    if rec.get("_edge_key") == edge_key:
                        return True
        return False

    # ─── 批量写入 ──────────────────────────────────────────

    def save_structures(self, records: list[dict]) -> int:
        """批量追加结构节点，返回新增数"""
        count = 0
        for rec in records:
            self.append_structure(rec)
            count += 1
        return count

    def save_edges(self, records: list[dict]) -> int:
        """批量追加边，返回新增数"""
        count = 0
        for rec in records:
            self.append_edge(rec)
            count += 1
        return count

    # ─── 读取 ──────────────────────────────────────────────

    def load_all_structures(self) -> list[dict]:
        """加载所有结构节点"""
        return self._load_jsonl(self.structures_file)

    def load_all_zones(self) -> list[dict]:
        """加载所有 Zone 节点"""
        return self._load_jsonl(self.zones_file)

    def load_all_narratives(self) -> list[dict]:
        """加载所有叙事节点"""
        return self._load_jsonl(self.narratives_file)

    def load_all_edges(self) -> list[dict]:
        """加载所有边"""
        return self._load_jsonl(self.edges_file)

    def _load_jsonl(self, path: Path) -> list[dict]:
        if not path.exists():
            return []
        records = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return records

    def load_structures_by_symbol(self, symbol: str) -> list[dict]:
        """按品种加载结构"""
        return [s for s in self.load_all_structures() if s.get("symbol") == symbol]

    def load_structures_by_zone(self, zone_key: str) -> list[dict]:
        """按 Zone 加载结构"""
        return [s for s in self.load_all_structures() if s.get("zone_key") == zone_key]

    def load_narratives_by_keyword(self, keyword: str) -> list[dict]:
        """按关键词搜索叙事"""
        return [n for n in self.load_all_narratives() if keyword in n.get("text", "")]

    def load_edges_by_type(self, edge_type: str) -> list[dict]:
        """按边类型加载"""
        return [e for e in self.load_all_edges() if e.get("edge_type") == edge_type]

    def load_edges_from(self, source: str) -> list[dict]:
        """加载从某个节点出发的所有边"""
        return [e for e in self.load_all_edges() if e.get("source") == source]

    def load_edges_to(self, target: str) -> list[dict]:
        """加载指向某个节点的所有边"""
        return [e for e in self.load_all_edges() if e.get("target") == target]

    # ─── 索引重建 ──────────────────────────────────────────

    def rebuild_indexes(self) -> dict:
        """重建所有派生索引，返回索引统计"""
        structures = self.load_all_structures()
        narratives = self.load_all_narratives()

        # by_zone: zone_key → [struct_id]
        by_zone: dict[str, list[str]] = {}
        for s in structures:
            zk = s.get("zone_key", "")
            sid = s.get("struct_id", "")
            if zk and sid:
                by_zone.setdefault(zk, []).append(sid)

        # by_symbol: symbol → [struct_id]
        by_symbol: dict[str, list[str]] = {}
        for s in structures:
            sym = s.get("symbol", "")
            sid = s.get("struct_id", "")
            if sym and sid:
                by_symbol.setdefault(sym, []).append(sid)

        # by_narrative: 关键词 → [narrative_id]
        by_narrative: dict[str, list[str]] = {}
        # 预定义关键词
        keywords = ["恐慌", "供需", "政策", "流动性", "投机",
                     "急跌", "急涨", "慢跌", "慢涨", "均衡",
                     "压缩", "释放", "突破", "反转", "派发",
                     "底部", "顶部", "中继", "整理"]
        for n in narratives:
            nid = n.get("narrative_id", "")
            text = n.get("text", "")
            for kw in keywords:
                if kw in text:
                    by_narrative.setdefault(kw, []).append(nid)

        # 写入索引文件
        self._write_index("by_zone.json", by_zone)
        self._write_index("by_symbol.json", by_symbol)
        self._write_index("by_narrative.json", by_narrative)

        return {
            "zones_indexed": len(by_zone),
            "symbols_indexed": len(by_symbol),
            "narrative_keywords": len(by_narrative),
            "total_structures": len(structures),
            "total_narratives": len(narratives),
        }

    def _write_index(self, filename: str, data: dict) -> None:
        path = self.idx_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_index(self, filename: str) -> dict:
        """加载指定索引"""
        path = self.idx_dir / filename
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # ─── 快照 ──────────────────────────────────────────────

    def save_snapshot(self, label: str | None = None) -> str:
        """
        保存当日图谱快照。
        返回快照文件路径。
        """
        date_str = label or datetime.now().strftime("%Y-%m-%d")
        snapshot = {
            "date": date_str,
            "created_at": datetime.now().isoformat(),
            "structures": self.load_all_structures(),
            "zones": self.load_all_zones(),
            "narratives": self.load_all_narratives(),
            "edges": self.load_all_edges(),
            "stats": self.stats(),
        }
        path = self.snap_dir / f"{date_str}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_json_safe(snapshot), f, ensure_ascii=False, indent=2)
        return str(path)

    def load_snapshot(self, date_str: str) -> dict | None:
        """加载指定日期的快照"""
        path = self.snap_dir / f"{date_str}.json"
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def diff_snapshots(self, date_a: str, date_b: str) -> dict:
        """
        对比两个日期的图谱快照，输出变化。
        用于分析演化链和叙事递归。
        """
        snap_a = self.load_snapshot(date_a) or {}
        snap_b = self.load_snapshot(date_b) or {}

        structs_a = {s["struct_id"] for s in snap_a.get("structures", []) if "struct_id" in s}
        structs_b = {s["struct_id"] for s in snap_b.get("structures", []) if "struct_id" in s}

        narratives_a = {n.get("text", "") for n in snap_a.get("narratives", [])}
        narratives_b = {n.get("text", "") for n in snap_b.get("narratives", [])}

        return {
            "date_a": date_a,
            "date_b": date_b,
            "new_structures": list(structs_b - structs_a),
            "removed_structures": list(structs_a - structs_b),
            "persisting_structures": list(structs_a & structs_b),
            "new_narratives": list(narratives_b - narratives_a),
            "narrative_changes": [
                {"old": a, "new": b}
                for a in narratives_a
                for b in narratives_b
                if a != b and a and b
                and _narrative_similarity(a, b) > 0.3
            ],
        }

    # ─── 从编译结果批量写入 ────────────────────────────────

    def ingest_compile_result(self, structures: list, symbol: str = "") -> dict:
        """
        将 compile_full() 的输出批量写入存储。

        每个 Structure → 1 条结构记录 + 1 条 Zone 记录 + 1~N 条叙事记录 + N 条边
        """
        ts = datetime.now().strftime("%Y-%m-%d")
        struct_records = []
        zone_records = []
        narrative_records = []
        edge_records = []

        for i, st in enumerate(structures):
            sym = st.symbol or symbol or "unknown"
            zone_key = f"{sym}:{st.zone.price_center:.0f}"
            struct_id = f"{sym}_S{i}_{st.t_start.strftime('%Y%m%d') if st.t_start else 'nodate'}"
            s_node = f"struct:{struct_id}"
            z_node = f"zone:{sym}_{st.zone.price_center:.0f}"

            # 结构记录
            struct_rec = {
                "struct_id": struct_id,
                "symbol": sym,
                "zone_key": zone_key,
                "zone_center": st.zone.price_center,
                "zone_bandwidth": st.zone.bandwidth,
                "cycle_count": st.cycle_count,
                "avg_speed_ratio": round(st.avg_speed_ratio, 4),
                "avg_time_ratio": round(st.avg_time_ratio, 4),
                "contrast_type": st.zone.context_contrast.value,
                "narrative": st.narrative_context,
                "typicality": st.typicality,
                "label": st.label or "",
                "compile_date": ts,
                "t_start": st.t_start.isoformat() if st.t_start else "",
                "t_end": st.t_end.isoformat() if st.t_end else "",
            }
            if st.motion:
                struct_rec["phase_tendency"] = st.motion.phase_tendency
                struct_rec["conservation_flux"] = round(st.motion.conservation_flux, 4)
                struct_rec["stable_distance"] = round(st.motion.stable_distance, 4)
            if st.projection:
                struct_rec["compression_level"] = round(st.projection.compression_level, 4)
            if st.stability_verdict:
                struct_rec["stability"] = st.stability_verdict.surface
                struct_rec["stability_verified"] = st.stability_verdict.verified
            struct_rec["liquidity_stress"] = round(st.liquidity_stress, 4)
            struct_rec["fear_index"] = round(st.fear_index, 4)
            struct_rec["time_compression"] = round(st.time_compression, 4)

            struct_records.append(struct_rec)

            # Zone 记录
            zone_records.append({
                "zone_key": zone_key,
                "zone_id": z_node,
                "symbol": sym,
                "price_center": st.zone.price_center,
                "bandwidth": st.zone.bandwidth,
                "strength": st.zone.strength,
                "contrast_type": st.zone.context_contrast.value,
                "source": st.zone.source.value,
            })

            # 边：结构 → Zone
            edge_records.append({
                "source": s_node,
                "target": z_node,
                "edge_type": "belongs_to",
            })

            # 边：结构 → 品种
            sym_node = f"symbol:{sym}"
            edge_records.append({
                "source": s_node,
                "target": sym_node,
                "edge_type": "of_symbol",
            })

            # 叙事记录 + 边
            if st.narrative_context:
                nid = f"narrative:{sym}_{i}_{ts}"
                narrative_records.append({
                    "narrative_id": nid,
                    "text": st.narrative_context,
                    "symbol": sym,
                    "zone_key": zone_key,
                    "timestamp": ts,
                })
                edge_records.append({
                    "source": s_node,
                    "target": nid,
                    "edge_type": "has_narrative",
                })

            # 差异转移边
            if st.motion and st.motion.transfer_target:
                # 转移目标 = 同品种内找到 zone_center 最接近的结构
                target_zone_center = st.zone.price_center  # 简化：实际应根据 transfer_target 解析
                edge_records.append({
                    "source": s_node,
                    "target": f"symbol:{sym}",  # 简化目标
                    "edge_type": "transfer_to",
                    "channel": st.motion.transfer_target,
                    "strength": st.motion.transfer_strength,
                })

        # 写入存储
        self.save_structures(struct_records)
        for zr in zone_records:
            self.append_zone(zr)
        for nr in narrative_records:
            self.append_narrative(nr)
        self.save_edges(edge_records)

        # 重建索引
        idx_stats = self.rebuild_indexes()

        return {
            "structures_ingested": len(struct_records),
            "zones_ingested": len(zone_records),
            "narratives_ingested": len(narrative_records),
            "edges_ingested": len(edge_records),
            **idx_stats,
        }

    # ─── 每日增量编译（核心入口）────────────────────────────

    def daily_ingest(self, structures: list, symbol: str = "") -> dict:
        """
        每日增量编译入口。

        相比 ingest_compile_result()，增加了跨天关联：
        1. 比对同 Zone 的"昨日结构"，建立 evolves_to 演化边
        2. 叙事变化时建立 narrative_evolves 递归边
        3. 差异转移建 transfer_to 边
        4. 自动保存当日快照

        每日调用一次，自动处理去重和关联。
        """
        ts = datetime.now().strftime("%Y-%m-%d")

        # ── 1. 加载已有数据 ──
        existing_structures = self.load_all_structures()
        existing_narratives = self.load_all_narratives()

        # 建索引：zone_key → 最新的结构记录
        latest_by_zone: dict[str, dict] = {}
        for s in existing_structures:
            zk = s.get("zone_key", "")
            ct = s.get("compile_date", "")
            if zk:
                prev = latest_by_zone.get(zk)
                if prev is None or ct > prev.get("compile_date", ""):
                    latest_by_zone[zk] = s

        # 建索引：zone_key → 最新的叙事文本
        latest_narrative_by_zone: dict[str, dict] = {}
        for n in existing_narratives:
            zk = n.get("zone_key", "")
            ts_n = n.get("timestamp", "")
            if zk:
                prev = latest_narrative_by_zone.get(zk)
                if prev is None or ts_n > prev.get("timestamp", ""):
                    latest_narrative_by_zone[zk] = n

        # ── 2. 写入今日数据 ──
        base_stats = self.ingest_compile_result(structures, symbol)

        # ── 3. 建立跨天关联边 ──
        evolution_edges = []
        narrative_edges = []
        transfer_edges = []

        for i, st in enumerate(structures):
            sym = st.symbol or symbol or "unknown"
            zone_key = f"{sym}:{st.zone.price_center:.0f}"
            compile_date = st.t_start.strftime("%Y%m%d") if st.t_start else "nodate"
            new_struct_id = f"{sym}_S{i}_{compile_date}"
            new_s_node = f"struct:{new_struct_id}"

            # 3a. 演化边：昨日结构 → 今日结构
            prev_struct = latest_by_zone.get(zone_key)
            if prev_struct:
                prev_id = prev_struct.get("struct_id", "")
                prev_date = prev_struct.get("compile_date", "")
                if prev_id and prev_date != ts:
                    old_s_node = f"struct:{prev_id}"
                    # 确认不是同一条记录
                    if old_s_node != new_s_node:
                        evolution_edges.append({
                            "source": old_s_node,
                            "target": new_s_node,
                            "edge_type": "evolves_to",
                            "from_date": prev_date,
                            "to_date": ts,
                        })

            # 3b. 叙事递归边：旧叙事 → 新叙事
            if st.narrative_context:
                prev_narr = latest_narrative_by_zone.get(zone_key)
                if prev_narr:
                    old_text = prev_narr.get("text", "")
                    old_nid = prev_narr.get("narrative_id", "")
                    new_nid = f"narrative:{sym}_{i}_{ts}"
                    if old_text != st.narrative_context and old_nid and new_nid:
                        narrative_edges.append({
                            "source": old_nid,
                            "target": new_nid,
                            "edge_type": "narrative_evolves",
                            "old_text": old_text,
                            "new_text": st.narrative_context,
                        })

            # 3c. 差异转移边
            if st.motion and st.motion.transfer_target and st.motion.transfer_strength > 0:
                # 在已有结构中寻找转移目标
                transfer_channel = st.motion.transfer_target
                if transfer_channel == "volume":
                    # 转移到成交量维度——标记为跨维度转移
                    transfer_edges.append({
                        "source": new_s_node,
                        "target": f"symbol:{sym}",
                        "edge_type": "transfer_to",
                        "channel": "volume",
                        "strength": st.motion.transfer_strength,
                        "date": ts,
                    })
                elif transfer_channel == "shorter_timeframe":
                    transfer_edges.append({
                        "source": new_s_node,
                        "target": f"symbol:{sym}",
                        "edge_type": "transfer_to",
                        "channel": "5min",
                        "strength": st.motion.transfer_strength,
                        "date": ts,
                    })

        # 写入关联边
        for e in evolution_edges:
            self.append_edge(e)
        for e in narrative_edges:
            self.append_edge(e)
        for e in transfer_edges:
            self.append_edge(e)

        # ── 4. 重建索引 ──
        idx_stats = self.rebuild_indexes()

        # ── 5. 保存当日快照 ──
        snap_path = self.save_snapshot(ts)

        return {
            "date": ts,
            **base_stats,
            "evolution_edges": len(evolution_edges),
            "narrative_evolves": len(narrative_edges),
            "transfer_edges": len(transfer_edges),
            "snapshot": snap_path,
            **idx_stats,
        }

    def stats(self) -> dict:
        """存储概览"""
        structures = self.load_all_structures()
        zones = self.load_all_zones()
        narratives = self.load_all_narratives()
        edges = self.load_all_edges()

        # 按边类型统计
        edge_type_counts = {}
        for e in edges:
            et = e.get("edge_type", "unknown")
            edge_type_counts[et] = edge_type_counts.get(et, 0) + 1

        # 按品种统计
        symbol_counts = {}
        for s in structures:
            sym = s.get("symbol", "unknown")
            symbol_counts[sym] = symbol_counts.get(sym, 0) + 1

        # 快照列表
        snapshots = [f.stem for f in self.snap_dir.glob("*.json")]

        return {
            "structures": len(structures),
            "zones": len(zones),
            "narratives": len(narratives),
            "edges": len(edges),
            "edge_types": edge_type_counts,
            "symbols": symbol_counts,
            "snapshots": snapshots,
        }

    def __repr__(self):
        s = self.stats()
        return (f"GraphStore(structures={s['structures']}, zones={s['zones']}, "
                f"narratives={s['narratives']}, edges={s['edges']})")


# ─── 工具函数 ──────────────────────────────────────────────

def _narrative_similarity(a: str, b: str) -> float:
    """简易叙事相似度（基于共享关键词）"""
    if not a or not b:
        return 0.0
    words_a = set(a.split("·"))
    words_b = set(b.split("·"))
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union) if union else 0.0

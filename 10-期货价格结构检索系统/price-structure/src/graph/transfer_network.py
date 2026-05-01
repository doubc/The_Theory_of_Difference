"""
跨品种差异转移图谱 — TransferNetwork

对应机制：守恒 + 循环（设计书 P1 #9）

核心能力：
1. 构建品种之间的差异转移网络
2. 节点 = 品种，边 = 差异转移强度
3. 基于守恒通量（conservation_flux）的跨品种联动检测
4. Granger 因果检验辅助的传导方向推断
5. 可视化：力导向图 + 热力矩阵

理论基础：
  差异守恒公理：差异不可消灭，只能转移。
  当一个品种的结构进入释放阶段（flux 大正值），
  而另一个品种同期进入蓄势阶段（flux 大负值），
  可能存在差异转移通道。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
import numpy as np


# ─── 数据结构 ──────────────────────────────────────────────

@dataclass
class FluxRecord:
    """单品种单时间点的通量记录"""
    symbol: str
    timestamp: datetime
    conservation_flux: float
    phase_tendency: str
    zone_center: float
    cycle_count: int
    movement_type: str = ""


@dataclass
class TransferEdge:
    """品种间的差异转移边"""
    source_symbol: str
    target_symbol: str
    strength: float  # 转移强度 (0~1)
    direction: str  # source→target
    correlation: float  # 通量相关系数
    lag_days: int  # 滞后天数
    confidence: str  # 高/中/低
    evidence_count: int  # 证据数量


@dataclass
class TransferPath:
    """差异转移路径"""
    path: list[str]  # [品种A, 品种B, 品种C, ...]
    total_strength: float
    path_length: int
    is_cycle: bool  # 是否形成闭环


@dataclass
class ProductNode:
    """品种节点"""
    symbol: str
    name: str
    avg_flux: float
    flux_volatility: float
    dominant_phase: str  # 主导阶段
    transfer_centrality: float  # 转移网络中的中心度
    connected_products: int  # 连接品种数


@dataclass
class TransferNetworkReport:
    """转移网络分析报告"""
    timestamp: datetime
    products: list[ProductNode]
    edges: list[TransferEdge]
    paths: list[TransferPath]
    hot_spots: list[dict]  # 热点：高转移活跃度的品种对
    systemic_stress: float  # 系统级转移压力 (0~1)


# ─── 网络构建器 ──────────────────────────────────────────

class TransferNetwork:
    """
    跨品种差异转移网络

    基于守恒通量的时间序列，检测品种间的差异转移关系。
    """

    def __init__(
        self,
        correlation_threshold: float = -0.3,  # 负相关阈值（差异转移特征）
        min_overlap_days: int = 30,  # 最少重叠天数
        lag_range: tuple[int, int] = (0, 10),  # 滞后检测范围（天）
    ):
        self.correlation_threshold = correlation_threshold
        self.min_overlap_days = min_overlap_days
        self.lag_range = lag_range
        self._flux_history: dict[str, list[FluxRecord]] = {}
        self._edges: list[TransferEdge] = []
        self._nodes: dict[str, ProductNode] = {}

    # ─── 数据输入 ──────────────────────────────────────────

    def add_flux_record(self, record: FluxRecord) -> None:
        """添加一条通量记录"""
        self._flux_history.setdefault(record.symbol, []).append(record)

    def add_flux_batch(self, records: list[FluxRecord]) -> None:
        """批量添加通量记录"""
        for r in records:
            self.add_flux_record(r)

    def ingest_from_structures(self, structures: list, symbol: str) -> int:
        """
        从编译结果提取通量记录。

        Args:
            structures: compile_full() 输出
            symbol: 品种代码

        Returns:
            记录数量
        """
        count = 0
        for st in structures:
            if not st.motion:
                continue
            record = FluxRecord(
                symbol=symbol,
                timestamp=st.t_end or datetime.now(),
                conservation_flux=st.motion.conservation_flux,
                phase_tendency=st.motion.phase_tendency,
                zone_center=st.zone.price_center,
                cycle_count=st.cycle_count,
                movement_type=st.motion.movement_type.value if hasattr(st.motion, 'movement_type') else "",
            )
            self.add_flux_record(record)
            count += 1
        return count

    # ─── 网络构建 ──────────────────────────────────────────

    def build_network(self) -> TransferNetworkReport:
        """
        构建完整的差异转移网络。

        Returns:
            TransferNetworkReport
        """
        symbols = list(self._flux_history.keys())

        # 1. 计算品种间转移边
        self._edges = []
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                edge = self._compute_transfer_edge(symbols[i], symbols[j])
                if edge and edge.strength > 0.1:
                    self._edges.append(edge)

        # 2. 计算品种节点属性
        self._nodes = {}
        for sym in symbols:
            self._nodes[sym] = self._compute_product_node(sym)

        # 3. 检测转移路径
        paths = self._detect_transfer_paths()

        # 4. 热点检测
        hot_spots = self._detect_hot_spots()

        # 5. 系统压力
        systemic = self._compute_systemic_stress()

        return TransferNetworkReport(
            timestamp=datetime.now(),
            products=list(self._nodes.values()),
            edges=self._edges,
            paths=paths,
            hot_spots=hot_spots,
            systemic_stress=systemic,
        )

    # ─── 分析接口 ──────────────────────────────────────────

    def get_product_neighbors(self, symbol: str) -> list[TransferEdge]:
        """获取某个品种的所有转移连接"""
        return [
            e for e in self._edges
            if e.source_symbol == symbol or e.target_symbol == symbol
        ]

    def get_strongest_transfers(self, top_n: int = 10) -> list[TransferEdge]:
        """获取最强的转移关系"""
        return sorted(self._edges, key=lambda e: e.strength, reverse=True)[:top_n]

    def get_transfer_matrix(self) -> tuple[list[str], np.ndarray]:
        """
        生成转移强度矩阵。

        Returns:
            (symbols列表, NxN 转移强度矩阵)
        """
        symbols = sorted(self._nodes.keys())
        n = len(symbols)
        matrix = np.zeros((n, n))

        sym_idx = {s: i for i, s in enumerate(symbols)}
        for edge in self._edges:
            i = sym_idx.get(edge.source_symbol)
            j = sym_idx.get(edge.target_symbol)
            if i is not None and j is not None:
                matrix[i][j] = edge.strength
                matrix[j][i] = edge.strength

        return symbols, matrix

    # ─── 内部计算 ──────────────────────────────────────────

    def _compute_transfer_edge(self, sym_a: str, sym_b: str) -> TransferEdge | None:
        """计算两个品种间的转移边"""
        records_a = sorted(self._flux_history.get(sym_a, []), key=lambda r: r.timestamp)
        records_b = sorted(self._flux_history.get(sym_b, []), key=lambda r: r.timestamp)

        if not records_a or not records_b:
            return None

        # 对齐时间序列
        aligned_a, aligned_b = self._align_time_series(records_a, records_b)
        if len(aligned_a) < self.min_overlap_days:
            return None

        flux_a = np.array([r.conservation_flux for r in aligned_a])
        flux_b = np.array([r.conservation_flux for r in aligned_b])

        # 计算不同滞后的相关性
        best_corr = 0.0
        best_lag = 0
        for lag in range(self.lag_range[0], self.lag_range[1] + 1):
            if lag == 0:
                corr = np.corrcoef(flux_a, flux_b)[0, 1]
            elif lag > 0:
                if len(flux_a) > lag:
                    corr = np.corrcoef(flux_a[:-lag], flux_b[lag:])[0, 1]
                else:
                    continue
            else:
                if len(flux_b) > abs(lag):
                    corr = np.corrcoef(flux_a[abs(lag):], flux_b[:lag])[0, 1]
                else:
                    continue

            if not np.isnan(corr) and abs(corr) > abs(best_corr):
                best_corr = corr
                best_lag = lag

        # 差异转移特征：负相关（一个释放，另一个蓄势）
        # 或者正相关但有滞后（传导效应）
        if best_corr < self.correlation_threshold:
            # 负相关 → 差异转移
            strength = min(1.0, abs(best_corr))
            direction = f"{sym_a}→{sym_b}" if best_lag >= 0 else f"{sym_b}→{sym_a}"
            confidence = "高" if abs(best_corr) > 0.6 else "中" if abs(best_corr) > 0.4 else "低"
        elif best_corr > 0.5 and best_lag > 0:
            # 正相关 + 滞后 → 传导效应
            strength = min(1.0, best_corr * 0.8)
            direction = f"{sym_a}→{sym_b}" if best_lag > 0 else f"{sym_b}→{sym_a}"
            confidence = "中"
        else:
            # 相关性不显著
            return None

        # 统计证据数量（连续同向变化的天数）
        evidence = self._count_evidence(flux_a, flux_b, best_lag)

        return TransferEdge(
            source_symbol=sym_a,
            target_symbol=sym_b,
            strength=round(strength, 3),
            direction=direction,
            correlation=round(best_corr, 3),
            lag_days=best_lag,
            confidence=confidence,
            evidence_count=evidence,
        )

    def _align_time_series(
        self,
        records_a: list[FluxRecord],
        records_b: list[FluxRecord],
    ) -> tuple[list[FluxRecord], list[FluxRecord]]:
        """对齐两个品种的时间序列"""
        # 按日期索引
        dates_a = {r.timestamp.date(): r for r in records_a}
        dates_b = {r.timestamp.date(): r for r in records_b}

        # 取交集
        common_dates = sorted(set(dates_a.keys()) & set(dates_b.keys()))

        aligned_a = [dates_a[d] for d in common_dates]
        aligned_b = [dates_b[d] for d in common_dates]

        return aligned_a, aligned_b

    def _count_evidence(self, flux_a: np.ndarray, flux_b: np.ndarray, lag: int) -> int:
        """统计转移证据数量"""
        count = 0
        if lag >= 0:
            for i in range(lag, min(len(flux_a), len(flux_b))):
                # 一个正值一个负值 = 转移证据
                if flux_a[i - lag] * flux_b[i] < 0:
                    count += 1
        else:
            for i in range(abs(lag), min(len(flux_a), len(flux_b))):
                if flux_a[i] * flux_b[i - abs(lag)] < 0:
                    count += 1
        return count

    def _compute_product_node(self, symbol: str) -> ProductNode:
        """计算品种节点属性"""
        records = self._flux_history.get(symbol, [])
        if not records:
            return ProductNode(
                symbol=symbol, name=symbol, avg_flux=0.0,
                flux_volatility=0.0, dominant_phase="unknown",
                transfer_centrality=0.0, connected_products=0,
            )

        fluxes = [r.conservation_flux for r in records]
        avg_flux = np.mean(fluxes)
        volatility = np.std(fluxes)

        # 主导阶段
        phases = [r.phase_tendency for r in records if r.phase_tendency]
        if phases:
            from collections import Counter
            dominant = Counter(phases).most_common(1)[0][0]
        else:
            dominant = "unknown"

        # 中心度：连接边数 / 总品种数
        connected = len(set(
            e.source_symbol if e.target_symbol == symbol else e.target_symbol
            for e in self._edges
            if e.source_symbol == symbol or e.target_symbol == symbol
        ))
        total_products = max(len(self._flux_history), 1)
        centrality = connected / total_products

        return ProductNode(
            symbol=symbol,
            name=symbol,
            avg_flux=round(avg_flux, 4),
            flux_volatility=round(volatility, 4),
            dominant_phase=dominant,
            transfer_centrality=round(centrality, 3),
            connected_products=connected,
        )

    def _detect_transfer_paths(self) -> list[TransferPath]:
        """检测转移路径（BFS）"""
        if not self._edges:
            return []

        # 构建邻接表
        adj: dict[str, list[tuple[str, float]]] = {}
        for e in self._edges:
            adj.setdefault(e.source_symbol, []).append((e.target_symbol, e.strength))
            adj.setdefault(e.target_symbol, []).append((e.source_symbol, e.strength))

        paths = []
        visited_pairs = set()

        for start in adj:
            # BFS 找最长路径
            queue = [(start, [start], 1.0)]
            while queue:
                current, path, strength = queue.pop(0)

                if len(path) > 2:
                    key = tuple(sorted(path))
                    if key not in visited_pairs:
                        visited_pairs.add(key)
                        is_cycle = len(path) > 2 and path[-1] in [
                            e.target_symbol for e in self._edges
                            if e.source_symbol == path[0]
                        ]
                        paths.append(TransferPath(
                            path=list(path),
                            total_strength=round(strength, 3),
                            path_length=len(path),
                            is_cycle=is_cycle,
                        ))

                if len(path) >= 4:  # 限制路径长度
                    continue

                for neighbor, edge_strength in adj.get(current, []):
                    if neighbor not in path:
                        queue.append((
                            neighbor,
                            path + [neighbor],
                            strength * edge_strength,
                        ))

        # 按强度排序
        paths.sort(key=lambda p: p.total_strength, reverse=True)
        return paths[:20]  # 返回 top 20

    def _detect_hot_spots(self) -> list[dict]:
        """检测转移热点"""
        hot_spots = []
        for edge in self._edges:
            if edge.strength > 0.5 and edge.evidence_count > 5:
                hot_spots.append({
                    "pair": f"{edge.source_symbol} ↔ {edge.target_symbol}",
                    "strength": edge.strength,
                    "correlation": edge.correlation,
                    "lag_days": edge.lag_days,
                    "evidence": edge.evidence_count,
                    "direction": edge.direction,
                })
        hot_spots.sort(key=lambda h: h["strength"], reverse=True)
        return hot_spots[:10]

    def _compute_systemic_stress(self) -> float:
        """计算系统级转移压力"""
        if not self._edges:
            return 0.0

        # 高强度边的数量占比
        strong_edges = sum(1 for e in self._edges if e.strength > 0.5)
        edge_pressure = strong_edges / max(len(self._edges), 1)

        # 品种通量波动率的平均值
        volatilities = [
            n.flux_volatility for n in self._nodes.values()
            if n.flux_volatility > 0
        ]
        avg_volatility = np.mean(volatilities) if volatilities else 0.0

        # 综合压力
        stress = 0.6 * edge_pressure + 0.4 * min(1.0, avg_volatility * 5)
        return round(stress, 3)

    # ─── 序列化 ──────────────────────────────────────────

    def to_dict(self) -> dict:
        """导出为可序列化字典"""
        return {
            "products": len(self._nodes),
            "edges": len(self._edges),
            "flux_records": sum(len(v) for v in self._flux_history.values()),
            "nodes": {
                sym: {
                    "avg_flux": n.avg_flux,
                    "volatility": n.flux_volatility,
                    "phase": n.dominant_phase,
                    "centrality": n.transfer_centrality,
                    "connections": n.connected_products,
                }
                for sym, n in self._nodes.items()
            },
            "edges_detail": [
                {
                    "source": e.source_symbol,
                    "target": e.target_symbol,
                    "strength": e.strength,
                    "correlation": e.correlation,
                    "lag": e.lag_days,
                    "confidence": e.confidence,
                }
                for e in self._edges
            ],
        }

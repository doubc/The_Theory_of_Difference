"""
数据层 — 统一读取接口

支持两种 CSV 格式（自动检测）：
  格式A: 分号分隔，每个值独立引号  — "date";"open";"high";...
  格式B: 整行引号包裹，值双引号    — "date;""open"";""high"";..."

内置去重、数据清洗、质量报告。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


# ─── Bar 数据类 ────────────────────────────────────────────

@dataclass
class Bar:
    """统一 K 线数据格式"""
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    open_interest: float | None = None
    adj_factor: float | None = None
    extra: dict | None = None


def bar_to_dict(b: Bar) -> dict:
    return {
        "symbol": b.symbol,
        "timestamp": b.timestamp,
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "volume": b.volume,
        "open_interest": b.open_interest,
        "adj_factor": b.adj_factor,
    }


# ─── 数据质量报告 ──────────────────────────────────────────

@dataclass
class DataQualityReport:
    """数据加载后的质量报告"""
    symbol: str
    raw_rows: int
    unique_dates: int
    duplicate_rows: int
    malformed_rows: int
    cleaned_rows: int
    date_start: datetime | None = None
    date_end: datetime | None = None
    price_min: float = 0.0
    price_max: float = 0.0
    anomaly_flags: list[str] = field(default_factory=list)

    def __str__(self):
        lines = [
            f"  品种:     {self.symbol}",
            f"  原始行数: {self.raw_rows}",
            f"  唯一日期: {self.unique_dates}",
            f"  重复行:   {self.duplicate_rows}",
            f"  格式异常: {self.malformed_rows}",
            f"  清洗后:   {self.cleaned_rows}",
            f"  时间范围: {self.date_start} ~ {self.date_end}",
            f"  价格范围: {self.price_min:.0f} ~ {self.price_max:.0f}",
        ]
        if self.anomaly_flags:
            lines.append(f"  异常标记: {len(self.anomaly_flags)} 条")
            for flag in self.anomaly_flags[:5]:
                lines.append(f"    - {flag}")
            if len(self.anomaly_flags) > 5:
                lines.append(f"    ... 及另外 {len(self.anomaly_flags) - 5} 条")
        return "\n".join(lines)


# ─── CSV 解析核心 ──────────────────────────────────────────

def _detect_format(file_path: Path) -> str:
    """检测 CSV 格式: 'A' = 独立引号, 'B' = 整行引号"""
    with open(file_path, encoding="utf-8", errors="replace") as f:
        first_line = f.readline().rstrip("\n")
    # 格式B: 整行以 " 开头，内部包含 ;"""
    if first_line.startswith('"') and '""' in first_line:
        return "B"
    return "A"


def _parse_format_a(file_path: Path) -> tuple[list[str], list[dict]]:
    """格式A: "date";"open";"high";..."""
    rows = []
    with open(file_path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f, delimiter=";")
        header = [h.strip('"').strip() for h in next(reader)]
        col = {name: i for i, name in enumerate(header)}

        for line_num, row in enumerate(reader, start=2):
            clean = [v.strip('"').strip() for v in row]
            if len(clean) < len(header):
                continue
            rows.append({k: clean[col[k]] for k in header})
    return header, rows


def _parse_format_b(file_path: Path) -> tuple[list[str], list[dict]]:
    # 格式B: 整行被双引号包裹, 内部每个值用双引号包围, 以分号分隔
    # 例如: "date;"open";"high";..."
    rows = []
    with open(file_path, encoding="utf-8", errors="replace") as f:
        # 第一行: header
        first = f.readline().rstrip("\n")
        # 去掉外层引号
        inner = first[1:-1] if first.startswith('"') and first.endswith('"') else first
        # 按 ;"" 分割（或 "";" ）
        header = []
        for token in inner.split(";"):
            token = token.strip('"').strip()
            header.append(token)
        col = {name: i for i, name in enumerate(header)}

        for line_num, line in enumerate(f, start=2):
            line = line.rstrip("\n")
            if not line:
                continue
            inner = line[1:-1] if line.startswith('"') and line.endswith('"') else line
            parts = inner.split(";")
            clean = [p.strip('"').strip() for p in parts]
            if len(clean) < len(header):
                continue
            rows.append({k: clean[col[k]] for k in header})
    return header, rows


# ─── CSV 数据加载器 ────────────────────────────────────────

class CSVLoader:
    """
    CSV 数据加载器，内置：
    - 双格式自动检测
    - 按日期去重（保留最后一条）
    - 数据质量报告
    """

    def __init__(self, file_path: str, symbol: str = "CU000"):
        self.file_path = Path(file_path)
        self.symbol = symbol
        self._bars: list[Bar] | None = None
        self._report: DataQualityReport | None = None

    def _parse_and_clean(self) -> tuple[list[Bar], DataQualityReport]:
        fmt = _detect_format(self.file_path)

        if fmt == "A":
            header, raw_rows = _parse_format_a(self.file_path)
        else:
            header, raw_rows = _parse_format_b(self.file_path)

        raw_count = len(raw_rows)
        malformed = 0
        anomaly_flags = []

        # 解析为 Bar 对象 + 去重
        seen_dates: dict[str, tuple[int, Bar]] = {}  # date_str -> (index, bar)
        for row in raw_rows:
            try:
                date_str = row.get("date", "").split(" ")[0]
                ts = datetime.strptime(date_str, "%Y-%m-%d")
                o = float(row["open"])
                h = float(row["high"])
                l = float(row["low"])
                c = float(row["close"])
                v = float(row["vol"])

                # 基本校验
                if h < l:
                    anomaly_flags.append(f"{date_str}: high({h}) < low({l})")
                    h, l = max(h, l), min(h, l)
                if o <= 0 or c <= 0:
                    anomaly_flags.append(f"{date_str}: non-positive price (open={o}, close={c})")
                    continue
                if v < 0:
                    anomaly_flags.append(f"{date_str}: negative volume ({v})")
                    v = 0

                # 换月标记
                new_flag = None
                if "new" in row:
                    try:
                        new_flag = int(row["new"])
                    except ValueError:
                        pass

                bar = Bar(
                    symbol=self.symbol,
                    timestamp=ts,
                    open=o, high=h, low=l, close=c, volume=v,
                    extra={"new": new_flag} if new_flag is not None else None,
                )

                if date_str in seen_dates:
                    # 重复日期：保留最后一条
                    seen_dates[date_str] = (seen_dates[date_str][0], bar)
                else:
                    seen_dates[date_str] = (len(seen_dates), bar)

            except (ValueError, KeyError) as e:
                malformed += 1
                continue

        # 按日期排序
        bars = [bar for _, bar in sorted(seen_dates.values(), key=lambda x: x[0])]
        bars.sort(key=lambda b: b.timestamp)

        duplicate_count = raw_count - malformed - len(bars)

        report = DataQualityReport(
            symbol=self.symbol,
            raw_rows=raw_count,
            unique_dates=len(bars),
            duplicate_rows=duplicate_count,
            malformed_rows=malformed,
            cleaned_rows=len(bars),
            date_start=bars[0].timestamp if bars else None,
            date_end=bars[-1].timestamp if bars else None,
            price_min=min(b.low for b in bars) if bars else 0,
            price_max=max(b.high for b in bars) if bars else 0,
            anomaly_flags=anomaly_flags,
        )

        return bars, report

    @property
    def bars(self) -> list[Bar]:
        if self._bars is None:
            self._bars, self._report = self._parse_and_clean()
        return self._bars

    @property
    def report(self) -> DataQualityReport:
        if self._report is None:
            _ = self.bars  # 触发解析
        return self._report

    def get(
            self,
            start: str | datetime | None = None,
            end: str | datetime | None = None,
    ) -> list[Bar]:
        bars = self.bars
        if start:
            s = _to_dt(start)
            bars = [b for b in bars if b.timestamp >= s]
        if end:
            e = _to_dt(end)
            bars = [b for b in bars if b.timestamp <= e]
        return bars

    def summary(self) -> dict:
        bars = self.bars
        return {
            "symbol": self.symbol,
            "count": len(bars),
            "start": bars[0].timestamp if bars else None,
            "end": bars[-1].timestamp if bars else None,
            "price_range": (
                min(b.low for b in bars),
                max(b.high for b in bars),
            ) if bars else (0, 0),
        }


# ─── MySQL 数据加载器（骨架）─────────────────────────────────

class MySQLLoader:
    """
    生产环境从 MySQL 读取。
    适配 sina 数据库结构: {code} (日线), {code}m5 (5分钟线)
    """

    def __init__(self, host='localhost', user='root', password='root', db='sina'):
        from sqlalchemy import create_engine
        self.engine = create_engine(f'mysql+pymysql://{user}:{password}@{host}/{db}?charset=utf8')

    def get(
            self,
            symbol: str,
            start: str | datetime | None = None,
            end: str | datetime | None = None,
            freq: str = "1d",
    ) -> list[Bar]:
        import pandas as pd
        
        # 根据频率选择表名
        table_name = f"{symbol}m5" if freq == "5m" else symbol
        
        sql = f"SELECT `date`, `open`, `high`, `low`, `close`, `vol` FROM sina.`{table_name}`"
        conditions = []
        params = {}
        
        if start:
            s = _to_dt(start).strftime('%Y-%m-%d')
            conditions.append("`date` >= %(start)s")
            params['start'] = s
        if end:
            e = _to_dt(end).strftime('%Y-%m-%d')
            conditions.append("`date` <= %(end)s")
            params['end'] = e
            
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        
        sql += " ORDER BY `date`"
        
        try:
            df = pd.read_sql(sql, con=self.engine, params=params)
            if df.empty:
                return []
            
            # 核心修复：按日期去重，保留最后一条记录
            df['date'] = pd.to_datetime(df['date'])
            df = df.drop_duplicates(subset=['date'], keep='last')
            df = df.sort_values('date').reset_index(drop=True)
            
            bars = []
            for _, row in df.iterrows():
                bars.append(Bar(
                    symbol=symbol,
                    timestamp=row['date'],
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row.get('vol', 0)),
                ))
            return bars
        except Exception as e:
            print(f"MySQL 读取失败: {e}")
            return []


# ─── 工具函数 ──────────────────────────────────────────────

def _to_dt(s: str | datetime) -> datetime:
    if isinstance(s, datetime):
        return s
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {s}")


# ─── 快捷函数 ──────────────────────────────────────────────

def load_cu0(data_dir: str = "data", dedup: bool = True) -> CSVLoader:
    """
    加载铜连续合约数据。
    dedup=True 优先加载去重版本 cu0.csv，否则用 cu0.csv。
    """
    if dedup:
        path = Path(data_dir) / "cu0.csv"
        if path.exists():
            return CSVLoader(str(path), symbol="CU000")
    path = Path(data_dir) / "cu0.csv"
    return CSVLoader(str(path), symbol="CU000")

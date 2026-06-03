#!/usr/bin/env python3
"""
每日行情更新 + 全市场机会扫描 一体化脚本
用途：cron 自动调用，更新 MySQL 行情数据后执行结构扫描
"""
import os, sys, json, glob
from datetime import datetime
from pathlib import Path

# 项目根目录
PROJECT = r"C:\Users\Administrator\Documents\the_theory_of_difference\10-期货价格结构检索系统\price-structure"
os.chdir(PROJECT)
sys.path.insert(0, PROJECT)

def step1_update_data() -> dict:
    """Step 1: 从新浪 API 更新行情到 MySQL"""
    print("=" * 60)
    print(f"[{datetime.now():%H:%M:%S}] Step 1: 更新行情数据...")
    print("=" * 60)
    
    ret = {"success": [], "failed": [], "count": 0}
    
    try:
        import subprocess
        r = subprocess.run([sys.executable, "update_today.py"],
                          capture_output=True, text=True, timeout=120)
        print(r.stdout[-3000:])
        if r.stderr:
            print("STDERR:", r.stderr[-1000:])
        # 从输出解析成功/失败
        for line in r.stdout.split("\n"):
            if "成功:" in line:
                try:
                    ret["count"] = int(line.split(":")[1].strip())
                except:
                    pass
            elif "失败:" in line:
                try:
                    ret["failed"] = line.split(":")[1].strip()
                except:
                    pass
    
    except subprocess.TimeoutExpired:
        print("  ⚠️ 更新超时（2分钟）")
    except Exception as e:
        print(f"  ❌ 更新失败：{e}")
    
    print(f"  更新完成：成功 {ret['count']} 个品种")
    return ret


def step2_run_scan() -> dict:
    """Step 2: 执行全市场结构机会扫描"""
    print()
    print("=" * 60)
    print(f"[{datetime.now():%H:%M:%S}] Step 2: 运行全市场机会扫描...")
    print("=" * 60)
    
    ret = {"html_path": "", "json_path": "", "opportunities": 0, "structures": 0, "symbols": 0}
    
    try:
        import subprocess
        r = subprocess.run([sys.executable, "run_scan.py"],
                          capture_output=True, text=True, timeout=300)
        output = r.stdout
        print(output[-4000:])
        if r.stderr:
            print("STDERR:", r.stderr[-1500:])
        
        # 从输出解析关键指标
        for line in output.split("\n"):
            if "扫描" in line and "品种" in line and "结构" in line and "机会" in line:
                import re
                nums = re.findall(r'\d+', line)
                if len(nums) >= 3:
                    ret["symbols"] = int(nums[0])
                    ret["structures"] = int(nums[1])
                    ret["opportunities"] = int(nums[2])
            if line.startswith("HTML 日报:"):
                ret["html_path"] = line.split(":", 1)[1].strip()
            if line.startswith("JSON 快照:"):
                ret["json_path"] = line.split(":", 1)[1].strip()
            if "知识图谱" in line:
                ret["graph_info"] = line.strip()
        
        # fallback: 找最新的产出
        if not ret["html_path"]:
            html_files = sorted(glob.glob("output/daily_report_*.html"), key=os.path.getmtime)
            if html_files:
                ret["html_path"] = os.path.abspath(html_files[-1])
        if not ret["json_path"]:
            json_files = sorted(glob.glob("output/daily_scan_*.json"), key=os.path.getmtime)
            if json_files:
                ret["json_path"] = os.path.abspath(json_files[-1])
    
    except subprocess.TimeoutExpired:
        print("  ⚠️ 扫描超时（5分钟），结果可能不完整")
    except Exception as e:
        print(f"  ❌ 扫描失败：{e}")
    
    return ret


def step3_read_top_opportunities(json_path: str, top_n: int = 5) -> list:
    """Step 3: 从 JSON 快照中读取 top 机会"""
    if not json_path or not os.path.exists(json_path):
        return []
    
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        opps = data.get("opportunities", [])
        meta = data.get("scan_meta", {})
        
        results = []
        for opp in opps[:top_n]:
            results.append({
                "symbol": opp.get("symbol", "?"),
                "name": opp.get("symbol_name", "?"),
                "price": opp.get("current_price", 0),
                "attention_score": opp.get("attention_score", 0),
                "signal_type": opp.get("signal_type", "?"),
                "direction": opp.get("direction", "?"),
                "phase_tendency": opp.get("phase_tendency", "?"),
                "price_position": opp.get("price_position", "?"),
            })
        
        return {
            "meta": meta,
            "top": results,
            "total_opportunities": len(opps),
        }
    except Exception as e:
        print(f"  读取 JSON 快照失败：{e}")
        return []


def main():
    print(f"{'#' * 60}")
    print(f"#  期货价格结构检索系统 - 每日行情更新及扫描")
    print(f"#  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"{'#' * 60}")
    
    # Step 1
    update_result = step1_update_data()
    
    # Step 2
    scan_result = step2_run_scan()
    
    # Step 3: 读取结果
    print()
    print("=" * 60)
    print("📊 今日扫描结果摘要")
    print("=" * 60)
    
    top_data = step3_read_top_opportunities(scan_result.get("json_path", ""))
    
    if top_data:
        meta = top_data.get("meta", {})
        print(f"\n扫描概览：")
        print(f"  • 扫描 {meta.get('total_symbols', scan_result['symbols'])} 个品种")
        print(f"  • 识别 {meta.get('structures_found', scan_result['structures'])} 个结构")
        print(f"  • 产出 {top_data['total_opportunities']} 个机会")
        print(f"  • 模板库 {meta.get('template_count', '?')} 条")
        
        print(f"\n🏆 Top 机会：")
        for i, opp in enumerate(top_data.get("top", []), 1):
            score = opp.get("attention_score", 0)
            sig = opp.get("signal_type", "?")
            print(f"  {i}. {opp['symbol']} {opp['name']} "
                  f"| 价格={opp['price']} | 分数={score} "
                  f"| 信号={sig} | 方向={opp['direction']}")
    else:
        print("  ⚠️ 未能获取机会详情")
    
    if scan_result.get("html_path"):
        print(f"\n📄 HTML 日报：{scan_result['html_path']}")
    if scan_result.get("json_path"):
        print(f"📦 JSON 快照：{scan_result['json_path']}")
    
    print(f"\n{'=' * 60}")
    print(f"✅ 每日扫描完成 [{datetime.now():%Y-%m-%d %H:%M}]")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

"""
信号跟踪页 — 跟踪信号执行和绩效

功能：
  1. 查看当前持仓信号
  2. 记录信号平仓
  3. 信号绩效统计
  4. 信号历史回看
"""

from __future__ import annotations
import streamlit as st
from datetime import datetime
from src.workbench.data_flow import get_flow_manager, SignalRecord


def render_signal_tracking(ctx: dict):
    """渲染信号跟踪页面"""
    st.markdown("#### 📊 信号跟踪")
    st.caption("跟踪信号执行、记录平仓、查看绩效统计")

    flow = get_flow_manager()

    # ── 子 Tab ──
    tab_open, tab_stats, tab_history, tab_create = st.tabs([
        "📌 持仓信号", "📈 绩效统计", "📂 历史信号", "✏️ 手动录入"
    ])

    # ════════════════════════════════════════════════════════
    # 持仓信号
    # ════════════════════════════════════════════════════════
    with tab_open:
        st.markdown("**📌 当前持仓信号**")

        open_signals = flow.get_open_signals()

        if not open_signals:
            st.info("暂无持仓信号。在「📡 今日扫描」中发现信号后，可自动记录。")
        else:
            st.metric("持仓数量", len(open_signals))

            for sig in open_signals:
                dir_icon = "📈" if sig.direction == "long" else "📉" if sig.direction == "short" else "➡️"
                days_held = (datetime.now() - datetime.fromisoformat(sig.created_at)).days

                # 计算当前盈亏
                current_price = 0
                try:
                    bars = ctx.get("bars", [])
                    if bars and sig.symbol == ctx.get("selected_symbol"):
                        current_price = bars[-1].close
                except Exception:
                    pass

                unrealized_pnl = 0
                if current_price > 0 and sig.entry_price > 0:
                    if sig.direction == "long":
                        unrealized_pnl = current_price - sig.entry_price
                    else:
                        unrealized_pnl = sig.entry_price - current_price

                pnl_color = "#4caf50" if unrealized_pnl > 0 else "#ef5350" if unrealized_pnl < 0 else "#999"

                with st.expander(f"{dir_icon} {sig.symbol} · {sig.signal_type} · 持仓{days_held}天", expanded=False):
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("入场价", f"{sig.entry_price:.1f}")
                    with col2:
                        st.metric("止损", f"{sig.stop_loss_price:.1f}")
                    with col3:
                        st.metric("目标", f"{sig.take_profit_price:.1f}")
                    with col4:
                        st.metric("盈亏比", f"{sig.rr_ratio:.1f}")

                    if current_price > 0:
                        st.markdown(f"**当前价格**: {current_price:.1f} · "
                                   f"**浮动盈亏**: <span style='color:{pnl_color}'>{unrealized_pnl:+.1f}</span>",
                                   unsafe_allow_html=True)

                    st.caption(f"信号时间: {sig.created_at[:19]} · "
                              f"Zone: {sig.zone_center:.0f}±{sig.zone_bw:.0f} · "
                              f"通量: {sig.flux:+.3f} · "
                              f"质量: {sig.quality_tier}")

                    # 平仓操作
                    st.markdown("---")
                    close_col1, close_col2, close_col3 = st.columns([2, 1, 1])
                    with close_col1:
                        exit_price = st.number_input(
                            "平仓价格",
                            value=float(current_price) if current_price > 0 else float(sig.entry_price),
                            key=f"exit_price_{sig.created_at}"
                        )
                    with close_col2:
                        close_status = st.selectbox(
                            "平仓原因",
                            ["manual", "hit_target", "hit_stop", "expired"],
                            key=f"close_status_{sig.created_at}"
                        )
                    with close_col3:
                        if st.button("✅ 平仓", key=f"close_{sig.created_at}", type="primary"):
                            ok = flow.close_signal(
                                symbol=sig.symbol,
                                created_at=sig.created_at,
                                exit_price=exit_price,
                                status=close_status,
                            )
                            if ok:
                                st.success(f"✅ {sig.symbol} 已平仓")
                                st.rerun()
                            else:
                                st.error("平仓失败")

    # ════════════════════════════════════════════════════════
    # 绩效统计
    # ════════════════════════════════════════════════════════
    with tab_stats:
        st.markdown("**📈 信号绩效统计**")

        stats = flow.get_signal_stats()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("总信号", stats["total"])
        col2.metric("持仓中", stats["open"])
        col3.metric("已平仓", stats["closed"])
        col4.metric("命中率", f"{stats['hit_rate']:.0%}")

        if stats["closed"] > 0:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("止盈次数", stats["hit_target"])
            with col2:
                st.metric("止损次数", stats["hit_stop"])

            if stats["total_pnl"] != 0:
                pnl_color = "green" if stats["total_pnl"] > 0 else "red"
                st.markdown(f"**累计盈亏**: <span style='color:{pnl_color};font-size:1.2em;font-weight:700'>"
                           f"{stats['total_pnl']:+.1f}</span>", unsafe_allow_html=True)
        else:
            st.info("暂无已平仓信号，无法计算绩效。")

    # ════════════════════════════════════════════════════════
    # 历史信号
    # ════════════════════════════════════════════════════════
    with tab_history:
        st.markdown("**📂 历史信号**")

        if not flow.signal_file.exists():
            st.info("暂无信号记录")
        else:
            import json
            entries = []
            with open(flow.signal_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except Exception:
                            continue

            if not entries:
                st.info("暂无信号记录")
            else:
                # 筛选
                filter_col1, filter_col2 = st.columns(2)
                with filter_col1:
                    filter_status = st.selectbox("状态", ["全部", "open", "hit_target", "hit_stop", "manual", "expired"])
                with filter_col2:
                    filter_symbol = st.selectbox("品种", ["全部"] + list(set(e.get("symbol", "") for e in entries)))

                filtered = entries
                if filter_status != "全部":
                    filtered = [e for e in filtered if e.get("status") == filter_status]
                if filter_symbol != "全部":
                    filtered = [e for e in filtered if e.get("symbol") == filter_symbol]

                st.caption(f"共 {len(filtered)} 条记录")

                for e in filtered[:20]:
                    dir_icon = "📈" if e.get("direction") == "long" else "📉" if e.get("direction") == "short" else "➡️"
                    status_icon = {"open": "📌", "hit_target": "✅", "hit_stop": "❌", "manual": "🔧", "expired": "⏰"}.get(e.get("status", ""), "❓")

                    pnl = e.get("actual_pnl", 0)
                    pnl_color = "#4caf50" if pnl > 0 else "#ef5350" if pnl < 0 else "#999"

                    with st.expander(f"{status_icon} {dir_icon} {e.get('symbol', '')} · {e.get('signal_type', '')} · "
                                    f"{'盈' if pnl > 0 else '亏' if pnl < 0 else '—'}{abs(pnl):.1f}"):
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.markdown(f"**入场**: {e.get('entry_price', 0):.1f}")
                            st.markdown(f"**止损**: {e.get('stop_loss_price', 0):.1f}")
                            st.markdown(f"**目标**: {e.get('take_profit_price', 0):.1f}")
                        with col2:
                            st.markdown(f"**平仓**: {e.get('actual_exit_price', 0):.1f}")
                            st.markdown(f"**盈亏**: <span style='color:{pnl_color}'>{pnl:+.1f}</span>",
                                       unsafe_allow_html=True)
                            st.markdown(f"**持仓天数**: {e.get('actual_holding_days', 0)}")
                        with col3:
                            st.markdown(f"**状态**: {e.get('status', '')}")
                            st.markdown(f"**创建**: {e.get('created_at', '')[:19]}")
                            st.markdown(f"**平仓**: {e.get('closed_at', '')[:19]}")
                        if e.get("notes"):
                            st.info(e["notes"])

    # ════════════════════════════════════════════════════════
    # 手动录入
    # ════════════════════════════════════════════════════════
    with tab_create:
        st.markdown("**✏️ 手动录入信号**")

        create_col1, create_col2 = st.columns(2)
        with create_col1:
            new_symbol = st.text_input("品种代码", value=ctx.get("selected_symbol", ""), key="new_sig_symbol")
            new_type = st.selectbox("信号类型", [
                "breakout_confirm", "fake_breakout", "pullback_confirm",
                "structure_expired", "blind_breakout", "manual"
            ], key="new_sig_type")
            new_direction = st.selectbox("方向", ["long", "short", "neutral"], key="new_sig_dir")
            new_confidence = st.slider("置信度", 0.0, 1.0, 0.5, key="new_sig_conf")

        with create_col2:
            new_entry = st.number_input("入场价", value=0.0, key="new_sig_entry")
            new_stop = st.number_input("止损价", value=0.0, key="new_sig_stop")
            new_target = st.number_input("目标价", value=0.0, key="new_sig_target")
            new_zone_center = st.number_input("Zone 中心", value=0.0, key="new_sig_zone")
            new_zone_bw = st.number_input("Zone 带宽", value=0.0, key="new_sig_bw")

        new_notes = st.text_area("备注", key="new_sig_notes")

        if st.button("💾 保存信号", type="primary", key="save_new_signal"):
            if new_symbol and new_entry > 0:
                rr = abs(new_target - new_entry) / max(abs(new_entry - new_stop), 0.1) if new_stop != new_entry else 0

                signal = SignalRecord(
                    symbol=new_symbol.upper(),
                    signal_type=new_type,
                    direction=new_direction,
                    confidence=new_confidence,
                    entry_price=new_entry,
                    stop_loss_price=new_stop,
                    take_profit_price=new_target,
                    rr_ratio=round(rr, 2),
                    zone_center=new_zone_center,
                    zone_bw=new_zone_bw,
                    phase="",
                    flux=0.0,
                    quality_tier="",
                    notes=new_notes,
                )
                flow.save_signal(signal)
                st.success(f"✅ 信号已保存: {new_symbol.upper()} {new_type}")
            else:
                st.warning("请填写品种代码和入场价")

#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TZ = dt.timezone(dt.timedelta(hours=8))
LEDGER = ROOT / "竞彩模型赛前锁版与复盘账本.csv"
ROLLING = ROOT / "extracted" / "竞彩" / "滚动统计.json"
OUTPUT = ROOT / "records" / "portfolio_status.md"


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_ledger() -> list[dict[str, str]]:
    if not LEDGER.exists():
        return []
    with LEDGER.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def num(value: str | None) -> float:
    text = str(value or "").strip().replace("%", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def fmt_money(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def latest_file(directory: str) -> str:
    path = ROOT / "records" / directory
    if not path.exists():
        return "无"
    files = sorted(path.glob("*.md"))
    if not files:
        return "无"
    return str(files[-1].relative_to(ROOT)).replace("\\", "/")


def is_settled(row: dict[str, str]) -> bool:
    return any(str(row.get(k, "")).strip() for k in ("result", "hit", "return_amount", "profit", "review_notes"))


def official_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in rows if truthy(r.get("official_plan")) and not truthy(r.get("simulated_only"))]


def ledger_summary(rows: list[dict[str, str]]) -> dict[str, float | int | None]:
    settled = [r for r in official_rows(rows) if is_settled(r)]
    invested = sum(num(r.get("stake")) for r in settled)
    returned = sum(num(r.get("return_amount")) for r in settled)
    profit_values = [num(r.get("profit")) for r in settled if str(r.get("profit", "")).strip()]
    profit = sum(profit_values) if profit_values else returned - invested
    hit_count = sum(1 for r in settled if str(r.get("hit", "")).strip().lower() in {"1", "true", "yes", "y", "中", "hit"})
    roi = (profit / invested) if invested else None
    hit_rate = (hit_count / len(settled)) if settled else None
    return {
        "bets": len(settled),
        "invested": invested,
        "returned": returned,
        "profit": profit,
        "roi": roi,
        "hit_rate": hit_rate,
    }


def pending_positions(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in official_rows(rows) if num(r.get("stake")) > 0 and not is_settled(r)]


def rolling_pending(rolling: dict) -> list[dict[str, str]]:
    pending: list[dict[str, str]] = []
    for day in rolling.get("rolling_7day", {}).get("daily_detail", []) or []:
        date = str(day.get("date", ""))
        for bucket in ("conservative", "aggressive", "bookmaker"):
            item = day.get(bucket) or {}
            if str(item.get("hit", "")).strip().lower() == "pending" and num(str(item.get("invested", ""))) > 0:
                pending.append(
                    {
                        "date": date,
                        "type": bucket,
                        "scheme": str(item.get("scheme", "")),
                        "bets": str(item.get("bets", "")),
                        "invested": str(item.get("invested", "")),
                        "odds": str(item.get("odds", "")),
                        "note": str(item.get("note", "")),
                    }
                )
    return pending


def append_ledger_section(lines: list[str], rows: list[dict[str, str]]) -> None:
    positions = pending_positions(rows)
    summary = ledger_summary(rows)

    lines.extend(
        [
            "## 当前持仓（结构化账本）",
            "",
            "| 日期 | 场次 | 玩法 | 方向 | 锁定赔率 | stake | 状态 |",
            "|---|---|---|---|---:|---:|---|",
        ]
    )
    if positions:
        for r in positions:
            match = f"{r.get('match_id', '')} {r.get('home', '')} vs {r.get('away', '')}".strip()
            lines.append(
                "| "
                f"{r.get('date', '')} | {match} | {r.get('play_type', '')} | {r.get('selection', '')} | "
                f"{r.get('odds_at_lock', '')} | {r.get('stake', '')} | 未结算 |"
            )
    else:
        lines.append("| - | - | - | - | - | - | 当前无账本化未结算正式持仓 |")
    lines.extend(
        [
            "",
            "## 收益率（结构化账本正式方案）",
            "",
            "| 已结算笔数 | 投入 | 回报 | 净收益 | ROI | 命中率 |",
            "|---:|---:|---:|---:|---:|---:|",
            f"| {summary['bets']} | {fmt_money(float(summary['invested']))} | {fmt_money(float(summary['returned']))} | "
            f"{fmt_money(float(summary['profit']))} | {fmt_pct(summary['roi'])} | {fmt_pct(summary['hit_rate'])} |",
            "",
        ]
    )


def append_rolling_section(lines: list[str], rolling: dict) -> None:
    roll = rolling.get("rolling_7day", {}) or {}
    summary = roll.get("summary", {}) or {}
    by_type = roll.get("by_type", {}) or {}
    pending = rolling_pending(rolling)

    lines.extend(
        [
            "## 滚动统计快照",
            "",
            f"- 统计周期：{roll.get('period', 'unknown')}",
            f"- 更新时间：{rolling.get('last_updated', 'unknown')}",
            "",
            "| 口径 | 投注数 | 命中率 | 投入 | 回报 | 净收益 | ROI | 未结 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
            f"| 总计 | {summary.get('total_bets', 0)} | {summary.get('hit_rate', 'N/A')} | {summary.get('total_invested', 0)} | "
            f"{summary.get('total_return', 0)} | {summary.get('net_profit', 0)} | {summary.get('roi', 'N/A')} | {summary.get('pending', 0)} |",
        ]
    )
    labels = {"conservative": "稳健型", "aggressive": "进取型", "bookmaker": "庄家视角"}
    for key, label in labels.items():
        item = by_type.get(key, {}) or {}
        if not item:
            continue
        lines.append(
            f"| {label} | {item.get('total_bets', 0)} | {item.get('hit_rate', 'N/A')} | "
            f"{item.get('total_invested', 0)} | {item.get('total_return', 0)} | "
            f"{item.get('net_profit', 0)} | {item.get('roi', 'N/A')} | {item.get('pending', 0)} |"
        )

    lines.extend(["", "## 滚动统计未结样本", "", "| 日期 | 类型 | 方案 | 组合 | 投入 | 赔率 | 备注 |", "|---|---|---|---|---:|---:|---|"])
    if pending:
        for p in pending:
            lines.append(
                f"| {p['date']} | {p['type']} | {p['scheme']} | {p['bets']} | {p['invested']} | {p['odds']} | {p['note']} |"
            )
    else:
        lines.append("| - | - | - | - | - | - | 滚动统计未记录 pending 样本 |")
    lines.append("")


def build_report(now: dt.datetime) -> str:
    rows = read_ledger()
    rolling = read_json(ROLLING)
    lines = [
        "# 投资模型持仓与收益率看板",
        "",
        "> 自动更新文件。只统计账本化正式方案；模拟、观察、红灯跳过不计入正式收益。",
        "",
        "## 更新时间",
        "",
        f"- 生成时间：{now:%Y-%m-%d %H:%M:%S %z} (Asia/Shanghai)",
        f"- 账本文件：`{LEDGER.relative_to(ROOT)}`",
        f"- 账本记录数：{len(rows)}",
        f"- 最新21点终版：`{latest_file('21_final')}`",
        f"- 最新复盘：`{latest_file('reviews')}`",
        "",
    ]
    lines.insert(3, "> 观察池另按赛前锁定的让球单选主项与初盘赔率做模拟收益复盘；双选只作附录覆盖观察。")
    append_ledger_section(lines, rows)
    append_rolling_section(lines, rolling)
    lines.extend(
        [
            "## 数据口径",
            "",
            "- 当前持仓：`official_plan=true`、`simulated_only` 不为 true、`stake>0` 且尚无赛果/回报/复盘记录的账本行。",
            "- 结构化收益率：只统计已结算的正式方案账本行；如果 `profit` 为空，则用 `return_amount - stake` 估算。",
            "- 滚动统计快照：来自 `extracted/竞彩/滚动统计.json`，用于在账本尚未完整结构化时提供历史收益视图。",
            "- 低置信观察、黄灯模拟、冷门样本不计入正式收益，避免把模拟命中包装成真实收益。",
            "",
        ]
    )
    lines.insert(
        -1,
        "- 观察池收益优先按让球单选主项计算：每场 1u，命中回报=初盘赔率，未命中回报=0；赛前未锁单选主项时不得赛后择优计入。",
    )
    return "\n".join(lines)


def main() -> None:
    now = dt.datetime.now(TZ)
    OUTPUT.write_text(build_report(now).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()

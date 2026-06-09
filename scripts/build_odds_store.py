#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = ROOT / "records" / "odds_snapshots"
STORE_DIR = ROOT / "records" / "odds_store"

LINE_VALUES = {
    "平手": 0.0,
    "平手/半球": 0.25,
    "半球": 0.5,
    "半球/一球": 0.75,
    "一球": 1.0,
    "一球/球半": 1.25,
    "球半": 1.5,
    "球半/两球": 1.75,
    "两球": 2.0,
    "两球/两球半": 2.25,
    "两球半": 2.5,
    "两球半/三球": 2.75,
    "三球": 3.0,
    "三球/三球半": 3.25,
    "三球半": 3.5,
    "三球半/四球": 3.75,
    "四球": 4.0,
    "四球/四球半": 4.25,
    "四球半": 4.5,
}

MARKET_LABELS = {
    "asian_handicap": "亚盘让球",
    "handicap_1x2": "竞彩让球指数",
    "over_under": "亚洲大小球",
    "european_odds": "欧赔",
}

LINE_TOKEN = r"(?:平手/半球|半球/一球|一球/球半|球半/两球|两球/两球半|两球半/三球|三球/三球半|三球半/四球|四球/四球半|平手|半球|一球|球半|两球|两球半|三球|三球半|四球|四球半|\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)"
WATER_TOKEN = re.compile(r"(\d+\.\d{2,3})([↑↓]?)")
LINE_RE = re.compile(LINE_TOKEN)


def parse_line_value(raw: str | None) -> float | None:
    if not raw:
        return None
    raw = raw.strip()
    if raw in LINE_VALUES:
        return LINE_VALUES[raw]
    if "/" in raw:
        values: list[float] = []
        for item in raw.split("/"):
            try:
                values.append(float(item))
            except ValueError:
                return None
        return sum(values) / len(values) if values else None
    try:
        return float(raw)
    except ValueError:
        return None


def extract_line(segment: str) -> tuple[str | None, str | None]:
    segment = segment.replace("升", " ").replace("降", " ")
    match = LINE_RE.search(segment)
    if not match:
        return None, None
    raw = match.group(0)
    arrow_match = re.search(re.escape(raw) + r"([↑↓])?", segment)
    return raw, arrow_match.group(1) if arrow_match else None


def parse_handicap_like_row(text: str) -> dict[str, Any]:
    """Parse 500.com asian handicap / over-under rows when a full company row is present."""
    waters = list(WATER_TOKEN.finditer(text))
    if len(waters) < 4:
        return {}

    current_left, current_right, open_left, open_right = waters[0], waters[1], waters[-2], waters[-1]
    current_line, current_line_arrow = extract_line(text[current_left.end() : current_right.start()])
    open_line, open_line_arrow = extract_line(text[open_left.end() : open_right.start()])
    if not current_line or not open_line:
        return {}

    line_move = None
    current_segment = text[current_left.end() : current_right.start()]
    if "升" in current_segment:
        line_move = "升"
    elif "降" in current_segment:
        line_move = "降"

    parsed: dict[str, Any] = {
        "current_left": float(current_left.group(1)),
        "current_left_arrow": current_left.group(2) or None,
        "current_line": current_line,
        "current_line_arrow": current_line_arrow,
        "line_move": line_move,
        "current_right": float(current_right.group(1)),
        "current_right_arrow": current_right.group(2) or None,
        "open_left": float(open_left.group(1)),
        "open_left_arrow": open_left.group(2) or None,
        "open_line": open_line,
        "open_line_arrow": open_line_arrow,
        "open_right": float(open_right.group(1)),
        "open_right_arrow": open_right.group(2) or None,
    }
    parsed["current_line_value"] = parse_line_value(parsed.get("current_line"))
    parsed["open_line_value"] = parse_line_value(parsed.get("open_line"))
    return parsed


def direction_for_market(market: str, parsed: dict[str, Any]) -> str:
    current_line = parsed.get("current_line_value")
    open_line = parsed.get("open_line_value")
    left_delta = parsed.get("current_left", 0.0) - parsed.get("open_left", 0.0)
    right_delta = parsed.get("current_right", 0.0) - parsed.get("open_right", 0.0)

    if market == "asian_handicap":
        if current_line is not None and open_line is not None:
            if current_line > open_line:
                return "home_strengthened_line"
            if current_line < open_line:
                return "away_strengthened_line"
        if left_delta <= -0.03 and right_delta >= 0.03:
            return "home_strengthened_water"
        if right_delta <= -0.03 and left_delta >= 0.03:
            return "away_strengthened_water"
        return "balanced_or_unclear"

    if market == "over_under":
        if current_line is not None and open_line is not None:
            if current_line > open_line:
                return "over_strengthened_line"
            if current_line < open_line:
                return "under_strengthened_line"
        if left_delta <= -0.03 and right_delta >= 0.03:
            return "over_strengthened_water"
        if right_delta <= -0.03 and left_delta >= 0.03:
            return "under_strengthened_water"
        return "balanced_or_unclear"

    return "raw_only"


def representative_rows(rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    result = []
    seen = set()
    for row in rows:
        text = row.get("text", "")
        # Prefer full company rows with both current and opening odds timestamps.
        if not re.match(r"^\d+\s+", text):
            continue
        if text in seen:
            continue
        seen.add(text)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def snapshot_paths(day: str) -> list[Path]:
    return sorted(SNAPSHOT_DIR.glob(f"{day}-*.json"))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_store_for_day(day: str) -> tuple[Path, Path]:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    events_path = STORE_DIR / f"{day}-events.jsonl"
    summary_path = STORE_DIR / f"{day}-summary.md"

    events: list[dict[str, Any]] = []
    direction_counts: dict[str, Counter[str]] = defaultdict(Counter)
    latest_by_match: dict[str, dict[str, Any]] = {}
    paths = snapshot_paths(day)

    for path in paths:
        snapshot = load_json(path)
        snapshot_id = path.stem
        generated_at = snapshot.get("generated_at")
        for match in snapshot.get("matches", []):
            match_id = str(match.get("match_id", ""))
            latest_by_match[match_id] = {
                "match_id": match_id,
                "kickoff": match.get("kickoff"),
                "row_text": match.get("row_text"),
            }
            for market, detail in (match.get("details") or {}).items():
                rows = representative_rows(detail.get("rows") or [])
                if not rows:
                    continue
                for idx, row in enumerate(rows, start=1):
                    text = row.get("text", "")
                    parsed = parse_handicap_like_row(text) if market in {"asian_handicap", "over_under"} else {}
                    direction = direction_for_market(market, parsed) if parsed else "raw_only"
                    if parsed:
                        direction_counts[f"{match_id}:{market}"][direction] += 1
                    events.append(
                        {
                            "schema_version": "1.0",
                            "snapshot_id": snapshot_id,
                            "generated_at": generated_at,
                            "source": snapshot.get("source"),
                            "source_file": str(path.relative_to(ROOT)).replace("\\", "/"),
                            "match_id": match_id,
                            "kickoff": match.get("kickoff"),
                            "list_row": match.get("row_text"),
                            "market": market,
                            "market_label": MARKET_LABELS.get(market, market),
                            "row_index": idx,
                            "data_time": row.get("data_time"),
                            "raw_text": text,
                            "parsed": parsed,
                            "direction": direction,
                            "parse_status": "parsed" if parsed else "raw_only",
                            "url": detail.get("url"),
                            "status": detail.get("status"),
                            "charset": detail.get("charset"),
                        }
                    )

    with events_path.open("w", encoding="utf-8", newline="\n") as f:
        for event in events:
            f.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    lines = [
        f"# 赔率结构化摘要 - {day}",
        "",
        f"- 快照数：{len(paths)}",
        f"- 结构化/原始行：{len(events)}",
        "- 说明：500 比赛 ID 不是竞彩周编号，报告引用前必须用队名和开赛时间核验。",
        "- 方向只来自可解析的赛前快照行；无法解析时保留 raw_only，不补造方向。",
        "",
        "## 方向共振",
        "",
        "| 500比赛ID | 场次文本 | 市场 | 方向计数 |",
        "|---|---|---|---|",
    ]
    for key in sorted(direction_counts):
        match_id, market = key.split(":", 1)
        match = latest_by_match.get(match_id, {})
        counts = ", ".join(f"{name}={count}" for name, count in direction_counts[key].most_common())
        lines.append(
            f"| {match_id} | {match.get('row_text', '')} | {MARKET_LABELS.get(market, market)} | {counts} |"
        )
    if not direction_counts:
        lines.append("| - | - | - | 无可解析方向，仅保留原始行 |")

    lines.extend(
        [
            "",
            "## 最新快照入口",
            "",
        ]
    )
    for path in paths[-3:]:
        lines.append(f"- `{path.relative_to(ROOT).as_posix()}`")

    summary_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    (STORE_DIR / ".latest_path").write_text(str(summary_path.relative_to(ROOT)).replace("\\", "/"), encoding="utf-8")
    return events_path, summary_path


def odds_store_context(day: str, limit: int = 14000) -> str:
    summary = STORE_DIR / f"{day}-summary.md"
    if not summary.exists():
        return "## 结构化赔率方向摘要\nSTATUS: missing; 尚未生成 records/odds_store 摘要。\n"
    text = summary.read_text(encoding="utf-8", errors="replace")
    return "## 结构化赔率方向摘要\n" + text[:limit] + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build structured odds store from records/odds_snapshots.")
    parser.add_argument("--date", default=dt.datetime.now().date().isoformat())
    args = parser.parse_args()
    events_path, summary_path = build_store_for_day(args.date)
    print(f"wrote {events_path}")
    print(f"wrote {summary_path}")


if __name__ == "__main__":
    main()

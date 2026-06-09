#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TZ = dt.timezone(dt.timedelta(hours=8))
DATASET_DIR = ROOT / "records" / "dataset"
ODDS_SNAPSHOT_DIR = ROOT / "records" / "odds_snapshots"
ODDS_STORE_DIR = ROOT / "records" / "odds_store"
OBSERVATIONS_CSV = DATASET_DIR / "match_observations.csv"
DEFAULT_OUTPUT = DATASET_DIR / "jincai_match_database.json"

MARKET_LABELS = {
    "asian_handicap": "亚盘让球",
    "handicap_1x2": "竞彩让球指数",
    "over_under": "亚洲大小球",
    "european_odds": "欧赔",
}

TEAM_ALIASES = {
    "andorra": "安道尔",
    "argentina": "阿根廷",
    "bhutan": "不丹",
    "cambodia": "柬埔寨",
    "canada": "加拿大",
    "china": "中国",
    "cyprus": "塞浦路斯",
    "finland": "芬兰",
    "france": "法国",
    "hungary": "匈牙利",
    "iceland": "冰岛",
    "ireland": "爱尔兰",
    "iraq": "伊拉克",
    "ivory coast": "科特迪瓦",
    "kazakhstan": "哈萨克斯坦",
    "kenya": "肯尼亚",
    "lesotho": "莱索托",
    "liechtenstein": "列支敦士登",
    "mexico": "墨西哥",
    "montenegro": "黑山",
    "netherlands": "荷兰",
    "northern ireland": "北爱尔兰",
    "peru": "秘鲁",
    "serbia": "塞尔维亚",
    "singapore": "新加坡",
    "slovakia": "斯洛伐克",
    "slovenia": "斯洛文尼亚",
    "spain": "西班牙",
    "thailand": "泰国",
    "uzbekistan": "乌兹别克斯坦",
}


def compact(text: object, limit: int = 260) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()[:limit]


def slug(text: str) -> str:
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff]+", "-", text).strip("-").lower()
    return value[:80] or "unknown"


def alias_match_name(match_name: str) -> str:
    parts = re.split(r"\s+vs\s+", match_name, flags=re.I)
    if len(parts) != 2:
        return match_name
    home = TEAM_ALIASES.get(parts[0].strip().lower(), parts[0].strip())
    away = TEAM_ALIASES.get(parts[1].strip().lower(), parts[1].strip())
    return f"{home} vs {away}"


def parse_match_text(row_text: str) -> dict[str, str | None]:
    text = compact(row_text, 500)
    match_code = None
    code_match = re.search(r"(周[一二三四五六日]\d{3})", text)
    if code_match:
        match_code = code_match.group(1)

    kickoff_date = None
    kickoff_match = re.search(r"(\d{2}-\d{2}\s+\d{2}:\d{2})", text)
    if kickoff_match:
        kickoff_date = kickoff_match.group(1)

    home = away = None
    teams_match = re.search(
        r"\d{2}-\d{2}\s+\d{2}:\d{2}\s+(.+?)\s+VS\s+(.+?)(?:\s+\d|\s+析|\s*$)",
        text,
    )
    if not teams_match:
        teams_match = re.search(
            r"([\u4e00-\u9fffA-Za-z0-9().· -]+?)\s+VS\s+([\u4e00-\u9fffA-Za-z0-9().· -]+?)(?:\s+\d|\s+析|\s*$)",
            text,
        )
    if teams_match:
        home = compact(teams_match.group(1), 80)
        away = compact(teams_match.group(2), 80)

    competition = None
    comp_match = re.search(r"周[一二三四五六日]\d{3}\s+([^\s]+)", text)
    if comp_match:
        competition = comp_match.group(1)

    return {
        "match_code": match_code,
        "competition": competition,
        "display_kickoff": kickoff_date,
        "home": home,
        "away": away,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_snapshot_index() -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    matches: dict[str, dict[str, Any]] = {}
    snapshots_by_match: dict[str, list[str]] = defaultdict(list)
    for path in sorted(ODDS_SNAPSHOT_DIR.glob("*.json")):
        try:
            data = read_json(path)
        except Exception:
            continue
        snapshot_id = path.stem
        generated_at = data.get("generated_at")
        for item in data.get("matches", []) or []:
            match_id = str(item.get("match_id") or "").strip()
            if not match_id:
                continue
            parsed = parse_match_text(str(item.get("row_text") or ""))
            entry = matches.setdefault(
                match_id,
                {
                    "match_key": f"500:{match_id}",
                    "provider": "500彩票网",
                    "provider_match_id": match_id,
                    "kickoff": item.get("kickoff"),
                    "match_code": parsed.get("match_code"),
                    "competition": parsed.get("competition"),
                    "home": parsed.get("home"),
                    "away": parsed.get("away"),
                    "match_text": compact(item.get("row_text"), 500),
                    "source_files": [],
                    "odds_windows": [],
                    "predictions": [],
                    "result": None,
                },
            )
            if item.get("kickoff"):
                entry["kickoff"] = item.get("kickoff")
            for key in ["match_code", "competition", "home", "away"]:
                if parsed.get(key):
                    entry[key] = parsed[key]
            if item.get("row_text"):
                entry["match_text"] = compact(item.get("row_text"), 500)
            source_file = str(path.relative_to(ROOT)).replace("\\", "/")
            if source_file not in entry["source_files"]:
                entry["source_files"].append(source_file)
            snapshots_by_match[match_id].append(snapshot_id)
            if generated_at and not any(window.get("snapshot_id") == snapshot_id for window in entry["odds_windows"]):
                entry["odds_windows"].append(
                    {
                        "snapshot_id": snapshot_id,
                        "generated_at": generated_at,
                        "source_file": source_file,
                        "markets": {},
                    }
                )
    return matches, snapshots_by_match


def load_events() -> dict[str, dict[str, dict[str, list[dict[str, Any]]]]]:
    grouped: dict[str, dict[str, dict[str, list[dict[str, Any]]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for path in sorted(ODDS_STORE_DIR.glob("*-events.jsonl")):
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                match_id = str(event.get("match_id") or "").strip()
                snapshot_id = str(event.get("snapshot_id") or "").strip()
                market = str(event.get("market") or "").strip()
                if match_id and snapshot_id and market:
                    grouped[match_id][snapshot_id][market].append(event)
    return grouped


def numeric_avg(values: list[Any]) -> float | None:
    nums = [float(v) for v in values if isinstance(v, (int, float))]
    if not nums:
        return None
    return round(sum(nums) / len(nums), 3)


def summarize_market(events: list[dict[str, Any]]) -> dict[str, Any]:
    directions = Counter(compact(event.get("direction"), 80) for event in events if event.get("direction"))
    parsed_rows = [event.get("parsed") or {} for event in events if event.get("parsed")]
    current_lines = Counter(compact(row.get("current_line"), 40) for row in parsed_rows if row.get("current_line"))
    open_lines = Counter(compact(row.get("open_line"), 40) for row in parsed_rows if row.get("open_line"))
    samples = []
    for event in events:
        raw = compact(event.get("raw_text"), 180)
        if raw and raw not in samples:
            samples.append(raw)
        if len(samples) >= 2:
            break
    return {
        "market_label": MARKET_LABELS.get(compact(events[0].get("market")), compact(events[0].get("market"))),
        "row_count": len(events),
        "direction_counts": dict(directions.most_common()),
        "current_line_modes": dict(current_lines.most_common(5)),
        "open_line_modes": dict(open_lines.most_common(5)),
        "avg_current_left_water": numeric_avg([row.get("current_left") for row in parsed_rows]),
        "avg_current_right_water": numeric_avg([row.get("current_right") for row in parsed_rows]),
        "avg_open_left_water": numeric_avg([row.get("open_left") for row in parsed_rows]),
        "avg_open_right_water": numeric_avg([row.get("open_right") for row in parsed_rows]),
        "representative_rows": samples,
    }


def attach_event_summaries(matches: dict[str, dict[str, Any]]) -> None:
    grouped = load_events()
    for match_id, snapshots in grouped.items():
        entry = matches.get(match_id)
        if not entry:
            entry = {
                "match_key": f"500:{match_id}",
                "provider": "500彩票网",
                "provider_match_id": match_id,
                "kickoff": None,
                "match_code": None,
                "competition": None,
                "home": None,
                "away": None,
                "match_text": "",
                "source_files": [],
                "odds_windows": [],
                "predictions": [],
                "result": None,
            }
            matches[match_id] = entry
        windows_by_id = {window["snapshot_id"]: window for window in entry["odds_windows"]}
        for snapshot_id, markets in snapshots.items():
            first_event = next(iter(next(iter(markets.values()))), {})
            window = windows_by_id.setdefault(
                snapshot_id,
                {
                    "snapshot_id": snapshot_id,
                    "generated_at": first_event.get("generated_at"),
                    "source_file": first_event.get("source_file"),
                    "markets": {},
                },
            )
            if window not in entry["odds_windows"]:
                entry["odds_windows"].append(window)
            if first_event.get("list_row"):
                parsed = parse_match_text(str(first_event.get("list_row")))
                entry["match_text"] = compact(first_event.get("list_row"), 500)
                entry["kickoff"] = first_event.get("kickoff") or entry.get("kickoff")
                for key in ["match_code", "competition", "home", "away"]:
                    if parsed.get(key):
                        entry[key] = parsed[key]
            source_file = first_event.get("source_file")
            if source_file and source_file not in entry["source_files"]:
                entry["source_files"].append(source_file)
            for market, events in markets.items():
                window["markets"][market] = summarize_market(events)


def load_observations() -> list[dict[str, Any]]:
    if not OBSERVATIONS_CSV.exists():
        return []
    rows = []
    with OBSERVATIONS_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if any((value or "").strip() for value in row.values()):
                rows.append(row)
    return rows


def normalize_prediction(row: dict[str, str]) -> dict[str, Any]:
    fields = [
        "observation_id",
        "match_date",
        "lock_time",
        "source_record",
        "market_type",
        "market_scope",
        "minute",
        "score_state",
        "line",
        "selection",
        "odds_at_lock",
        "market_prob",
        "model_prob",
        "confidence_color",
        "value_score",
        "stability_score",
        "uncertainty_penalty",
        "official_plan",
        "simulated_only",
        "result_score",
        "settlement",
        "hit",
        "return_amount",
        "profit",
        "snapshot_file",
        "review_record",
        "notes",
    ]
    return {field: row.get(field, "") for field in fields if row.get(field, "") != ""}


def observation_key(row: dict[str, str]) -> str:
    return f"obs:{row.get('match_date', '')}:{slug(row.get('match', 'unknown'))}"


def attach_observations(matches: dict[str, dict[str, Any]]) -> None:
    by_display: dict[str, str] = {}
    for match_id, entry in matches.items():
        names = []
        if entry.get("home") and entry.get("away"):
            names.append(f"{entry['home']} vs {entry['away']}".lower())
        if entry.get("match_text"):
            names.append(str(entry["match_text"]).lower())
        for name in names:
            by_display[name] = match_id

    for row in load_observations():
        prediction = normalize_prediction(row)
        match_name = compact(row.get("match"), 180)
        match_id = None
        lower_names = [match_name.lower(), alias_match_name(match_name).lower()]
        for display, candidate in by_display.items():
            if any(lower and lower in display for lower in lower_names):
                match_id = candidate
                break
        if match_id is None:
            match_id = observation_key(row)
            matches.setdefault(
                match_id,
                {
                    "match_key": match_id,
                    "provider": "manual_observation",
                    "provider_match_id": None,
                    "kickoff": None,
                    "match_code": None,
                    "competition": row.get("league") or None,
                    "home": None,
                    "away": None,
                    "match_text": match_name,
                    "source_files": [],
                    "odds_windows": [],
                    "predictions": [],
                    "result": None,
                },
            )
        entry = matches[match_id]
        entry["predictions"].append(prediction)
        if row.get("source_record") and row["source_record"] not in entry["source_files"]:
            entry["source_files"].append(row["source_record"])
        if row.get("review_record") and row["review_record"] not in entry["source_files"]:
            entry["source_files"].append(row["review_record"])
        if row.get("result_score"):
            entry["result"] = {
                "score": row.get("result_score"),
                "source": row.get("review_record") or row.get("source_record"),
                "settlements": sorted(
                    {
                        pred.get("settlement", "")
                        for pred in entry["predictions"]
                        if pred.get("settlement")
                    }
                ),
            }


def trim_match(entry: dict[str, Any]) -> dict[str, Any]:
    entry["odds_windows"] = sorted(entry["odds_windows"], key=lambda item: item.get("generated_at") or item.get("snapshot_id") or "")
    entry["source_files"] = sorted(set(entry.get("source_files") or []))
    return entry


def build_database() -> dict[str, Any]:
    matches, _snapshots_by_match = load_snapshot_index()
    attach_event_summaries(matches)
    attach_observations(matches)
    trimmed = [trim_match(value) for value in matches.values()]
    trimmed.sort(key=lambda item: (item.get("kickoff") or "9999", item.get("match_key") or ""))
    return {
        "schema_version": "1.0",
        "generated_at": dt.datetime.now(TZ).isoformat(),
        "description": "Lightweight one-file jincai match database. Raw snapshots remain in records/odds_snapshots for audit.",
        "sources": {
            "odds_snapshots": "records/odds_snapshots/*.json",
            "odds_events": "records/odds_store/*-events.jsonl",
            "observations": "records/dataset/match_observations.csv",
        },
        "counts": {
            "matches": len(trimmed),
            "matches_with_odds": sum(1 for item in trimmed if item.get("odds_windows")),
            "matches_with_predictions": sum(1 for item in trimmed if item.get("predictions")),
            "matches_with_results": sum(1 for item in trimmed if item.get("result")),
            "prediction_rows": sum(len(item.get("predictions") or []) for item in trimmed),
        },
        "matches": trimmed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build compact one-file jincai match database.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output JSON path.")
    args = parser.parse_args()

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    database = build_database()
    output.write_text(json.dumps(database, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {output}")
    print(json.dumps(database["counts"], ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

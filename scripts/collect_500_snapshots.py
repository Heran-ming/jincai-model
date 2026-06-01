#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
TZ = dt.timezone(dt.timedelta(hours=8))
LIST_URL = "https://odds.500.com/yazhi_jczq.shtml"
DETAIL_URLS = {
    "asian_handicap": "https://odds.500.com/fenxi/yazhi-{match_id}.shtml",
    "handicap_1x2": "https://odds.500.com/fenxi/rangqiu-{match_id}.shtml?lot=jczq",
    "over_under": "https://odds.500.com/fenxi/daxiao-{match_id}.shtml",
    "european_odds": "https://odds.500.com/fenxi/ouzhi-{match_id}.shtml",
}


def compact_text(value: str, limit: int = 700) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()[:limit]


def html_meta_charset(raw: bytes) -> str | None:
    head = raw[:4096]
    patterns = [
        rb"<meta[^>]+charset=[\"']?\s*([A-Za-z0-9_\-]+)",
        rb"<meta[^>]+content=[\"'][^\"']*charset=([A-Za-z0-9_\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, head, flags=re.I)
        if match:
            return match.group(1).decode("ascii", errors="ignore")
    return None


def decode_score(text: str) -> int:
    replacement_penalty = text.count("\ufffd") * 20
    question_penalty = text.count("?") * 4
    mojibake_penalty = sum(text.count(mark) for mark in ("鍚", "鐞", "绔", "銆", "Ã", "Â")) * 8
    chinese_bonus = len(re.findall(r"[\u4e00-\u9fff]", text))
    return replacement_penalty + question_penalty + mojibake_penalty - chinese_bonus


def decode_html(raw: bytes, header_charset: str | None) -> tuple[str, str]:
    candidates: list[str] = []
    for item in [header_charset, html_meta_charset(raw), "utf-8", "gb18030", "gbk", "big5"]:
        if item and item.lower() not in [candidate.lower() for candidate in candidates]:
            candidates.append(item)

    best_text = ""
    best_charset = candidates[0] if candidates else "utf-8"
    best_score = 10**9
    for charset in candidates:
        try:
            text = raw.decode(charset, errors="replace")
        except LookupError:
            continue
        score = decode_score(text)
        if score < best_score:
            best_text = text
            best_charset = charset
            best_score = score
    return best_text, best_charset


def fetch_html(url: str, limit: int = 700_000, retries: int = 3) -> dict:
    retry_codes = {403, 429, 500, 502, 503, 504}
    for attempt in range(1, retries + 1):
        req = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
                "Referer": LIST_URL,
            },
        )
        try:
            with urlopen(req, timeout=20) as resp:
                raw = resp.read(limit)
                text, charset = decode_html(raw, resp.headers.get_content_charset())
                return {
                    "status": resp.status,
                    "url": resp.geturl(),
                    "bytes": len(raw),
                    "charset": charset,
                    "attempt": attempt,
                    "html": text,
                }
        except HTTPError as exc:
            if exc.code in retry_codes and attempt < retries:
                time.sleep(0.8 * attempt)
                continue
            return {"status": exc.code, "url": url, "attempt": attempt, "error": f"http_error:{exc.code}"}
        except URLError as exc:
            if attempt < retries:
                time.sleep(0.8 * attempt)
                continue
            return {"status": None, "url": url, "attempt": attempt, "error": f"url_error:{exc.reason}"}
        except Exception as exc:  # pragma: no cover
            return {"status": None, "url": url, "attempt": attempt, "error": f"error:{type(exc).__name__}:{exc}"}
    return {"status": None, "url": url, "attempt": retries, "error": "retry_exhausted"}


class MainListParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_main_tbody = False
        self.tbody_depth = 0
        self.current_row: dict | None = None
        self.matches: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "tbody":
            if self.in_main_tbody:
                self.tbody_depth += 1
            elif attr_map.get("id") == "main-tbody":
                self.in_main_tbody = True
                self.tbody_depth = 1
        if not self.in_main_tbody:
            return
        if tag == "tr":
            self.current_row = {"attrs": attr_map, "parts": [], "links": []}
        elif self.current_row is not None and tag == "input":
            if attr_map.get("type") == "checkbox" and attr_map.get("value"):
                self.current_row["match_id"] = attr_map["value"]
        elif self.current_row is not None and tag == "a":
            if attr_map.get("href"):
                self.current_row["links"].append(attr_map["href"])

    def handle_data(self, data: str) -> None:
        if self.current_row is not None:
            self.current_row["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "tr" and self.current_row is not None:
            if self.current_row.get("match_id"):
                self.matches.append(
                    {
                        "match_id": self.current_row["match_id"],
                        "kickoff": self.current_row["attrs"].get("date-dtime"),
                        "row_text": compact_text(" ".join(self.current_row["parts"]), 900),
                        "links": self.current_row["links"][:8],
                    }
                )
            self.current_row = None
        elif tag == "tbody" and self.in_main_tbody:
            self.tbody_depth -= 1
            if self.tbody_depth <= 0:
                self.in_main_tbody = False


class DetailTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_target_table = False
        self.table_depth = 0
        self.row_stack: list[dict] = []
        self.rows: list[dict] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self._seen_rows: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        if tag == "title":
            self.in_title = True
        if tag == "table":
            if self.in_target_table:
                self.table_depth += 1
            elif attr_map.get("id") == "datatb":
                self.in_target_table = True
                self.table_depth = 1
        if self.in_target_table and tag == "tr":
            self.row_stack.append({"attrs": attr_map, "parts": []})

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        for row in self.row_stack:
            row["parts"].append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "tr" and self.row_stack:
            row = self.row_stack.pop()
            row_text = compact_text(" ".join(row["parts"]))
            if row_text and row_text not in self._seen_rows:
                self._seen_rows.add(row_text)
                self.rows.append(
                    {
                        "data_time": row["attrs"].get("data-time"),
                        "text": row_text,
                    }
                )
        elif tag == "table" and self.in_target_table:
            self.table_depth -= 1
            if self.table_depth <= 0:
                self.in_target_table = False

    @property
    def title(self) -> str:
        return compact_text(" ".join(self.title_parts), 180)


def extract_same_history_links(text: str, page_url: str, limit: int = 12) -> list[str]:
    links = re.findall(
        r"""href=["']([^"']+(?:yazhi_same|rangqiu_same|daxiao_same|ouzhi_same)\.php[^"']*)["']""",
        text,
        flags=re.I,
    )
    result: list[str] = []
    for link in links:
        absolute = urljoin(page_url, html.unescape(link))
        if absolute not in result:
            result.append(absolute)
    return result[:limit]


def parse_detail_page(response: dict) -> dict:
    if response.get("status") != 200 or not response.get("html"):
        return {key: value for key, value in response.items() if key != "html"}

    parser = DetailTableParser()
    parser.feed(response["html"])
    return {
        "status": response["status"],
        "url": response["url"],
        "bytes": response["bytes"],
        "charset": response["charset"],
        "attempt": response.get("attempt", 1),
        "title": parser.title,
        "row_count": len(parser.rows),
        "rows": parser.rows[:120],
        "same_history_links": extract_same_history_links(response["html"], response["url"]),
    }


def output_dir_path(output_dir: Path | None = None) -> Path:
    return output_dir or ROOT / "records" / "odds_snapshots"


def collect_snapshot(
    *,
    now: dt.datetime | None = None,
    output_dir: Path | None = None,
    max_matches: int | None = None,
) -> Path:
    now = now or dt.datetime.now(TZ)
    max_matches = max_matches or max(1, min(int(os.environ.get("JINCAI_500_MAX_MATCHES", "20")), 40))
    request_interval = max(0.0, float(os.environ.get("JINCAI_500_REQUEST_INTERVAL", "0.75")))
    snapshot = {
        "schema_version": "1.0",
        "source": "500彩票网",
        "source_url": LIST_URL,
        "generated_at": now.isoformat(),
        "pre_match_only": True,
        "mapping_note": "500比赛ID不是竞彩周编号。报告引用前必须结合队名与开赛时间核验映射。",
        "matches": [],
        "errors": [],
    }

    list_response = fetch_html(LIST_URL)
    snapshot["list_status"] = {key: value for key, value in list_response.items() if key != "html"}
    if list_response.get("status") == 200 and list_response.get("html"):
        parser = MainListParser()
        parser.feed(list_response["html"])
        matches = parser.matches[:max_matches]
        snapshot["list_match_count"] = len(parser.matches)
        for match in matches:
            details = {}
            for market, template in DETAIL_URLS.items():
                if request_interval:
                    time.sleep(request_interval)
                url = template.format(match_id=match["match_id"])
                details[market] = parse_detail_page(fetch_html(url))
            snapshot["matches"].append({**match, "details": details})
    else:
        snapshot["errors"].append(
            {
                "stage": "list",
                "detail": list_response.get("error") or f"unexpected_status:{list_response.get('status')}",
            }
        )

    out_dir = output_dir_path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{now:%Y-%m-%d-%H%M%S}.json"
    out.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        latest_value = str(out.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        latest_value = str(out)
    (out_dir / ".latest_path").write_text(latest_value, encoding="utf-8")
    return out


def latest_snapshot_path(day: str, output_dir: Path | None = None) -> Path | None:
    candidates = sorted(output_dir_path(output_dir).glob(f"{day}-*.json"))
    return candidates[-1] if candidates else None


def latest_snapshot_context(day: str, output_dir: Path | None = None, limit: int = 26000) -> str:
    path = latest_snapshot_path(day, output_dir)
    if not path:
        return "## 500彩票网赛前结构化快照\nSTATUS: missing; 尚未运行赛前快照采集器。\n"

    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [
        "## 500彩票网赛前结构化快照",
        f"FILE: {path.name}",
        f"generated_at={data.get('generated_at')}",
        f"pre_match_only={data.get('pre_match_only')}",
        f"list_match_count={data.get('list_match_count', 0)}",
        f"mapping_note={data.get('mapping_note')}",
    ]
    for error in data.get("errors", []):
        lines.append(f"ERROR: {error}")
    for match in data.get("matches", []):
        lines.extend(
            [
                "",
                f"### 500比赛ID {match.get('match_id')}",
                f"kickoff={match.get('kickoff')}",
                f"list_row={match.get('row_text')}",
            ]
        )
        for market, detail in (match.get("details") or {}).items():
            lines.append(
                f"- {market}: status={detail.get('status')} charset={detail.get('charset')} "
                f"rows={detail.get('row_count', 0)} title={detail.get('title', '')}"
            )
            for row in (detail.get("rows") or [])[:4]:
                lines.append(f"  row: {row.get('text', '')}")
            same_links = detail.get("same_history_links") or []
            if same_links:
                lines.append(f"  same_history_links={len(same_links)}; sample={same_links[0]}")
    return "\n".join(lines)[:limit] + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect pre-match 500.com odds snapshots.")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--max-matches", type=int)
    args = parser.parse_args()
    out = collect_snapshot(output_dir=args.output_dir, max_matches=args.max_matches)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

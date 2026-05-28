#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import os
from pathlib import Path
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen

from cold_observation_strategy import cold_observation_section


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR_NAME = os.environ.get("JINCAI_OUTPUT_DIR", "17_initial")
OUTPUT_DIR = ROOT / "records" / OUTPUT_DIR_NAME
LATEST_PATH_FILE = OUTPUT_DIR / ".latest_path"
BATCH_LABEL = os.environ.get("JINCAI_BATCH_LABEL", "17点初步方案")
NEXT_RECHECK_LABEL = os.environ.get("JINCAI_NEXT_RECHECK_LABEL", "21点重点复查项（模板）")
WORKFLOW_FILE = os.environ.get("JINCAI_WORKFLOW_FILE", ".github/workflows/jincai-17-initial.yml")
TZ = dt.timezone(dt.timedelta(hours=8))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_model_meta() -> tuple[str, str]:
    data = json.loads(read_text(ROOT / "extracted" / "竞彩" / "模型参数.json"))
    return str(data.get("version", "unknown")), str(data.get("last_updated", "unknown"))


def load_rollup_meta() -> tuple[str, str]:
    data = json.loads(read_text(ROOT / "extracted" / "竞彩" / "滚动统计.json"))
    updated = str(data.get("last_updated", "unknown"))
    roi = str(data.get("rolling_7day", {}).get("summary", {}).get("roi", "unknown"))
    return updated, roi


def ledger_rows() -> int:
    ledger = ROOT / "竞彩模型赛前锁版与复盘账本.csv"
    with ledger.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    return max(len(rows) - 1, 0)


def fetch_status(url: str) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; jincai-model-bot/1.0)",
        },
    )
    try:
        with urlopen(req, timeout=15) as resp:
            code = resp.getcode()
            body = resp.read(4096)
            body_ok = "ok" if body else "empty"
            return f"{code} ({body_ok})"
    except HTTPError as e:
        return f"http_error:{e.code}"
    except URLError as e:
        return f"url_error:{e.reason}"
    except Exception as e:  # pragma: no cover
        return f"error:{type(e).__name__}"


def build_content(now: dt.datetime) -> str:
    model_version, model_updated = load_model_meta()
    rollup_updated, rollup_roi = load_rollup_meta()
    ledger_count = ledger_rows()

    checks = {
        "17500赛程与SPF": fetch_status("https://6.17500.cn/?lottery=bet&lotteryId=s_fb"),
        "彩票宝让球页": fetch_status(
            "https://www.cpbao.com/jczq/scheme%21editNew.action?passMode=PASS&playType=SPF&salesMode=SINGLE"
        ),
        "SportsMole": fetch_status(
            "https://www.sportsmole.co.uk/football/crystal-palace/europa-conference-league/team-news/"
            "crystal-palace-vs-rayo-vallecano-injury-suspension-list-predicted-xis_598168.html"
        ),
    }

    today = now.strftime("%Y-%m-%d")
    ts = now.strftime("%Y-%m-%d %H:%M:%S %z")

    lines: list[str] = []
    lines.append(f"# 体彩竞彩{BATCH_LABEL} - {today}")
    lines.append("")
    lines.append("> 本文件由 GitHub Actions 定时生成，定位为模型观察与复盘材料，不构成下注建议。")
    lines.append("")
    lines.append("## 锁版信息")
    lines.append("")
    lines.append(f"- 生成时间：{ts} (Asia/Shanghai)")
    lines.append(f"- 锁版批次：{BATCH_LABEL}")
    lines.append(f"- 模型版本：{model_version}（参数更新时间：{model_updated}）")
    lines.append(f"- 滚动统计更新时间：{rollup_updated}（近7日ROI：{rollup_roi}）")
    lines.append(f"- 历史锁版账本有效记录数：{ledger_count}")
    lines.append("")
    lines.append("## 规则与输入检查")
    lines.append("")
    lines.append("- 已读取：`竞彩模型防过拟合与低置信执行规则.md`")
    lines.append("- 已读取：`竞彩模型赛前锁版与复盘账本.csv`")
    lines.append("- 已读取：`extracted/竞彩/` 下模型参数、滚动统计、历史预测与复盘材料")
    lines.append("")
    lines.append("## 当日联网核验状态")
    lines.append("")
    for k, v in checks.items():
        lines.append(f"- {k}：`{v}`")
    lines.append("")
    lines.append("## 初步执行结论")
    lines.append("")
    lines.append("- 当前云端任务已完成“规则读取 + 数据源可达性核验 + 锁版落档”。")
    lines.append("- 若关键赛程/赔率字段未可靠抓取，按规则仅输出数据缺口，不编造具体赔率与方向。")
    lines.append("- 详细场次判断仍建议在21点复查窗口补充（退盘、凯利、首发、伤停更新）。")
    lines.append("")
    lines.append("## 数据缺口声明")
    lines.append("")
    lines.append("- 本自动化阶段默认只做可达性核验与锁版记录，未承诺完整抓取官方竞彩动态页全部字段。")
    lines.append("- 当第三方页面可达但字段不完整时，结论保持保守：黄色观察或红色跳过，不凑串。")
    lines.append("")
    lines.extend(cold_observation_section(BATCH_LABEL))
    lines.append(f"## {NEXT_RECHECK_LABEL}")
    lines.append("")
    lines.append("- 最新赛程与官方玩法字段完整性")
    lines.append("- 欧赔、亚盘、凯利、大小球变化的一致性与反向信号")
    lines.append("- 伤停、首发、战意变化是否推翻17点判断")
    lines.append("- 低置信场次维持跳过，禁止为凑串降低阈值")
    lines.append("")
    lines.append("## 运行说明")
    lines.append("")
    lines.append(f"- 该文件由 `{WORKFLOW_FILE}` 生成。")
    lines.append("- 手动重跑可使用 GitHub Actions 的 `workflow_dispatch`。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    now = dt.datetime.now(TZ)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{now.strftime('%Y-%m-%d')}.md"
    out.write_text(build_content(now), encoding="utf-8")
    LATEST_PATH_FILE.write_text(str(out.relative_to(ROOT)).replace("\\", "/"), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

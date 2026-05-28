#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cold_observation_strategy import cold_observation_section


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "records" / "21_final"
LATEST_PATH_FILE = OUTPUT_DIR / ".latest_path"
TZ = dt.timezone(dt.timedelta(hours=8))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict:
    return json.loads(read_text(path))


def ledger_rows() -> int:
    with (ROOT / "竞彩模型赛前锁版与复盘账本.csv").open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    return max(len(rows) - 1, 0)


def fetch_status(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; jincai-model-bot/1.0)"})
    try:
        with urlopen(req, timeout=15) as resp:
            code = resp.getcode()
            body = resp.read(4096)
            return f"{code} ({'ok' if body else 'empty'})"
    except HTTPError as e:
        return f"http_error:{e.code}"
    except URLError as e:
        return f"url_error:{e.reason}"
    except Exception as e:  # pragma: no cover
        return f"error:{type(e).__name__}"


def resolve_target_date(now: dt.datetime) -> dt.date:
    configured = os.environ.get("TARGET_DATE")
    if configured:
        return dt.date.fromisoformat(configured)

    # GitHub scheduled jobs can run late. If the 21:05 job starts after
    # midnight China time, it still belongs to the previous match day.
    if now.hour < 6:
        return now.date() - dt.timedelta(days=1)
    return now.date()


def build_content(now: dt.datetime, target_date: dt.date) -> str:
    day = target_date.strftime("%Y-%m-%d")
    initial_file = ROOT / "records" / "17_initial" / f"{day}.md"
    initial_exists = initial_file.exists()

    model = load_json(ROOT / "extracted" / "竞彩" / "模型参数.json")
    roll = load_json(ROOT / "extracted" / "竞彩" / "滚动统计.json")
    checks = {
        "17500赛程与SPF": fetch_status("https://6.17500.cn/?lottery=bet&lotteryId=s_fb"),
        "彩票宝让球页": fetch_status(
            "https://www.cpbao.com/jczq/scheme%21editNew.action?passMode=PASS&playType=SPF&salesMode=SINGLE"
        ),
        "赔率复查参考页": fetch_status("https://tips.gg/article/independiente-del-valle-vs-rosario-central-28-05-2026/"),
    }

    ts = now.strftime("%Y-%m-%d %H:%M:%S %z")
    out: list[str] = []
    out.append(f"# 体彩竞彩21点最终方案 - {day}")
    out.append("")
    out.append("> 本文件由 GitHub Actions 定时生成，定位为模型观察与复盘材料，不构成下注建议。")
    out.append("")
    out.append("## 锁版信息")
    out.append("")
    out.append(f"- 生成时间：{ts} (Asia/Shanghai)")
    out.append("- 锁版批次：21点最终方案")
    out.append(f"- 模型版本：{model.get('version', 'unknown')}")
    out.append(f"- 滚动统计更新时间：{roll.get('last_updated', 'unknown')}")
    out.append(f"- 历史锁版账本有效记录数：{ledger_rows()}")
    out.append(f"- 当日17点初稿：`{'已读取' if initial_exists else '缺失'}` -> `records/17_initial/{day}.md`")
    out.append("")
    out.append("## 输入材料")
    out.append("")
    out.append("- 已读取：`竞彩模型防过拟合与低置信执行规则.md`")
    out.append("- 已读取：`竞彩模型赛前锁版与复盘账本.csv`")
    out.append("- 已读取：`extracted/竞彩/模型参数.json`、`extracted/竞彩/滚动统计.json`")
    out.append("- 已读取：`extracted/竞彩/赔率时间窗口分析.md`")
    out.append("- 已读取：`records/17_initial/YYYY-MM-DD.md`（若存在）")
    out.append("")
    out.append("## 21点联网核验状态")
    out.append("")
    for k, v in checks.items():
        out.append(f"- {k}：`{v}`")
    out.append("")
    out.append("## 终版执行结论")
    out.append("")
    if initial_exists:
        out.append("- 已在17点初稿基础上完成21点复查锁版。")
    else:
        out.append("- 当日17点初稿缺失，终版降级为仅复查记录，不输出正式推荐。")
    out.append("- 黄色场次仅观察或模拟，红色场次继续跳过。")
    out.append("- 若关键赔率/凯利/首发数据不完整，维持保守，不编造方向。")
    out.append("")
    out.append("## 21点重点复查模板")
    out.append("")
    out.append("- 17点与21点赔率方向是否一致（升盘/退盘/平赔异动）")
    out.append("- 伤停与首发是否推翻17点判断")
    out.append("- 市场去水概率与模型概率差是否仍有安全边际")
    out.append("- 黄色场次是否降红；红色是否继续跳过")
    out.append("")
    out.append("## 数据缺口声明")
    out.append("")
    out.append("- 本自动化当前优先保证“规则读取 + 复查落档 + 风险声明”。")
    out.append("- 当外部页面可达但字段缺失时，输出缺口，不补造数据。")
    out.append("")
    out.extend(cold_observation_section("21点终版"))
    out.append("## 运行说明")
    out.append("")
    out.append("- 该文件由 `.github/workflows/jincai-21-final.yml` 生成。")
    out.append("- 手动重跑可使用 GitHub Actions 的 `workflow_dispatch`。")
    out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    now = dt.datetime.now(TZ)
    target_date = resolve_target_date(now)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output = OUTPUT_DIR / f"{target_date.strftime('%Y-%m-%d')}.md"
    output.write_text(build_content(now, target_date), encoding="utf-8")
    LATEST_PATH_FILE.write_text(str(output.relative_to(ROOT)).replace("\\", "/"), encoding="utf-8")
    print(f"wrote {output}")


if __name__ == "__main__":
    main()

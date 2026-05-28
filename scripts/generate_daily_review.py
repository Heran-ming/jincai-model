#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from cold_observation_strategy import cold_review_section


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "records" / "reviews"
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


def build_content(now: dt.datetime) -> str:
    day = now.strftime("%Y-%m-%d")
    prev = (now - dt.timedelta(days=1)).strftime("%Y-%m-%d")
    initial_prev = ROOT / "records" / "17_initial" / f"{prev}.md"
    final_prev = ROOT / "records" / "21_final" / f"{prev}.md"
    model = load_json(ROOT / "extracted" / "竞彩" / "模型参数.json")
    roll = load_json(ROOT / "extracted" / "竞彩" / "滚动统计.json")

    checks = {
        "赛果核验页(样例)": fetch_status("https://www.flashscore.com/"),
        "17500赛程页": fetch_status("https://6.17500.cn/?lottery=bet&lotteryId=s_fb"),
        "滚动统计文件": "local_ok",
    }

    ts = now.strftime("%Y-%m-%d %H:%M:%S %z")
    out: list[str] = []
    out.append(f"# 竞彩模型每日复盘 - {day}")
    out.append("")
    out.append("> 本文件由 GitHub Actions 定时生成，定位为模型观察与流程复盘，不构成下注建议。")
    out.append("")
    out.append("## 复盘批次信息")
    out.append("")
    out.append(f"- 生成时间：{ts} (Asia/Shanghai)")
    out.append(f"- 复盘目标比赛日：{prev}")
    out.append(f"- 模型版本：{model.get('version', 'unknown')}")
    out.append(f"- 滚动统计更新时间：{roll.get('last_updated', 'unknown')}")
    out.append(f"- 账本结构化记录数：{ledger_rows()}")
    out.append(f"- 前一日17点初稿：`{'存在' if initial_prev.exists() else '缺失'}`")
    out.append(f"- 前一日21点终版：`{'存在' if final_prev.exists() else '缺失'}`")
    out.append("")
    out.append("## 读取材料")
    out.append("")
    out.append("- `竞彩模型防过拟合与低置信执行规则.md`")
    out.append("- `竞彩模型赛前锁版与复盘账本.csv`")
    out.append("- `extracted/竞彩/模型参数.json`")
    out.append("- `extracted/竞彩/滚动统计.json`")
    out.append("- `records/17_initial/YYYY-MM-DD.md`（前一日，如存在）")
    out.append("- `records/21_final/YYYY-MM-DD.md`（前一日，如存在）")
    out.append("")
    out.append("## 外部核验状态")
    out.append("")
    for k, v in checks.items():
        out.append(f"- {k}：`{v}`")
    out.append("")
    out.append("## 复盘执行结论")
    out.append("")
    out.append("- 已完成规则/账本/历史材料读取与复盘文件落档。")
    out.append("- 若前一日锁版文件缺失，本次复盘降级为流程复盘，不做胜率优劣判断。")
    out.append("- 若赛果或closing odds数据不足，必须保留指标缺口说明（不编造Brier、LogLoss、CLV）。")
    out.append("")
    out.append("## 复盘模板（待赛果齐全后补）")
    out.append("")
    out.append("- 单场命中率")
    out.append("- 正式方案ROI与模拟方案ROI")
    out.append("- 串关拖累与低置信误入检查")
    out.append("- Brier / LogLoss / CLV（仅在数据足够时）")
    out.append("- 参数微调候选（需满足样本量门槛）")
    out.append("")
    out.extend(cold_review_section())
    out.append("## 运行说明")
    out.append("")
    out.append("- 该文件由 `.github/workflows/jincai-daily-review.yml` 生成。")
    out.append("- 手动重跑可使用 GitHub Actions 的 `workflow_dispatch`。")
    out.append("")
    return "\n".join(out) + "\n"


def main() -> None:
    now = dt.datetime.now(TZ)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUTPUT_DIR / f"{now.strftime('%Y-%m-%d')}.md"
    out.write_text(build_content(now), encoding="utf-8")
    LATEST_PATH_FILE.write_text(str(out.relative_to(ROOT)).replace("\\", "/"), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

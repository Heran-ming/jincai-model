#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
TZ = dt.timezone(dt.timedelta(hours=8))


PLAN_SOURCES = [
    ("17500胜平负", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb&s=0&a=1"),
    ("17500让球胜平负", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb&s=0&a=2"),
    ("17500总进球", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb&s=0&a=4"),
    ("彩票网竞彩", "https://www.17500.cn/"),
]

REVIEW_SOURCES = [
    ("17500赛果参考", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb"),
    ("Flashscore", "https://www.flashscore.com/"),
]


def read_text(path: Path, limit: int = 24000) -> str:
    if not path.exists():
        return f"[missing] {path.relative_to(ROOT)}"
    text = path.read_text(encoding="utf-8", errors="replace")
    return text[:limit]


def ledger_rows() -> int:
    path = ROOT / "竞彩模型赛前锁版与复盘账本.csv"
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as f:
        return max(len(list(csv.reader(f))) - 1, 0)


def fetch_snippet(name: str, url: str, limit: int = 18000) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; jincai-model-bot/2.0)"})
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read(limit * 3)
            charset = resp.headers.get_content_charset() or "utf-8"
            text = raw.decode(charset, errors="replace")
    except HTTPError as e:
        return f"## {name}\nURL: {url}\nSTATUS: http_error:{e.code}\n"
    except URLError as e:
        return f"## {name}\nURL: {url}\nSTATUS: url_error:{e.reason}\n"
    except Exception as e:  # pragma: no cover
        return f"## {name}\nURL: {url}\nSTATUS: error:{type(e).__name__}\n"

    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f"## {name}\nURL: {url}\nSTATUS: 200\nSNIPPET:\n{text[:limit]}\n"


def output_text_from_openai_response(data: dict) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"].strip()
    parts: list[str] = []
    for item in data.get("output", []) or []:
        for content in item.get("content", []) or []:
            text = content.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts).strip()


def output_text_from_chat_response(data: dict) -> str:
    choices = data.get("choices", [])
    if not choices:
        return ""
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "\n".join(parts).strip()
    return ""


def call_openai_responses(prompt: str) -> tuple[str | None, str | None]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY is not configured in GitHub Secrets."

    payload = {
        "model": os.environ.get("OPENAI_MODEL", "gpt-5.4"),
        "reasoning": {"effort": os.environ.get("OPENAI_REASONING_EFFORT", "high")},
        "input": prompt,
        "max_output_tokens": int(os.environ.get("OPENAI_MAX_OUTPUT_TOKENS", "14000")),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:2000]
        return None, f"OpenAI API HTTP {e.code}: {detail}"
    except Exception as e:  # pragma: no cover
        return None, f"OpenAI API error: {type(e).__name__}: {e}"

    text = output_text_from_openai_response(data)
    if not text:
        return None, f"OpenAI API returned no output text. response_id={data.get('id', 'unknown')}"
    return text, None


def call_openai_compatible_chat(
    *,
    provider_name: str,
    api_key_env: str,
    base_url: str,
    model: str,
    prompt: str,
) -> tuple[str | None, str | None]:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        return None, f"{api_key_env} is not configured in GitHub Secrets."

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是保守的竞彩模型记录员。只输出可复盘的 Markdown 正文，不编造数据。",
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": float(os.environ.get("AI_TEMPERATURE", "0.2")),
        "max_tokens": int(os.environ.get("AI_MAX_TOKENS", "12000")),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    endpoint = base_url.rstrip("/") + "/chat/completions"
    req = Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=240) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:2000]
        return None, f"{provider_name} API HTTP {e.code}: {detail}"
    except Exception as e:  # pragma: no cover
        return None, f"{provider_name} API error: {type(e).__name__}: {e}"

    text = output_text_from_chat_response(data)
    if not text:
        return None, f"{provider_name} API returned no output text. response_id={data.get('id', 'unknown')}"
    return text, None


def call_llm(prompt: str) -> tuple[str | None, str | None]:
    provider = os.environ.get("AI_PROVIDER", "deepseek").strip().lower()
    if provider == "openai":
        return call_openai_responses(prompt)
    if provider == "deepseek":
        return call_openai_compatible_chat(
            provider_name="DeepSeek",
            api_key_env="DEEPSEEK_API_KEY",
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash"),
            prompt=prompt,
        )
    return None, f"Unsupported AI_PROVIDER: {provider}. Use 'deepseek' or 'openai'."


def local_context(day: str, previous_day: str | None = None) -> str:
    files = [
        ROOT / "竞彩模型防过拟合与低置信执行规则.md",
        ROOT / "竞彩模型赛前锁版与复盘账本.csv",
        ROOT / "extracted" / "竞彩" / "模型参数.json",
        ROOT / "extracted" / "竞彩" / "滚动统计.json",
        ROOT / "extracted" / "竞彩" / "赔率时间窗口分析.md",
        ROOT / "extracted" / "竞彩" / "复盘报告-20260527.md",
        ROOT / "records" / "1130_initial" / f"{day}.md",
        ROOT / "records" / "17_check" / f"{day}.md",
        ROOT / "records" / "21_final" / f"{day}.md",
    ]
    if previous_day:
        files.extend(
            [
                ROOT / "records" / "1130_initial" / f"{previous_day}.md",
                ROOT / "records" / "17_check" / f"{previous_day}.md",
                ROOT / "records" / "21_final" / f"{previous_day}.md",
            ]
        )

    blocks = [f"ledger_rows={ledger_rows()}"]
    for path in files:
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        blocks.append(f"\n## FILE {rel}\n{read_text(path)}")
    return "\n".join(blocks)


def write_report(output_dir: str, target_date: dt.date, content: str) -> Path:
    out_dir = ROOT / "records" / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{target_date:%Y-%m-%d}.md"
    out.write_text(content.rstrip() + "\n", encoding="utf-8")
    (out_dir / ".latest_path").write_text(str(out.relative_to(ROOT)).replace("\\", "/"), encoding="utf-8")
    return out


def failure_report(title: str, now: dt.datetime, reason: str) -> str:
    return "\n".join(
        [
            f"# {title}",
            "",
            "> 本文件由 GitHub Actions 生成。AI 生成未完成，因此不输出预测方向，不用模板冒充结果。",
            "",
            "## 生成失败",
            "",
            f"- 生成时间：{now:%Y-%m-%d %H:%M:%S %z} (Asia/Shanghai)",
            f"- 原因：{reason}",
            "",
            "## 风险声明",
            "",
            "- 未可靠生成完整赛前锁版，不给正式方案。",
            "- 不补造赔率、概率、伤停或战意信息。",
            "- 请修复上方原因后手动重跑 workflow_dispatch。",
            "",
        ]
    )


def build_plan_prompt(
    *,
    batch_label: str,
    target_date: dt.date,
    now: dt.datetime,
    next_recheck_label: str,
    workflow_file: str,
) -> str:
    day = f"{target_date:%Y-%m-%d}"
    source_blocks = "\n\n".join(fetch_snippet(name, url) for name, url in PLAN_SOURCES)
    return f"""
你是一个保守的中国体彩竞彩赛前锁版记录员。请只输出 Markdown 正文，不要代码块，不要写模板，不要写“待补”。

当前任务：生成 `{batch_label}`。
比赛日：{day}
生成时间：{now:%Y-%m-%d %H:%M:%S %z} Asia/Shanghai
工作流文件：{workflow_file}
下一复查项标题：{next_recheck_label}

硬性纪律：
1. 这是模型观察与复盘材料，不是下注建议，不鼓励下注。
2. 必须先依据本地规则、历史预测、滚动统计、当天 11:30/17:00/21:00 记录和联网赔率片段综合判断。
3. 如果无法从片段中可靠提取最新赛程、玩法、赔率、凯利、亚盘、大小球、伤停或战意，必须明确写数据缺口；不得编造。
4. 每场必须赛前锁版：生成时间、数据窗口、玩法、赔率、方向、核心依据、最大反方证据、推翻条件。
5. 每场给三分：价值分、稳定分、不确定性惩罚，并标记绿色/黄色/红色。
6. 黄色只观察或模拟，红色跳过，不允许为了凑串加入低置信场次。
7. 必须加入冷门与双选观察：先判断单选能否到绿灯；黄灯再检查胜平负双选或让球双选是否能覆盖主要风险。红灯不能通过双选升级。
8. 输出必须包含候选场次、初步/最终方向、赔率变化信号、市场去水概率与模型概率差（数据足够才写）、主要风险、暂不推荐原因、{next_recheck_label}。
9. 如果数据不足导致没有正式推荐，也要输出一份完整的“无正式方案/空仓”报告，而不是流程模板。

请按以下结构输出：
- 标题
- 锁版信息
- 数据来源与数据缺口
- 候选场次总表
- 正式方案结论
- 黄灯双选/让球双选升级检查
- 逐场赛前锁版
- {next_recheck_label}
- 最终摘要

本地上下文：
{local_context(day)}

联网赔率片段：
{source_blocks}
""".strip()


def generate_plan(
    *,
    output_dir: str,
    batch_label: str,
    next_recheck_label: str,
    workflow_file: str,
    target_date: dt.date,
) -> Path:
    now = dt.datetime.now(TZ)
    title = f"体彩竞彩{batch_label} - {target_date:%Y-%m-%d}"
    prompt = build_plan_prompt(
        batch_label=batch_label,
        target_date=target_date,
        now=now,
        next_recheck_label=next_recheck_label,
        workflow_file=workflow_file,
    )
    content, error = call_llm(prompt)
    if error:
        content = failure_report(title, now, error)
    return write_report(output_dir, target_date, content)


def build_review_prompt(now: dt.datetime) -> tuple[str, dt.date]:
    target = now.date() - dt.timedelta(days=1)
    day = f"{target:%Y-%m-%d}"
    source_blocks = "\n\n".join(fetch_snippet(name, url) for name, url in REVIEW_SOURCES)
    prompt = f"""
你是一个保守的竞彩模型赛后复盘记录员。请只输出 Markdown 正文，不要代码块，不要流程模板。

当前任务：生成每日复盘。
复盘目标比赛日：{day}
生成时间：{now:%Y-%m-%d %H:%M:%S %z} Asia/Shanghai

硬性纪律：
1. 先读取赛前规则、账本、滚动统计、历史预测、目标日 11:30/17:00/21:00 记录。
2. 如果赛果、closing odds、Brier、LogLoss、CLV 数据不足，必须说明缺口，不得编造。
3. 复盘要区分正式方案、模拟方案、黄灯双选/让球双选观察、红灯跳过。
4. 只有样本量和阈值满足时才提出模型参数调整；否则只记录观察。
5. 输出要包含命中/失误、赔率变化复盘、错误归因、下一轮规则修正候选。

本地上下文：
{local_context(day, previous_day=day)}

联网赛果片段：
{source_blocks}
""".strip()
    return prompt, target


def generate_review() -> Path:
    now = dt.datetime.now(TZ)
    prompt, target = build_review_prompt(now)
    content, error = call_llm(prompt)
    if error:
        content = failure_report(f"竞彩模型每日复盘 - {now:%Y-%m-%d}", now, error)
    return write_report("reviews", now.date(), content)

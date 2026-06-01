#!/usr/bin/env python3
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
TZ = dt.timezone(dt.timedelta(hours=8))


PLAN_SOURCES = [
    ("17500胜平负", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb&s=0&a=1"),
    ("17500让球胜平负", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb&s=0&a=2"),
    ("17500总进球", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb&s=0&a=4"),
    ("彩票网竞彩", "https://www.17500.cn/"),
    ("500彩票网指数中心", "https://odds.500.com/"),
    ("澳客足球数据", "https://www.okooo.com/"),
    ("澳客移动数据", "https://m.okooo.com/"),
    ("7M足球资料库", "https://data.7m.com.cn/"),
    ("7M赛事资料", "https://data.7m.com.cn/matches_data/index.shtml"),
]

ODDS_SEARCH_SITE_QUERIES = [
    "site:odds.500.com 竞彩足球 欧赔 亚盘 即时指数",
    "site:okooo.com 竞彩足球 欧赔 亚盘 必发 凯利",
    "site:data.7m.com.cn 足球 欧赔 亚盘 赔率",
    "site:jibao.310win.com 竞彩足球 欧赔 亚盘",
]

REVIEW_SOURCES = [
    ("17500赛果参考", "https://6.17500.cn/?lottery=bet&lotteryId=s_fb"),
    ("Flashscore", "https://www.flashscore.com/"),
]


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


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
        if item and item.lower() not in [c.lower() for c in candidates]:
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


def fetch_snippet(name: str, url: str, limit: int = 18000) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; jincai-model-bot/2.0)",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
        },
    )
    try:
        with urlopen(req, timeout=20) as resp:
            raw = resp.read(limit * 3)
            text, charset = decode_html(raw, resp.headers.get_content_charset())
    except HTTPError as e:
        return f"## {name}\nURL: {url}\nSTATUS: http_error:{e.code}\n"
    except URLError as e:
        return f"## {name}\nURL: {url}\nSTATUS: url_error:{e.reason}\n"
    except Exception as e:  # pragma: no cover
        return f"## {name}\nURL: {url}\nSTATUS: error:{type(e).__name__}\n"

    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return f"## {name}\nURL: {url}\nSTATUS: 200\nCHARSET: {charset}\nSNIPPET:\n{text[:limit]}\n"


def search_result_limit() -> int:
    return max(1, min(env_int("JINCAI_SEARCH_RESULTS_PER_QUERY", 4), 8))


def search_query_limit() -> int:
    return max(1, min(env_int("JINCAI_SEARCH_MAX_QUERIES", 8), 20))


def compact_text(text: object, limit: int = 900) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text).strip()[:limit]


def call_tavily_search(query: str) -> tuple[str | None, str | None]:
    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return None, "TAVILY_API_KEY is not configured."

    payload = {
        "query": query,
        "topic": os.environ.get("TAVILY_TOPIC", "general"),
        "search_depth": os.environ.get("TAVILY_SEARCH_DEPTH", "basic"),
        "max_results": search_result_limit(),
        "include_answer": False,
        # Tavily extracts cleaned text/markdown itself, which works better than
        # a plain GitHub runner on JavaScript-heavy odds pages.
        "include_raw_content": os.environ.get("TAVILY_INCLUDE_RAW_CONTENT", "markdown"),
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = Request(
        "https://api.tavily.com/search",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        return None, f"Tavily HTTP {e.code}: {detail}"
    except Exception as e:
        return None, f"Tavily error: {type(e).__name__}: {e}"

    lines = [f"### Tavily query: {query}"]
    for idx, result in enumerate(data.get("results", [])[: search_result_limit()], start=1):
        title = compact_text(result.get("title"), 160)
        url = compact_text(result.get("url"), 260)
        content = compact_text(result.get("content") or result.get("raw_content"), 1100)
        score = result.get("score")
        lines.extend(
            [
                f"- result {idx}: {title}",
                f"  url: {url}",
                f"  score: {score}",
                f"  snippet: {content}",
            ]
        )
    return "\n".join(lines), None


def call_brave_search(query: str) -> tuple[str | None, str | None]:
    api_key = os.environ.get("BRAVE_SEARCH_API_KEY")
    if not api_key:
        return None, "BRAVE_SEARCH_API_KEY is not configured."

    params = urlencode(
        {
            "q": query,
            "count": search_result_limit(),
            "country": os.environ.get("BRAVE_SEARCH_COUNTRY", "cn"),
            "search_lang": os.environ.get("BRAVE_SEARCH_LANG", "zh-hans"),
            "safesearch": os.environ.get("BRAVE_SAFESEARCH", "moderate"),
        }
    )
    req = Request(
        f"https://api.search.brave.com/res/v1/web/search?{params}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
    )
    try:
        with urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        return None, f"Brave Search HTTP {e.code}: {detail}"
    except Exception as e:
        return None, f"Brave Search error: {type(e).__name__}: {e}"

    lines = [f"### Brave query: {query}"]
    for idx, result in enumerate((data.get("web") or {}).get("results", [])[: search_result_limit()], start=1):
        snippets = [result.get("description")]
        snippets.extend(result.get("extra_snippets") or [])
        lines.extend(
            [
                f"- result {idx}: {compact_text(result.get('title'), 160)}",
                f"  url: {compact_text(result.get('url'), 260)}",
                f"  snippet: {compact_text(' '.join(s for s in snippets if s), 1100)}",
            ]
        )
    return "\n".join(lines), None


def call_search(query: str) -> tuple[str | None, str | None]:
    provider = os.environ.get("JINCAI_SEARCH_PROVIDER", "auto").strip().lower()
    providers = ["tavily", "brave"] if provider == "auto" else [p.strip() for p in provider.split(",") if p.strip()]
    errors: list[str] = []
    for item in providers:
        if item == "tavily":
            text, error = call_tavily_search(query)
        elif item == "brave":
            text, error = call_brave_search(query)
        else:
            text, error = None, f"Unsupported search provider: {item}"
        if text:
            return text, None
        if error:
            errors.append(error)
    return None, "; ".join(errors) if errors else "No search provider configured."


def extract_jincai_matches(source_blocks: str) -> list[tuple[str, str, str, str]]:
    pattern = re.compile(
        r"(周[一二三四五六日]\d{3})\s+"
        r"([\u4e00-\u9fffA-Za-z]+)\s+"
        r"\d{2}-\d{2}\s+\d{2}:\d{2}\s+"
        r"\S+\s+\S+\s+"
        r"([\u4e00-\u9fffA-Za-z0-9]+)\s+"
        r"([\u4e00-\u9fffA-Za-z0-9]+)\s+"
        r"\d+\.\d{2}\s+\d+\.\d{2}\s+\d+\.\d{2}"
    )
    seen: set[tuple[str, str, str]] = set()
    matches: list[tuple[str, str, str, str]] = []
    for match_id, league, home, away in pattern.findall(source_blocks):
        key = (match_id, home, away)
        if key in seen:
            continue
        seen.add(key)
        matches.append((match_id, league, home, away))
    return matches


def build_search_supplement(*, day: str, source_blocks: str, mode: str) -> str:
    if os.environ.get("JINCAI_SEARCH_ENABLED", "1").strip().lower() in {"0", "false", "no"}:
        return "## 搜索补充\nSTATUS: disabled by JINCAI_SEARCH_ENABLED\n"

    if not os.environ.get("TAVILY_API_KEY") and not os.environ.get("BRAVE_SEARCH_API_KEY"):
        return (
            "## 搜索补充\n"
            "STATUS: disabled; no TAVILY_API_KEY or BRAVE_SEARCH_API_KEY configured. "
            "Only fixed sources were used.\n"
        )

    base = f"{day} 竞彩足球 今日 欧赔 亚盘 大小球 凯利 伤停 战意 500彩票网 澳客 7M"
    queries = [base] if mode == "plan" else [f"{day} 竞彩足球 赛果 比分 赛后 复盘"]
    if mode == "plan":
        queries.extend(f"{day} {query}" for query in ODDS_SEARCH_SITE_QUERIES)
    for match_id, league, home, away in extract_jincai_matches(source_blocks):
        if mode == "plan":
            queries.append(
                f"{day} 竞彩足球 {match_id} {league} {home} vs {away} "
                "欧赔 亚盘 大小球 凯利 500彩票网 澳客 7M"
            )
        else:
            queries.append(f"{day} 竞彩足球 {match_id} {home} vs {away} 赛果 比分")

    blocks = ["## 搜索补充", "说明：搜索 API 返回摘要/抽取文本，用于补充 JS 渲染站点无法被 GitHub runner 直接读取的问题。"]
    for query in queries[: search_query_limit()]:
        text, error = call_search(query)
        if text:
            blocks.append(text)
        else:
            blocks.append(f"### Search query: {query}\nSTATUS: search_error:{error}")
    return "\n\n".join(blocks)


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

    thinking_type = os.environ.get("DEEPSEEK_THINKING", "enabled").strip().lower()
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是保守的竞彩模型记录员。只输出可复盘的 Markdown 正文，不编造数据。",
            },
            {"role": "user", "content": prompt},
        ],
        "max_tokens": int(os.environ.get("AI_MAX_TOKENS", "12000")),
    }
    if thinking_type == "enabled":
        payload["thinking"] = {"type": "enabled"}
        payload["reasoning_effort"] = os.environ.get("DEEPSEEK_REASONING_EFFORT", "high")
    else:
        payload["thinking"] = {"type": "disabled"}
        payload["temperature"] = float(os.environ.get("AI_TEMPERATURE", "0.2"))
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
    search_blocks = build_search_supplement(day=day, source_blocks=source_blocks, mode="plan")
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
10. 必须区分“观察绿灯”和“执行绿灯”：观察绿灯只进入模拟池、遮蔽回放和复盘；执行绿灯才允许进入正式单场候选或正式串关。
11. 缺少亚盘、凯利、伤停、首发或战意中的部分数据时，应增加不确定性惩罚，不得机械地把全部场次标红。存在方向矛盾、多个未覆盖核心风险或全部外部确认缺失时，仍不得升级为执行绿灯。
12. 当日竞彩场次达到 8 场及以上时，必须输出最多 3 场观察绿灯，或逐场说明为何没有任何场次达到观察绿灯。不得为了数量硬升绿。

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

联网搜索补充：
{search_blocks}
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
    search_blocks = build_search_supplement(day=day, source_blocks=source_blocks, mode="review")
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

联网搜索补充：
{search_blocks}
""".strip()
    return prompt, target


def generate_review() -> Path:
    now = dt.datetime.now(TZ)
    prompt, target = build_review_prompt(now)
    content, error = call_llm(prompt)
    if error:
        content = failure_report(f"竞彩模型每日复盘 - {now:%Y-%m-%d}", now, error)
    return write_report("reviews", now.date(), content)

#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import os

from ai_jincai_report import TZ, generate_plan


def resolve_target_date(now: dt.datetime) -> dt.date:
    configured = os.environ.get("TARGET_DATE")
    if configured:
        return dt.date.fromisoformat(configured)

    # GitHub scheduled jobs can run late. If the 21:05 job starts after
    # midnight China time, it still belongs to the previous match day.
    if now.hour < 6:
        return now.date() - dt.timedelta(days=1)
    return now.date()


def main() -> None:
    now = dt.datetime.now(TZ)
    out = generate_plan(
        output_dir="21_final",
        batch_label="21点最终方案",
        next_recheck_label="赛后复盘重点",
        workflow_file=".github/workflows/jincai-21-final.yml",
        target_date=resolve_target_date(now),
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

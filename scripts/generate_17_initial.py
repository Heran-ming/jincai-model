#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import os

from ai_jincai_report import TZ, generate_plan


def main() -> None:
    now = dt.datetime.now(TZ)
    output_dir = os.environ.get("JINCAI_OUTPUT_DIR", "17_initial")
    out = generate_plan(
        output_dir=output_dir,
        batch_label=os.environ.get("JINCAI_BATCH_LABEL", "17点初步方案"),
        next_recheck_label=os.environ.get("JINCAI_NEXT_RECHECK_LABEL", "21点重点复查项"),
        workflow_file=os.environ.get("JINCAI_WORKFLOW_FILE", ".github/workflows/jincai-17-initial.yml"),
        target_date=now.date(),
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

from ai_jincai_report import generate_review


def main() -> None:
    out = generate_review()
    print(f"wrote {out}")


if __name__ == "__main__":
    main()

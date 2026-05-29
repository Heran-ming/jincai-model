# 竞彩模型

这是竞彩模型的长期资料库，用于保存赛前锁版、赔率复查、赛后复盘、模型参数和滚动统计。

## 核心文件

- `竞彩模型防过拟合与低置信执行规则.md`：执行规则与风控约束。
- `竞彩模型赛前锁版与复盘账本.csv`：赛前锁版与复盘账本。
- `records/portfolio_status.md`：每日更新的持仓与收益率看板。
- `extracted/竞彩/`：历史预测、复盘、微调报告和模型数据。

## 自动化约定

- 11:30 任务输出当天初始方案到 `records/1130_initial/YYYY-MM-DD.md`。
- 17:00 任务输出当天复查方案到 `records/17_check/YYYY-MM-DD.md`。
- 21:00 任务读取当天初始/复查方案，并输出最终方案到 `records/21_final/YYYY-MM-DD.md`。
- 21:00 任务同时刷新 `records/portfolio_status.md`，用于查看当前持仓。
- 每日复盘任务读取预测、赛果和账本，输出复盘到 `records/reviews/YYYY-MM-DD.md`，并刷新 `records/portfolio_status.md` 的收益率。
- 盲测回放写入 `records/blind_tests/YYYY-MM-DD-blind-replay.md`，用于隐藏赛果后验证模型和流程。

赛前自动化都会通过 Telegram 推送对应的最新生成文件。所有自动化都应优先读取本仓库内的规则、账本、历史记录和参数文件；无法可靠获取最新数据时必须明说，不补造数据。

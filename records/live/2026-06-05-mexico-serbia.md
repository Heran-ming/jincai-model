# Mexico vs Serbia 临场预测锁版 - 2026-06-05

> 本报告用于模型观察与赛后复盘，不构成下注建议。当前时间已接近/达到开球，按临场锁版处理；未可靠获取实时比分时，不做赛中盘伪装。

## 锁版信息

- 生成时间：`2026-06-05 10:01:40 +0800`
- 比赛：Mexico vs Serbia
- 赛事：International Friendly
- 场地：Estadio Nemesio Diez, Toluca, Mexico
- 开球时间：`2026-06-05 10:00 +0800` 左右
- 数据窗口：`2026-06-05 09:50-10:05 +0800`
- 模型版本：`v1.8.3`
- 结论：墨西哥是市场强热门，但胜赔被压得过低；优先看低比分结构，不追墨西哥深让。

## 已读取材料

- `竞彩模型防过拟合与低置信执行规则.md`
- `竞彩模型赛前锁版与复盘账本.csv`
- `extracted/竞彩/模型参数.json`
- `extracted/竞彩/滚动统计.json`
- `records/reviews/2026-06-05.md`

## 核验来源

- Tips.GG odds：`https://tips.gg/matches/football/04-06-2026/mexico-vs-serbia/09-00/odds/`
- SportyTrader odds comparison：`https://www.sportytrader.com/en/odds/mexico-serbia-8417460/`
- Sports Mole match guide/data model：`https://www.sportsmole.co.uk/football/international-friendlies/mexico-vs-serbia_game_248588.html`
- Sports Mole preview/team news：`https://www.sportsmole.co.uk/football/mexico/preview/mexico-vs-serbia-prediction-team-news-lineups_598572.html`
- FootballPredictions：`https://footballpredictions.com/footballpredictions/internationalfriendliespredictions/mexico-vs-serbia-prediction-05-06-2026/`
- FOX Sports schedule/odds context：`https://www.foxsports.com/stories/soccer/mexico-vs-serbia-how-watch-prediction-odds-friendly-preview`
- El Pais Mexico preview：`https://elpais.com/mexico/2026-06-03/mexico-serbia-horario-y-donde-ver-el-ultimo-partido-amistoso-del-tri.html`

## 数据缺口

1. 未可靠取得中国竞彩官方编号；按用户最新口径，竞彩官方缺口只记录，不纳入黄绿灯计算。
2. 开球临近，实时比分和滚球盘口可能已变化；本文只锁定赛前/临场公开赔率，不使用赛中赔率。
3. 半场让球、半场大小球只搜到部分市场名，未得到足够稳定单项赔率，最高只黄灯观察。
4. 友谊赛且为世界杯前最后热身，双方轮换和控制强度都可能改变全场节奏。

## 市场与模型差

Tips.GG 可见 1X2 多家公司大致区间：

- Mexico 胜：`1.22-1.32`
- 平局：`4.75-5.60`
- Serbia 胜：`8.50-10.00`，个别异常低值不采用

以 `1.28 / 5.00 / 8.50` 粗略去水：

| 市场 | 赔率 | 市场去水概率 | 模型概率 | 差值 | 处理 |
|---|---:|---:|---:|---:|---|
| Mexico 胜 | `1.28` | 约 `70.4%` | `51-58%` | 模型显著低于市场 | 黄灯，不追低赔 |
| 平局 | `5.00` | 约 `18.0%` | `24-28%` | 模型高于市场 | 冷门观察，不单买 |
| Serbia 胜 | `8.50` | 约 `10.6%` | `18-22%` | 模型高于市场 | 只作为反方风险 |
| 小 `2.5` | `2.10` 片段 | 模型约 `59%` | `56-60%` | 有价值但来源分歧 | 黄偏绿观察 |
| 小 `3.5` | `1.40` 片段 | 模型约 `79%` | `74-80%` | 稳定但赔率低 | 黄偏绿观察 |
| BTTS No | `1.67` 片段 | 模型约 `56-57%` | `55-58%` | 边际很薄 | 黄灯，不能由小球直接推 |

## 方向判断

### 1. 全场小 3.5 - 黄偏绿观察

- 市场：全场亚洲/欧式大小球
- 单选主项：小 `3.5`
- 参考赔率：约 `1.40`
- 命中条件：90 分钟总进球 `0-3`
- 核心依据：
  - Sports Mole 数据模型给 Under `3.5` 约 `79.6%`。
  - Mexico 最近热身赛比分偏小，刚 `1-0` Australia。
  - FootballPredictions 也倾向墨西哥胜且低比分，列出 Under `3.5`。
  - 昨天复盘显示友谊赛热门胜负不稳，但大小球方向相对更可复盘。
- 最大反方证据：
  - Sports Mole 预览正文预测 `3-1`，刚好打穿小 `3.5`。
  - 墨西哥主场世界杯前最后热身，若早进球，比赛可能被拉开。
- 推翻条件：
  - 若临场/赛中盘口从 `3.5` 降至 `3.0/2.75`，不追小。
  - 若首发明确是强攻组合并且 Serbia 后防大幅轮换，降黄。
- 三分：价值 `4`，稳定 `5`，惩罚 `4`
- 灯色：黄偏绿

### 2. Mexico 胜 - 黄灯

- 市场：全场胜平负
- 单选主项：Mexico 胜
- 参考赔率：`1.22-1.32`
- 命中条件：Mexico 90 分钟胜出
- 核心依据：
  - 市场明显支持 Mexico，主场、世界杯前最后热身、近期 5 胜 2 平。
  - Serbia 未进世界杯，且上场 `0-3` Cape Verde，状态信号差。
- 最大反方证据：
  - 市场去水概率约 `70%`，但 Sports Mole 数据模型只给 Mexico 胜 `50.77%`，分歧很大。
  - 昨天复盘刚验证：友谊赛强热门胜负方向容易被轮换/控节奏击穿。
- 推翻条件：
  - 墨西哥胜低于 `1.25` 不追。
  - 若半场仍 `0-0`，不追胜负方向，优先转小球观察。
- 三分：价值 `2`，稳定 `5`，惩罚 `5`
- 灯色：黄

### 3. Mexico -1 / 深让 - 跳过

- 市场：全场让球
- 主项：Mexico `-1` 或更深
- 处理：跳过，不追穿盘。
- 理由：
  - Sports Mole 数据模型最可能比分是 `1-0`，其次 `2-0/2-1/1-1`。
  - `1-0` 会让亚洲 `-1` 走盘、欧洲 `-1` 让平，无法支持强穿。
  - 昨天 France/Slovenia/Spain/Kenya 的热门胜负复盘已提示：友谊赛追热门穿盘风险高。
- 灯色：红/跳过

### 4. BTTS No - 黄灯，不升绿

- 市场：双方是否进球
- 主项：BTTS No
- 参考赔率：约 `1.67`
- 命中条件：至少一队 0 进球
- 核心依据：
  - FootballPredictions 给出 BTTS No。
  - Mexico 防守记录较好，Serbia 状态不稳。
- 最大反方证据：
  - Sports Mole 数据模型显示 Serbia 进球 `0.5+` 约 `54.29%`。
  - 昨天 Lesotho/Kenya 已经出现“小 2.5 命中但 BTTS No 失败”的样本，不能再把低比分直接转 BTTS No。
- 三分：价值 `3`，稳定 `4`，惩罚 `5`
- 灯色：黄

## 盘口池

| 市场 | 方向 | 参考赔率 | 灯色 | 备注 |
|---|---|---:|---|---|
| 全场大小球 | 小 `3.5` | `1.40` | 黄偏绿 | 最顺的保守结构，但赔率低 |
| 全场大小球 | 小 `2.5` | `2.10` 片段 | 黄偏绿 | 有价值但分歧更大，比分 `2-1/3-1` 是风险 |
| 全场胜平负 | Mexico 胜 | `1.22-1.32` | 黄 | 方向合理，赔率太低 |
| 全场让球 | Mexico `-1` | `1.48-1.83` 片段 | 红/跳过 | 1 球小胜概率高，不追穿盘 |
| BTTS | No | `1.67` | 黄 | 不能由小球直接升绿 |
| 半场胜平负 | 半场平 | 仅模型概率约 `45%` | 黄 | 若有 `2.20+` 可观察；低于 `2.00` 不追 |
| 半场大小球 | 半场小 `1.5` | 缺稳定单项赔率 | 黄/跳过 | 只记录，不反推 |

## 最终结论

- 不给正式绿灯。
- 如果只选一个观察方向：全场小 `3.5`。
- 如果赔率允许冒一点波动：小 `2.5 @2.00+` 比 Mexico 胜更有价值。
- 不追 Mexico `-1/-1.5` 深让。
- BTTS No 只黄灯，不能当主项。
- 比分分布：`1-0`、`2-0`、`2-1`、`1-1`；若早段进球，`3-1` 是小球反方。

## 读写路径

已读取：

- `竞彩模型防过拟合与低置信执行规则.md`
- `竞彩模型赛前锁版与复盘账本.csv`
- `extracted/竞彩/模型参数.json`
- `extracted/竞彩/滚动统计.json`
- `records/reviews/2026-06-05.md`

已写入：

- `records/live/2026-06-05-mexico-serbia.md`

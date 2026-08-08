# 体彩数字彩 V1 设计说明

## 目标

把已经预留的体彩扩展口正式接入产品，先覆盖和现有号码分析模型同构的三种数字型玩法：

- 大乐透 `dlt`
- 排列3 `pl3`
- 排列5 `pl5`

本轮不接足彩、竞彩、胜负彩等非号码型玩法。它们需要赛程、赔率、球队/选手维度，不适合复用当前热冷号、遗漏、和值、走势和号码池模型。

## 数据来源

官方体彩历史开奖页当前由 `https://www.lottery.gov.cn/kj/kjlb.html?...` 加载静态 iframe，iframe 内脚本调用：

- `https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry`
- 关键参数：`gameNo`、`provinceId=0`、`pageNo`、`pageSize`
- 游戏映射：大乐透 `85`，排列3 `35`，排列5 `350133`

接口在直接服务端请求时可能触发官方 WAF，所以实现必须把“网络请求”和“字段标准化”拆开：

- 网络层使用官方默认路径，但支持环境变量覆盖 base URL。
- `auto` 模式先请求官方 API；如果遇到官方 WAF 403，则切到官方页面浏览器态，从 `lottery.gov.cn` 历史开奖页进入 iframe，再在页面上下文里请求官方 API。
- 解析层独立测试，支持官方常见字段 `lotteryDrawNum`、`lotteryDrawTime`、`lotteryDrawResult`、`prizeLevelList`。
- 入库仍写现有 `draws` 表，保持分析、预测、策略实验室无需关心来源差异。

## 号码标准化

- 大乐透：`lotteryDrawResult` 前 5 位作为 `red_numbers`，后 2 位作为 `blue_number`，存储为逗号分隔字符串。
- 排列3：3 位数字全部存入 `red_numbers`，允许重复，无 `blue_number`。
- 排列5：5 位数字全部存入 `red_numbers`，允许重复，无 `blue_number`。
- `game_name` 使用规则表内中文名作为兜底。
- `content` 存储销售额、奖池、奖级等摘要，`raw_json` 保留原始行。

## 产品行为

- `/api/games` 返回七个正式玩法：福彩四种 + 体彩三种。没有本地历史数据的体彩玩法也要显示入口，元数据为空即可。
- `/api/analysis/{game}` 对体彩玩法可返回空样本分析，不报 404。
- `/api/predict` 支持体彩玩法；大乐透返回 5+2，排列3/排列5返回允许重复的按位数字。
- `/api/strategy/{game}` 和筛选/回测能力复用规则表，体彩无历史样本时返回低样本提示和可生成的候选。
- 前端首页、分析中心、策略实验室都展示体彩标签。

## 爬取命令

```bash
python -m playwright install chromium
python -m lottery_luck.sports_crawler --games dlt,pl3,pl5 --source auto --page-size 100
```

如需强制使用官方页面浏览器态：

```bash
python -m lottery_luck.sports_crawler --games dlt --source browser --page-size 100
```

## 风险

- 官方接口可能要求浏览器态参数或被 WAF 限制；V1 只采集官方链路，不接第三方开奖源。
- 体彩历史数据初始为空时，分析质量低；UI 必须清楚表现为“样本不足”，不能暗示确定性。
- 大乐透双后区号码需要前端特殊球样式继续居中，不出现多余连接符。

# 复盘闭环与运营增强 V1 Design

## 背景

P0 的玄学可信度、生成留痕和三种生成模式已经上线。下一步重点不是继续证明“号码能预测”，而是把产品叙事改成“玄学合参生成 -> 开奖后回来复盘 -> 再生成下一组”，让用户有理由反复打开。

## 范围

本轮交付 P1/P2 的可用闭环：

- 后台“一键福彩补采”，把当前福彩命令提示变成可点击操作入口。
- 开奖复盘 API，根据用户历史财运号和最新开奖计算命中数量、命中号码、财眼是否命中和一句复盘话术。
- 首页历史财运号支持复盘状态，用户生成后可看到“待复盘 / 已复盘”。
- AI 解读分层，预测 payload 明确返回 `interpretation_layers.short_hook` 和 `interpretation_layers.long_reading`，号码仍由本地算法生成。
- 号码池增加玄学点评字段，给每组号码标注进财/守财/散财倾向和是否冲本命财格。
- 分析页增加“彩民常看”默认视图，把热冷、遗漏、和值、奇偶、重号放在最前。
- 数据质量监控增强，后台展示健康颜色等级、缺口趋势和最近失败原因置顶。

## 非目标

- 不把用户历史财运号上传服务器长期存储；首页历史仍保存在浏览器 localStorage。
- 不让 AI 直接生成号码；AI 只参与解释文案和特征描述。
- 不重做分析中心的信息架构；本轮只增加默认重点视图，不移除已有专业工具。
- 不做登录、提醒推送或服务端定时任务。

## 后端设计

### 福彩补采

新增 `POST /api/admin/crawl/cwl`。请求字段为：

- `games`: 默认 `["ssq", "3d", "kl8"]`，不再暴露七乐彩到前台主导航，但仍允许后端补采。
- `page_size`: 默认 100，范围 1-500。

实现上复用 `lottery_luck.crawler.fetch_game_rows`、`normalize_api_row` 和 `upsert_draw`，并记录 `crawl_logs`。返回结构与体彩补采一致：`crawl` 和刷新后的 `health`。

### 复盘 API

新增 `lottery_luck.review` 模块和 `POST /api/review/{game_key}`。请求包含：

- `main`: 用户生成的主号。
- `special`: 用户生成的特别号。
- `fortune_eye`: 财眼号码，优先用特别号；无特别号时用主号最后一位。

接口读取最新一期开奖，返回：

- `latest_draw`
- `main_hits`
- `special_hits`
- `hit_count`
- `fortune_eye_hit`
- `status`: `pending` 或 `reviewed`
- `summary`: 面向用户的短复盘话术

### AI 解读分层

`PredictionEngine.predict` 返回 `interpretation_layers`：

- `short_hook`: 一句钩子，首页可直接高亮。
- `long_reading`: 解释命格、今日气口、喜用元素和号码组合。

DeepSeek 仍走现有 `AiFeature`，没有 AI 时使用本地解释模板。

### 号码池玄学点评

`analyze_number_pool` 每个 entry 增加 `fortune_commentary`：

- `wealth_type`: `进财` / `守财` / `散财`
- `compatibility`: `相合` / `略冲` / `中性`
- `comment`: 一句话点评

这版不需要用户出生信息，先按号码和值、尾数五行和重复度做轻量点评。

## 前端设计

### 首页历史复盘

本地历史记录新增结构化字段：

- `main_numbers`
- `special_numbers`
- `fortune_eye`
- `review`

渲染历史记录时调用 `/api/review/{game_key}` 做即时复盘，成功后写回 localStorage。卡片上展示命中数量、命中号码、财眼状态和复盘话术。

### 后台页面

新增福彩补采卡片，操作方式和体彩补采一致。数据健康表：

- 状态 pill 使用 healthy / attention / empty / failed 颜色。
- 缺口列展示 `missing_recent_count` 和 `staleness_days`。
- 日志区域顶部展示最近失败原因。

### 分析页

在现有分析卡片前增加“彩民常看”摘要区，用同一份 analysis payload 渲染：

- 热号
- 冷号
- 遗漏
- 奇偶
- 和值
- 重号

## 测试策略

- 后端用 pytest 覆盖福彩补采 API、复盘 API、AI 分层字段、号码池玄学点评、数据健康失败摘要。
- 前端静态测试覆盖新增 DOM 节点和 JS 关键函数。
- 浏览器验证首页历史复盘、后台福彩补采入口、分析页“彩民常看”在桌面和移动端不溢出。

## 风险与处理

- 福彩官方接口失败时，接口返回 `failed_games` 并写入日志，后台显示最近失败原因。
- 用户历史记录可能是旧格式；前端复盘时兼容 `number_text` 解析，并在下一次保存时写入新格式。
- 没有最新开奖数据时，复盘返回 `pending`，不伪造命中结果。

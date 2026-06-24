# MarketNoticeBot

面向**十年长期定投者**的每周大盘提醒机器人：每周固定时间把宽基资产的位置、温度与机械定投倍数推送到飞书，帮助判断「这一周要不要加码定投」，而不是做短线择时。

> 这是一个学习与纪律工具，**不构成任何投资建议**。它只描述已经发生的价格/回撤/宏观信号，不预测涨跌、不预测危机。

本项目构建在多智能体金融分析框架 [TradingAgents](https://github.com/TauricResearch/TradingAgents) 之上，复用它的分析师团队产出深度学习材料，再压缩成一条「人话」周报。

---

## 它做什么

每周一次（默认周三早上），对一篮子宽基资产（美股科技/大盘、港股、黄金/原油、中国科技与半导体等）：

- 计算**距 52 周高点回撤**、**较 200 日均线乖离**、**温度档**（中性 / 回调区 / 明显回撤 / 偏热）；
- 按机械规则给出**本周定投倍数 1x / 2x / 3x**（只在「已实现大回撤 + 跌破长期均线」时才加码，纯反应式、不预测）；
- 附上**宏观慢变量**（VIX、美债 10Y-2Y 利差）；
- 通过**飞书自定义机器人 webhook（带签名）**冷推送。

刻意**不包含任何个人持仓数据**——推送内容全部是公开市场信息，可以安全地放进群里。

## 两层架构

| 层 | 脚本 | 成本 | 作用 |
|---|---|---|---|
| **轻量快照** | `scripts/weekly_market_snapshot.py` | 纯标准库，零 LLM | 价格/回撤/均线/倍数/宏观，秒级生成 |
| **重型周报** | `scripts/run_weekly_deep_analysis.py` + `scripts/compile_weekly_learning_report.py` | 跑 TradingAgents 多智能体 + LLM 汇总 | 逐资产跑分析师团队（含情绪面），再由 LLM 汇总成中文学习日报，飞书卡片推送 |
| **学习信（周六）** | `scripts/weekly_learning_letter.py` + `scripts/learning_syllabus.py` | 单次 LLM，零多智能体 | 面向零基础的每周金融学习信，固定大纲循序渐进 + 行情大事插播 |

`scripts/run_weekly_market_snapshot.sh`（周三）和 `scripts/run_weekly_learning_letter.sh`（周六）分别供 cron 调用。

### 周六金融学习信

一封写给「完全零基础」长期定投者的学习信，和周三的行情/决策报告分工：周三回答「现在怎么做」，周六回答「金融到底怎么运作」。约 52 周的固定大纲（`learning_syllabus.py`）循序渐进、不重复；遇到真实市场大事（某指数单周大跌或 VIX 飙升）时临时插播一期应景专题，且不消耗大纲进度。每期含：本周核心概念、用本周真实数据举例、术语卡、常见误区、历史小课堂、思考题（附答案）。进度记录在 `learning-progress.json`（运行时状态，不入库）。

## 数据源

刻意使用底层标的与官方指数，**不使用可能带申赎溢价的境内场内 ETF 价格**：

- 美股 ETF（QQQ/SPY/GLD/USO 等）→ 新浪美股日 K
- 恒生 / 恒生科技 / 科创50 → 腾讯行情
- 中证半导体等指数 → 中证指数官方接口（见 `tradingagents/dataflows/direct_index_data.py`）
- 宏观（DGS10/DGS2/VIX）→ FRED（无 key 走 CSV 接口，可选 `FRED_API_KEY`）
- 估值（标普500 Shiller CAPE / TTM PE + 历史分位）→ multpl.com（`valuation.py`；纳指/港股/中国指数暂无可靠免费历史 PE 源，仍以价格回撤为温度代理）
- 情绪面 → 新闻 + StockTwits + Reddit + 已验证的东方财富股吧（`tradingagents/dataflows/eastmoney_guba.py`）

## 快速开始

```bash
git clone <your-fork-url> MarketNoticeBot
cd MarketNoticeBot
python3.12 -m venv .venv && . .venv/bin/activate
pip install .            # 轻量快照仅需标准库；重型周报需要框架依赖
```

配置飞书推送（**不要提交到仓库**）：

```bash
cat > feishu.env <<'EOF'
FEISHU_WEBHOOK=https://open.feishu.cn/open-apis/bot/v2/hook/<your-hook-id>
FEISHU_SECRET=<your-sign-secret>
# 可选：FRED_API_KEY=<your-key>
EOF
chmod 600 feishu.env
```

跑一次轻量快照（先打印不推送）：

```bash
python scripts/weekly_market_snapshot.py --config feishu.env --print-only
```

确认无误后去掉 `--print-only` 即会推送飞书。设置每周定时（例：周三 08:00）：

```cron
0 8 * * 3 /path/to/MarketNoticeBot/scripts/run_weekly_market_snapshot.sh   # 周三 行情/决策
0 8 * * 6 /path/to/MarketNoticeBot/scripts/run_weekly_learning_letter.sh   # 周六 学习信
```

重型周报额外需要一个 LLM provider 的 API key（如 `DEEPSEEK_API_KEY`），见下游框架配置。

## 飞书推送

使用飞书群自定义机器人，开启「签名校验」。签名算法：`HMAC-SHA256(key = f"{timestamp}\n{secret}", msg = "")` → base64，随 `{"timestamp", "sign", ...}` POST。实现见 `scripts/weekly_market_snapshot.py` 的 `send_feishu`。长文自动切分成多张飞书交互卡片。

## 设计原则

- **不碰持仓**：推送零个人持仓，持仓分析只在私聊里做。
- **轻量层不烧 LLM**：每周的便宜路径纯数据计算；多智能体只在重型周报里跑。
- **机械、反应式**：倍数基于已实现回撤 + 均线位置，不预测未来、不越跌越买（存储类标的仅作产业观察，不给倍数）。
- **不预测危机**：只解释已观察到的波动/利率/趋势信号。

## 致谢

分析师团队、研究/交易/风控智能体、数据流与 CLI 均来自 [TradingAgents](https://github.com/TauricResearch/TradingAgents)（Multi-Agents LLM Financial Trading Framework）。MarketNoticeBot 在其之上增加了直连指数数据源、东方财富股吧情绪源，以及面向长期定投者的每周飞书提醒管线。

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework},
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138},
}
```

## 免责声明

本项目仅供长期定投的学习与纪律参考，不构成任何形式的投资建议或未来表现保证。资产配置与定投决策请结合个人情况独立做出。

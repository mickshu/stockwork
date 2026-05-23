# 📈 A 股基本面 + 技术面 + 大师观点 分析助手

基于 Streamlit + akshare 的 A 股一站式分析工具：输入股票代码或中文名，自动产出公司基本面诊断、技术面信号、10 位投资大师视角与综合评分报告。

## ✨ 功能特性

- **🔍 智能输入**：下拉框加载全市场 5500+ 股票，支持**代码或中文名搜索**（输入「茅台」即可联想到 `600519 贵州茅台`）
- **📑 基本面诊断**：ROE / 资产负债率 / 近 3 年净利润 CAGR / 现金流质量 / PE-行业对比
- **📈 技术面信号**：K 线 + MA + 布林带 + MACD + RSI + KDJ，叠加**周线 MA20 趋势**判断
- **🎓 大师观点（10 位）**：格雷厄姆 / 巴菲特 / 芒格 / 段永平 / 林奇 / 费雪 / 索罗斯 / 马克斯 / 达利欧 / 西蒙斯——把同一组数据放到不同分析框架下，看哪些大师买、哪些避
- **🎯 综合评分**：三步框架打分（基本面 60% + 技术面 40%），输出 *推荐关注 / 观察 / 暂缓* 三档结论
- **⚠️ 风险提示**：每份报告**自动列出至少 3 条核心风险**（高杠杆 / 现金流差 / 估值偏高 / 业务下滑 等）
- **🛡 数据严谨**：强制**前复权**、清洗 NaN / Inf / 非正值、关键接口缓存、push2 不可达时自动降级

## 🗂 项目结构

```
stockwork/
├── app.py                    # Streamlit 入口
├── requirements.txt
├── CLAUDE.md                 # 项目级开发约束
├── data/
│   └── fetcher.py            # akshare 封装 + 缓存 + 代理绕过 + 兜底
├── analysis/
│   ├── fundamental.py        # 基本面指标
│   ├── technical.py          # 技术指标 (MA/MACD/RSI/KDJ/BOLL + 周线趋势)
│   ├── masters.py            # 10 位投资大师规则引擎
│   ├── risk.py               # 风险因子自动识别
│   └── scoring.py            # 三步框架综合打分
├── ui/
│   ├── sidebar.py            # 侧边栏 (代码/中文联想补全)
│   ├── overview_tab.py       # 概览
│   ├── fundamental_tab.py    # 基本面
│   ├── technical_tab.py      # 技术面 (plotly 三联子图)
│   ├── masters_tab.py        # 大师观点 (10 张卡片 + 共识汇总)
│   └── report_tab.py         # 综合评分 + 风险提示
└── utils/
    ├── validators.py         # 输入校验 / 价格异常检测
    └── format.py             # 数字 / 百分比格式化
```

## 🚀 快速开始

### 环境要求

- Python 3.9+
- macOS / Linux / Windows
- 可访问外网（拉取 akshare 数据）

### 安装

```bash
git clone git@github.com:mickshu/stockwork.git
cd stockwork
pip install -r requirements.txt
```

> 若 `pip` 提示二进制装到了 `~/Library/Python/3.x/bin` 而不在 PATH，需把该目录加进 PATH，或用 `python3 -m streamlit run app.py` 启动。

### 启动

```bash
streamlit run app.py
```

浏览器会自动打开 [http://localhost:8501](http://localhost:8501)。

### 使用步骤

1. 在左侧栏点击下拉框，**输入代码（`600519`）或中文（`茅台`）** 即可联想匹配
2. 选择 K 线周期与均线参数
3. 点击 **「🔍 开始分析」**
4. 在 **概览 / 基本面 / 技术面 / 🎓 大师观点 / 综合评分** 五个 tab 中查看结果

## 📊 评分模型

| 模块 | 权重 | 满分构成 |
|---|---|---|
| **基本面** | 60% | 5 项指标各 20 分；达标给满分，未达标减半 |
| **技术面** | 40% | 周线趋势 40 分 + 综合信号映射 60 分 |
| **结论** | — | ≥ 80 推荐关注；60–79 观察；< 60 暂缓 |

## 🎓 投资大师评估框架

| 大师 | 学派 | 核心判定 |
|---|---|---|
| 本杰明·格雷厄姆 | 防御型价值投资 | PE<15 + PB<1.5 + 低负债 |
| 沃伦·巴菲特 | 价值 + 护城河 + 长期 | 高 ROE + 强现金流 + 合理 PE |
| 查理·芒格 | 高质量企业 | 高 ROE + 持续成长 + 不贵 |
| 段永平 | 本分长期主义 | 利润持续 + 现金流强 + 低负债 |
| 彼得·林奇 | PEG 选股 | PEG = PE / CAGR < 1 |
| 菲利普·费雪 | 成长股长期持有 | 高 CAGR（>15%） |
| 乔治·索罗斯 | 趋势 + 反身性 | 周线趋势 + 技术信号 |
| 霍华德·马克斯 | 周期 + 逆向 | PE 显著低于行业均值 |
| 瑞·达利欧 | 全天候 + 风险平价 | 4 项核心指标整体健康度 |
| 詹姆斯·西蒙斯 | 量化交易 | 纯技术信号 score 映射 |

每位大师输出：⭐ 1-5 星 + 买入/观望/回避 + 看好理由 + 主要顾虑。

## 🛡 数据严谨性约束（来自 `CLAUDE.md`）

| 约束 | 实现位置 |
|---|---|
| 历史价格**强制前复权** | `data/fetcher.py::get_price_history` 内 `assert adjust == 'qfq'` |
| NaN / Inf / ≤0 价格触发 Warning | `utils/validators.py::check_price_series` |
| 技术指标只依赖 `[0..t]` 行，无前瞻偏差 | `analysis/technical.py` 全部使用 `rolling` / `ewm` |
| 风险提示至少 3 条 | `analysis/risk.py::detect_risks` 内置兜底通用风险 |
| 国内 API 自动绕过系统代理 | `data/fetcher.py` 顶部设置 `NO_PROXY` |
| push2 不可达时降级到名称兜底 | `data/fetcher.py::get_stock_info` |
| 实时报价失败时用最新 K 线收盘价兜底 | `app.py` 中的 quote fallback 逻辑 |

## 🧪 数据源

| 接口 | 用途 |
|---|---|
| `ak.stock_info_a_code_name` | 全市场代码-名称表（联想补全 + 兜底） |
| `ak.stock_individual_info_em` | 公司基本信息（行业、市值、上市日期） |
| `ak.stock_zh_a_hist` | 历史 K 线（强制 `adjust='qfq'`） |
| `ak.stock_financial_abstract_ths` | 财务摘要（ROE / 负债率 / 净利润 / 现金流） |
| `ak.stock_bid_ask_em` | 实时报价 |
| `ak.stock_zh_valuation_baidu` | PE(TTM) / PB / 总市值 |
| `ak.stock_board_industry_name_em` | 行业平均 PE（估值对比） |

## 🩺 常见问题

**Q：报错 `Unable to connect to proxy`？**
A：本机有全局代理（Clash/Surge 等）且代理服务异常。代码已默认对 `eastmoney.com / 10jqka.com.cn / baidu.com / sina.com.cn` 等域名绕过代理；如仍报错可临时 `HTTP_PROXY= HTTPS_PROXY= NO_PROXY='*' streamlit run app.py`。

**Q：报错 `Remote end closed connection`（`push2.eastmoney.com`）？**
A：部分网络下东财 push2 节点不可达。应用已做降级：股票名称仍可显示，实时报价用 K 线收盘价兜底，不影响主要分析。可尝试更换 DNS（`223.5.5.5` / `119.29.29.29`）。

## 🧭 不在本期范围

- 回测引擎（backtrader）
- 多因子选股 / 全市场扫描
- 实盘下单接口
- 用户登录 / 持仓管理

## ⚠️ 免责声明

本工具仅供**学习研究**使用，所有输出（含买卖信号、综合评分、大师观点、风险提示）**不构成任何投资建议**。市场有风险，投资需谨慎。

## 📄 License

MIT

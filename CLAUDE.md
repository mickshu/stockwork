# 股票投资与量化分析系统 (Stock Investment & Quantitative System)

## 项目概述
本专案致力于股票数据获取、基本面/技术面分析、多因子选股模型建立及量化交易策略回测。

## 核心技术栈
- 语言：Python 3.11+
- 数据获取：akshare, yfinance, baostock
- 数据处理：pandas, numpy
- 技术指标：ta-lib, pandas-ta
- 回测框架：backtrader

## 常用指令
- 环境依赖安装：`pip install -r requirements.txt`
- 运行策略回测：`python main.py --mode backtest --strategy <name>`
- 抓取最新财报：`python data/fetcher.py --type earnings --ticker <symbol>`
- 运行测试用例：`pytest tests/`

## 股票分析与代码规范约束

### 1. 数据与计算严谨性 (极其重要)
- **前瞻偏差防御**：在编写任何回测逻辑时，绝对禁止使用未来数据（Look-ahead bias）。所有指标计算必须严格基于 `T-1` 或更早的历史数据。
- **复权处理**：获取股价历史数据进行技术面分析时，默认必须使用**前复权（Pro-adjusted）**数据，避免因除权除息导致指标突变。
- **异常值处理**：数据清洗时必须处理 `NaN` 和 Inf 值，价格序列出现零或负数时须触发 Warning。

### 2. 投资分析框架
当你（Claude）帮我分析某只股票或编写研究报告时，请遵循以下三步框架：
- **基本面筛选**：优先检查 ROE > 15%、资产负债率 < 50%、近3年净利润复合增长率 > 10%。
- **技术面共振**：结合周线 MA20 趋势及日线 RSI/MACD 寻找买卖点，避免盲目左侧抄底。
- **风险提示**：在任何分析报告的末尾，必须列出该股的 3 个潜在核心风险（如行业周期、商誉过高、现金流恶化）。

### 3. 代码风格
- 所有的量化因子函数必须包含详细的 Docstring，注明输入的 DataFrame 格式要求。
- 交易信号输出必须包含：时间戳、股票名称、股票代码、信号类型（买入/卖出）、触发价格、当前仓位。

# 息策 Agent（MortgageAgent）

房贷提前还款分析服务：提供 REST API 计算节省利息，生成专业 PDF，并导出还款明细 Excel/ZIP；内置 LangChain 聊天示例帮助你用大模型给出还贷建议。

## 快速开始

```bash
python -m pip install -r requirements.txt
uvicorn mortgage_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

- 健康检查：`GET /health`
- Swagger：`http://127.0.0.1:8000/docs`

## 请求体（LoanRequest）

- `principal` 本金(元)，`annual_rate` 年利率(%)，`term_months` 期数（月），`method` `equal_payment`/`equal_principal`
- `paid_periods` 已还期数（或传 null 搭配 `first_payment_date` 计算）
- `prepay_amount` 本次提前还款金额(元)
- `invest_annual_rate` 可选：理财年化收益率(%)

## 接口

### 1) 计算节省利息

`POST /v1/mortgages/prepayment:calc`

- 响应：`savings_shorten_interest`（月供不变/缩短年限方案），`savings_reduce_payment_interest`（期限不变/降低月供方案）

### 2) 生成 PDF 报告

`POST /v1/mortgages/prepayment:report`

- 响应：PDF 下载流
- PDF 说明：首页核心摘要、两种方案对比、临界点提示、理财 vs 还贷建议
- 保存位置：若传 `output_dir` 则落盘到该目录，否则生成到系统临时目录

### 3) 导出 ZIP（含明细 Excel + 报告）

`POST /v1/mortgages/prepayment:export-zip`

- ZIP 内文件（中文名）：`原方案.xlsx`、`减少月供.xlsx`、`缩短年限.xlsx`、`报告.pdf`
- Excel 列：期数、月供、本金、利息、余额、利息占比（<50% 红色标记），Arial 10pt，隔行底色

curl 示例：

```bash
curl -X POST "http://127.0.0.1:8000/v1/mortgages/prepayment:export-zip" \
  -H "Content-Type: application/json" \
  -o repayment_schedules.zip \
  -d '{
    "principal": 1000000,
    "annual_rate": 3.5,
    "term_months": 360,
    "method": "equal_payment",
    "paid_periods": 24,
    "prepay_amount": 100000,
    "invest_annual_rate": 2.5
  }'
```
## 其他

- ZIP 中已包含 PDF，无需二次调用报告接口。
- PDF 字体：中文使用 STSong，数字/英文使用 Helvetica 混排，避免拥挤；金额/百分比统一混排保证“￥”正常显示。

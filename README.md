# 智能房贷代理

[![CI/CD](https://github.com/your-username/your-repo/actions/workflows/deploy.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/deploy.yml)
[![Codecov](https://codecov.io/gh/your-username/your-repo/branch/main/graph/badge.svg)](https://codecov.io/gh/your-username/your-repo)

**智能房贷代理**是一个基于 FastAPI 的房贷分析服务。它提供 REST API，用于计算提前还款能节省的利息，生成专业的 PDF 分析报告，并能导出包含还款明细的 Excel 文件。

## ✨ 功能特性

- **提前还款分析**：计算并对比“缩短年限”和“降低月供”两种方案下的利息节省情况。
- **专业 PDF 报告**：一键生成包含核心摘要、方案对比、理财 vs. 还贷建议的 PDF 报告。
- **Excel 明细导出**：导出包含原方案和新方案还款明细的 ZIP 包，组合贷导出自动按商贷/公积金动态列并区分配色（蓝色=商贷、绿色=公积金）。
- **安全与限流**：内置参数校验、行数/文件大小上限与基于 IP 的速率限制，支持可选 API Key 保护，抵御滥用请求。
- **RESTful API**：提供标准化的 API 接口，易于集成。
- **容器化部署**：通过 Docker 和 Docker Compose 实现快速、一致的部署。
- **自动化 CI/CD**：集成 GitHub Actions，实现代码提交后自动测试、构建和部署。

---

## 🚀 快速开始

### 1. 本地开发环境

**前置条件**:
- Python 3.10+

```bash
# 克隆仓库
git clone https://github.com/your-username/your-repo.git
cd your-repo

# 安装依赖
pip install -r requirements.txt

# 启动应用
uvicorn mortgage_agent.api:app --reload --host 0.0.0.0 --port 8000
```
现在，你可以在 `http://127.0.0.1:8000/docs` 访问 API 文档。

### 2. 本地 Docker 环境

**前置条件**:
- Docker
- Docker Compose

```bash
# 启动服务 (前台)
docker-compose up

# 启动服务 (后台)
docker-compose up -d
```
服务将在 `http://127.0.0.1` (通过 Nginx) 或 `http://127.0.0.1:8000` (直接访问 API) 上可用。

---

## 🤖 CI/CD 自动化流程

本项目使用 GitHub Actions 实现自动化，工作流定义在 `.github/workflows/deploy.yml`。

### 触发条件
- **Push 到 `main` 分支**: 触发完整的测试、构建和生产环境部署。
- **Push 到 `develop` 分支**: 触发测试和 Docker 镜像构建，但不部署。
- **创建 Pull Request 到 `main`**: 触发测试。

### 主要阶段

1.  **`test`**:
    - 在 Python 3.10 和 3.11 上运行代码质量检查 (Flake8, Black, isort)。
    - 执行单元测试并生成代码覆盖率报告。
    - 上传覆盖率报告到 Codecov。

2.  **`build`**:
    - 登录到 Docker Hub。
    - 构建 Docker 镜像并根据 Git 提交的 SHA 生成版本标签。
    - 将镜像推送到 Docker Hub。

3.  **`deploy`**:
    - **仅在 `main` 分支或创建 Release 时触发**。
    - 通过 SSH 连接到生产服务器。
    - 拉取最新的代码和 Docker 镜像。
    - 使用 `docker-compose` 重启服务以应用更新。
    - 验证部署是否成功。

---

## 🛠️ 部署指南

### 1. 服务器初始化

在你的服务器上（推荐 Ubuntu 20.04+），执行 `scripts/server-init.sh` 脚本来准备部署环境。

```bash
# 1. 复制脚本到服务器
scp scripts/server-init.sh your-user@your-server:/tmp/

# 2. SSH 连接并执行
ssh your-user@your-server
sudo bash /tmp/server-init.sh
```
该脚本会：
- 安装 Docker 和 Docker Compose。
- 创建一个名为 `deploy` 的部署用户（推荐）。
- 设置防火墙规则。
- 克隆项目仓库到 `/home/deploy/mortgage-agent`。

### 2. 配置 GitHub Secrets

为了让 GitHub Actions 能够自动部署，你需要在你的 GitHub 仓库中配置以下 `Secrets`：

- `DOCKER_USERNAME`: 你的 Docker Hub 用户名。
- `DOCKER_PASSWORD`: 你的 Docker Hub 密码或访问令牌。
- `SERVER_HOST`: 你服务器的 IP 地址或域名。
- `SERVER_USER`: 用于部署的用户名 (例如 `deploy`)。
- `SERVER_PRIVATE_KEY`: 用于 SSH 连接的私钥。
- `SERVER_PORT`: SSH 端口 (默认为 `22`)。

### 3. 配置文件

在服务器上，你需要创建一个 `.env` 文件来存储环境变量。

```bash
# 以 deploy 用户登录
su - deploy
cd ~/mortgage-agent

# 从模板创建配置文件
cp .env.example .env

# 编辑配置文件
nano .env
```
根据你的需求修改 `.env` 文件，例如数据库连接、日志级别等。

### 4. 触发首次部署

当你将代码推送到 `main` 分支时，CI/CD 流程将自动开始。

```bash
git push origin main
```
你可以在 GitHub 仓库的 "Actions" 标签页中查看部署进度。

---

## 📂 API 接口说明

### 验证与限流
- 请求参数：本金 ≤ `MAX_PRINCIPAL`（默认 3000 万），年利率 ≤ `MAX_ANNUAL_RATE`（默认 30%），期限 ≤ `MAX_TERM_MONTHS`（默认 600 期），提前还款额 ≤ 本金×`MAX_PREPAY_RATIO`（默认 1.0）。
- 组合贷：`fund_principal` 与 `commercial_principal` 不能同时为 0，任一为 0 则不生成对应贷款列。
- 导出保护：单份计划最大行数 `MAX_SCHEDULE_ROWS`（默认 2000），导出 ZIP 体积 `MAX_EXPORT_BYTES`（默认 6 MiB）超限返回 `413`。
- 速率限制：普通接口默认 `RATE_LIMIT_DEFAULT`（默认 60/min），导出接口 `RATE_LIMIT_EXPORT`（默认 15/min）；超限返回 `429`。限流会优先读取 `X-Forwarded-For` / `X-Real-IP` 头（由反向代理写入），缺省回退到远端地址。
- API Key（可选）：设置环境变量 `API_KEY` 后，所有 `/v1/*` 路由需携带请求头 `X-API-Key: <值>`，否则返回 `401`。未设置时保持公开访问。
- 防护提示：部署时请确保 Nginx/反向代理正确写入真实 IP 头；如使用多层代理请按需调整可信头顺序。

### 请求体 (`LoanRequest`)
- `principal`: 贷款本金 (元)
- `annual_rate`: 年利率 (%)
- `term_months`: 贷款总期数 (月)
- `method`: 还款方式 (`equal_payment` 或 `equal_principal`)
- `paid_periods`: 已还期数
- `prepay_amount`: 本次提前还款金额 (元)
- `invest_annual_rate`: (可选) 你的投资理财年化收益率 (%)

### 主要接口

- `POST /v1/mortgages/prepayment:calc`:
  **功能**: 计算提前还款可节省的利息。
  **响应**: JSON，包含 `savings_shorten_interest` 与 `savings_reduce_payment_interest`。

- `POST /v1/mortgages/prepayment:export-zip`:
  **功能**: 导出包含 PDF 报告和 Excel 还款明细的 ZIP 包。
  **响应**: ZIP 文件流，响应头携带 `X-Savings-Reduce` 和 `X-Savings-Shorten`，便于前端直接展示节省金额。

- `POST /v1/mortgages/combined:export-xlsx`:
  **功能**: 组合贷（公积金+商贷）计算并导出 Excel（ZIP 打包），响应头 `X-Total-Interest` 返回总利息。
  **请求体**: `fund_principal`, `fund_annual_rate`, `commercial_principal`, `commercial_annual_rate`, `term_months`, `method`；当 `fund_principal` 或 `commercial_principal` 为 0 时，对应贷款列将被自动隐藏。
  **响应**: ZIP 文件流，内含 `房贷月供明细.xlsx`，列顺序为 “期数 / 月供总额 /（商贷列）/（公积金列）/ 利息总占比”；商贷与公积金列使用不同配色。

**cURL 示例:**
```bash
curl -X POST "http://127.0.0.1:8000/v1/mortgages/prepayment:export-zip" \
  -H "Content-Type: application/json" \
  -D headers.txt \
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
生成的 `headers.txt` 中会包含节省金额的响应头，ZIP 内含 3 份 Excel 与 1 份 PDF 报告。

**cURL 示例（组合贷导出）:**
```bash
curl -X POST "http://127.0.0.1:8000/v1/mortgages/combined:export-xlsx" \
  -H "Content-Type: application/json" \
  -D headers_combined.txt \
  -o combined_mortgage.zip \
  -d '{
    "fund_principal": 600000,
    "fund_annual_rate": 3.1,
    "commercial_principal": 400000,
    "commercial_annual_rate": 4.2,
    "term_months": 360,
    "method": "equal_payment"
  }'
```
`headers_combined.txt` 会包含 `X-Total-Interest`，下载的 ZIP 内含 `房贷月供明细.xlsx`，仅在有对应贷款时展示商贷/公积金列，并用不同底色区分。

**cURL 示例 (开启 API Key)**
```bash
curl -X POST "http://127.0.0.1:8000/v1/mortgages/prepayment:calc" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "principal": 1000000,
    "annual_rate": 3.5,
    "term_months": 360,
    "method": "equal_payment",
    "prepay_amount": 100000
  }'
```


## 📄 License

This project is licensed under the MIT License.

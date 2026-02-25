# 智能房贷代理

[![CI/CD](https://github.com/your-username/your-repo/actions/workflows/deploy.yml/badge.svg)](https://github.com/your-username/your-repo/actions/workflows/deploy.yml)
[![Codecov](https://codecov.io/gh/your-username/your-repo/branch/main/graph/badge.svg)](https://codecov.io/gh/your-username/your-repo)

**智能房贷代理**是一个基于 FastAPI 的房贷分析服务。它提供 REST API，用于计算提前还款能节省的利息，生成专业的 PDF 分析报告，并能导出包含还款明细的 Excel 文件。

## ✨ 功能特性

- **提前还款分析**：计算并对比“缩短年限”和“降低月供”两种方案下的利息节省情况。
- **专业 PDF 报告**：一键生成包含核心摘要、方案对比、理财 vs. 还贷建议的 PDF 报告。
- **Excel 明细导出**：导出包含原方案和新方案还款明细的 ZIP 包，方便用户进行详细分析。
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
  **响应**: 返回两种方案（缩短年限/降低月供）的节省金额。

- `POST /v1/mortgages/prepayment:report`:
  **功能**: 生成详细的 PDF 分析报告。
  **响应**: PDF 文件流。

- `POST /v1/mortgages/prepayment:export-zip`:
  **功能**: 导出包含 PDF 报告和 Excel 还款明细的 ZIP 包。
  **响应**: ZIP 文件流。

**cURL 示例:**
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

---

## 📄 License

This project is licensed under the MIT License.

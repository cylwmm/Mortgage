# CI/CD 配置文件总结

这个文档介绍了所有新增的 CI/CD 配置文件及其具体用途。

---

## 📦 新增文件清单

### 1. **工作流和自动化**

#### `.github/workflows/deploy.yml` 📋
**作用**：GitHub Actions 工作流定义，自动化 CI/CD 流程

**包含的阶段**：
```
test job (代码检查和单元测试)
  ├─ 安装依赖
  ├─ 格式检查 (Black)
  ├─ Import 排序检查 (isort)
  ├─ 代码质量检查 (Flake8)
  ├─ 单元测试和覆盖率
  └─ 上传测试报告

build job (Docker 镜像构建)
  ├─ 设置 Docker Buildx
  ├─ 登录 Docker Hub
  ├─ 提取版本信息
  └─ 构建并推送镜像

deploy job (远程服务器部署)
  ├─ 配置 SSH
  ├─ 拉取最新代码
  ├─ 停止旧容器
  ├─ 启动新容器
  ├─ 健康检查
  └─ 通知结果
```

**触发条件**：
- `git push origin main` - 生产环境部署
- `git push origin develop` - 构建镜像（不部署）
- Pull Request - 仅运行测试

**说明**：每行代码都有详细注释，解释其功能

---

### 2. **容器化配置**

#### `Dockerfile` 🐳
**作用**：定义应用的 Docker 镜像

**关键特性**：
```
多阶段构建（减小镜像大小）
├─ 构建阶段 (Builder)
│  ├─ Python 3.11-slim 基础镜像
│  ├─ 安装编译工具
│  └─ 安装 Python 依赖到 /root/.local
│
└─ 运行阶段 (Runtime)
   ├─ Python 3.11-slim 基础镜像
   ├─ 安装中文字体（PDF 生成）
   ├─ 复制依赖
   ├─ 创建非 root 用户（安全）
   ├─ 健康检查配置
   └─ 启动命令
```

**优点**：
- 最终镜像大小：~300MB（对比全阶段 ~800MB）
- 非 root 用户运行（提高安全性）
- 自动健康检查

#### `docker-compose.yml` 🔗
**作用**：容器编排和服务组合

**包含的服务**：
```
mortgage-api (FastAPI 应用)
├─ 镜像：docker.io/username/mortgage-agent:latest
├─ 端口：127.0.0.1:8000（仅本地访问）
├─ 环境变量：LOG_LEVEL, PYTHONUNBUFFERED
├─ 挂载卷：output/, logs/
├─ 健康检查：每 30 秒检查一次
└─ 资源限制：1 CPU, 512MB 内存

nginx (反向代理)
├─ 镜像：nginx:1.25-alpine
├─ 端口：80, 443
├─ 配置文件：./nginx.conf
├─ 挂载卷：ssl/, logs/nginx/
└─ 依赖：mortgage-api
```

**网络隔离**：
- 内部网络 `mortgage-network`
- 只有 Nginx 暴露到外部
- API 仅限本地 127.0.0.1 访问
- Nginx → API 通过 Docker 网络通信

---

### 3. **Nginx 配置**

#### `nginx.conf` ⚙️
**作用**：反向代理、HTTPS 终止、缓存和安全配置

**关键配置**：

```nginx
# 上游定义
upstream mortgage_backend {
    server mortgage-api:8000;  # Docker 网络内容器名
}

# HTTP 重定向到 HTTPS
server {
    listen 80;
    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS 服务器（主要）
server {
    listen 443 ssl http2;
    
    # SSL 证书（占位符）
    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    
    # 代理路由
    location /v1/ {
        proxy_pass http://mortgage_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 长时间超时（PDF 生成可能耗时）
        proxy_connect_timeout 30s;
        proxy_read_timeout 60s;
    }
    
    # 安全响应头
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-XSS-Protection "1; mode=block" always;
}
```

**安全特性**：
- HSTS：强制 HTTPS
- X-Content-Type-Options：防止 MIME 嗅探
- X-Frame-Options：防止 Clickjacking
- X-XSS-Protection：防止 XSS 攻击

---

### 4. **环境配置**

#### `.env.example` 🔐
**作用**：环境变量模板（范本），不会提交到 Git

**包含的配置项**：
```
# 应用配置
LOG_LEVEL=info
ENVIRONMENT=production

# Docker 配置
DOCKER_USERNAME=your_docker_username
DOCKER_PASSWORD=your_docker_password

# 服务器配置（用于 CI/CD）
SERVER_USER=deploy
SERVER_HOST=your.server.com
SERVER_PORT=22
SERVER_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----

# 应用运行
API_HOST=0.0.0.0
API_PORT=8000
OUTPUT_DIR=/app/output

# Nginx 配置
SERVER_DOMAIN=mortgage.example.com
SSL_CERT_PATH=/etc/nginx/ssl/cert.pem
SSL_KEY_PATH=/etc/nginx/ssl/key.pem
```

**使用方式**：
```bash
cp .env.example .env
# 编辑 .env 文件，设置实际值
# 不要提交 .env 到 Git（已在 .gitignore）
```

#### `.gitignore` 🚫
**作用**：Git 忽略规则，防止敏感文件提交

**包含的规则**：
```
__pycache__/         # Python 缓存
*.py[cod]           # 编译文件
.pytest_cache/      # 测试缓存
.coverage           # 覆盖率数据
.env                # 环境变量（敏感信息）
.env.local          # 本地覆盖
output/             # 输出文件
logs/               # 日志文件
ssl/*.pem           # SSL 证书
ssl/*.key           # SSL 密钥
```

---

### 5. **部署脚本**

#### `scripts/deploy.sh` 🚀
**作用**：手动部署脚本（GitHub Actions 的备选方案）

**主要功能**：
```bash
1. 依赖检查 (Docker, Git, SSH)
2. 配置验证 (SERVER_USER, SERVER_HOST)
3. 镜像构建 (docker build)
4. 镜像推送 (docker push)
5. 远程部署 (SSH 连接)
   ├─ 创建备份
   ├─ 拉取代码
   ├─ 停止旧容器
   ├─ 启动新容器
   └─ 健康检查
6. 部署验证 (curl /health)
```

**使用方式**：
```bash
bash scripts/deploy.sh production      # 部署到生产环境
bash scripts/deploy.sh staging         # 部署到测试环境
```

**环境支持**：
- `production` - main 分支
- `staging` - develop 分支
- `develop` - feature 分支

#### `scripts/server-init.sh` 🔧
**作用**：一键初始化服务器部署环境

**完成的任务**：
```
1. 系统更新 (apt-get update/upgrade)
2. 基础工具安装 (curl, git, vim, htop...)
3. Docker 安装
4. Docker Compose 安装
5. 防火墙配置 (UFW)
   ├─ 允许 SSH (22)
   ├─ 允许 HTTP (80)
   ├─ 允许 HTTPS (443)
   └─ SSH 连接限制
6. Fail2Ban 配置（防暴力破解）
7. 部署用户创建 (deploy)
8. 应用目录创建
9. Systemd 服务配置（可选）
10. 自签名证书生成（开发用）
11. 系统性能优化
```

**使用方式**：
```bash
# 在本地复制脚本到服务器
scp scripts/server-init.sh root@your-server:/tmp/

# 在服务器上运行（需要 root）
ssh root@your-server
sudo bash /tmp/server-init.sh
```

**脚本安全**：
- 使用 `set -e` 防止错误继续执行
- 检查系统依赖
- 创建非 root 部署用户
- 配置防火墙和 Fail2Ban
- 详细的日志输出

#### `scripts/local-test.sh` 🧪
**作用**：本地测试 Docker 镜像和容器

**测试项目**：
```
1. Docker 环境检查
2. 本地镜像构建
3. 容器启动
4. 服务启动等待
5. 功能测试
   ├─ 健康检查 (/health)
   ├─ Swagger 文档 (/docs)
   ├─ API 请求测试 (/v1/mortgages/prepayment:calc)
   └─ Nginx 代理测试 (Nginx → API)
6. 日志查看
7. 清理测试环境
```

**使用方式**：
```bash
bash scripts/local-test.sh

# 测试完成后容器继续运行，可以：
# 访问 http://localhost:8000/docs
# 访问 http://localhost/health

# 停止容器
docker-compose -f docker-compose.test.yml down
```

#### `scripts/setup-github-secrets.sh` 🔐
**作用**：一键配置 GitHub Actions Secrets

**功能**：
```
1. GitHub CLI 检查
2. 登录状态验证
3. 交互式输入配置信息
   ├─ Docker Hub 用户名
   ├─ Docker Hub 密码/Token
   ├─ 服务器地址
   ├─ SSH 端口
   └─ 用户名
4. SSH 密钥检查
5. 自动创建 GitHub Secrets
6. SSH 连接测试
```

**使用方式**：
```bash
# 方式 1：交互式配置
bash scripts/setup-github-secrets.sh

# 方式 2：命令行参数
bash scripts/setup-github-secrets.sh \
  --username your_docker_username \
  --password your_docker_password \
  --server-host 123.45.67.89 \
  --server-user deploy

# 前置条件：
# 1. 安装 GitHub CLI: brew install gh
# 2. 登录 GitHub: gh auth login
```

---

### 6. **文档**

#### `CICD_GUIDE.md` 📖
**作用**：完整的 CI/CD 部署指南

**内容**：
- 快速开始步骤
- 文件说明
- 工作流程图
- SSL/TLS 证书配置
- 监控和日志查看
- 故障排查
- 性能优化建议
- 更新和回滚说明
- 最佳实践

**长度**：450+ 行，包含详细示例

#### `QUICKSTART.md` 🚀
**作用**：快速参考和一步一步配置清单

**内容**：
- 7 步完整配置流程
- GitHub Secrets 详细说明
- 日常操作命令
- 常见问题解答
- 工作流程图
- 项目结构说明

**长度**：300+ 行，面向快速上手

---

## 🔄 文件关系图

```
提交代码
  │
  ├─→ .github/workflows/deploy.yml
  │   ├─→ 运行测试 (需要 requirements.txt)
  │   ├─→ 构建镜像 (需要 Dockerfile)
  │   └─→ 远程部署 (需要 .env, docker-compose.yml, nginx.conf)
  │
  ├─→ Dockerfile
  │   └─→ 构建容器镜像
  │
  ├─→ docker-compose.yml
  │   ├─→ 定义容器编排
  │   ├─→ 引用 nginx.conf
  │   └─→ 读取 .env 环境变量
  │
  ├─→ nginx.conf
  │   └─→ 代理配置
  │
  ├─→ scripts/
  │   ├─→ deploy.sh (手动部署)
  │   ├─→ server-init.sh (服务器初始化)
  │   ├─→ local-test.sh (本地测试)
  │   └─→ setup-github-secrets.sh (GitHub 配置)
  │
  └─→ 文档
      ├─→ CICD_GUIDE.md (详细指南)
      └─→ QUICKSTART.md (快速开始)
```

---

## 🎯 文件执行顺序

### 初次部署

```
1️⃣ 服务器初始化
   └─ bash scripts/server-init.sh
      (一次性，配置服务器环境)

2️⃣ 本地测试
   └─ bash scripts/local-test.sh
      (验证 Docker 镜像和容器)

3️⃣ GitHub Secrets 配置
   └─ bash scripts/setup-github-secrets.sh
      (或手动在 GitHub 网页配置)

4️⃣ 推送代码触发自动部署
   └─ git push origin main
      (触发 .github/workflows/deploy.yml)
```

### 后续更新

```
1️⃣ 修改代码
   └─ nano mortgage_agent/api.py

2️⃣ 提交并推送
   └─ git push origin main
      (自动触发 deploy.yml)

3️⃣ 查看部署进度
   └─ GitHub → Actions 标签页
```

---

## 💾 文件大小和性能

| 文件 | 大小 | 作用 |
|-----|------|------|
| `.github/workflows/deploy.yml` | ~6 KB | 自动化流程 |
| `Dockerfile` | ~1 KB | 容器定义 |
| `docker-compose.yml` | ~2 KB | 容器编排 |
| `nginx.conf` | ~3 KB | 反向代理 |
| `.env.example` | ~1 KB | 配置模板 |
| `scripts/deploy.sh` | ~8 KB | 部署脚本 |
| `scripts/server-init.sh` | ~12 KB | 初始化脚本 |
| `scripts/local-test.sh` | ~7 KB | 测试脚本 |
| `scripts/setup-github-secrets.sh` | ~6 KB | Secrets 配置 |
| `CICD_GUIDE.md` | ~15 KB | 详细文档 |
| `QUICKSTART.md` | ~8 KB | 快速指南 |

**总计**：~63 KB（文本文件，极小）

---

## 🔐 敏感信息处理

| 信息 | 存储位置 | 安全措施 |
|-----|--------|--------|
| `.env` 文件 | `.gitignore` | 不提交 Git |
| Docker 凭证 | GitHub Secrets | 加密存储 |
| SSH 私钥 | GitHub Secrets | 加密存储 |
| SSL 证书 | `ssl/` 目录 | `.gitignore` |
| 服务器密码 | 不使用密码 | SSH 密钥认证 |

---

## ✅ 验证清单

- [ ] 所有文件已创建
- [ ] 文件权限正确（`chmod +x scripts/*.sh`）
- [ ] Git 配置已更新（`.gitignore`）
- [ ] 本地测试通过（`bash scripts/local-test.sh`）
- [ ] GitHub Secrets 已配置
- [ ] 服务器已初始化
- [ ] 首次部署成功
- [ ] 应用可访问

---

**下一步**：阅读 `QUICKSTART.md` 快速开始！ 🚀


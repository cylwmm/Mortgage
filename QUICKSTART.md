# 快速参考 - CI/CD 配置清单

## 🎯 一步一步配置

### ✅ 第 1 步：准备服务器

- [ ] 确保有一台 Linux 服务器（Ubuntu 20.04+ 推荐）
- [ ] 记下服务器 IP 地址
- [ ] 确保有 root 或 sudo 权限

### ✅ 第 2 步：初始化服务器

```bash
# 在本地运行（复制文件）
scp scripts/server-init.sh root@your-server:/tmp/

# 在服务器上运行（需要 root）
ssh root@your-server
bash /tmp/server-init.sh
# 脚本自动完成所有配置
```

**脚本完成后的确认：**
- [ ] Docker 已安装：`docker --version`
- [ ] deploy 用户已创建
- [ ] 应用目录存在：`/home/deploy/mortgage-agent`

### ✅ 第 3 步：配置 GitHub Secrets

在 GitHub 仓库：`Settings` → `Secrets and variables` → `Actions` → `New repository secret`

**需要添加的 Secrets：**

| 名称 | 值 | 获取方式 |
|-----|-----|--------|
| `DOCKER_USERNAME` | 你的 Docker Hub 用户名 | https://hub.docker.com/settings/general |
| `DOCKER_PASSWORD` | Docker Hub Personal Access Token | https://hub.docker.com/settings/security → New Access Token |
| `SERVER_USER` | `deploy` | （固定值） |
| `SERVER_HOST` | 你的服务器 IP 或域名 | 例：`123.45.67.89` |
| `SERVER_PORT` | `22` | （固定值） |
| `SERVER_PRIVATE_KEY` | SSH 私钥内容 | `cat ~/.ssh/id_rsa` |

**详细步骤：**

```bash
# 1. 生成 SSH 密钥对（如果没有）
ssh-keygen -t rsa -f ~/.ssh/id_rsa -N ""

# 2. 复制私钥内容（粘贴到 SERVER_PRIVATE_KEY secret）
cat ~/.ssh/id_rsa
# 输出示例：
# -----BEGIN RSA PRIVATE KEY-----
# MIIEowIBAAKCAQEA1234567890...
# ...
# -----END RSA PRIVATE KEY-----

# 3. 添加公钥到服务器
ssh-copy-id -i ~/.ssh/id_rsa.pub deploy@your-server

# 4. 验证连接
ssh -i ~/.ssh/id_rsa deploy@your-server "docker --version"
```

### ✅ 第 4 步：配置应用环境

```bash
# 1. SSH 连接到服务器
ssh deploy@your-server

# 2. 进入应用目录
cd ~/mortgage-agent

# 3. 复制环境变量模板
cp .env.example .env

# 4. 编辑 .env 文件
nano .env

# 需要修改的关键配置：
# - DOCKER_USERNAME = 你的 Docker Hub 用户名
# - SERVER_DOMAIN = 你的服务器域名（例：mortgage.example.com）
# - LOG_LEVEL = info（生产环境）或 debug（开发）
```

### ✅ 第 5 步：配置 SSL 证书

**开发环境（已自动生成）：**
```bash
# 证书已生成在：~/mortgage-agent/ssl/
# 浏览器访问时会显示不安全警告（正常）
```

**生产环境（Let's Encrypt）：**
```bash
ssh deploy@your-server
sudo apt-get install certbot python3-certbot-nginx

# 申请证书
sudo certbot certonly --standalone -d your-domain.com

# 复制证书
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem \
  ~/mortgage-agent/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem \
  ~/mortgage-agent/ssl/key.pem

# 修改权限
sudo chown deploy:deploy ~/mortgage-agent/ssl/*

# 重启容器
cd ~/mortgage-agent
docker-compose restart nginx
```

### ✅ 第 6 步：推送代码触发部署

```bash
# 本地运行
git add .
git commit -m "chore: add CI/CD configuration"
git push origin main

# 查看部署进度
# GitHub 网页 → Actions 标签页
# 等待所有检查完成（绿色对勾）
```

### ✅ 第 7 步：验证部署

```bash
# 方法 1：访问 API
curl https://your-domain.com/health

# 方法 2：访问 Swagger 文档
# 打开浏览器访问：https://your-domain.com/docs

# 方法 3：查看容器状态
ssh deploy@your-server
cd ~/mortgage-agent
docker-compose ps
docker-compose logs -f

# 预期输出：
# mortgage-api   Up    127.0.0.1:8000->8000/tcp
# mortgage-nginx Up    0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
```

---

## 📋 项目结构说明

```
mortgage-agent/
├── .github/workflows/
│   └── deploy.yml              # ← GitHub Actions 工作流
├── scripts/
│   ├── deploy.sh              # ← 手动部署脚本
│   └── server-init.sh         # ← 服务器初始化脚本
├── mortgage_agent/
│   ├── api.py                 # ← FastAPI 应用
│   ├── calculator.py
│   ├── report.py
│   └── __init__.py
├── Dockerfile                 # ← Docker 镜像定义
├── docker-compose.yml         # ← 容器编排配置
├── nginx.conf                 # ← Nginx 配置
├── .env.example               # ← 环境变量模板
├── .gitignore                 # ← Git 忽略规则
├── requirements.txt           # ← Python 依赖
├── CICD_GUIDE.md              # ← 完整部署指南
├── QUICKSTART.md              # ← 本文件
└── README.md                  # ← 项目说明
```

---

## 🔄 日常操作

### 部署新版本

```bash
# 1. 修改代码
nano mortgage_agent/api.py

# 2. 提交并推送
git add .
git commit -m "feat: add new feature"
git push origin main

# 3. GitHub Actions 自动部署（1-5 分钟）
# 观看进度：GitHub 网页 → Actions 标签页
```

### 查看服务日志

```bash
ssh deploy@your-server
cd ~/mortgage-agent

# API 日志
docker-compose logs -f mortgage-api

# Nginx 日志
docker-compose logs -f nginx

# 容器状态
docker-compose ps
```

### 获取输出文件

```bash
# 获取 PDF 报告
scp deploy@your-server:~/mortgage-agent/output/*.pdf ./

# 获取所有输出
scp -r deploy@your-server:~/mortgage-agent/output/ ./
```

### 重启服务

```bash
ssh deploy@your-server
cd ~/mortgage-agent

# 重启所有容器
docker-compose restart

# 或重启特定服务
docker-compose restart mortgage-api
```

### 回滚到上一版本

```bash
ssh deploy@your-server
cd ~/mortgage-agent

# 查看备份
ls -la backups/

# 恢复备份
cp backups/docker-compose.yml.20240101_120000 docker-compose.yml

# 重启容器
docker-compose down
docker-compose up -d
```

---

## 🐛 常见问题

### Q: 部署失败，提示 "连接被拒绝"

**A:** SSH 密钥配置有问题
```bash
# 验证本地连接
ssh -i ~/.ssh/id_rsa deploy@your-server

# 检查 GitHub Secrets 中的 SERVER_PRIVATE_KEY 是否正确复制
# （包括 -----BEGIN RSA PRIVATE KEY----- 和 -----END RSA PRIVATE KEY-----）
```

### Q: Docker 镜像推送失败

**A:** Docker Hub 凭证过期
```bash
# 生成新的 Personal Access Token
# https://hub.docker.com/settings/security

# 更新 GitHub Secrets 中的 DOCKER_PASSWORD
```

### Q: 访问 HTTPS 时显示 "不安全"

**A:** 这是正常的（开发环境使用自签名证书）
- 生产环境请配置 Let's Encrypt 证书（见第 5 步）
- 浏览器点击"高级"→"继续访问"可临时访问

### Q: 服务无法访问（404）

**A:** 检查 Nginx 配置
```bash
ssh deploy@your-server
cd ~/mortgage-agent

# 检查 Nginx 日志
docker-compose logs nginx | grep error

# 验证后端服务是否运行
docker-compose ps

# 测试后端直接访问（仅限服务器）
curl http://localhost:8000/health
```

### Q: 磁盘空间不足

**A:** 清理 Docker 资源
```bash
# 查看磁盘使用
df -h

# 查看 Docker 镜像大小
docker images

# 清理未使用的容器和镜像
docker system prune -a --volumes
```

---

## 🎓 工作流程图

```
┌──────────────┐
│   Git Push   │ (git push origin main)
└──────┬───────┘
       │
       ↓
┌─────────────────────────────┐
│   GitHub Actions (测试阶段)   │
│ - 代码格式检查 (Black, isort) │
│ - 代码质量检查 (Flake8)       │
│ - 单元测试                   │
└──────┬──────────────────────┘
       │ (✓ 通过)
       ↓
┌──────────────────────────────┐
│  Docker 镜像构建和推送         │
│ - 多阶段构建（减小镜像大小）    │
│ - 推送到 Docker Hub          │
└──────┬───────────────────────┘
       │
       ↓
┌────────────────────────────────┐
│  SSH 连接服务器部署            │
│ - 拉取最新代码                 │
│ - 停止旧容器                   │
│ - 启动新容器                   │
│ - 健康检查                     │
└──────┬─────────────────────────┘
       │
       ↓
┌──────────────────┐
│  部署完成 ✓      │
│ 应用已上线        │
└──────────────────┘
```

---

## 📞 需要帮助？

1. **查看详细日志**：GitHub Actions 中点击失败的工作流
2. **查看服务器日志**：`docker-compose logs`
3. **检查系统状态**：`docker stats`, `free -h`, `df -h`
4. **查看完整指南**：阅读 `CICD_GUIDE.md`

---

**祝部署顺利！** 🚀


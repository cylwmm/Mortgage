# CI/CD 部署文档

## 📋 概述

本文档介绍如何使用 GitHub Actions + Docker 实现自动化 CI/CD，将应用部署到你的服务器。

### 核心特性

- ✅ **自动化测试** - 每次提交自动运行单元测试
- ✅ **代码质量检查** - 使用 Black, isort, Flake8 检查代码规范
- ✅ **Docker 容器化** - 多阶段构建，镜像精简
- ✅ **自动部署** - 推送到 main 分支自动部署到生产环境
- ✅ **Nginx 反向代理** - HTTPS 支持、负载均衡、缓存加速
- ✅ **零停机部署** - Docker Compose 滚动更新
- ✅ **日志管理** - 结构化日志、容器日志卷挂载

---

## 🚀 快速开始

### 第一步：初始化服务器

在你的服务器上运行初始化脚本（需要 root 权限）：

```bash
# 方法 1：本地复制脚本到服务器
scp scripts/server-init.sh deploy@your-server:/tmp/
ssh deploy@your-server "sudo bash /tmp/server-init.sh"

# 方法 2：直接从网络运行（如果脚本托管在网上）
ssh deploy@your-server "curl -sSL https://your-repo-raw-url/scripts/server-init.sh | sudo bash"
```

**脚本做了什么？**
- 更新系统包
- 安装 Docker 和 Docker Compose
- 配置防火墙（开放 22, 80, 443 端口）
- 创建 `deploy` 用户
- 设置 Fail2Ban 防暴力破解
- 创建应用目录结构
- 生成自签名证书（开发用）

### 第二步：配置 GitHub Secrets

在 GitHub 仓库页面：`Settings` → `Secrets and variables` → `Actions`

添加以下 Secrets：

| Secret 名称 | 说明 | 示例 |
|-----------|------|------|
| `DOCKER_USERNAME` | Docker Hub 用户名 | `your_dockerhub_username` |
| `DOCKER_PASSWORD` | Docker Hub 密码或 Token | `dckr_pat_xxx` |
| `SERVER_USER` | 服务器用户名 | `deploy` |
| `SERVER_HOST` | 服务器 IP 或域名 | `123.45.67.89` |
| `SERVER_PORT` | SSH 端口 | `22` |
| `SERVER_PRIVATE_KEY` | SSH 私钥内容 | 见下面的说明 |

**生成 SSH 密钥对（如果没有）：**

在本地运行：
```bash
# 生成密钥对（一直回车使用默认值）
ssh-keygen -t rsa -f ~/.ssh/id_rsa -N ""

# 打印私钥内容（复制到 SERVER_PRIVATE_KEY secret）
cat ~/.ssh/id_rsa

# 添加公钥到服务器授权列表
ssh-copy-id -i ~/.ssh/id_rsa.pub deploy@your-server
```

### 第三步：配置应用环境

连接到服务器配置应用环境变量：

```bash
ssh deploy@your-server
cd ~/mortgage-agent

# 复制示例配置
cp .env.example .env

# 编辑 .env 文件
nano .env
# 根据实际需要修改配置项
```

### 第四步：推送代码触发部署

```bash
# 推送到 main 分支自动触发部署
git push origin main
```

在 GitHub Actions 查看部署进度：`Actions` 标签页

---

## 📁 文件说明

### `.github/workflows/deploy.yml`
GitHub Actions 工作流配置，定义 CI/CD 流程：
- **test job**: 代码检查和单元测试
- **build job**: Docker 镜像构建和推送
- **deploy job**: 服务器部署和验证

### `Dockerfile`
Docker 镜像定义，使用多阶段构建：
```
构建阶段          运行阶段
(Builder)    →    (Runtime)
- Python 3.11
- 编译依赖          - Python 3.11
- pip install       - 运行时依赖
                     - 非 root 用户
                     - 健康检查
```

### `docker-compose.yml`
容器编排配置：
- **mortgage-api** 服务：FastAPI 应用
- **nginx** 服务：反向代理和 HTTPS 终止
- 挂载卷：输出目录、日志目录
- 网络隔离：内部通信通过 Docker 网络
- 资源限制：CPU、内存限制防止过载

### `nginx.conf`
Nginx 反向代理配置：
- HTTP → HTTPS 重定向
- SSL/TLS 证书配置（占位符）
- 代理到后端 FastAPI 应用
- 压缩、缓存、安全头配置
- API 路由匹配

### `.env.example`
环境变量模板，需复制为 `.env` 并根据实际情况修改：
- 应用日志级别
- 环境标识（development/staging/production）
- Docker 仓库凭证
- 服务器连接信息
- SSL 证书路径

### `scripts/deploy.sh`
手动部署脚本（备选方案），如果不使用 GitHub Actions 可手动运行：
```bash
bash scripts/deploy.sh production
```

### `scripts/server-init.sh`
服务器初始化脚本，自动配置部署环境

---

## 🔄 工作流程

```
┌─────────────┐
│  Git Push   │
│  to main    │
└──────┬──────┘
       ↓
┌──────────────────────┐
│ GitHub Actions       │
│ 1. Test & Lint       │──→ 失败则停止
│ 2. Build Docker img  │
│ 3. Push to registry  │
└──────┬───────────────┘
       ↓ (success)
┌──────────────────────────┐
│ SSH to Server            │
│ 1. Pull latest code      │
│ 2. Stop old containers   │
│ 3. Pull new Docker img   │
│ 4. Start containers      │
│ 5. Health check          │
└──────┬───────────────────┘
       ↓ (success)
┌──────────────────┐
│  Deployment OK   │
│ App is running   │
└──────────────────┘
```

---

## 🔐 SSL/TLS 证书配置

### 开发环境（自签名证书）

脚本已自动生成，位于：
```
~/mortgage-agent/ssl/cert.pem
~/mortgage-agent/ssl/key.pem
```

**浏览器访问时会出现不安全警告（正常）**

### 生产环境（Let's Encrypt）

在服务器上运行：

```bash
# 安装 certbot
sudo apt-get install certbot python3-certbot-nginx

# 申请证书
sudo certbot certonly --standalone \
  -d your-domain.com \
  -d www.your-domain.com

# 复制证书到应用目录
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem \
  ~/mortgage-agent/ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem \
  ~/mortgage-agent/ssl/key.pem

# 修改权限
sudo chown deploy:deploy ~/mortgage-agent/ssl/*.pem

# 重启容器生效
cd ~/mortgage-agent
docker-compose restart nginx
```

**自动续期**：Let's Encrypt 证书有效期 90 天，设置 cron 任务自动续期：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每月 1 号自动续期）
0 0 1 * * certbot renew --quiet && cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ~/mortgage-agent/ssl/cert.pem && cp /etc/letsencrypt/live/your-domain.com/privkey.pem ~/mortgage-agent/ssl/key.pem && cd ~/mortgage-agent && docker-compose restart nginx
```

---

## 📊 监控和日志

### 查看日志

```bash
# SSH 连接到服务器
ssh deploy@your-server

# 进入应用目录
cd ~/mortgage-agent

# 查看 Docker 容器日志
docker-compose logs -f mortgage-api      # API 日志
docker-compose logs -f nginx             # Nginx 日志

# 查看所有容器
docker-compose ps

# 查看容器资源占用
docker stats
```

### 查看输出文件

```bash
# PDF 和 ZIP 文件保存在
~/mortgage-agent/output/

# 获取 PDF 报告到本地
scp deploy@your-server:~/mortgage-agent/output/*.pdf ./
```

---

## 🛠️ 故障排查

### 问题 1：部署失败，显示 "连接被拒绝"

**原因**：SSH 密钥配置不正确

**解决**：
```bash
# 1. 验证本地 SSH 连接
ssh -i ~/.ssh/id_rsa deploy@your-server

# 2. 如果连接成功，检查 GitHub Secrets 中 SERVER_PRIVATE_KEY 是否正确
# 应该是私钥的完整内容（包括 -----BEGIN RSA PRIVATE KEY----- 等）
cat ~/.ssh/id_rsa
```

### 问题 2：Docker 镜像推送失败

**原因**：Docker Hub 凭证过期或不正确

**解决**：
```bash
# 1. 本地登录测试
docker login

# 2. 更新 GitHub Secrets 中的 DOCKER_PASSWORD
# （不是密码，而是 Personal Access Token）
# 可从 https://hub.docker.com/settings/security 生成
```

### 问题 3：服务启动但无法访问

**原因**：防火墙或端口被占用

**解决**：
```bash
ssh deploy@your-server

# 检查防火墙
sudo ufw status

# 检查端口占用
sudo netstat -tlnp | grep 80
sudo netstat -tlnp | grep 443

# 检查容器是否运行
docker-compose ps

# 查看容器错误日志
docker-compose logs nginx
```

### 问题 4：内存或 CPU 不足

**原因**：服务器配置过低或存在内存泄漏

**解决**：
```bash
# 检查系统资源
docker stats
free -h
df -h

# 查看 Docker 镜像大小
docker images

# 清理未使用的容器和镜像
docker system prune -a
```

---

## 📈 性能优化建议

### 1. 增加 worker 进程数

编辑 `docker-compose.yml`：
```yaml
command: >
  uvicorn mortgage_agent.api:app
  --host 0.0.0.0
  --port 8000
  --workers 4
  --loop uvloop
```

### 2. 增加资源限制

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 1G
```

### 3. 启用 Nginx 缓存

在 `nginx.conf` 中添加：
```nginx
proxy_cache_path /var/cache/nginx levels=1:2 keys_zone=mortgage_cache:10m;

location /v1/ {
    proxy_cache mortgage_cache;
    proxy_cache_valid 200 1h;
}
```

### 4. 启用 Gzip 压缩

已在 `nginx.conf` 中默认启用

---

## 🔄 更新和回滚

### 更新应用

```bash
# 本地推送代码
git add .
git commit -m "feat: add new feature"
git push origin main

# GitHub Actions 自动部署（查看 Actions 标签页）
```

### 手动回滚

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

## 📝 最佳实践

### 1. 分支管理

- `main` 分支：生产环境（受保护，需代码审查）
- `develop` 分支：测试环境
- `feature/*` 分支：功能分支

### 2. 提交信息规范

```bash
# ✓ 良好的提交信息
git commit -m "feat: add prepayment calculator"
git commit -m "fix: correct interest calculation"
git commit -m "docs: update API documentation"

# ✗ 不好的提交信息
git commit -m "update"
git commit -m "fix bug"
```

### 3. 环境隔离

```
.env          ← 不要提交（git ignore）
.env.example  ← 提交（占位符）
```

### 4. 定期备份

```bash
# 手动备份数据
ssh deploy@your-server "tar -czf ~/backup-$(date +%Y%m%d).tar.gz ~/mortgage-agent"

# 定期清理旧备份
ssh deploy@your-server "find ~/backups -type f -mtime +30 -delete"
```

---

## 🆘 获取帮助

查看詳細日誌：
```bash
# GitHub Actions 日志
# 在 GitHub Actions 中点击失败的工作流，查看详细日志

# 服务器日志
ssh deploy@your-server
cd ~/mortgage-agent
docker-compose logs --tail=100

# 系统日志
journalctl -u docker -f
systemctl status mortgage-agent
```

---

## 📚 相关资源

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Docker 文档](https://docs.docker.com/)
- [FastAPI 生产部署](https://fastapi.tiangolo.com/deployment/)
- [Nginx 配置指南](https://nginx.org/en/docs/)
- [Let's Encrypt](https://letsencrypt.org/)


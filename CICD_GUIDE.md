# CI/CD 部署指南

## 📋 概述

本文档为你介绍了如何利用 **GitHub Actions** 和 **Docker** 实现自动化 CI/CD，从而将你的应用高效、可靠地部署到服务器。

### 核心特性

- ✅ **自动化测试**：每次代码提交都会自动运行单元测试，确保代码质量。
- ✅ **代码质量检查**：通过 Black、isort 和 Flake8 等工具，自动执行代码规范检查。
- ✅ **Docker 容器化**：采用多阶段构建技术，有效减小 Docker 镜像的体积。
- ✅ **自动部署**：代码推送到 `main` 分支后，将自动部署到生产环境。
- ✅ **Nginx 反向代理**：支持 HTTPS、负载均衡和缓存，提升应用性能和安全性。
- ✅ **零停机部署**：借助 Docker Compose 实现滚动更新，确保服务持续可用。
- ✅ **日志管理**：结构化的日志记录与容器日志卷挂载，便于问题排查。

---

## 🚀 快速开始

### 第一步：初始化服务器

在你的服务器上运行 `scripts/server-init.sh` 脚本，以完成环境初始化。

```bash
# 方法一：通过 SSH 远程执行
ssh your-user@your-server "curl -sSL https://raw.githubusercontent.com/your-username/your-repo/main/scripts/server-init.sh | sudo bash"

# 方法二：先复制再执行
scp scripts/server-init.sh your-user@your-server:/tmp/
ssh your-user@your-server "sudo bash /tmp/server-init.sh"
```

**此脚本将完成以下工作**：
- 更新系统软件包。
- 安装 Docker 和 Docker Compose。
- 配置防火墙，开放 22、80 和 443 端口。
- 创建一个专用的 `deploy` 用户。
- （可选）安装并配置 Fail2Ban，以防止暴力破解。
- 在 `/home/deploy/mortgage-agent` 创建应用目录并克隆仓库。

### 第二步：配置 GitHub Secrets

为了让 GitHub Actions 能够顺利执行，你需要在 GitHub 仓库中设置以下 Secrets：

前往 `Settings` → `Secrets and variables` → `Actions`，然后添加以下内容：

| Secret 名称 | 说明 | 示例 |
|--------------------|--------------------------------|--------------------------------|
| `DOCKER_USERNAME` | 你的 Docker Hub 用户名 | `yourdockerhubusername` |
| `DOCKER_PASSWORD` | 你的 Docker Hub 密码或 Token | `dckr_pat_xxxxxxxx` |
| `SERVER_HOST` | 你服务器的 IP 地址或域名 | `123.45.67.89` |
| `SERVER_USER` | 用于部署的 SSH 用户名 | `deploy` |
| `SERVER_PORT` | 服务器的 SSH 端口 | `22` |
| `SERVER_PRIVATE_KEY` | 用于 SSH 连接的私钥 | (见下方说明) |

**如何生成和使用 SSH 密钥**：

如果你还没有 SSH 密钥，可以在本地计算机上运行以下命令来生成：
```bash
# 生成一个新的 SSH 密钥对
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# 将公钥复制到服务器，以便进行免密登录
ssh-copy-id deploy@your-server
```
生成后，`cat ~/.ssh/id_rsa` 的内容即为 `SERVER_PRIVATE_KEY` 的值。

### 第三步：配置应用环境

通过 SSH 连接到你的服务器，并配置应用所需的环境变量。

```bash
ssh deploy@your-server
cd ~/mortgage-agent

# 从模板文件创建 .env 文件
cp .env.example .env

# 编辑 .env 文件，根据你的需求修改配置
nano .env
```

### 第四步：触发部署

现在，一切准备就绪。只需将代码推送到 `main` 分支，即可触发自动部署。

```bash
git push origin main
```

你可以在 GitHub 仓库的 **Actions** 标签页中实时查看部署进度。

---

## 📁 文件与目录结构说明

- **`.github/workflows/deploy.yml`**: 定义了 CI/CD 的完整流程，包括测试、构建和部署。
- **`Dockerfile`**: 用于构建应用的多阶段 Docker 镜像。
- **`docker-compose.yml`**: 编排 `mortgage-api` 和 `nginx` 等服务。
- **`nginx.conf`**: Nginx 的配置文件，用于反向代理。
- **`scripts/server-init.sh`**: 用于快速初始化服务器环境的脚本。
- **`mortgage_agent/`**: 包含所有应用源代码。

通过以上步骤，你已经成功搭建了一个全自动的 CI/CD 系统。现在，你可以专注于代码开发，而部署的繁琐工作将由系统自动完成。

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

## 🌥️ 微信小程序云托管部署

依赖新的 GitHub Actions 工作流 `Deploy to WeChat Cloud Hosting`（手动触发）。准备好以下 Secrets 后，即可一键构建镜像并发布到腾讯云 CloudBase/云托管：

- `TCB_ENV_ID`、`TCB_REGION`、`TCB_SECRET_ID`、`TCB_SECRET_KEY`：CloudBase 环境与访问密钥
- `TCR_SERVER`、`TCR_NAMESPACE`、`TCR_USERNAME`、`TCR_PASSWORD`：腾讯云容器镜像服务（TCR）仓库信息
- 可选：`LOG_LEVEL`、`RATE_LIMIT_DEFAULT`、`RATE_LIMIT_EXPORT`、`ROOT_PATH`、`UVICORN_WORKERS`

触发步骤：
1. 在 GitHub Actions 选择 **Deploy to WeChat Cloud Hosting** → `Run workflow`，可填写自定义 `image_tag`（默认使用当前 commit SHA）。
2. 工作流会构建并推送镜像到 TCR，然后渲染 `cloudbaserc.json` 并调用 `TencentCloudBase/cloudbase-action@v2` 部署。
3. 云托管会自动注入 `PORT` 环境变量，若通过网关设置了路径前缀，可在 Secrets 中设置 `ROOT_PATH` 与之对应。

云托管使用 `cloudbaserc.json` 描述容器服务，默认 CPU=1、内存=2GiB，副本范围 0-2（按 CPU 自动扩缩容）。根据需求在文件或工作流中调整 `CONTAINER_PORT`、资源规格或环境变量。
